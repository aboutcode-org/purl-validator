#!/usr/bin/env python3
"""
Benchmark the Python, Rust, and Go PurlValidator implementations.

The benchmark uses the PURL source data from purl-validator.rs/fst_builder/data.
And checks:

- time to build each index
- index size on disk
- time to run 1,000,000 lookups, with half known and half unknown PURLs

"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time


WORKSPACE = Path("workspace")
PYTHON_REPO = WORKSPACE / "purl-validator"
RUST_REPO = WORKSPACE / "purl-validator.rs"
GO_REPO = WORKSPACE / "purlvalidator-go"
DEFAULT_DATA_DIR = RUST_REPO / "fst_builder/data"
DEFAULT_REPORT = WORKSPACE / "benchmark-report.md"
DEFAULT_WORK_DIR = WORKSPACE / "benchmark-tmp"



class BenchmarkError(Exception):
    pass


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode:
        output = completed.stdout[-4000:]
        raise BenchmarkError(
            f"Command failed with exit code {completed.returncode}: {' '.join(command)}\n{output}"
        )


def timed(function):
    start = time.perf_counter()
    result = function()
    return time.perf_counter() - start, result


def read_purls(data_dir: Path) -> tuple[list[str], int, int]:
    purls: list[str] = []
    files = sorted(data_dir.glob("*.txt"))
    raw_count = 0
    for path in files:
        with path.open("r", encoding="utf-8", errors="replace") as lines:
            for line in lines:
                purl = line.strip()
                if not purl:
                    continue
                raw_count += 1
                purls.append(purl)
    return sorted(set(purls)), raw_count, len(files)


def write_queries(purls: list[str], query_count: int, seed: int, path: Path) -> None:
    rng = random.Random(seed)
    hit_count = query_count // 2
    miss_count = query_count - hit_count
    known_lookup_purls = [purl for purl in purls if purl.startswith("pkg:pypi/")]
    if not known_lookup_purls:
        known_lookup_purls = purls
    queries = [rng.choice(known_lookup_purls) for _ in range(hit_count)]
    queries.extend(f"pkg:npm/purl-validator-benchmark-unknown-{index:07}" for index in range(miss_count))
    rng.shuffle(queries)
    path.write_text("\n".join(queries) + "\n", encoding="utf-8")


def copy_data_files(data_dir: Path, target_dir: Path) -> None:
    if data_dir.resolve() == target_dir.resolve():
        return
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    for source in sorted(data_dir.glob("*.txt")):
        shutil.copy2(source, target_dir / source.name)


def write_rust_lookup_harness(work_dir: Path, fst_path: Path, query_path: Path) -> Path:
    project = work_dir / "rust_lookup"
    if project.exists():
        shutil.rmtree(project)
    (project / "src").mkdir(parents=True)
    (project / "Cargo.toml").write_text(
        textwrap.dedent(
            f"""
            [package]
            name = "purl-validator-rust-lookup-bench"
            version = "0.1.0"
            edition = "2024"

            [dependencies]
            fst = "0.4.7"
            packageurl = "0.6.0"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (project / "src/main.rs").write_text(
        textwrap.dedent(
            f"""
            use fst::Set;
            use packageurl::PackageUrl;
            use std::fs;
            use std::str::FromStr;
            use std::time::Instant;

            fn main() -> Result<(), Box<dyn std::error::Error>> {{
                let fst_data = fs::read({json.dumps(str(fst_path))})?;
                let set = Set::new(fst_data.as_slice())?;
                let queries = fs::read_to_string({json.dumps(str(query_path))})?;
                let start = Instant::now();
                let mut hits = 0usize;
                for query in queries.lines() {{
                    let purl = PackageUrl::from_str(query)?;
                    if purl.version().is_some()
                        || !purl.qualifiers().is_empty()
                        || purl.subpath().is_some()
                    {{
                        return Err("unsupported PURL".into());
                    }}
                    let key = query.trim_end_matches('/');
                    if set.contains(key) {{
                        hits += 1;
                    }}
                }}
                println!("hits={{}}", hits);
                println!("lookup_seconds={{:.6}}", start.elapsed().as_secs_f64());
                Ok(())
            }}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return project


def write_go_lookup_harness(work_dir: Path, fst_path: Path, query_path: Path) -> Path:
    project = work_dir / "go_lookup"
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    (project / "go.mod").write_text(
        textwrap.dedent(
            """
            module purl-validator-go-lookup-bench

            go 1.22.3

            require (
                github.com/blevesearch/vellum v1.1.0
                github.com/package-url/packageurl-go v0.1.5
            )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (project / "main.go").write_text(
        textwrap.dedent(
            f"""
            package main

            import (
                "bufio"
                "fmt"
                "os"
                "time"

                "github.com/blevesearch/vellum"
                packageurl "github.com/package-url/packageurl-go"
            )

            func main() {{
                data, err := os.ReadFile({json.dumps(str(fst_path))})
                if err != nil {{
                    panic(err)
                }}
                fstMap, err := vellum.Load(data)
                if err != nil {{
                    panic(err)
                }}
                file, err := os.Open({json.dumps(str(query_path))})
                if err != nil {{
                    panic(err)
                }}
                defer file.Close()

                start := time.Now()
                hits := 0
                scanner := bufio.NewScanner(file)
                scanner.Buffer(make([]byte, 1024), 1024*1024)
                for scanner.Scan() {{
                    query := scanner.Text()
                    instance, err := packageurl.FromString(query)
                    if err != nil {{
                        panic(err)
                    }}
                    if instance.Version != "" || len(instance.Qualifiers) > 0 || instance.Subpath != "" {{
                        panic("unsupported PURL")
                    }}
                    ok, err := fstMap.Contains([]byte(query))
                    if err != nil {{
                        panic(err)
                    }}
                    if ok {{
                        hits++
                    }}
                }}
                if err := scanner.Err(); err != nil {{
                    panic(err)
                }}
                fmt.Printf("hits=%d\\n", hits)
                fmt.Printf("lookup_seconds=%.6f\\n", time.Since(start).Seconds())
            }}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return project


def parse_lookup_output(output_path: Path) -> tuple[int, float]:
    text = output_path.read_text(encoding="utf-8")
    hits = None
    seconds = None
    for line in text.splitlines():
        if line.startswith("hits="):
            hits = int(line.split("=", 1)[1])
        if line.startswith("lookup_seconds="):
            seconds = float(line.split("=", 1)[1])
    if hits is None or seconds is None:
        raise BenchmarkError(f"Cannot parse lookup output from {output_path}:\n{text}")
    return hits, seconds


def benchmark_python(purls: list[str], query_path: Path, work_dir: Path) -> dict[str, object]:
    sys.path.insert(0, str(PYTHON_REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "purl_validator", PYTHON_REPO / "src/purl_validator/__init__.py"
    )
    if not spec or not spec.loader:
        raise BenchmarkError("Cannot load purl_validator module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    index = work_dir / "python-purls.map"

    def build():
        generated = Path(module.create_purl_map(purls))
        shutil.copy2(generated, index)

    build_seconds, _result = timed(build)

    validator = module.PurlValidator(index)
    queries = query_path.read_text(encoding="utf-8").splitlines()

    def lookup():
        hits = 0
        start = time.perf_counter()
        for query in queries:
            if validator.validate_purl(query):
                hits += 1
        return hits, time.perf_counter() - start

    hits, lookup_seconds = lookup()
    return {
        "name": "Python purl-validator",
        "build_seconds": build_seconds,
        "lookup_seconds": lookup_seconds,
        "index_size": index.stat().st_size,
        "hits": hits,
        "index": index,
    }


def benchmark_rust(data_dir: Path, query_path: Path, work_dir: Path) -> dict[str, object]:
    copy_data_files(data_dir, RUST_REPO / "fst_builder/data")
    index = RUST_REPO / "purls.fst"
    if index.exists():
        index.unlink()

    run_command(["cargo", "build", "--release", "--bin", "fst_builder"], cwd=RUST_REPO)
    builder = RUST_REPO / "target/release/fst_builder"
    build_seconds, _result = timed(lambda: run_command([str(builder)], cwd=RUST_REPO))

    copied_index = work_dir / "rust-purls.fst"
    shutil.copy2(index, copied_index)

    harness = write_rust_lookup_harness(work_dir, copied_index, query_path)
    run_command(["cargo", "build", "--release"], cwd=harness)
    output_path = work_dir / "rust-lookup.out"

    def run_lookup():
        completed = subprocess.run(
            [str(harness / "target/release/purl-validator-rust-lookup-bench")],
            cwd=harness,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        output_path.write_text(completed.stdout, encoding="utf-8")

    run_lookup()
    hits, lookup_seconds = parse_lookup_output(output_path)
    return {
        "name": "Rust purl-validator.rs",
        "build_seconds": build_seconds,
        "lookup_seconds": lookup_seconds,
        "index_size": copied_index.stat().st_size,
        "hits": hits,
        "index": copied_index,
    }


def benchmark_go(data_dir: Path, query_path: Path, work_dir: Path) -> dict[str, object]:
    copy_data_files(data_dir, GO_REPO / "cmd/data")
    index = GO_REPO / "purls.fst"
    if index.exists():
        index.unlink()

    env = os.environ.copy()
    env["PATH"] = f"/usr/local/go/bin:{env.get('PATH', '')}"
    build_seconds, _result = timed(
        lambda: run_command(["go", "run", "./cmd/main.go"], cwd=GO_REPO, env=env)
    )

    copied_index = work_dir / "go-purls.fst"
    shutil.copy2(index, copied_index)

    harness = write_go_lookup_harness(work_dir, copied_index, query_path)
    run_command(["go", "mod", "tidy"], cwd=harness, env=env)
    run_command(["go", "build", "-o", "lookup-bench", "."], cwd=harness, env=env)
    output_path = work_dir / "go-lookup.out"

    completed = subprocess.run(
        [str(harness / "lookup-bench")],
        cwd=harness,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    output_path.write_text(completed.stdout, encoding="utf-8")
    hits, lookup_seconds = parse_lookup_output(output_path)
    return {
        "name": "Go purlvalidator-go",
        "build_seconds": build_seconds,
        "lookup_seconds": lookup_seconds,
        "index_size": copied_index.stat().st_size,
        "hits": hits,
        "index": copied_index,
    }


def mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def write_report(
    report_path: Path,
    data_dir: Path,
    raw_count: int,
    unique_count: int,
    file_count: int,
    query_count: int,
    seed: int,
    results: list[dict[str, object]],
) -> None:
    lines = [
        "# PurlValidator implementation benchmark",
        "",
        "This benchmark uses the data from `purl-validator.rs/fst_builder/data/`.",
        "",
        "Input summary:",
        "",
        f"- Data directory: `{data_dir}`",
        f"- Input files: `{file_count}`",
        f"- Unique PURLs: `{unique_count}`",
        f"- Lookup queries: `{query_count}`",
        f"- Expected known PURLs: `{query_count // 2}`",
        f"- Expected unknown PURLs: `{query_count - (query_count // 2)}`",
        f"- Query seed: `{seed}`",
        "",
        "Results:",
        "",
    ]
    for result in results:
        size = int(result["index_size"])
        lines.extend(
            [
                f"## {result['name']}",
                "",
                f"- Build time: `{float(result['build_seconds']):.6f}` seconds",
                f"- Lookup time: `{float(result['lookup_seconds']):.6f}` seconds",
                f"- Lookup hits: `{int(result['hits'])}`",
                f"- Lookup index size: `{size}` bytes, `{mib(size)}`",
                f"- Lookup index: `{result['index']}`",
                "",
            ]
        )
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--queries", type=int, default=1000000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    query_path = args.work_dir / "queries.txt"

    purls, raw_count, file_count = read_purls(args.data_dir)
    write_queries(purls, args.queries, args.seed, query_path)

    results = [
        benchmark_python(purls, query_path, args.work_dir),
        benchmark_rust(args.data_dir, query_path, args.work_dir),
        benchmark_go(args.data_dir, query_path, args.work_dir),
    ]

    write_report(
        report_path=args.report,
        data_dir=args.data_dir,
        raw_count=raw_count,
        unique_count=len(purls),
        file_count=file_count,
        query_count=args.queries,
        seed=args.seed,
        results=results,
    )
    print(args.report)
    return 0


if __name__ == "__main__":
    main()
