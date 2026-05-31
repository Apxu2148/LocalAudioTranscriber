import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config
from app import utils as utils_module


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"
config.JOBS_DIR = PROJECT_TMP

with patch.object(utils_module, "setup_logging"):
    from app import main as main_module  # noqa: E402


class HttpSmokeTests(unittest.TestCase):
    def test_interface_assets_disable_browser_cache(self) -> None:
        with TestClient(main_module.app) as client:
            for url in ["/", "/static/app.js", "/static/style.css", "/static/tour.js"]:
                response = client.get(url)
                self.assertEqual(200, response.status_code, url)
                self.assertEqual("no-store, no-cache, must-revalidate, max-age=0", response.headers["cache-control"])
                self.assertEqual("no-cache", response.headers["pragma"])
                self.assertEqual("0", response.headers["expires"])

    def test_status_exposes_app_version_and_queue_shape(self) -> None:
        fake_transcriber_status = {
            "configured_device": "auto",
            "configured_compute_type": "auto",
            "in_progress": False,
        }
        with (
            patch.object(main_module.recorder, "microphone_status", return_value={"available": True}),
            patch.object(main_module.system_recorder, "output_status", return_value={"available": True}),
            patch.object(main_module.transcriber, "status", return_value=fake_transcriber_status),
            patch.object(main_module, "model_statuses", return_value=[]),
            TestClient(main_module.app) as client,
        ):
            status_response = client.get("/api/status")
            self.assertEqual(200, status_response.status_code)
            self.assertEqual(config.APP_VERSION, status_response.json()["app_version"])
            self.assertIn(".mp4", status_response.json()["supported_formats"])

            queue_response = client.get("/api/queue/status")
            self.assertEqual(200, queue_response.status_code)
            self.assertEqual("empty", queue_response.json()["status"])
            self.assertIn("progress_percent", queue_response.json())


if __name__ == "__main__":
    unittest.main()
