import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from . import config
from .utils import timestamp_for_filename


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadedAudio:
    source_path: Path
    source_title: str | None
    source_platform: str
    audio_duration_sec: float | None

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["source_path"] = str(self.source_path)
        payload["downloaded_audio_path"] = str(self.source_path)
        return payload


class UrlDownloader:
    def __init__(self, downloads_dir: Path | None = None) -> None:
        self.downloads_dir = downloads_dir or config.DOWNLOADS_DIR

    def download(self, source_url: str) -> dict:
        url = self._validate_url(source_url)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"url__{timestamp_for_filename()}__{uuid4().hex[:8]}"
        output_template = str(self.downloads_dir / f"{prefix}.%(ext)s")

        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError(
                "Не найден yt-dlp. Установите зависимости из requirements-cpu.txt и перезапустите run.bat."
            ) from exc

        options = {
            "format": "m4a/bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 15,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
        }

        logger.info("Downloading URL audio: url=%s output=%s", url, output_template)
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                prepared_path = Path(downloader.prepare_filename(info))
        except Exception as exc:
            logger.exception("URL audio download failed: url=%s", url)
            raise RuntimeError(f"Не удалось скачать аудио по ссылке: {exc}") from exc

        source_path = self._find_downloaded_audio(prefix, prepared_path)
        if source_path is None:
            raise RuntimeError("yt-dlp завершил работу, но извлеченный аудиофайл не найден.")

        result = DownloadedAudio(
            source_path=source_path,
            source_title=self._optional_text(info.get("title")),
            source_platform=self._platform(info),
            audio_duration_sec=self._optional_float(info.get("duration")),
        )
        logger.info(
            "URL audio downloaded: url=%s file=%s platform=%s title=%s duration=%s",
            url,
            result.source_path,
            result.source_platform,
            result.source_title,
            result.audio_duration_sec,
        )
        return result.as_dict()

    def _find_downloaded_audio(self, prefix: str, prepared_path: Path) -> Path | None:
        candidates = [
            prepared_path.with_suffix(".m4a"),
            prepared_path,
        ]
        candidates.extend(sorted(self.downloads_dir.glob(f"{prefix}.*")))
        return next((path for path in candidates if path.exists() and path.is_file()), None)

    @staticmethod
    def _validate_url(source_url: str) -> str:
        url = (source_url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("Укажите корректную публичную HTTP(S)-ссылку.")
        if parsed.username or parsed.password:
            raise RuntimeError("Ссылки со встроенной авторизацией не поддерживаются.")
        return url

    @staticmethod
    def _platform(info: dict) -> str:
        extractor = str(info.get("extractor_key") or info.get("extractor") or "unknown").lower()
        if "youtube" in extractor:
            return "youtube"
        if "rutube" in extractor:
            return "rutube"
        if extractor == "vk" or "vkontakte" in extractor:
            return "vk"
        return extractor or "unknown"

    @staticmethod
    def _optional_text(value) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _optional_float(value) -> float | None:
        try:
            return round(float(value), 3) if value is not None else None
        except (TypeError, ValueError):
            return None
