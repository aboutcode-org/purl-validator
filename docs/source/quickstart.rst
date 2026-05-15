.. _quickstart:

Quickstart
==========

Python
------

Install the Python package:

.. code-block:: bash

    pip install purl-validator

Validate a PURL:

.. code-block:: python

    from purl_validator import PurlValidator

    validator = PurlValidator()

    print(validator.validate_purl("pkg:nuget/FluentValidation"))
    print(validator.validate_purl("pkg:nuget/non-existent-foo-bar"))

Rust
----

Install the Rust crate:

.. code-block:: bash

    cargo add purl_validator

Validate a PURL:

.. code-block:: rust

    use purl_validator::validate;

    fn main() {
        let exists = validate("pkg:nuget/FluentValidation")
            .expect("input must be a supported base PURL");

        println!("{exists}");
    }

Go
--

Install the Go module:

.. code-block:: bash

    go get github.com/aboutcode-org/purlvalidator-go

Validate a PURL:

.. code-block:: go

    package main

    import (
        "fmt"
        "log"

        purlvalidator "github.com/aboutcode-org/purlvalidator-go"
    )

    func main() {
        exists, err := purlvalidator.Validate("pkg:nuget/FluentValidation")
        if err != nil {
            log.Fatal(err)
        }

        fmt.Println(exists)
    }

Next steps
----------

- Use the Python README for Python-specific helper APIs:  https://github.com/aboutcode-org/purl-validator
- Use the Rust README for error handling with ``ValidateError``: https://github.com/aboutcode-org/purl-validator.rs
- Use the Go README for ``Validate`` return values and integration examples: https://github.com/aboutcode-org/purlvalidator-go
