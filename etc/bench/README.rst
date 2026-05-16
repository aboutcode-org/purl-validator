PurlValidator data structure evaluation
=======================================

This document details the research and evaluation of various efficient
data structures for compact PURLs storage and lookup.

It contains:

-  reference to evaluation/bench scripts
-  documentation on the various libraries and data structures under
   consideration
-  the final choice (spoiler an FST, aka. finite state transducer)

Context and Problem
-------------------

PurlValidator needs a local queryable dataset of known PURLs to answer
one question:

   Does this PURL exist in the reference dataset?

The lookup index should be built for each release, and shipped with the
library for access without a network connection. And we want a Go, Rust
and Python implementation. The PURls themselves are collected using
PurlDB and FederatedCode.

Solution
--------

High level design
~~~~~~~~~~~~~~~~~

The lookup key is a PURL, cleaned to only keep type, namespace, and
name, (without version, qualifiers and subpath)

This keeps validation focused for now. Version validation could come
later by extending indexed PURLs with version or baking in support VERS
version parsing for validation

Solution elements: Data structures considered
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Built-in set and map
-  FST
-  DAWG
-  Bloom filter
-  SQLite

Considered but not evaluated:

-  Minimal perfect hash: no compression
-  Trie or radix tree: DAWG and FST are similar, but are more compact.
   Suffix trees are way too big.

Built-in set and map
^^^^^^^^^^^^^^^^^^^^

Built-in sets and maps are the simplest baseline in each language, they
are as fast as can be, but they have no compression and no built-in
serialization or memory mapping, and memory use grows quickly for large
datasets.

An interesting path could be to use built-in sets in Rust and Go
generating the code with all the PURL strings so that there is no
specific deserialization. The porblem there is the size as the data is
not compressed.

Built-ins structures are useful for benchmarks as reference but are not
suitable as the main packaged data structure because they are too big.

FST: finite state transducer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

https://en.wikipedia.org/wiki/Finite-state_transducer

An FST stores a sorted set of strings in a compact automaton. PURLs
share common prefixes such as ``pkg:npm/``, ``pkg:pypi/``, and
``pkg:maven/``. This sharing helps reduce stored data.

FST lookup is exact for this use case. The Rust and Go implementations
already ship an FST file. The library opens or embeds that file and
performs membership checks without rebuilding the index.

The main cost is build complexity. Input must be prepared, sorted, and
encoded when the package data is refreshed.

DAWG: directed acyclic word graph
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

See https://stevehanov.ca/blog/compressing-dictionaries-with-a-dawg

this is aka. DAFSA
https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton

A DAWG is a compact data structure for a set of strings. It can merge
repeated prefixes and suffixes like an FST. The DAWG is interesting in
that it can support prefix lookup, but in general the DAWG is bigger and
slower than an FST, and has fewer mature/maintained library support.

Bloom filter
^^^^^^^^^^^^

https://en.wikipedia.org/wiki/Bloom_filter

A Bloom filter can store a large set in a small space, but it is a
probalistic structure and can answer that a value is surely absent or
maybe present. In that later case, you need an extra full dataset to
validate further the “maybe”: this is the problem of false positives
with these filters, hence a Bloom filter cannot not be used as the only
lookup structure, and does not make sense here. Instead, a Bloom filter
could be used before an exact structure to skip some exact lookups as
performance optimization, but outside of the validator.

SQLite
^^^^^^

https://sqlite.org/

SQLite can store PURLs in a SQL table with an index for exact lookup.

The tradeoff is operational weight. Each SQLite language binding adds a
dependency (though this is built in Python). The validator only needs
immutable membership checks, not SQL full power with queries, and update
transactions; but on the other hand the SQLite DB could be the same
across all languages.

SQLite could useful as a benchmark and debugging format. It is not the
first choice for a small language library because this is not
compressed. But it will be a future enhancement for sure.

Preferred solution: FST
~~~~~~~~~~~~~~~~~~~~~~~

Based on the benchmark and otrher criteria, let’s use an FST-backed
lookup for every languages. Do not use a Bloom filter (probalistic). Do
not use native structures that use too much memory.

And for the library selection, we have these high level requirements:

-  We want exact result without false positives, e.g., no bloom filter.
-  Offline use, with no network is a must: the dataset must be bundled
   in the releases.
-  With build time index construction, the construction time is not
   critical.
-  The bundled index should be small enough to ship below crates, and
   Pypi archive size limits.
-  No rebuild at startup/runtime, and fast enough load time from disk,
   ideally memory-mapped.
-  Fast enough lookup.
-  Libraries should be maintained, active FOSS for Rust/Go/Python.

The final selected FST libraries are:

-  Rust: fst crate with a memory-mapped set
   https://github.com/BurntSushi/fst/
-  Python: ducer with a memory-mapped map, dict-like
   https://github.com/jfolz/ducer (ducer uses the Rust fst crate inside)
