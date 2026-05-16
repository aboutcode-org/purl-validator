#!/usr/bin/env python3
"""
Benchmark of Python built-ins, SQLite, fst for PURL validation.

The benchmark uses PURL source data from purl-validator.rs/fst_builder/data.
It measures:

- time to build each index/data structure
- time to run lookup with generated queries
- FST size on disk

"""

from __future__ import annotations

import argparse
import mmap
import random
import sqlite3
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
    storage: str


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


def time_purl_lookup(name, lookup_fun, queries):
    start = time.perf_counter()
    _res = [lookup_fun(query) for query in queries]
    elapsed = time.perf_counter() - start
    return name, elapsed


def benchmark_set(purls, queries) -> Result:
    start = time.perf_counter()
    values = set(purls)
    build_seconds = time.perf_counter() - start
    name, elapsed = time_purl_lookup("python set", values.__contains__, queries)
    return Result(name, build_seconds, elapsed, "no disk file")


def benchmark_dict(purls, queries) -> Result:
    start = time.perf_counter()
    values = dict.fromkeys(purls, 1)
    build_seconds = time.perf_counter() - start
    name, elapsed = time_purl_lookup("python dict", values.__contains__, queries)
    return Result(name, build_seconds, elapsed, "no disk file")


def benchmark_sorted_list(purls, queries) -> Result:
    start = time.perf_counter()
    values = list(purls)
    build_seconds = time.perf_counter() - start

    def contains(value):
        index = bisect_left(values, value)
        return index != len(values) and values[index] == value

    name, elapsed = time_purl_lookup("sorted list+bisect", contains, queries)
    return Result(name, build_seconds, elapsed, "no disk file")


def benchmark_sqlite(purls, queries) -> Result:
    start = time.perf_counter()
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE purls (purl TEXT PRIMARY KEY)")
    connection.executemany("INSERT INTO purls (purl) VALUES (?)", ((purl,) for purl in purls))
    connection.commit()
    build_seconds = time.perf_counter() - start

    def contains(value):
        row = connection.execute("SELECT 1 FROM purls WHERE purl = ?", (value,)).fetchone()
        return row is not None

    name, elapsed = time_purl_lookup("sqlite in memory", contains, queries)
    connection.close()
    return Result(name, build_seconds, elapsed, "no disk file")


def benchmark_ducer_fst(purls, queries) -> Result:

    with tempfile.TemporaryDirectory() as temp_dir:
        map_path = Path(temp_dir) / "purls.map"
        # encode as binaries
        entries = [(purl.encode("utf-8"), 1) for purl in purls]

        start = time.perf_counter()
        ducer.Map.build(map_path, entries)
        build_seconds = time.perf_counter() - start

        with map_path.open("rb") as map_file:
            mapped = mmap.mmap(map_file.fileno(), 0, access=mmap.ACCESS_READ)
            purl_map = ducer.Map(mapped)

            def contains(value):
                return bool(purl_map.get(value.encode("utf-8")))

            name, elapsed = time_purl_lookup("ducer FST", contains, queries)
            return Result(name, build_seconds, elapsed, f"{map_path.stat().st_size} bytes")


def make_queries(purls, count):
    """
    Return a list of ``count`` query PURLs, half them being invalid
    """
    if not purls:
        return []
    hit_count = count // 2
    miss_count = count - hit_count
    hits = [random.choice(purls) for _ in range(hit_count)]
    misses = [f"{random.choice(purls)}-invalid-{index}" for index in range(miss_count)]
    queries = hits + misses
    random.shuffle(queries)
    return queries


def format_report(results):
    """
    Return a formatted results text from a list of results
    """
    lines = []
    for result in results:
        lines.append(f"data structure      : {result.name:}")
        lines.append(f"  build time (secs) : {result.build_seconds:>12.6f} ")
        lines.append(f"  lookup time (secs): {result.lookup_seconds:>14.6f} ")
        lines.append(f"  storage size      :     {result.storage:<27}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Directory of text files with one PURL per line.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write report in this file.",
    )
    args = parser.parse_args()

    random.seed(42)

    purls, file_count = load_purls(path=args.input)
    if not purls:
        raise Exception(f"No PURLs in {args.input}")

    queries = make_queries(purls=purls, count=1000000)
    results = [
        benchmark_set(purls=purls, queries=queries),
        benchmark_dict(purls=purls, queries=queries),
        benchmark_sorted_list(purls=purls, queries=queries),
        benchmark_sqlite(purls=purls, queries=queries),
        benchmark_ducer_fst(purls=purls, queries=queries)
    ]

    report = format_report(
        input_path=args.input,
        file_count=file_count,
        purls=purls,
        queries=queries,
        results=results,
    )
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
