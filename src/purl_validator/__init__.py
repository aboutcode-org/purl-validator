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


PURLS = """
pkg:maven/be.sweetmustard.vinegar/vinegar-pattern-matcher@0.1.1
pkg:maven/be.sweetmustard.vinegar/vinegar-pattern-matcher@0.1.1?classifier=sources
pkg:maven/be.sweetmustard.vinegar/vinegar-pattern-matcher@0.1.0
pkg:maven/be.sweetmustard.vinegar/vinegar-pattern-matcher@0.1.0?classifier=sources
""".split()


def create_purl_map(purls):
    # Ensure elements of `purls` are strings:
    purl_strs = []
    for purl in purls:
        if not isinstance(purl, (PackageURL, str)):
            raise ValueError(f"invalid purl in `purls`: {purl}")
        if isinstance(purl, PackageURL):
            purl_str = purl.to_string()
        else:
            purl_str = purl
        purl_strs.append(purl_str)

    # purl strs must be sorted and converted to bytes before going into the Map
    prepared_purl_strs = [(bytes(purl_str, "utf-8"), 1) for purl_str in sorted(purl_strs)]

    # create map
    temp_dir = fileutils.get_temp_dir()
    map_loc = Path(temp_dir) / "purls.map"
    ducer.Map.build(map_loc, prepared_purl_strs)

    return map_loc


class PurlValidator:
    def __init__(self, purl_map_loc=None):
        self.created_maps = []

        if purl_map_loc:
            if not isinstance(purl_map_loc, (Path, str)):
                raise ValueError("`purl_map_loc` must be a Path or path string")
            if not isinstance(purl_map_loc, Path):
                # Ensure purl_map_loc is a Path
                purl_map_loc = Path(purl_map_loc)
        else:
            # Create purl map from PURLS
            purl_map_loc = self.create_purl_map(purls=PURLS)

        self.purl_map = self.load_purl_map(location=purl_map_loc)

    def __del__(self):
        for loc in self.created_maps:
            fileutils.delete(loc.parent)

    def create_purl_map(self, purls):
        purl_map_loc = create_purl_map(purls)
        self.created_maps.append(purl_map_loc)
        return purl_map_loc

    def load_purl_map(self, location):
        with open(location, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        m = ducer.Map(mm)
        return m

    def validate_purl(self, purl):
        if not isinstance(purl, (PackageURL, str)):
            raise ValueError("`purl` must be a PackageURL or purl string")

        # Ensure `purl` is a PackageURL
        if isinstance(purl, str):
            purl = PackageURL.from_string(purl)

        # Convert purl to bytes
        purl_bytes = bytes(purl.to_string(), "utf-8")

        return bool(self.purl_map.get(purl_bytes))


if __name__ == "__main__":
    purl_validator = PurlValidator()
    print(
        purl_validator.validate_purl(
            "pkg:maven/be.sweetmustard.vinegar/vinegar-pattern-matcher@0.1.1"
        )
    )
