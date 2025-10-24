purl-validator
================================

PURLs are everywhere in SBOMs. But with adoption comes widespread errors.
A recent study on the quality of SBOMs revealed that for many proprietary and
open source tools, PURLs in SBOMs are inconsistent, fake, incorrect, or
misleading. This is a serious problem to any application of SBOMs for
cybersecurity and application security, as well as related compliance
regulations. This project is to create a PURL validator that's decentralized
such that libraries can use it offline and help them create better PURLs.

Building this compact dataset is new territory. There is research
and exploration necessary for creating a super compact data structure
that is also easy and fast to query across multiple languages. The data
structure will also need memory-mapping to avoid running out of memory.
