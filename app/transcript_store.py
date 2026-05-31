import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .utils import timestamp_for_filename, write_json_file, write_text_file


WINDOWS_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_SOURCE_STEM_LENGTH = 96


def safe_filename_part(value: str, *, max_length: int = MAX_SOURCE_STEM_LENGTH) -> str:
    cleaned = WINDOWS_INVALID_CHARS.sub("_", value.strip())
    cleaned = cleaned.rstrip(" .")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        cleaned = "file"

    if len(cleaned) <= max_length:
        return cleaned

    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[: max_length - len(digest) - 2].rstrip(' ._')}__{digest}"


def source_stem_for(source_filename: str) -> str:
    return safe_filename_part(Path(source_filename).stem)


def technical_details_for_exception(exc: Exception) -> str:
    details = getattr(exc, "technical_details", "")
    return str(details or exc)


class TranscriptStore:
    def __init__(self, transcripts_dir: Path | None = None) -> None:
        self.transcripts_dir = transcripts_dir or config.TRANSCRIPTS_DIR

    def save_success(
        self,
        *,
        source_path: Path,
        source_filename: str,
        source_type: str,
        result: Any,
    ) -> dict:
        transcript_path, json_path = self._reserve_paths(source_filename, result.model)
        transcript_text = result.text or "Распознаваемая речь не найдена."
        transcript_path.write_text(transcript_text, encoding="utf-8")

        payload = self._base_payload(
            source_path=source_path,
            source_filename=source_filename,
            source_type=source_type,
            transcript_path=transcript_path,
            model=result.model,
        )
        payload.update(
            {
                "device": result.device,
                "compute_type": result.compute_type,
                "audio_duration_sec": self._rounded(result.audio_duration_sec),
                "processing_time_sec": self._rounded(result.transcribe_time_sec),
                "transcribe_time_sec": self._rounded(result.transcribe_time_sec),
                "realtime_factor": self._rounded(result.realtime_factor),
                "segments_count": len(result.segments),
                "load_errors": result.load_errors,
                "status": "completed",
            }
        )
        write_json_file(json_path, payload)

        return {
            "text": transcript_text,
            "segments": result.segments,
            "transcript_path": str(transcript_path),
            "json_path": str(json_path),
            "benchmark_path": str(json_path),
            "benchmark": {
                "transcript_file": str(transcript_path),
                "audio_file": str(source_path),
                "source_audio": str(source_path),
                "model": result.model,
                "device": result.device,
                "compute_type": result.compute_type,
                "audio_duration_sec": payload["audio_duration_sec"],
                "transcribe_time_sec": payload["processing_time_sec"],
                "processing_time_sec": payload["processing_time_sec"],
                "realtime_factor": payload["realtime_factor"],
                "segments_count": payload["segments_count"],
                "load_errors": result.load_errors,
            },
            "audio_duration_sec": payload["audio_duration_sec"],
            "processing_time_sec": payload["processing_time_sec"],
            "realtime_factor": payload["realtime_factor"],
            "device": result.device,
            "compute_type": result.compute_type,
        }

    def save_error(
        self,
        *,
        source_path: Path,
        source_filename: str,
        source_type: str,
        model: str,
        error_message: str,
        technical_details: str = "",
    ) -> dict:
        transcript_path, json_path = self._reserve_paths(source_filename, model)
        payload = self._base_payload(
            source_path=source_path,
            source_filename=source_filename,
            source_type=source_type,
            transcript_path=transcript_path,
            model=model,
        )
        payload.update(
            {
                "status": "error",
                "error_message": error_message,
                "technical_details": technical_details,
            }
        )
        write_json_file(json_path, payload)
        return {
            "transcript_path": None,
            "json_path": str(json_path),
            "benchmark_path": str(json_path),
        }

    def _reserve_paths(self, source_filename: str, model: str) -> tuple[Path, Path]:
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timestamp_for_filename()
        stem = source_stem_for(source_filename)
        safe_model = safe_filename_part(model, max_length=32)
        prefix = f"{stem}__{timestamp}__{safe_model}__transcript"

        counter = 1
        while True:
            suffix = "" if counter == 1 else f"__{counter}"
            transcript_path = self.transcripts_dir / f"{prefix}{suffix}.txt"
            json_path = transcript_path.with_suffix(".json")
            if not transcript_path.exists() and not json_path.exists():
                return transcript_path, json_path
            counter += 1

    @staticmethod
    def _rounded(value: float | None) -> float | None:
        return round(value, 3) if value is not None else None

    @staticmethod
    def _base_payload(
        *,
        source_path: Path,
        source_filename: str,
        source_type: str,
        transcript_path: Path,
        model: str,
    ) -> dict:
        return {
            "source_type": source_type,
            "source_path": str(source_path),
            "source_filename": source_filename,
            "source_stem": source_stem_for(source_filename),
            "transcript_path": str(transcript_path),
            "model": model,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
