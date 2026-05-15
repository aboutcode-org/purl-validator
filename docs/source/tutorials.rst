.. _tutorials:

Tutorials
=========

Validate a list of PURLs with Python
------------------------------------

Create a file named ``purls.txt``:

.. code-block:: text

    pkg:nuget/FluentValidation
    pkg:nuget/non-existent-foo-bar
    pkg:pypi/django

Run this script:

.. code-block:: python

    from pathlib import Path
    from purl_validator import PurlValidator

    validator = PurlValidator()

    for line in Path("purls.txt").read_text().splitlines():
        purl = line.strip()
        if not purl:
            continue
        print(purl, validator.validate_purl(purl))


Use PurlValidator in an SBOM check
----------------------------------

The basic workflow is:

1. Extract PURLs from an SBOM.
2. Convert each PURL to its base identity.
3. Validate each base PURL with one PurlValidator library.
4. Report unknown PURLs for review.

An unknown PURL may be a typo, a wrong package type, or a package missing from
the packaged reference data. Handle unknown PURLs according to the policy for
your project.
