import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.queue_manager import QueueFile, QueueManager, QueueUrl


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"


class QueueManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefix = f"codex_queue_manager_{uuid4().hex}"
        self.created_paths: list[Path] = []
        self.managers: list[QueueManager] = []
        self.timestamp_patch = patch("app.queue_manager.timestamp_for_filename", return_value=self.prefix)
        self.timestamp_patch.start()

    def tearDown(self) -> None:
        for manager in self.managers:
            manager.wait(timeout=1)
        self.timestamp_patch.stop()
        paths = set(self.created_paths)
        paths.update(PROJECT_TMP.glob(f"*{self.prefix}*"))
        for path in paths:
            path.unlink(missing_ok=True)

    def make_file(self, name: str) -> QueueFile:
        path = PROJECT_TMP / f"{self.prefix}__{name}"
        path.write_bytes(b"test")
        self.created_paths.append(path)
        return QueueFile(source_path=path, source_filename=name)

    def make_manager(self, **kwargs) -> QueueManager:
        manager = QueueManager(jobs_dir=PROJECT_TMP, **kwargs)
        self.managers.append(manager)
        return manager

    def track_job(self, status: dict) -> dict:
        self.created_paths.append(Path(status["job_path"]))
        return status

    def test_processes_files_sequentially_and_persists_job_json(self) -> None:
        processed: list[str] = []

        def processor(item: dict, _model: str, _device: str) -> dict:
            processed.append(item["source_filename"])
            return {
                "audio_duration_sec": 10,
                "processing_time_sec": 2,
                "realtime_factor": 5,
                "transcript_path": f"{item['source_path']}.txt",
                "json_path": f"{item['source_path']}.json",
            }

        manager = self.make_manager(
            processor=processor,
            duration_reader=lambda _path: 10,
        )
        status = self.track_job(manager.add_files([self.make_file("one.wav"), self.make_file("two.wav")]))
        job_path = Path(status["job_path"])
        manager.start("small", "cpu")
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)

        status = manager.status()
        self.assertEqual(["one.wav", "two.wav"], processed)
        self.assertEqual("completed", status["status"])
        self.assertEqual(2, status["completed_items"])
        self.assertEqual(100, status["progress_percent"])
        self.assertTrue(job_path.exists())
        payload = json.loads(job_path.read_text(encoding="utf-8"))
        self.assertEqual("completed", payload["status"])
        self.assertEqual(["completed", "completed"], [item["status"] for item in payload["items"]])
        self.assertEqual("cpu", payload["device_preference"])

    def test_continues_after_error_and_retries_failed_items(self) -> None:
        attempts: list[str] = []
        should_fail = {"bad.wav"}

        def processor(item: dict, _model: str, _device: str) -> dict:
            attempts.append(item["source_filename"])
            if item["source_filename"] in should_fail:
                raise RuntimeError("expected failure")
            return {
                "audio_duration_sec": 4,
                "processing_time_sec": 1,
                "realtime_factor": 4,
                "transcript_path": f"{item['source_path']}.txt",
                "json_path": f"{item['source_path']}.json",
            }

        manager = self.make_manager(
            processor=processor,
            error_recorder=lambda item, _model, _device, _exc: {"json_path": f"{item['source_path']}.error.json"},
            duration_reader=lambda _path: 4,
        )
        self.track_job(manager.add_files([self.make_file("bad.wav"), self.make_file("good.wav")]))
        manager.start("small")
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)

        status = manager.status()
        self.assertEqual(["bad.wav", "good.wav"], attempts)
        self.assertEqual(1, status["failed_items"])
        self.assertEqual(1, status["completed_items"])
        self.assertTrue(status["items"][0]["json_path"].endswith(".error.json"))

        should_fail.clear()
        manager.retry_errors()
        manager.start("small")
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)
        status = manager.status()
        self.assertEqual("completed", status["status"])
        self.assertEqual(2, status["completed_items"])
        self.assertEqual(0, status["failed_items"])

    def test_stop_after_current_cancels_pending_items(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def processor(item: dict, _model: str, _device: str) -> dict:
            started.set()
            release.wait(timeout=3)
            return {
                "audio_duration_sec": 1,
                "processing_time_sec": 1,
                "realtime_factor": 1,
                "transcript_path": f"{item['source_path']}.txt",
                "json_path": f"{item['source_path']}.json",
            }

        manager = self.make_manager(
            processor=processor,
            duration_reader=lambda _path: 1,
        )
        self.track_job(manager.add_files([self.make_file("one.wav"), self.make_file("two.wav")]))
        manager.start("small")
        self.assertTrue(started.wait(timeout=2))
        manager.stop_after_current()
        release.set()
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)

        status = manager.status()
        self.assertEqual("cancelled", status["status"])
        self.assertEqual(["completed", "cancelled"], [item["status"] for item in status["items"]])

    def test_clear_removes_in_memory_queue_but_keeps_job_json(self) -> None:
        manager = self.make_manager(processor=lambda _item, _model, _device: {})
        status = self.track_job(manager.add_files([self.make_file("one.wav")]))
        job_path = Path(status["job_path"])
        manager.clear()

        self.assertTrue(job_path.exists())
        self.assertEqual("empty", manager.status()["status"])
        self.assertEqual([], manager.status()["items"])

    def test_mixed_queue_downloads_url_and_reuses_snapshot(self) -> None:
        downloaded = self.make_file("downloaded.m4a")
        calls: list[tuple[str, str, str]] = []

        def processor(item: dict, model: str, device: str) -> dict:
            calls.append((item["source_type"], model, device))
            return {
                "audio_duration_sec": 2,
                "processing_time_sec": 1,
                "realtime_factor": 2,
                "transcript_path": f"{item['source_path']}.txt",
                "json_path": f"{item['source_path']}.json",
            }

        manager = self.make_manager(
            processor=processor,
            downloader=lambda _url: {
                "source_path": str(downloaded.source_path),
                "source_title": "Public lesson",
                "source_platform": "youtube",
                "audio_duration_sec": 2,
            },
            duration_reader=lambda _path: 2,
        )
        self.track_job(manager.add_files([self.make_file("local.wav")]))
        manager.add_urls([QueueUrl("https://example.test/video")])
        manager.start("base", "cuda")
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)

        status = manager.status()
        self.assertEqual([("local_file", "base", "cuda"), ("url", "base", "cuda")], calls)
        self.assertEqual("youtube", status["items"][1]["source_platform"])
        self.assertEqual(str(downloaded.source_path), status["items"][1]["downloaded_audio_path"])

    def test_preserves_recording_source_type(self) -> None:
        manager = self.make_manager(processor=lambda _item, _model, _device: {})
        status = self.track_job(manager.add_files([
            QueueFile(
                source_path=self.make_file("mic.wav").source_path,
                source_filename="mic.wav",
                source_type="mic",
            )
        ]))
        self.assertEqual("mic", status["items"][0]["source_type"])

    def test_url_download_error_does_not_stop_queue(self) -> None:
        processed: list[str] = []

        def processor(item: dict, _model: str, _device: str) -> dict:
            processed.append(item["source_filename"])
            return {"processing_time_sec": 1}

        manager = self.make_manager(
            processor=processor,
            downloader=lambda _url: (_ for _ in ()).throw(RuntimeError("download failed")),
            duration_reader=lambda _path: 1,
        )
        self.track_job(manager.add_urls([QueueUrl("https://example.test/bad")]))
        manager.add_files([self.make_file("good.wav")])
        manager.start("small", "auto")
        manager.wait(timeout=3)
        self.assertFalse(manager.is_running)
        status = manager.status()
        self.assertEqual(1, status["failed_items"])
        self.assertEqual(1, status["completed_items"])
        self.assertEqual(["good.wav"], processed)


if __name__ == "__main__":
    unittest.main()
