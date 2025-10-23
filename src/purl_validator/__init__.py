#
# Copyright (c) nexB Inc. and others.
# SPDX-License-Identifier: Apache-2.0
#
# Visit https://aboutcode.org and https://github.com/aboutcode-org/ for support and download.
# ScanCode is a trademark of nexB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from pathlib import Path
import mmap

from commoncode import fileutils
from packageurl import PackageURL
import ducer


PURL_MAP_LOCATION = Path(__file__).parent / "purls.map"


def create_purl_map_entry(purl):
    """
    Given a `purl` that is a PackageURL proper or a string representation of
    one, return a bytestring containing the type, namespace (if available), and
    name of the package from `purl`.
    """
    if not isinstance(purl, (PackageURL, str)):
        raise ValueError(f"invalid `purl`: {purl}")

    # Ensure `purl` is a PackageURL
    if isinstance(purl, str):
        p = PackageURL.from_string(purl)
    else:
        p = purl

    # Create purl map entry string
    if p.namespace:
        purl_str = f"{p.type}/{p.namespace}/{p.name}"
    else:
        purl_str = f"{p.type}/{p.name}"

    # Convert purl map entry string to bytes
    return bytes(purl_str, "utf-8")


def create_purl_map(purls):
    """
    Given an iterable of `purls`, that can be either PackageURLs proper or
    strings representing them, return a Ducer map that contains strings created
    from the type, namespace (if available), and name of the packages from
    `purls`.
    """
    # purl map entries must be unique, sorted, and converted to bytes before going into the Map
    purl_map_entries = set(create_purl_map_entry(purl) for purl in purls)
    prepared_purl_map_entries = sorted((purl_map_entry, 1) for purl_map_entry in purl_map_entries)

    # create map
    temp_dir = fileutils.get_temp_dir()
    map_loc = Path(temp_dir) / "purls.map"
    ducer.Map.build(map_loc, prepared_purl_map_entries)

    return map_loc


class PurlValidator:
    def __init__(self, purl_map_loc=PURL_MAP_LOCATION):
        self.purl_map = self.load_map(location=purl_map_loc)

    @classmethod
    def load_map(cls, location):
        with open(location, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        m = ducer.Map(mm)
        return m

    def validate_purl(self, purl):
        """
        Given a `purl` that is a PackageURL proper or a string representation of
        one, return True if `purl` exists, False otherwise.
        """
        purl_map_entry = create_purl_map_entry(purl)
        in_purl_map = bool(self.purl_map.get(purl_map_entry))
        return in_purl_map
