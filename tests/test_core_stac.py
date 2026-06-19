# -*- coding: utf-8 -*-
"""
Unit tests for core_stac.py.

These tests exercise the pure-Python logic (no QGIS, no live network).
Network access is replaced by monkeypatching the private HTTP helpers.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core_stac  # noqa: E402


class TestRasterDetection(unittest.TestCase):
    def test_by_extension(self):
        self.assertTrue(core_stac._is_raster_asset({"href": "x/y.tif"}))
        self.assertTrue(core_stac._is_raster_asset({"href": "x/y.JP2"}))

    def test_by_mime(self):
        self.assertTrue(
            core_stac._is_raster_asset({"href": "a", "type": "image/tiff"})
        )

    def test_by_role(self):
        self.assertTrue(
            core_stac._is_raster_asset({"href": "a", "roles": ["data"]})
        )

    def test_negative(self):
        self.assertFalse(
            core_stac._is_raster_asset(
                {"href": "meta.json", "type": "application/json"}
            )
        )


class TestParseItem(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "id": "S2_TEST",
            "bbox": [12.0, 41.0, 12.5, 41.5],
            "properties": {
                "datetime": "2023-06-01T10:00:00Z",
                "eo:cloud_cover": 12.3,
                "platform": "sentinel-2a",
                "gsd": 10,
                "eo:bands": [{"name": "B04"}, {"name": "B03"}, {"name": "B02"}],
                "proj:epsg": 32633,
            },
            "assets": {
                "thumbnail": {
                    "href": "http://x/thumb.png", "type": "image/png",
                    "roles": ["thumbnail"],
                },
                "visual": {
                    "href": "http://x/visual.tif",
                    "type": "image/tiff; application=geotiff",
                    "roles": ["visual"], "file:size": 2 * 1024 * 1024,
                },
                "B04": {
                    "href": "http://x/B04.tif",
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                },
            },
        }

    def test_fields(self):
        parsed = core_stac.parse_stac_item(
            self.feature, "http://cat", "Test Catalog"
        )
        self.assertEqual(parsed["id"], "S2_TEST")
        self.assertEqual(parsed["catalog_name"], "Test Catalog")
        self.assertEqual(parsed["cloud_cover"], 12.3)
        self.assertEqual(parsed["bands_count"], 3)
        self.assertEqual(parsed["preview"], "http://x/thumb.png")

    def test_asset_size_and_sort(self):
        parsed = core_stac.parse_stac_item(self.feature)
        # Raster assets must come before the thumbnail (sorted first).
        self.assertTrue(parsed["assets"][0]["is_raster"])
        visual = next(a for a in parsed["assets"] if a["key"] == "visual")
        self.assertEqual(visual["size_mb"], 2.0)

    def test_best_raster_prefers_data(self):
        parsed = core_stac.parse_stac_item(self.feature)
        best = core_stac.best_raster_asset(parsed)
        self.assertEqual(best["key"], "B04")  # role "data" wins over "visual"


class TestGeocode(unittest.TestCase):
    def test_empty_query(self):
        self.assertEqual(core_stac.geocode_nominatim("   "), [])

    def test_parses_results(self):
        fake = [{
            "display_name": "Roma, Italia",
            "lon": "12.4964",
            "lat": "41.9028",
            "boundingbox": ["41.79", "42.00", "12.34", "12.62"],
        }]
        orig = core_stac._http_get
        core_stac._http_get = lambda url, timeout=10: fake
        try:
            res = core_stac.geocode_nominatim("Roma")
        finally:
            core_stac._http_get = orig
        self.assertEqual(len(res), 1)
        w, s, e, n = res[0]["bbox"]
        self.assertAlmostEqual(w, 12.34)
        self.assertAlmostEqual(s, 41.79)
        self.assertAlmostEqual(e, 12.62)
        self.assertAlmostEqual(n, 42.00)

    def test_network_error_returns_empty(self):
        orig = core_stac._http_get

        def boom(url, timeout=10):
            raise OSError("no network")

        core_stac._http_get = boom
        try:
            self.assertEqual(core_stac.geocode_nominatim("Roma"), [])
        finally:
            core_stac._http_get = orig


class TestSigning(unittest.TestCase):
    def test_non_azure_unchanged(self):
        h = "https://earth-search.aws.element84.com/x/B04.tif"
        self.assertEqual(core_stac.sign_href_if_needed(h), h)

    def test_already_signed_unchanged(self):
        h = ("https://x.blob.core.windows.net/c/B04.tif"
             "?st=2024&se=2024&sig=abc")
        self.assertEqual(core_stac.sign_href_if_needed(h), h)

    def test_azure_gets_signed(self):
        h = "https://x.blob.core.windows.net/c/B04.tif"
        orig = core_stac._http_get
        core_stac._http_get = lambda url, timeout=10: {"href": h + "?sig=TOK"}
        try:
            out = core_stac.sign_href_if_needed(h)
        finally:
            core_stac._http_get = orig
        self.assertEqual(out, h + "?sig=TOK")

    def test_sign_failure_returns_original(self):
        h = "https://x.blob.core.windows.net/c/B04.tif"
        orig = core_stac._http_get

        def boom(url, timeout=10):
            raise OSError("down")

        core_stac._http_get = boom
        try:
            self.assertEqual(core_stac.sign_href_if_needed(h), h)
        finally:
            core_stac._http_get = orig


class TestHtmlDetection(unittest.TestCase):
    def test_html_content_type(self):
        self.assertTrue(
            core_stac._looks_like_html_or_login("text/html; charset=utf-8")
        )

    def test_html_body_sniff(self):
        self.assertTrue(
            core_stac._looks_like_html_or_login("", b"<!DOCTYPE html>\n<html>")
        )

    def test_real_tiff_not_flagged(self):
        self.assertFalse(
            core_stac._looks_like_html_or_login(
                "image/tiff", b"II*\x00\x08\x00\x00\x00"
            )
        )


class TestSearchErrors(unittest.TestCase):
    def test_search_handles_failure_gracefully(self):
        orig = core_stac._http_post

        def boom(url, body, timeout=20):
            raise OSError("down")

        core_stac._http_post = boom
        try:
            out = core_stac.stac_search("http://cat", [0, 0, 1, 1])
        finally:
            core_stac._http_post = orig
        self.assertEqual(out["items"], [])
        self.assertIsNotNone(out["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
