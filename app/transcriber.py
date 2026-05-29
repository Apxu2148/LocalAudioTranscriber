import logging
import os
import shutil
import site
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from . import config
from .utils import audio_duration_seconds, format_segment_time


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: list[dict]
    audio_duration_sec: float | None
    transcribe_time_sec: float
    realtime_factor: float | None
    model: str
    device: str
    compute_type: str
    load_errors: list[str] = field(default_factory=list)


class AudioTranscriber:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_lock = threading.Lock()
        self._transcribe_lock = threading.Lock()
        self._runtime_device: str | None = None
        self._runtime_compute_type: str | None = None
        self._load_errors: list[str] = []
        self._dll_paths_added: list[str] = []

    def status(self) -> dict:
        return {
            "model": config.WHISPER_MODEL,
            "configured_device": config.WHISPER_DEVICE,
            "configured_compute_type": config.WHISPER_COMPUTE_TYPE,
            "runtime_device": self._runtime_device,
            "runtime_compute_type": self._runtime_compute_type,
            "model_loaded": self._model is not None,
            "cuda_device_count": self._cuda_device_count(),
            "cuda_dll_paths_added": self._dll_paths_added,
            "last_load_errors": self._load_errors,
            "ffmpeg_found": shutil.which("ffmpeg") is not None,
        }

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if not audio_path.exists():
            raise RuntimeError("Файл не найден.")

        suffix = audio_path.suffix.lower()
        if suffix not in config.SUPPORTED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
            raise RuntimeError(f"Формат {suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")

        self._check_ffmpeg()
        audio_duration = audio_duration_seconds(audio_path)
        model = self._get_model()

        logger.info(
            "Starting transcription: file=%s model=%s device=%s compute_type=%s duration=%s",
            audio_path,
            config.WHISPER_MODEL,
            self._runtime_device,
            self._runtime_compute_type,
            audio_duration,
        )

        started_at = time.perf_counter()

        try:
            kwargs = {
                "beam_size": config.WHISPER_BEAM_SIZE,
                "vad_filter": config.WHISPER_VAD_FILTER,
                "condition_on_previous_text": config.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            }
            if config.WHISPER_LANGUAGE:
                kwargs["language"] = config.WHISPER_LANGUAGE

            with self._transcribe_lock:
                segments_iter, _info = model.transcribe(str(audio_path), **kwargs)
                segments = list(segments_iter)
        except MemoryError as exc:
            logger.exception("Transcription failed: not enough memory")
            raise RuntimeError(
                "Не хватает памяти для модели Whisper small. Освободите память или вручную измените настройки модели/compute_type."
            ) from exc
        except Exception as exc:
            message = str(exc)
            if "out of memory" in message.lower() or "not enough memory" in message.lower():
                logger.exception("Transcription failed: out of memory")
                raise RuntimeError(
                    "Не хватает памяти для модели Whisper small. Освободите память или вручную измените настройки модели/compute_type."
                ) from exc
            logger.exception("Transcription failed")
            raise RuntimeError(f"Ошибка транскрибации: {message}") from exc

        transcribe_time = time.perf_counter() - started_at
        realtime_factor = audio_duration / transcribe_time if audio_duration and transcribe_time > 0 else None
        structured_segments: list[dict] = []
        lines: list[str] = []

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue

            start = format_segment_time(segment.start)
            end = format_segment_time(segment.end)
            lines.append(f"[{start} - {end}] {text}")
            structured_segments.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                }
            )

        logger.info(
            "Transcription finished: file=%s duration=%s time=%.3fs realtime_factor=%s device=%s compute_type=%s",
            audio_path,
            audio_duration,
            transcribe_time,
            realtime_factor,
            self._runtime_device,
            self._runtime_compute_type,
        )

        return TranscriptionResult(
            text="\n".join(lines).strip(),
            segments=structured_segments,
            audio_duration_sec=audio_duration,
            transcribe_time_sec=transcribe_time,
            realtime_factor=realtime_factor,
            model=config.WHISPER_MODEL,
            device=self._runtime_device or "unknown",
            compute_type=self._runtime_compute_type or "unknown",
            load_errors=list(self._load_errors),
        )

    def _get_model(self) -> WhisperModel:
        with self._model_lock:
            if self._model is not None:
                return self._model

            self._configure_cuda_dll_paths()
            self._load_errors = []

            requested_device = config.WHISPER_DEVICE.strip().lower()
            requested_compute = config.WHISPER_COMPUTE_TYPE.strip().lower()

            if requested_device in {"auto", "cuda"}:
                cuda_count = self._cuda_device_count()
                if cuda_count > 0:
                    cuda_compute_types = (
                        [requested_compute]
                        if requested_compute != "auto"
                        else list(config.GPU_COMPUTE_TYPE_CANDIDATES)
                    )

                    for compute_type in cuda_compute_types:
                        model = self._try_load_model("cuda", compute_type)
                        if model is not None:
                            return model
                else:
                    self._load_errors.append("CUDA devices were not reported by CTranslate2.")
                    logger.info("CUDA is not available according to CTranslate2")

            if requested_device not in {"auto", "cuda", "cpu"}:
                self._load_errors.append(f"Unknown WHISPER_DEVICE={config.WHISPER_DEVICE}; falling back to CPU.")
                logger.warning("Unknown WHISPER_DEVICE=%s; falling back to CPU", config.WHISPER_DEVICE)

            cpu_compute_types = (
                [config.CPU_COMPUTE_TYPE]
                if requested_compute == "auto"
                else [requested_compute, config.CPU_COMPUTE_TYPE]
            )

            seen: set[str] = set()
            for compute_type in cpu_compute_types:
                if compute_type in seen:
                    continue
                seen.add(compute_type)
                model = self._try_load_model("cpu", compute_type)
                if model is not None:
                    return model

            details = " | ".join(self._load_errors) if self._load_errors else "unknown error"
            raise RuntimeError(f"Не удалось загрузить модель Whisper '{config.WHISPER_MODEL}': {details}")

    def _try_load_model(self, device: str, compute_type: str) -> WhisperModel | None:
        try:
            logger.info(
                "Loading Whisper model: model=%s device=%s compute_type=%s",
                config.WHISPER_MODEL,
                device,
                compute_type,
            )
            model = WhisperModel(
                config.WHISPER_MODEL,
                device=device,
                compute_type=compute_type,
                download_root=str(config.MODELS_DIR / "faster-whisper"),
            )
            self._model = model
            self._runtime_device = device
            self._runtime_compute_type = compute_type
            logger.info(
                "Whisper model loaded: model=%s device=%s compute_type=%s",
                config.WHISPER_MODEL,
                device,
                compute_type,
            )
            return model
        except MemoryError as exc:
            message = f"{device}/{compute_type}: not enough memory"
            self._load_errors.append(message)
            logger.exception("Failed to load Whisper model: %s", message)
            return None
        except Exception as exc:
            message = f"{device}/{compute_type}: {exc}"
            self._load_errors.append(message)
            if device == "cuda":
                logger.warning("CUDA load failed; will try fallback if available: %s", message)
            else:
                logger.exception("CPU load failed: %s", message)
            return None

    def _configure_cuda_dll_paths(self) -> None:
        if self._dll_paths_added:
            return

        candidate_dirs = [
            config.BASE_DIR / ".venv" / "Lib" / "site-packages" / "torch" / "lib",
        ]

        for site_packages in site.getsitepackages():
            site_path = Path(site_packages)
            candidate_dirs.extend(site_path.glob("nvidia/*/bin"))
            candidate_dirs.extend(site_path.glob("nvidia/*/lib"))

        for directory in candidate_dirs:
            if not directory.exists():
                continue

            directory_text = str(directory)
            if directory_text not in os.environ.get("PATH", ""):
                os.environ["PATH"] = directory_text + os.pathsep + os.environ.get("PATH", "")

            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(directory_text)
                except OSError:
                    pass

            self._dll_paths_added.append(directory_text)
            logger.info("Added CUDA DLL search path: %s", directory_text)

    def _cuda_device_count(self) -> int:
        try:
            return int(ctranslate2.get_cuda_device_count())
        except Exception as exc:
            logger.warning("Could not query CUDA device count: %s", exc)
            return 0

    def _check_ffmpeg(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "ffmpeg не найден. Установите ffmpeg и добавьте его папку bin в PATH, затем перезапустите приложение."
            )
