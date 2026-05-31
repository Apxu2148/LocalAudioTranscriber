import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.transcript_store import TranscriptStore, safe_filename_part


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"


class TranscriptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefix = f"codex_transcript_store_{uuid4().hex}"
        self.created_paths: list[Path] = []
        self.store = TranscriptStore(PROJECT_TMP)

    def tearDown(self) -> None:
        paths = set(self.created_paths)
        paths.update(PROJECT_TMP.glob(f"*{self.prefix}*"))
        for path in paths:
            path.unlink(missing_ok=True)

    def create_source_file(self, name: str) -> Path:
        path = PROJECT_TMP / f"{self.prefix}__{name}"
        path.write_bytes(b"test")
        self.created_paths.append(path)
        return path

    def track_result(self, result: dict) -> dict:
        for key in ("transcript_path", "json_path"):
            if result.get(key):
                self.created_paths.append(Path(result[key]))
        return result

    def test_saves_source_related_unique_txt_and_json_names(self) -> None:
        source_path = self.create_source_file("uploaded.mp4")
        source_filename = f"{self.prefix}__lesson:01?.mp4"
        result = SimpleNamespace(
            text="recognized text",
            segments=[],
            model="small",
            device="cpu",
            compute_type="int8",
            audio_duration_sec=10.1234,
            transcribe_time_sec=2.3456,
            realtime_factor=4.321,
            load_errors=[],
        )

        first = self.track_result(self.store.save_success(
            source_path=source_path,
            source_filename=source_filename,
            source_type="local_file",
            result=result,
        ))
        second = self.track_result(self.store.save_success(
            source_path=source_path,
            source_filename=source_filename,
            source_type="local_file",
            result=result,
        ))

        first_path = Path(first["transcript_path"])
        second_path = Path(second["transcript_path"])
        self.assertRegex(
            first_path.name,
            rf"^{re.escape(self.prefix)}_lesson_01___\d{{8}}_\d{{6}}__small__transcript\.txt$",
        )
        self.assertNotEqual(first_path, second_path)
        payload = json.loads(Path(first["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual(source_filename, payload["source_filename"])
        self.assertEqual(f"{self.prefix}_lesson_01_", payload["source_stem"])
        self.assertEqual("completed", payload["status"])
        self.assertEqual(2.346, payload["processing_time_sec"])

    def test_error_json_is_saved_without_overwriting_existing_files(self) -> None:
        source_path = self.create_source_file("video.mp4")
        source_filename = f"{self.prefix}__video.mp4"
        first = self.track_result(self.store.save_error(
            source_path=source_path,
            source_filename=source_filename,
            source_type="local_file",
            model="small",
            error_message="В видеофайле не найдена аудиодорожка.",
        ))
        second = self.track_result(self.store.save_error(
            source_path=source_path,
            source_filename=source_filename,
            source_type="local_file",
            model="small",
            error_message="В видеофайле не найдена аудиодорожка.",
        ))
        self.assertNotEqual(first["json_path"], second["json_path"])
        payload = json.loads(Path(first["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual("error", payload["status"])

    def test_long_stem_is_shortened_readably(self) -> None:
        value = "lesson_" + "a" * 160
        cleaned = safe_filename_part(value)
        self.assertLessEqual(len(cleaned), 96)
        self.assertTrue(cleaned.startswith("lesson_"))


if __name__ == "__main__":
    unittest.main()