-  Go: vellum “fst” module (originally from
   https://github.com/couchbase/vellum now at
   https://github.com/blevesearch/vellum) which is mostly inspired from
   the Rust fst crate

Appendix: Benchmarks
--------------------

This directory contains the benchmark Python scripts and mini benchmark
projects used for PurlValidator evaluation in Go and Rust.

The benchmarks compare offline PURL existence checks using:

- Python: memory-mapped ``ducer``.
- Rust: crate ``fst``.
- Go: embedded Vellum FST.
- Python built-in ``set`` and ``dict``,
- Python sorted list,
- Python embedded SQLite,
- and a Rust DAWG.


Expected checkout layout
~~~~~~~~~~~~~~~~~~~~~~~~

We assume you have Python, Go and Rust pre-installed:
``python``, Rust ``cargo`` and Go ``go`` must be on the ``PATH``.


First clone the three repos, in the same ``workspace`` directory:

- ``git clone https://github.com/aboutcode-org/purl-validator``
- ``git clone https://github.com/aboutcode-org/purl-validator.rs``
- ``git clone https://github.com/aboutcode-org/purlvalidator-go``

The scripts derive the workspace path from this ``purl-validator`` clone.
Use ``--workspace`` only when the three clones are not in the same parent
directory.

Install the Python dependencies from the Python repo:

.. code:: sh

   cd purl-validator
   python3 -m venv venv
   . venv/bin/activate
   python -m pip install -U pip
   python -m pip install -r requirements.txt packageurl-python


The Rust and Go lookup test project code is checked in under:

-  ``etc/bench/rust-lookup-bench``
-  ``etc/bench/go-lookup-bench``

The Python benchmark driver builds and runs those projects.



Benchmarking FST vs. DAWG
~~~~~~~~~~~~~~~~~~~~~~~~~

Note: there is a Go benchmark comparing FST and DAWG data structures, plus
other structures:

https://github.com/timurgarif/go-fsa-trie-bench

The local Rust benchmark compares the ``fst`` and ``dawg`` crates using
the base PURLs from ``purl-validator.rs/fst_builder/data``.

Run it from the purl-validator/ dir (with activated venv):

.. code:: sh

   cargo build --release --manifest-path etc/bench/rust-fst-dawg-bench/Cargo.toml
   etc/bench/rust-fst-dawg-bench/target/release/rust-fst-dawg-bench

The dataset profile has 2,324,119 unique sorted base PURL. The benchmark
is to run 1M queries, where 500K are expected to fail.

-  The fst crate index was built in 11s, with a 25MB serialized file,
   and took 0.703s for 1M lookups.
-  The dawg crate index was built in 18s, with a 794MB serialized file,
   and took 28s for 1M lookups.

The outcome is that the preferred structure is an FST over a DAWG (at
least with these implementations).


Benchmarking FST against built-ins and SQLite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Additional review compares the Python ``ducer`` FST library against
other approaches. ``ducer`` uses the Rust ``fst`` crate, and Go Vellum is
based on the same FST design.

The ``etc/bench/alternative_benchmark.py`` script compares
Python lookup using a list of PURLs (text file with one PURL per line)
for these candidates:

-  Python ``set``.
-  Python ``dict``.
-  Python sorted list plus ``bisect``.
-  In-memory SQLite.
-  FST using a ``ducer.Map`` (a Python wrapper on the Rust fst crate).

Data (PURL lists) is from ``purl-validator.rs/fst_builder/data/``

Run it from the purl-validator/ dir (with activated venv):

.. code:: sh

   python etc/bench/alternative_benchmark.py \
       --input ../purl-validator.rs/fst_builder/data \
       --limit 0 \
       --queries 1000000 \
       --report tmp/alternative-structures.txt

Results with 2,324,119 unique PURLs and 1M lookup queries, 500K existing
PURLs:

.. code:: text

   structure               build (secs)   lookup (secs)   storage size
   --------------------   ------------   --------------   ---------------------------
   python set               0.206540       0.275906        304MB in RAM
   python dict              0.449625       0.429034        298MB in RAM
   ducer FST                3.700943       1.805585         26MB on disk
   sorted list+bisect       0.017540       2.783555        236MB in RAM
   sqlite in memory         4.855480       4.220032        207MB on disk (or 65MB with zstd)


Benchmarking FST in Python, Go, and Rust
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This benchmark runs three PURL validators implementations.
The script is ``etc/bench/go-rust-py_benchmark.py``.

The benchmark goes through these steps:

-  loads PURL lists from ``purl-validator.rs/fst_builder/data``.
-  builds the Python ``ducer`` map (i.e., a Rust FST using the ``fst`` crate).
-  builds the Rust FST with ``purl-validator.rs``.
-  builds the Go FST with ``purlvalidator-go``.
-  runs 1M lookups, with 500K known PURLs and 500K unknown PURLs.


Run it from the purl-validator/ dir (with activated venv):

.. code:: sh

   python etc/bench/go-rust-py_benchmark.py \
       --queries 1000000 \
       --report tmp/go-rust-py-results.txt

PURL data is from ``purl-validator.rs/fst_builder/data/``

Results with 2,324,119 unique PURLs and 1M lookup queries, 500K existing
PURLs:

.. code:: text

   structure               build (secs)   lookup (secs)   storage size (ondisk)
   --------------------   ------------   --------------   ---------------------------
   Python purl-validator    16.664847      4.926029         25MB
   Rust purl-validator.rs   11.849877      0.348128         25MB
   Go purlvalidator-go       2.325181      0.704749         25MB


Evaluation and final solution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Rust implementation has the fastest lookup in this run. The Python
on-disk FST is about the same size as the Rust FST because both use the
same backing FST implementation.

The Go index build is faster in this run. That may be worth checking
against the Rust FST builder.

The Python ``set`` and ``dict`` are fast baselines, but they use much
more RAM than the on-disk FST.
