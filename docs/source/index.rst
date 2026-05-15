PurlValidator Documentation
===========================

PurlValidator checks whether a base Package-URL (PURL) is present in a known
package catalog. It works without a network connection after installation.

A valid PURL string can still name a package that is not known. PurlValidator
adds this package identity check for SBOM, VEX, SCA, and compliance workflows.

Why?
-----

Package-URL, or PURL, is the de-facto standard for identifying software
packages, used by open source SCA tools, SBOM and VEX specs, and vulnerability
databases. But using a standard syntax does not prevent errors: A recent
study on the quality of software bill of materials (SBoM) revealed that for too
often PURLs in SBOMs are still inconsistent, fake, incorrect, or misleading.
This is a major impairment to any application of SBOMs, and industry-wide
cybersecurity and application security.

The PurlValidator project is a public service, based on PurlDB, to validate all
the PURLs. An extension of the purl2all project, PurlValidator validates the
PURL syntax against any known PURLs by exposing PurlDB's reference data of
20M+ PURLs. PurlValidator also provides decentralized libraries for offline
use that can be integrated in multiple tech stacks for all major ecosystems,
beyond what is already available for PURL tools. The goal of this project is to
provide an accessible, single source of truth to the security and SBOM ecosystem
at large and improve the quality and accuracy of PURLs in use, imperative for
CRA compliance.


Documentation overview
----------------------

Getting started
~~~~~~~~~~~~~~~

- :ref:`quickstart`
- :ref:`introduction`

Tutorials
~~~~~~~~~

- :ref:`tutorials`

How-to guides
~~~~~~~~~~~~~

- :ref:`how_to_guides`

Reference
~~~~~~~~~

- :ref:`reference`

Explanations
~~~~~~~~~~~~

- :ref:`explanations`
- :ref:`data_structure_rationale`

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`

.. toctree::
   :maxdepth: 2
   :hidden:

   quickstart
   introduction
   tutorials
   how-to-guides
   reference
   explanations
   data-structure-rationale
   contribute/contrib_doc
