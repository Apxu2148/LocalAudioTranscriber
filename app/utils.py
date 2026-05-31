from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from uuid import uuid4

import numpy as np
import soundfile as sf

from . import config


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_segment_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def write_text_file(directory: Path, prefix: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{prefix}_{timestamp_for_filename()}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def write_json_file(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_json_file_atomic(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        for attempt in range(3):
            try:
                temp_path.replace(path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.05)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return path


def compute_audio_levels(audio: np.ndarray) -> tuple[float, float]:
    if audio.size == 0:
        return 0.0, 0.0

    samples = np.asarray(audio, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak = float(np.max(np.abs(samples)))
    return rms, peak


def audio_duration_seconds(audio_path: Path) -> float | None:
    try:
        info = sf.info(str(audio_path))
        if info.frames and info.samplerate:
            return float(info.frames / info.samplerate)
    except Exception:
        pass

    try:
        import av

        with av.open(str(audio_path)) as container:
            if container.duration:
                return float(container.duration / av.time_base)

            audio_streams = [stream for stream in container.streams if stream.type == "audio"]
            if audio_streams and audio_streams[0].duration and audio_streams[0].time_base:
                return float(audio_streams[0].duration * audio_streams[0].time_base)
    except Exception:
        return None

    return None


def validate_media_for_transcription(media_path: Path) -> None:
    if media_path.suffix.lower() != ".mp4":
        return

    try:
        import av

        with av.open(str(media_path)) as container:
            if not any(stream.type == "audio" for stream in container.streams):
                raise RuntimeError("В видеофайле не найдена аудиодорожка.")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Не удалось прочитать видеофайл: {exc}") from exc


def setup_logging() -> None:
    root_logger = logging.getLogger()
    if any(getattr(handler, "_local_audio_transcriber", False) for handler in root_logger.handlers):
        return

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.LOGS_DIR / "app.log"

    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler._local_audio_transcriber = True
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
