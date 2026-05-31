import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.url_downloader import UrlDownloader


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"


class FakeYoutubeDL:
    last_options = None

    def __init__(self, options: dict) -> None:
        self.options = options
        FakeYoutubeDL.last_options = options
        self.path = Path(options["outtmpl"].replace("%(ext)s", "m4a"))

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def extract_info(self, _url: str, download: bool) -> dict:
        self.path.write_bytes(b"audio")
        return {"title": "Public lesson", "extractor_key": "Youtube", "duration": 12, "ext": "m4a"}

    def prepare_filename(self, _info: dict) -> str:
        return str(self.path)


class UrlDownloaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefix = f"codex_url_downloader_{uuid4().hex}"
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in PROJECT_TMP.glob(f"{self.prefix}*"):
            path.unlink(missing_ok=True)

    def test_download_uses_audio_only_options_and_returns_metadata(self) -> None:
        fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        downloader = UrlDownloader(PROJECT_TMP)
        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("app.url_downloader.timestamp_for_filename", return_value=self.prefix):
                result = downloader.download("https://example.test/public-video")

        self.assertEqual("Public lesson", result["source_title"])
        self.assertEqual("youtube", result["source_platform"])
        self.assertTrue(Path(result["source_path"]).exists())
        self.assertEqual("m4a/bestaudio/best", FakeYoutubeDL.last_options["format"])
        self.assertTrue(FakeYoutubeDL.last_options["noplaylist"])
        self.assertEqual("m4a", FakeYoutubeDL.last_options["postprocessors"][0]["preferredcodec"])

    def test_rejects_non_http_url(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "HTTP"):
            UrlDownloader(PROJECT_TMP).download("file:///private/audio.wav")


if __name__ == "__main__":
    unittest.main()
