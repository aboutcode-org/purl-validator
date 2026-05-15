.. _data_structure_rationale:

FST Data Structure Rationale
=============================

PurlValidator needs exact membership lookup for a large list of base PURLs. The
lookup data index is built before release and bundled with each library.


See https://github.com/aboutcode-org/purl-validator/tree/main/etc/bench for
actual detailed rationale and bench for the choice of an FST.


Why FSTs are used?
------------------

Finite state transducers store sorted strings in a compact form. PURLs share
prefixes such as ``pkg:npm/``, ``pkg:pypi/``, and ``pkg:maven/``. This makes an
FST useful for exact package identity queries.

FST can be memory-mapped and are super compact. They are not as fast as native
set, but the memory consumption is so much lower than this make them the most
attractive solution, even if it takes more time to build.


Requirements
---------------

The index structure should provide:

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




Selected FST libraries
--------------------------

Python uses ``ducer.Map`` with ``mmap``. The map is stored on disk and opened
without loading the full catalog into Python objects.

Rust uses ``fst::Set``. The generated FST is embedded into the crate.

Go uses Vellum FST. The generated FST is embedded into the module.

Alternatives
------------

We considered also built-in sets and maps as a baseline:

- Python: ``set`` and ``dict``.
- Rust: ``HashSet`` and ``HashMap``.
- Go: ``map[string]struct{}`` and ``map[string]bool``.

These structures are simple and fast. They require loading all keys into
runtime memory, so they are less useful as the packaged lookup format.

Sorted arrays or slices can use binary search. They are simple and exact, but
lookup takes repeated string comparisons and the strings still need to be
loaded.

SQLite can store the PURLs in an indexed table. It gives exact results, but it
adds a database dependency for a read-only membership check. It has way more
features than needed and is overkill for our use case.

Bloom filters are small and fast, but they can return false positives. They
should cannot be used as validation index.

A DAWG can store a set of strings by sharing prefixes and suffixes. It may be a
valid alternative to an FST (it is very similar to) but there are few maintained
libraries in the target languages.
