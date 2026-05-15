.. _reference:

Reference
=========

Supported ecosystems
--------------------

The current validators package indexed reference data for these pacakge types/ecosystems:

- ``apk``
- ``cargo``
- ``composer``
- ``conan``
- ``cpan``
- ``cran``
- ``debian``
- ``maven``
- ``npm``
- ``nuget``
- ``pypi``
- ``swift``

Base PURLs
----------

A base PURL is a Package-URL without a version, qualifiers, or subpath.

Examples:

.. code-block:: text

    pkg:pypi/django
    pkg:npm/%40angular/core
    pkg:maven/org.apache.commons/commons-lang3

Unsupported examples:

.. code-block:: text

    pkg:pypi/django@5.0.0
    pkg:npm/%40angular/core?repository_url=https://registry.npmjs.org
    pkg:maven/org.apache.commons/commons-lang3#src/main

Implementation summary
----------------------

- Python uses a memory-mapped compact map through ``ducer.Map``.
- Rust uses an embedded ``fst::Set`` generated from sorted PURL strings.
- Go uses an embedded Vellum FST generated from sorted PURL strings.


Language APIs
-------------

Python:

.. code-block:: python

    from purl_validator import PurlValidator

    validator = PurlValidator()
    exists = validator.validate_purl("pkg:pypi/django")

Rust:

.. code-block:: rust

    let exists = purl_validator::validate("pkg:pypi/django")?;

Go:

.. code-block:: go

    exists, err := purlvalidator.Validate("pkg:pypi/django")
