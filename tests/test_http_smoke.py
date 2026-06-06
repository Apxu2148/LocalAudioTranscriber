import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import PropertyMock, patch

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

    def test_recording_queue_and_transcript_reader_are_path_constrained(self) -> None:
        with TemporaryDirectory(dir=PROJECT_TMP) as temp_dir:
            root = Path(temp_dir)
            recordings_dir = root / "recordings"
            transcripts_dir = root / "transcripts"
            recordings_dir.mkdir()
            transcripts_dir.mkdir()
            recording_path = recordings_dir / "mic.wav"
            missing_recording_path = recordings_dir / "missing.wav"
            transcript_path = transcripts_dir / "result.txt"
            non_txt_transcript_path = transcripts_dir / "result.json"
            outside_transcript_path = root / "outside.txt"
            recording_path.write_bytes(b"audio")
            transcript_path.write_text("recognized text", encoding="utf-8")
            non_txt_transcript_path.write_text("{}", encoding="utf-8")
            outside_transcript_path.write_text("private text", encoding="utf-8")

            with (
                patch.object(config, "RECORDINGS_DIR", recordings_dir),
                patch.object(config, "TRANSCRIPTS_DIR", transcripts_dir),
                patch.object(main_module.queue_manager, "add_files", return_value={"status": "pending"}) as add_files,
                TestClient(main_module.app) as client,
            ):
                response = client.post(
                    "/api/queue/add-recordings",
                    json={"files": [{"file_path": str(recording_path), "source_type": "mic"}]},
                )
                self.assertEqual(200, response.status_code)
                queued_file = add_files.call_args.args[0][0]
                self.assertEqual(recording_path, queued_file.source_path)
                self.assertEqual("mic", queued_file.source_type)

                rejected_recording = client.post(
                    "/api/queue/add-recordings",
                    json={"files": [{"file_path": str(outside_transcript_path), "source_type": "mic"}]},
                )
                self.assertEqual(400, rejected_recording.status_code)
                missing_recording = client.post(
                    "/api/queue/add-recordings",
                    json={"files": [{"file_path": str(missing_recording_path), "source_type": "mic"}]},
                )
                self.assertEqual(400, missing_recording.status_code)
                rejected_source_type = client.post(
                    "/api/queue/add-recordings",
                    json={"files": [{"file_path": str(recording_path), "source_type": "browser"}]},
                )
                self.assertEqual(400, rejected_source_type.status_code)

                read_response = client.get("/api/transcripts/read", params={"file_path": "result.txt"})
                self.assertEqual(200, read_response.status_code)
                self.assertEqual("recognized text", read_response.json()["text"])

                rejected_absolute = client.get("/api/transcripts/read", params={"file_path": str(transcript_path)})
                self.assertEqual(400, rejected_absolute.status_code)
                rejected_read = client.get("/api/transcripts/read", params={"file_path": str(outside_transcript_path)})
                self.assertEqual(400, rejected_read.status_code)
                rejected_non_txt = client.get("/api/transcripts/read", params={"file_path": non_txt_transcript_path.name})
                self.assertEqual(400, rejected_non_txt.status_code)
                rejected_traversal = client.get("/api/transcripts/read", params={"file_path": "../outside.txt"})
                self.assertEqual(400, rejected_traversal.status_code)

    def test_runtime_switch_endpoints_reject_inactive_tracks(self) -> None:
        with TestClient(main_module.app) as client:
            mic_response = client.post("/api/record/switch-microphone", json={"device_id": 1})
            self.assertEqual(400, mic_response.status_code)
            output_response = client.post("/api/record/switch-output-device", json={"output_device_id": "speaker"})
            self.assertEqual(400, output_response.status_code)

    def test_runtime_switch_endpoints_delegate_to_recorders(self) -> None:
        with (
            patch.object(type(main_module.recorder), "is_recording", new_callable=PropertyMock, return_value=True),
            patch.object(
                type(main_module.system_recorder),
                "is_recording",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                main_module.recorder,
                "switch_input_device",
                return_value={"track": "mic", "device_id": 2, "device_name": "Mic 2"},
            ) as switch_mic,
            patch.object(
                main_module.system_recorder,
                "switch_output_device",
                return_value={"track": "system", "output_device_id": "speaker-2", "output_device_name": "Speaker 2"},
            ) as switch_output,
            TestClient(main_module.app) as client,
        ):
            mic_response = client.post("/api/record/switch-microphone", json={"device_id": 2})
            self.assertEqual(200, mic_response.status_code)
            self.assertEqual("mic", mic_response.json()["track"])
            switch_mic.assert_called_once_with(2)

            output_response = client.post(
                "/api/record/switch-output-device",
                json={"output_device_id": "speaker-2"},
            )
            self.assertEqual(200, output_response.status_code)
            self.assertEqual("system", output_response.json()["track"])
            switch_output.assert_called_once_with("speaker-2")

    def test_runtime_switch_endpoint_reports_backend_failure(self) -> None:
        with (
            patch.object(type(main_module.recorder), "is_recording", new_callable=PropertyMock, return_value=True),
            patch.object(main_module.recorder, "switch_input_device", side_effect=RuntimeError("device busy")),
            TestClient(main_module.app) as client,
        ):
            response = client.post("/api/record/switch-microphone", json={"device_id": 2})
            self.assertEqual(500, response.status_code)
            self.assertIn("device busy", response.json()["detail"]["message"])

    def test_direct_transcription_routes_remain_available(self) -> None:
        paths = {route.path for route in main_module.app.routes}
        self.assertIn("/api/transcribe", paths)
        self.assertIn("/api/transcribe/file", paths)


if __name__ == "__main__":
    unittest.main()
