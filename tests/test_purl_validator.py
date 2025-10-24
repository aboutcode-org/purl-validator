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

import purl_validator
from packageurl import PackageURL
from commoncode import fileutils
from commoncode.testcase import FileBasedTesting


class TestPurlValidator(FileBasedTesting):
    def setUp(self):
        self.created_purl_maps = []
        return super().setUp()

    def tearDown(self):
        for purl_map in self.created_purl_maps:
            fileutils.delete(purl_map.parent)
        return super().tearDown()

    def create_purl_map(self, purls):
        purl_map_loc = purl_validator.create_purl_map(purls)
        self.created_purl_maps.append(purl_map_loc)
        return purl_map_loc

    def test_purl_validator_create_purl_map_entry(self):
        test_purl1 = PackageURL(type="npm", namespace="@test", name="test", version="1.0")
        test_purl2 = "pkg:npm/test2@2.0"
        test_purl3 = "not-a-purl"
        test_purl4 = []

        self.assertEqual(b"npm/@test/test", purl_validator.create_purl_map_entry(test_purl1))
        self.assertEqual(b"npm/test2", purl_validator.create_purl_map_entry(test_purl2))

        with self.assertRaises(ValueError):
            purl_validator.create_purl_map_entry(test_purl3)

        with self.assertRaises(ValueError):
            purl_validator.create_purl_map_entry(test_purl4)

    def test_purl_validator_create_purl_map_entry(self):
        test_purl1 = PackageURL(type="npm", namespace="@test", name="test", version="1.0")
        test_purl2 = "pkg:npm/test2@2.0"
        test_purl3 = "not-a-purl"
        test_purl4 = []
        purls = [test_purl1, test_purl2]

        purl_map_loc = self.create_purl_map(purls)
        purl_map = purl_validator.PurlValidator.load_map(purl_map_loc)
        expected_results = [(b"npm/@test/test", 1), (b"npm/test2", 1)]
        results = [(k, v) for k, v in purl_map.items()]
        self.assertEqual(expected_results, results)

        with self.assertRaises(ValueError):
            self.create_purl_map([test_purl3])

        with self.assertRaises(ValueError):
            self.create_purl_map([test_purl4])
