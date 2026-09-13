from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from unittest import mock

from app.services import seo_publish
from app.services.seo_publish import evaluate_listing_for_seo, seo_slug


class SeoPublishTests(unittest.TestCase):
    def test_slug_is_stable_for_latin_and_cyrillic(self) -> None:
        self.assertEqual(seo_slug("Toyota"), "toyota")
        self.assertEqual(seo_slug("Тойота"), "toyota")
        self.assertEqual(seo_slug("Step WGN"), "step-wgn")

    def test_complete_listing_is_publishable(self) -> None:
        result = evaluate_listing_for_seo(
            market="japan",
            brand="Toyota",
            model="Raize",
            year=2022,
            price=1_400_000,
            images_count=3,
        )
        self.assertTrue(result.eligible)
        self.assertEqual(result.url, "/cars/japan/toyota/raize/")
        self.assertIsNone(result.reason)

    def test_incomplete_listing_stays_catalog_only(self) -> None:
        result = evaluate_listing_for_seo(
            market="korea",
            brand="Kia",
            model="Seltos",
            year=None,
            price=None,
            images_count=0,
        )
        self.assertFalse(result.eligible)
        self.assertIn("год", result.reason or "")
        self.assertIn("цена", result.reason or "")
        self.assertIn("фотография", result.reason or "")

    def test_site_root_is_forwarded_to_publisher_process(self) -> None:
        with (
            mock.patch.object(seo_publish.settings, "seo_publish_command", "node publish.mjs"),
            mock.patch.object(seo_publish.settings, "seo_publish_workdir", "/opt/primcom/seo-publisher"),
            mock.patch.object(seo_publish.settings, "primcom_site_root", "/srv/primcom/public"),
            mock.patch.object(
                seo_publish.subprocess,
                "run",
                return_value=CompletedProcess(["node", "publish.mjs"], 0, "ok", ""),
            ) as run,
        ):
            result = seo_publish._run_publish_command()

        self.assertTrue(result.ok)
        self.assertEqual(run.call_args.kwargs["env"]["PRIMCOM_SITE_ROOT"], "/srv/primcom/public")


if __name__ == "__main__":
    unittest.main()
