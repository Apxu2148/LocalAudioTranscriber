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


class ModelLoadError(RuntimeError):
    def __init__(self, model_name: str, technical_details: str) -> None:
        self.model_name = model_name
        self.technical_details = technical_details
        self.user_message = (
            f"Не удалось загрузить модель {model_name}.\n\n"
            "Вероятная причина: модель еще не скачана локально, а приложение не смогло подключиться "
            "к Hugging Face для первой загрузки.\n\n"
            "Что можно сделать:\n"
            "1. Проверьте интернет.\n"
            "2. Проверьте, не блокирует ли доступ антивирус, firewall, VPN или корпоративная сеть.\n"
            "3. Попробуйте снова позже.\n"
            "4. Выберите модель small, если она уже скачана локально.\n"
            "5. При необходимости заранее скачайте модель на компьютере с доступом к интернету."
        )
        super().__init__(self.user_message)


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
    model_load_time_sec: float = 0
    transcription_time_sec: float = 0
    load_errors: list[str] = field(default_factory=list)


class AudioTranscriber:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_name: str | None = None
        self._model_device_preference: str | None = None
        self._model_lock = threading.Lock()
        self._transcribe_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._runtime_device: str | None = None
        self._runtime_compute_type: str | None = None
        self._load_errors: list[str] = []
        self._dll_paths_added: list[str] = []
        self._is_transcribing = False
        self._active_model: str | None = None
        self._phase: str | None = None
        self._last_error: str | None = None

    def status(self) -> dict:
        with self._state_lock:
            is_transcribing = self._is_transcribing
            active_model = self._active_model
            phase = self._phase
            last_error = self._last_error

        return {
            "default_model": config.WHISPER_MODEL,
            "supported_models": list(config.SUPPORTED_WHISPER_MODELS),
            "loaded_model": self._model_name,
            "active_model": active_model,
            "phase": phase,
            "configured_device": config.WHISPER_DEVICE,
            "configured_compute_type": config.WHISPER_COMPUTE_TYPE,
            "runtime_device": self._runtime_device,
            "runtime_compute_type": self._runtime_compute_type,
            "model_loaded": self._model is not None,
            "in_progress": is_transcribing,
            "cuda_device_count": self._cuda_device_count(),
            "cuda_available": self._cuda_device_count() > 0,
            "auto_resolved_device": "cuda" if self._cuda_device_count() > 0 else "cpu",
            "cuda_dll_paths_added": self._dll_paths_added,
            "last_load_errors": self._load_errors,
            "last_error": last_error,
            "ffmpeg_found": shutil.which("ffmpeg") is not None,
        }

    def transcribe(
        self,
        audio_path: Path,
        model_name: str | None = None,
        device_preference: str | None = None,
    ) -> TranscriptionResult:
        selected_model = self._normalize_model_name(model_name)
        selected_device = self._normalize_device_preference(device_preference)

        if not audio_path.exists():
            raise RuntimeError("Файл не найден.")

        suffix = audio_path.suffix.lower()
        if suffix not in config.SUPPORTED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
            raise RuntimeError(f"Формат {suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")

        with self._transcribe_lock:
            self._set_transcribing(True, selected_model, "preparing")
            started_at = time.perf_counter()

            try:
                self._check_ffmpeg()
                audio_duration = audio_duration_seconds(audio_path)
                self._set_phase("loading_model")
                model_load_started_at = time.perf_counter()
                model = self._get_model(selected_model, selected_device)
                model_load_time = time.perf_counter() - model_load_started_at
                self._set_phase("transcribing")
                transcription_started_at = time.perf_counter()

                logger.info(
                    "Starting transcription: file=%s model=%s device=%s compute_type=%s duration=%s",
                    audio_path,
                    selected_model,
                    self._runtime_device,
                    self._runtime_compute_type,
                    audio_duration,
                )

                kwargs = {
                    "beam_size": config.WHISPER_BEAM_SIZE,
                    "vad_filter": config.WHISPER_VAD_FILTER,
                    "condition_on_previous_text": config.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
                }
                if config.WHISPER_LANGUAGE:
                    kwargs["language"] = config.WHISPER_LANGUAGE

                segments_iter, _info = model.transcribe(str(audio_path), **kwargs)
                segments = list(segments_iter)
                transcription_time = time.perf_counter() - transcription_started_at
            except MemoryError as exc:
                message = self._memory_error_message(selected_model)
                logger.exception("Transcription failed: not enough memory")
                self._set_last_error(message)
                raise RuntimeError(message) from exc
            except RuntimeError as exc:
                self._set_last_error(str(exc))
                raise
            except Exception as exc:
                message = str(exc)
                if "out of memory" in message.lower() or "not enough memory" in message.lower():
                    friendly_message = self._memory_error_message(selected_model)
                    logger.exception("Transcription failed: out of memory")
                    self._set_last_error(friendly_message)
                    raise RuntimeError(friendly_message) from exc

                friendly_message = f"Ошибка транскрибации: {message}"
                logger.exception("Transcription failed")
                self._set_last_error(friendly_message)
                raise RuntimeError(friendly_message) from exc
            finally:
                self._set_transcribing(False, None, None)

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
            "Transcription finished: file=%s model=%s duration=%s time=%.3fs realtime_factor=%s device=%s compute_type=%s",
            audio_path,
            selected_model,
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
            model=selected_model,
            device=self._runtime_device or "unknown",
            compute_type=self._runtime_compute_type or "unknown",
            model_load_time_sec=model_load_time,
            transcription_time_sec=transcription_time,
            load_errors=list(self._load_errors),
        )

    def clear_model(self) -> None:
        with self._model_lock:
            self._reset_model_locked()

    def is_model_cached(self, model_name: str, device_preference: str) -> bool:
        with self._model_lock:
            return (
                self._model is not None
                and self._model_name == model_name
                and self._model_device_preference == device_preference
            )

    def _get_model(self, model_name: str, device_preference: str) -> WhisperModel:
        with self._model_lock:
            if (
                self._model is not None
                and self._model_name == model_name
                and self._model_device_preference == device_preference
            ):
                return self._model

            if self._model is not None:
                logger.info(
                    "Switching Whisper model: previous=%s/%s next=%s/%s",
                    self._model_name,
                    self._model_device_preference,
                    model_name,
                    device_preference,
                )
                self._reset_model_locked()

            self._configure_cuda_dll_paths()
            self._load_errors = []

            requested_device = device_preference
            requested_compute = config.WHISPER_COMPUTE_TYPE.strip().lower()
            cuda_attempted = False

            if requested_device in {"auto", "cuda"}:
                cuda_count = self._cuda_device_count()
                if cuda_count > 0:
                    cuda_compute_types = (
                        [requested_compute]
                        if requested_compute != "auto"
                        else list(config.GPU_COMPUTE_TYPE_CANDIDATES)
                    )

                    for compute_type in cuda_compute_types:
                        cuda_attempted = True
                        model = self._try_load_model(model_name, "cuda", compute_type, requested_device)
                        if model is not None:
                            return model
                else:
                    self._load_errors.append("CUDA devices were not reported by CTranslate2.")
                    logger.info("CUDA is not available according to CTranslate2")

            if requested_device == "cuda":
                details = " | ".join(self._load_errors) if self._load_errors else "CUDA is unavailable."
                raise RuntimeError(
                    "GPU/CUDA недоступна или модель не смогла загрузиться на GPU. "
                    "Выберите Авто или CPU. "
                    f"Технические подробности: {details}"
                )

            if cuda_attempted:
                logger.warning(
                    "CUDA model load failed or was unavailable; falling back to CPU: model=%s errors=%s",
                    model_name,
                    " | ".join(self._load_errors),
                )

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
                model = self._try_load_model(model_name, "cpu", compute_type, requested_device)
                if model is not None:
                    return model

            details = " | ".join(self._load_errors) if self._load_errors else "unknown error"
            logger.error("Whisper model load failed: model=%s details=%s", model_name, details)
            raise ModelLoadError(model_name, details)

    def _try_load_model(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        device_preference: str,
    ) -> WhisperModel | None:
        try:
            logger.info(
                "Loading Whisper model: model=%s device=%s compute_type=%s",
                model_name,
                device,
                compute_type,
            )
            model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(config.MODELS_DIR / "faster-whisper"),
            )
            self._model = model
            self._model_name = model_name
            self._model_device_preference = device_preference
            self._runtime_device = device
            self._runtime_compute_type = compute_type
            logger.info(
                "Whisper model loaded: model=%s device=%s compute_type=%s",
                model_name,
                device,
                compute_type,
            )
            return model
        except MemoryError:
            message = f"{device}/{compute_type}: not enough memory"
            self._load_errors.append(message)
            logger.exception("Failed to load Whisper model: model=%s %s", model_name, message)
            return None
        except Exception as exc:
            message = f"{device}/{compute_type}: {exc}"
            self._load_errors.append(message)
            if device == "cuda":
                logger.warning(
                    "CUDA load failed; CPU fallback will be tried if available: model=%s %s",
                    model_name,
                    message,
                    exc_info=True,
                )
            else:
                logger.exception("CPU load failed: model=%s %s", model_name, message)
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

    def _normalize_model_name(self, model_name: str | None) -> str:
        selected_model = (model_name or config.WHISPER_MODEL).strip()
        if selected_model not in config.SUPPORTED_WHISPER_MODELS:
            allowed = ", ".join(config.SUPPORTED_WHISPER_MODELS)
            raise RuntimeError(f"Модель Whisper '{selected_model}' не поддерживается в интерфейсе. Доступны: {allowed}.")
        return selected_model

    def _normalize_device_preference(self, device_preference: str | None) -> str:
        selected_device = (device_preference or config.WHISPER_DEVICE or "auto").strip().lower()
        if selected_device not in {"auto", "cpu", "cuda"}:
            raise RuntimeError("Устройство должно быть одним из значений: auto, cpu, cuda.")
        return selected_device

    def _memory_error_message(self, model_name: str) -> str:
        return (
            f"Не хватает памяти для модели Whisper '{model_name}'. "
            "Освободите память или выберите модель меньше, например small, base или tiny."
        )

    def _set_transcribing(self, value: bool, model_name: str | None, phase: str | None) -> None:
        with self._state_lock:
            self._is_transcribing = value
            self._active_model = model_name
            self._phase = phase
            if value:
                self._last_error = None

    def _set_phase(self, phase: str | None) -> None:
        with self._state_lock:
            self._phase = phase

    def _reset_model_locked(self) -> None:
        self._model = None
        self._model_name = None
        self._model_device_preference = None
        self._runtime_device = None
        self._runtime_compute_type = None

    def _set_last_error(self, message: str) -> None:
        with self._state_lock:
            self._last_error = message
