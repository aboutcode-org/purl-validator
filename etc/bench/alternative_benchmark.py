#!/usr/bin/env python3
"""
Benchmark of set data structures for PURLs.
"""

from __future__ import annotations

import argparse
import mmap
import random
import sqlite3
import sys
import tempfile
import time

from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

import ducer


@dataclass
class Result:
    name: str
    build_seconds: float
    lookup_seconds: float
    hits: int
    storage: str


def iter_input_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.txt"))
    return [path]


def load_purls(path: Path, limit: int | None) -> tuple[list[str], int, int]:
    purls: list[str] = []
    raw_count = 0
    for input_file in iter_input_files(path):
        with input_file.open("r", encoding="utf-8", errors="replace") as lines:
            for line in lines:
                purl = line.strip()
                if not purl:
                    continue
                raw_count += 1
                purls.append(purl)
                if limit and len(purls) >= limit:
                    unique = sorted(set(purls))
                    return unique, raw_count, len(iter_input_files(path))
    unique = sorted(set(purls))
    return unique, raw_count, len(iter_input_files(path))


def time_calls(name: str, lookup, queries: list[str]) -> tuple[str, int, float]:
    start = time.perf_counter()
    hits = sum(1 for query in queries if lookup(query))
    elapsed = time.perf_counter() - start
    return name, hits, elapsed


def benchmark_set(purls: list[str], queries: list[str]) -> Result:
    start = time.perf_counter()
    values = set(purls)
    build_seconds = time.perf_counter() - start
    name, hits, elapsed = time_calls("python_set", values.__contains__, queries)
    return Result(name, build_seconds, elapsed, hits, "no disk artifact")


def benchmark_dict(purls: list[str], queries: list[str]) -> Result:
    start = time.perf_counter()
    values = dict.fromkeys(purls, 1)
    build_seconds = time.perf_counter() - start
    name, hits, elapsed = time_calls("python_dict", values.__contains__, queries)
    return Result(name, build_seconds, elapsed, hits, "no disk artifact")


def benchmark_sorted_list(purls: list[str], queries: list[str]) -> Result:
    start = time.perf_counter()
    values = list(purls)
    build_seconds = time.perf_counter() - start

    def contains(value: str) -> bool:
        index = bisect_left(values, value)
        return index != len(values) and values[index] == value

    name, hits, elapsed = time_calls("sorted_list_bisect", contains, queries)
    return Result(name, build_seconds, elapsed, hits, "no disk artifact")


def benchmark_sqlite(purls: list[str], queries: list[str]) -> Result:
    start = time.perf_counter()
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE purls (purl TEXT PRIMARY KEY)")
    connection.executemany("INSERT INTO purls (purl) VALUES (?)", ((purl,) for purl in purls))
    connection.commit()
    build_seconds = time.perf_counter() - start

    def contains(value: str) -> bool:
        row = connection.execute("SELECT 1 FROM purls WHERE purl = ?", (value,)).fetchone()
        return row is not None

    name, hits, elapsed = time_calls("sqlite_memory", contains, queries)
    connection.close()
    return Result(name, build_seconds, elapsed, hits, "no disk artifact")


def benchmark_ducer(purls: list[str], queries: list[str]) -> Result | None:

    with tempfile.TemporaryDirectory() as temp_dir:
        map_path = Path(temp_dir) / "purls.map"
        entries = [(purl.encode("utf-8"), 1) for purl in purls]
        start = time.perf_counter()
        ducer.Map.build(map_path, entries)
        build_seconds = time.perf_counter() - start
        with map_path.open("rb") as map_file:
            mapped = mmap.mmap(map_file.fileno(), 0, access=mmap.ACCESS_READ)
            purl_map = ducer.Map(mapped)

            def contains(value: str) -> bool:
                return bool(purl_map.get(value.encode("utf-8")))

            name, hits, elapsed = time_calls("ducer_map", contains, queries)
            return Result(name, build_seconds, elapsed, hits, f"{map_path.stat().st_size} bytes")


def make_queries(purls: list[str], count: int) -> list[str]:
    if not purls:
        return []
    hit_count = count // 2
    miss_count = count - hit_count
    hits = [random.choice(purls) for _ in range(hit_count)]
    misses = [f"{random.choice(purls)}-missing-{index}" for index in range(miss_count)]
    queries = hits + misses
    random.shuffle(queries)
    return queries


def format_report(
    input_path: Path,
    file_count: int,
    raw_count: int,
    purls: list[str],
    queries: list[str],
    results: list[Result],
    load_seconds: float,
    seed: int,
) -> str:
    lines = [
        "PurlValidator lookup structure resulys",
        "========================================",
        "",
        f"Input path:             {input_path}",
        f"Input files:            {file_count}",
        f"Input load seconds:     {load_seconds:.6f}",
        f"Lookup queries:         {len(queries)}",
        f"Expected hits:          {len(queries) // 2}",
        f"Random seed:            {seed}",
        "",
        "Results",
        "-------",
        "",
        f"{'structure':<20} {'build_s':>12} {'lookup_s':>12} {'hits':>10} {'storage':>18}",
        f"{'-' * 20} {'-' * 12} {'-' * 12} {'-' * 10} {'-' * 18}",
    ]
    for result in results:
        lines.append(
            f"{result.name:<20} "
            f"{result.build_seconds:>12.6f} "
            f"{result.lookup_seconds:>12.6f} "
            f"{result.hits:>10} "
            f"{result.storage:>18}"
        )

    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Directory of text files with one PURL per line.",
    )
    parser.add_argument("--limit", type=int, default=100000, help="Maximum PURLs to load.")
    parser.add_argument("--queries", type=int, default=20000, help="Number of lookup queries.")
    parser.add_argument("--seed", type=int, default=1, help="Random seed for reproducible queries.")
    parser.add_argument("--report", type=Path, help="Write report to this file.")
    args = parser.parse_args()

    random.seed(args.seed)
    start = time.perf_counter()
    purls, raw_count, file_count = load_purls(args.input, args.limit)
    load_seconds = time.perf_counter() - start
    if not purls:
        print(f"No PURLs in {args.input}", file=sys.stderr)
        return 1

    queries = make_queries(purls, args.queries)
    results = [
        benchmark_set(purls, queries),
        benchmark_dict(purls, queries),
        benchmark_sorted_list(purls, queries),
        benchmark_sqlite(purls, queries),
    ]
    ducer_result = benchmark_ducer(purls, queries)
    if ducer_result:
        results.append(ducer_result)

    report = format_report(
        input_path=args.input,
        file_count=file_count,
        raw_count=raw_count,
        purls=purls,
        queries=queries,
        results=results,
        load_seconds=load_seconds,
        seed=args.seed,
    )
    print(report, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise main()
