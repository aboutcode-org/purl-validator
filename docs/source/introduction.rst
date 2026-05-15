.. _introduction:

Introduction
============

PurlValidator checks package identity for Package-URLs (PURLs). It does
not replace syntax validation. It adds a lookup against an index of packaged
reference data.

Why this exists?
-----------------

PURL is used in SBOMs, VEX documents, SCA tools, and vulnerability databases.
The PURL spec tells tools how to write a package identifier, but does
not prove that the package exists.

Common PURL data problems include:

- Misspelled package names.
- Wrong or made up package types.
- Package that are not present in an ecosystem.

PurlValidator answers this question:

Does this PURL exists for a known package?

Repositories
------------

We have three implementations in Rust, Go and Python.
Each repository has language-specific usage notes in its README.

- Python: https://github.com/aboutcode-org/purl-validator
- Rust: https://github.com/aboutcode-org/purl-validator.rs
- Go: https://github.com/aboutcode-org/purlvalidator-go


Validation scope
----------------

PurlValidator validates PURLs, ignoring version. A base PURL contains:

- Type, such as ``npm`` or ``pypi``.
- Optional namespace, such as an npm scope or Maven groupid.
- Name.

Versions, qualifiers, and subpaths are not part of the lookup query.
