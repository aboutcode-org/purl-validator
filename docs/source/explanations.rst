.. _explanations:

Explanations
============

Syntax validation and identity validation
-----------------------------------------

The Package-URL spec defines the PURL format. A PURL can follow the spec
format and still name a package that is not known in the package ecosystems.

PurlValidator checks the package PURL against reference data of known PURLs. This
helps find misspelled names, wrong package types, and PURL that
do not appear in the reference upstream ecosystem package repositories.


Offline validation
------------------

SBOM and compliance workflows may run in CI systems, private networks, or
air-gapped environments. PurlValidator packages lookup data with each released
library so validation does not need a network registry access at runtime.


Base PURL validation
--------------------

PURL existence is checked before version existence.

The current libraries validate base PURLs only, no versions. Version support
can be a future enhancement.
