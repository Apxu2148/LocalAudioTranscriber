import shutil
import subprocess
import unittest
from pathlib import Path
from uuid import uuid4

from app.utils import audio_duration_seconds, validate_media_for_transcription


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for MP4 fixture generation")
class MediaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefix = f"codex_media_validation_{uuid4().hex}"
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in reversed(self.created_paths):
            path.unlink(missing_ok=True)

    def create_path(self, name: str) -> Path:
        path = PROJECT_TMP / f"{self.prefix}__{name}"
        self.created_paths.append(path)
        return path

    def run_ffmpeg(self, *args: str) -> None:
        subprocess.run(
            [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
            check=True,
            timeout=5,
        )

    def test_accepts_mp4_with_audio_track(self) -> None:
        path = self.create_path("with_audio.mp4")
        self.run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=1000:duration=0.2", "-c:a", "aac", str(path))
        validate_media_for_transcription(path)

    def test_rejects_mp4_without_audio_track(self) -> None:
        path = self.create_path("without_audio.mp4")
        self.run_ffmpeg("-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.2", "-c:v", "mpeg4", str(path))
        with self.assertRaisesRegex(RuntimeError, "В видеофайле не найдена аудиодорожка"):
            validate_media_for_transcription(path)

    def test_reads_short_mp3_fixture_duration(self) -> None:
        path = self.create_path("short.mp3")
        self.run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", str(path))
        self.assertGreater(audio_duration_seconds(path) or 0, 0)


if __name__ == "__main__":
    unittest.main()
