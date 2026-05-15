# PurlValidator data structure evaluation

This document details the research and evaluation of various efficient data
structures for compact PURLs storage and lookup.

It contains:

- reference to evaluation/bench scripts
- documentation on the various libraries and data structures under consideration
- the final choice (spoiler an FST, aka. finite state transducer)


## Context and Problem

PurlValidator needs a local queryable dataset of known PURLs to answer one question:

> Does this PURL exist in the reference dataset?

The lookup index should be built for each release, and shipped with the library
for access without a network connection. And we want a Go, Rust and Python
implementation. The PURls themselves are collected using PurlDB and FederatedCode.


## Solution

### High level design

The lookup key is a PURL, cleaned to only keep type, namespace, and name,
(without version, qualifiers and subpath)

This keeps validation focused for now. Version validation could come later by
extending indexed PURLs with version or baking in support VERS version parsing
for validation

### Solution elements: Data structures considered

- Built-in set and map
- FST
- DAWG
- Bloom filter
- SQLite

Considered but not evaluated:

- Minimal perfect hash: no compression
- Trie or radix tree: DAWG and FST are similar, but are more compact. Suffix
  trees are way too big.

#### Built-in set and map

Built-in sets and maps are the simplest baseline in each language, they are as
fast as can be, but they have no compression and no built-in serialization or
memory mapping, and memory use grows quickly for large datasets.

An interesting path could be to use built-in sets in Rust and Go generating the
code with all the PURL strings so that there is no specific deserialization. The
porblem there is the size as the data is not compressed.

Built-ins structures are useful for benchmarks as reference but are not suitable
as the main packaged data structure because they are too big.


#### FST: finite state transducer

<https://en.wikipedia.org/wiki/Finite-state_transducer>

An FST stores a sorted set of strings in a compact automaton. PURLs share common
prefixes such as `pkg:npm/`, `pkg:pypi/`, and `pkg:maven/`. This sharing helps
reduce stored data.

FST lookup is exact for this use case. The Rust and Go implementations already
ship an FST file. The library opens or embeds that file and performs membership
checks without rebuilding the index.

The main cost is build complexity. Input must be prepared, sorted, and encoded
when the package data is refreshed.


#### DAWG: directed acyclic word graph

See <https://stevehanov.ca/blog/compressing-dictionaries-with-a-dawg>

this is aka. DAFSA
<https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton>

A DAWG is a compact data structure for a set of strings. It can merge repeated
prefixes and suffixes like an FST. The DAWG is interesting in that it can
support prefix lookup, but in general the DAWG is bigger and slower than an FST,
and has fewer mature/maintained library support.


#### Bloom filter

<https://en.wikipedia.org/wiki/Bloom_filter>

A Bloom filter can store a large set in a small space, but it is a probalistic
structure and can answer that a value is surely absent or maybe present. In that
later case, you need an extra full dataset to validate further the "maybe": this
is the problem of false positives with these filters, hence a Bloom filter
cannot not be used as the only lookup structure, and does not make sense here.
Instead, a Bloom filter could be used before an exact structure to skip some
exact lookups as performance optimization, but outside of the validator.


#### SQLite

<https://sqlite.org/>

SQLite can store PURLs in a SQL table with an index for exact lookup.

The tradeoff is operational weight. Each SQLite language binding adds a
dependency (though this is built in Python). The validator only needs immutable
membership checks, not SQL full power with queries, and update transactions; but
on the other hand the SQLite DB could be the same across all languages.

SQLite could useful as a benchmark and debugging format. It is not the first
choice for a small language library because this is not compressed. But it will
be a future enhancement for sure.


### Preferred solution: FST

Based on the benchmark and otrher criteria, let's use an FST-backed lookup for
every languages. Do not use a Bloom filter (probalistic). Do not use native
structures that use too much memory.

And for the library selection, we have these high level requirements:

- We want exact result without false positives, e.g., no bloom filter.
- Offline use, with no network is a must: the dataset must be bundled in the
  releases.
- With build time index construction, the construction time is not critical.
- The bundled index should be small enough to ship below crates, and Pypi
  archive size limits.
- No rebuild at startup/runtime, and fast enough load time from disk, ideally
  memory-mapped.
