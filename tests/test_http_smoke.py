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
            for url in ["/", "/static/app.js", "/static/style.css", "/static/tour.js", "/static/i18n.js"]:
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

    def test_new_queue_benchmark_and_storage_endpoints_are_lightweight(self) -> None:
        fake_transcriber_status = {"in_progress": False}
        with (
            patch.object(main_module.queue_manager, "add_urls", return_value={"status": "pending"}) as add_urls,
            patch.object(main_module.queue_manager, "start", return_value={"status": "running"}) as start_queue,
            patch.object(main_module.benchmark_service, "status", return_value={"status": "idle", "running": False}),
            patch.object(main_module.benchmark_service, "start", return_value={"status": "running"}) as start_benchmark,
            patch.object(main_module.transcriber, "status", return_value=fake_transcriber_status),
            TestClient(main_module.app) as client,
        ):
            add_response = client.post("/api/queue/add-urls", json={"urls": ["https://example.test/video"]})
            self.assertEqual(200, add_response.status_code)
            self.assertEqual("https://example.test/video", add_urls.call_args.args[0][0].source_url)

            queue_response = client.post("/api/queue/start", json={"model": "small", "device": "cpu"})
            self.assertEqual(200, queue_response.status_code)
            start_queue.assert_called_once_with("small", "cpu")

            benchmark_response = client.post(
                "/api/benchmark/run",
                json={"source_id": "prepared", "model": "small", "device": "cpu", "mode": "cold"},
            )
            self.assertEqual(200, benchmark_response.status_code)
            self.assertEqual("cpu", start_benchmark.call_args.kwargs["device"])

            self.assertEqual(200, client.get("/api/benchmark/status").status_code)
            storage_payload = client.get("/api/storage").json()
            self.assertIn("free_gb", storage_payload["disk"])


if __name__ == "__main__":
    unittest.main()
