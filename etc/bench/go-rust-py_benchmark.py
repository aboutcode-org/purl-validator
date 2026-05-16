#!/usr/bin/env python3
"""
Benchmark the Python, Rust, and Go PurlValidator implementations.

The benchmark uses PURL source data from purl-validator.rs/fst_builder/data.
It measures:

- time to build each FST index
- time to run lookup against generated queries
- FST size on disk
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import time

from dataclasses import dataclass
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
PYTHON_REPO = BENCH_DIR.parent.parent
DEFAULT_WORKSPACE = PYTHON_REPO.parent
RUST_LOOKUP_PROJECT = BENCH_DIR / "rust-lookup-bench"
GO_LOOKUP_PROJECT = BENCH_DIR / "go-lookup-bench"


@dataclass()
class Layout:
    workspace: Path
    python_repo: Path
    rust_repo: Path
    go_repo: Path
    data_dir: Path
    work_dir: Path
    rust_lookup_project: Path
    go_lookup_project: Path


@dataclass()
class Result:
    name: str
    build_seconds: float
    lookup_seconds: float
    storage: int


def run_command(command, cwd, env=None):
    results = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if results.returncode:
        output = results.stdout[-4000:]
        raise Exception(
            f"Command failed with exit code {results.returncode}: {' '.join(command)}\n{output}"
        )
    return results.stdout


def load_purls(path):
    purls = set()
    input_files = sorted(path.glob("*.txt"))
    for input_file in input_files:
        with input_file.open("r", encoding="utf-8", errors="replace") as lines:
            for line in lines:
                purl = line.strip()
                if purl:
                    purls.append(purl)

    return sorted(purls), len(input_files)


def time_call(function):
    start = time.perf_counter()
    result = function()
    return time.perf_counter() - start, result


def write_queries(purls, path):
    rng = random.Random(42)
    query_count = 1000000
    hit_count = query_count // 2
    miss_count = query_count - hit_count
    known_lookup_purls = [purl for purl in purls if purl.startswith("pkg:pypi/")]
    if not known_lookup_purls:
        known_lookup_purls = purls

    queries = [rng.choice(known_lookup_purls) for _index in range(hit_count)]
    queries.extend(
        f"pkg:npm/purl-validator-benchmark-unknown-{index:07}"
        for index in range(miss_count)
    )
    rng.shuffle(queries)
    path.write_text("\n".join(queries) + "\n", encoding="utf-8")


def copy_data_files(data_dir, target_dir):
    if data_dir.resolve() == target_dir.resolve():
        return
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    for source in sorted(data_dir.glob("*.txt")):
        shutil.copy2(source, target_dir / source.name)


def parse_lookup_output(text):
    hits = None
    seconds = None
    for line in text.splitlines():
        if line.startswith("hits="):
            hits = int(line.split("=", 1)[1])
        if line.startswith("lookup_seconds="):
            seconds = float(line.split("=", 1)[1])
    if hits is None or seconds is None:
        raise Exception(f"Cannot parse lookup output:\n{text}")
    return hits, seconds


def import_python_validator(python_repo):
    sys.path.insert(0, str(python_repo / "src"))
    spec = importlib.util.spec_from_file_location(
        "purl_validator",
        python_repo / "src" / "purl_validator" / "__init__.py",
    )
    if not spec or not spec.loader:
        raise Exception("Cannot load purl_validator module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as error:
        raise Exception(
            f"Missing Python dependency: {error.name}. "
            "Run the setup command from etc/bench/README.rst."
        ) from error
    return module


def benchmark_python(layout, purls, query_path):
    module = import_python_validator(layout.python_repo)
    index = layout.work_dir / "python-purls.map"

    def build():
        generated = Path(module.create_purl_map(purls))
        shutil.copy2(generated, index)

    build_seconds, _result = time_call(build)

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
    return Result(
        name="Python purl-validator",
        build_seconds=build_seconds,
        lookup_seconds=lookup_seconds,
        storage=index.stat().st_size,
        hits=hits,
    )


def benchmark_rust(layout, query_path):
    build_dir = layout.work_dir / "rust-builder"
    copy_data_files(layout.data_dir, build_dir / "fst_builder" / "data")
    index = build_dir / "purls.fst"
    if index.exists():
        index.unlink()

    run_command(["cargo", "build", "--release", "--bin", "fst_builder"], cwd=layout.rust_repo)
    builder = layout.rust_repo / "target" / "release" / "fst_builder"
    build_seconds, _result = time_call(lambda: run_command([str(builder)], cwd=build_dir))

    copied_index = layout.work_dir / "rust-purls.fst"
    shutil.copy2(index, copied_index)

    run_command(
        [
            "cargo",
            "build",
            "--release",
            "--manifest-path",
            str(layout.rust_lookup_project / "Cargo.toml"),
        ],
        cwd=layout.workspace,
    )
    binary = layout.rust_lookup_project / "target" / "release" / "purl-validator-rust-lookup-bench"
    output = run_command([str(binary), str(copied_index), str(query_path)], cwd=layout.workspace)
    hits, lookup_seconds = parse_lookup_output(output)
    return Result(
        name="Rust purl-validator.rs",
        build_seconds=build_seconds,
        lookup_seconds=lookup_seconds,
        storage=copied_index.stat().st_size,
        hits=hits,
    )


def go_env():
    env = os.environ.copy()
    go_bin = Path("/usr/local/go/bin")
    if go_bin.is_dir():
        env["PATH"] = f"{go_bin}:{env.get('PATH', '')}"
    return env


def benchmark_go(layout, query_path):
    build_dir = layout.work_dir / "go-builder"
    copy_data_files(layout.data_dir, build_dir / "cmd" / "data")
    index = build_dir / "purls.fst"
    if index.exists():
        index.unlink()

    env = go_env()
    generator = layout.work_dir / "go-fst-builder"
    run_command(["go", "build", "-o", str(generator), "./cmd"], cwd=layout.go_repo, env=env)
    build_seconds, _result = time_call(lambda: run_command([str(generator)], cwd=build_dir, env=env))

    copied_index = layout.work_dir / "go-purls.fst"
    shutil.copy2(index, copied_index)

    binary = layout.work_dir / "go-lookup-bench"
    run_command(["go", "build", "-o", str(binary), "."], cwd=layout.go_lookup_project, env=env)
    output = run_command([str(binary), str(copied_index), str(query_path)], cwd=layout.workspace, env=env)
    hits, lookup_seconds = parse_lookup_output(output)
    return Result(
        name="Go purlvalidator-go",
        build_seconds=build_seconds,
        lookup_seconds=lookup_seconds,
        storage=copied_index.stat().st_size,
        hits=hits,
    )


def format_size(siz):
    return f"{round(size / 1024 / 1024)}MB"


def format_report(results):
    """
    Return a formatted results text from a list of results
    """
    lines = []
    for result in results:
        lines.append(f"data structure      : {result.name:}")
        lines.append(f"  build time (secs) : {result.build_seconds:>12.6f} ")
        lines.append(f"  lookup time (secs): {result.lookup_seconds:>14.6f} ")
        lines.append(f"{format_size(result.storage):<27}")

    return "\n".join(lines) + "\n"


def validate_layout(layout):
    required_paths = [
        layout.python_repo / "src" / "purl_validator" / "__init__.py",
        layout.rust_repo / "Cargo.toml",
        layout.go_repo / "go.mod",
        layout.data_dir,
        layout.rust_lookup_project / "Cargo.toml",
        layout.go_lookup_project / "go.mod",
    ]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise Exception(f"Missing required paths:\n{formatted}")


def build_layout(args):
    workspace = args.workspace.resolve()
    python_repo = workspace / "purl-validator"
    rust_repo = workspace / "purl-validator.rs"
    go_repo = workspace / "purlvalidator-go"
    data_dir = args.data_dir.resolve() if args.data_dir else rust_repo / "fst_builder" / "data"
    work_dir = args.work_dir.resolve() if args.work_dir else python_repo / "tmp" / "implementation-bench"
    return Layout(
        workspace=workspace,
        python_repo=python_repo,
        rust_repo=rust_repo,
        go_repo=go_repo,
        data_dir=data_dir,
        work_dir=work_dir,
        rust_lookup_project=RUST_LOOKUP_PROJECT,
        go_lookup_project=GO_LOOKUP_PROJECT,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--report", type=Path, help="Write report in this file.")
    args = parser.parse_args()

    layout = build_layout(args)
    validate_layout(layout)
    layout.work_dir.mkdir(parents=True, exist_ok=True)

    query_path = layout.work_dir / "queries.txt"
    purls, _file_count = load_purls(layout.data_dir)
    if not purls:
        raise Exception(f"No PURLs in {layout.data_dir}")
    write_queries(purls, args.queries, query_path)

    results = [
        benchmark_python(layout, purls, query_path),
        benchmark_rust(layout, query_path),
        benchmark_go(layout, query_path),
    ]

    expected_hits = args.queries // 2
    for result in results:
        if result.hits != expected_hits:
            raise Exception(
                f"{result.name} returned {result.hits} hits; expected {expected_hits}"
            )

    report = format_report(results)
    print(report, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
