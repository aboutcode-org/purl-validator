.. _how_to_guides:

How-to Guides
=============

Choose an implementation
------------------------

Use the implementation that matches the application:

- Use Python for Python scripts, data pipelines, etc.
- Use Rust for Rust appss.
- Use Go for Go apps and command-line tools.

All implementations package PURL index data with the released library.


Update validation data
----------------------

PurlValidator index data is released with each package. To update the
data used by an application, update the PurlValidator package version.


Validation results
--------------------------

Treat validation results in these groups:

- Known: the PURL is valid and exists in the reference data.
- Unknown: the PURL is valid (parsing) but not present in the reference data.
- Invalid or unsupported: the input is not a supported or known PURL.

For SBOM checks, you should report unknown and invalid PURLs separately.
Invalid PURLs are usually an error of the SBOM or SCA producer tool.
Unknown PURLs could be new packages, or typos, or SCA tools inventions.
