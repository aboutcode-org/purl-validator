PurlValidator data structure evaluation
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
probabilistic structure and can answer that a value is surely absent or
maybe present. In that later case, you need an extra full dataset to
validate further the “maybe”: this is the problem of false positives
with these filters, hence a Bloom filter cannot not be used as the only
lookup structure, and does not make sense here. Instead, a Bloom filter
could be used before an exact structure to skip some exact lookup as
performance optimization, but outside of the validator.

SQLite
^^^^^^

https://sqlite.org/

SQLite can store PURLs in a SQL table with an index for exact lookup.

The trade-off is operational weight. Each SQLite language binding adds a
dependency (though this is built in Python). The validator only needs
immutable membership checks, not SQL full power with queries, and update
transactions; but on the other hand the SQLite DB could be the same
across all languages.

SQLite could useful as a benchmark and debugging format. It is not the
first choice for a small language library because this is not
compressed. But it will be a future enhancement for sure.

Preferred solution: FST
~~~~~~~~~~~~~~~~~~~~~~~

Based on the benchmark and other criteria, let’s use an FST-backed
lookup for every languages. Do not use a Bloom filter (probabilistic). Do
not use native structures that use too much memory.

And for the library selection, we have these high level requirements:

- We want exact result without false positives, e.g., no bloom filter.
- Offline use, with no network is a must: the dataset must be bundled
in the releases.
- With build time index construction, the construction time is not
critical.
- The bundled index should be small enough to ship below crates, and
Pypi archive size limits.
- No rebuild at startup/runtime, and fast enough load time from disk,
ideally memory-mapped.
- Fast enough lookup.
- Libraries should be maintained, active FOSS for Rust/Go/Python.

The final selected FST libraries are:

- Rust: fst crate with a memory-mapped set
https://github.com/BurntSushi/fst/
- Python: ducer with a memory-mapped map, dict-like
https://github.com/jfolz/ducer (ducer uses the Rust fst crate inside)
- Go: vellum “fst” module (originally from
https://github.com/couchbase/vellum now at
https://github.com/blevesearch/vellum) which is mostly inspired from