- Fast enough lookup.
- Libraries should be maintained, active FOSS for Rust/Go/Python.

The final selected FST libraries are:

- Rust: fst crate with a memory-mapped set <https://github.com/BurntSushi/fst/>
- Python: ducer with a memory-mapped map, dict-like
  <https://github.com/jfolz/ducer> (ducer uses the Rust fst crate inside)
- Go: vellum "fst" module (originally from
  <https://github.com/couchbase/vellum> now at
  <https://github.com/blevesearch/vellum>) which is mostly inspired from the
  Rust fst crate


## Appendix: Benchmarks

This directory contains evaluation and benchmark files for PurlValidator.

It compares structures for offline PURL membership checks with these
implementations use:

- Python: memory-mapped `ducer`.
- Rust: crate `fst`.
- Go: embedded Vellum FST.

... as well as the builtin Python set and dict, SQLite and a Rust DAWG

### Expected checkout layout

Run the scripts from a directory with these repositories checkouts:

- `/purl-validator`
- `/purl-validator.rs`
- `/purlvalidator-go`

### benchmarking FST vs. DAWG

There is a good benchmarch in Go comparing FST and DAWG data structures (and
other structures) that highlights why an FST is a better structure for our cases
than a DAWG:

<https://github.com/timurgarif/go-fsa-trie-bench>

We also did a simple synthetic benchmark of the Rust fst and dawg crates using
actual base PURLs using the data in
<https://github.com/aboutcode-org/purl-validator.rs/tree/main/fst_builder/data>

The `etc/bench/rust-fst-dawg-bench` code compare these fst and dawg crates.

The dataset profile has 2,324,119 unique sorted base PURL. The benchmark is to
run 1M queries, where 500K are expected to fail.

- The fst crate index was built in 11s, with a 26MB serialized file, and took
  0.703s for 1M lookups.
- The dawg crate index was built in 18s, with a 831MB serialized file, and took
  28s for 1M lookups.

The outcome is that the preferred structure is an FST over a DAWG (at least
with these implementations).

### benchmarking FST against builtin and SQLite

Since we picked the FST as the winner, additional review has been focused on
Python by comparing the ducer fst library against other approaches. Since it is
based on the Rust fst and Go's vellum is also based on the fst design, we cover
essentially the three languages at once.

The `etc/scripts/bench/alternative_benchmark.py` script compares Python lookup
using a text file with one PURL per line for these candidates:

- Python `set`.
- Python `dict`.
- Python Sorted list plus `bisect`.
- In-memory SQLite.
- FST using a `ducer.Map`.

Data is from `purl-validator.rs/fst_builder/data/`

Results with 2,324,119 unique PURLs and 1M lookup queries, 500K existing PURLs:

```text
structure               build (secs)   lookup (secs)   storage size
--------------------   ------------   --------------   ---------------------------
python set               0.206540       0.275906        304MB in RAM
python dict              0.449625       0.429034        298MB in RAM
ducer FST                3.700943       1.805585         26MB on disk
sorted list+bisect       0.017540       2.783555        236MB in RAM
sqlite in memory         4.855480       4.220032        207MB on disk (or 65MB with zstd)
```

### benchmarking FST in Python vs. Go vs. Rust

This benchmark runs each of the three validator released implementations. The
script is in `etc/scripts/bench/go-rust-py_benchmark.py`

Data is from `purl-validator.rs/fst_builder/data/`

Results with 2,324,119 unique PURLs and 1M lookup queries, 500K existing PURLs:

```text
structure               build (secs)   lookup (secs)   storage size (ondisk)
--------------------   ------------   --------------   ---------------------------
Python purl-validator    16.664847      4.926029         25MB
Rust purl-validator.rs   11.849877      0.348128         25MB
Go purlvalidator-go       2.325181      0.704749         25MB
```

### Evaluation

The results are consistent with expectations: Rust is faster than Go and Python.

And the Python on disk fst is the same size as the Rust fst (since this is the
same backing code).

Some surprises:

- The build of the Go index is the fastest which is surprising and could be an
  avenue of improvement for the Rust fst crate.

- Leaving aside the 10x larger RAM need, the Python set and dict are competitive
  speed wise (faster than the on-disk Rust FST) ans super fast to build too.
  
