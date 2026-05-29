import logging
import ctypes
import os
import threading
import time
from typing import Any

import numpy as np
import soundcard as sc
import soundfile as sf

from . import config
from .utils import compute_audio_levels, timestamp_for_filename, write_json_file


logger = logging.getLogger(__name__)


class SystemAudioRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._error: str | None = None

        self._output_path = None
        self._output_device_id: str | None = None
        self._output_device_name = ""
        self._sample_rate = config.SYSTEM_SAMPLE_RATE
        self._channels = config.SYSTEM_CHANNELS
        self._started_at: float | None = None

        self._total_frames = 0
        self._total_samples = 0
        self._sum_squares = 0.0
        self._peak = 0.0
        self._latest_rms = 0.0
        self._latest_peak = 0.0
        self._signal_seen_at: float | None = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def list_output_devices(self) -> dict:
        try:
            ensure_com_initialized()
            default_speaker = sc.default_speaker()
            default_id = default_speaker.id if default_speaker else None
            devices = []

            for index, speaker in enumerate(sc.all_speakers()):
                devices.append(
                    {
                        "id": speaker.id,
                        "index": index,
                        "name": speaker.name,
                        "channels": int(speaker.channels or 0),
                        "default_samplerate": config.SYSTEM_SAMPLE_RATE,
                        "is_default_output": speaker.id == default_id,
                        "hostapi": "Windows WASAPI",
                        "api_name": "WASAPI loopback",
                    }
                )
        except Exception as exc:
            logger.exception("Failed to list output devices")
            raise RuntimeError(f"Не удалось получить список устройств вывода: {exc}") from exc

        return {"default_output_device_id": default_id, "devices": devices}

    def output_status(self) -> dict:
        try:
            ensure_com_initialized()
            speaker = self._resolve_speaker(None)
            return {
                "available": True,
                "device_id": speaker.id,
                "device_name": speaker.name,
                "sample_rate": config.SYSTEM_SAMPLE_RATE,
                "channels": int(speaker.channels or config.SYSTEM_CHANNELS),
            }
        except RuntimeError as exc:
            return {"available": False, "message": str(exc)}

    def start(
        self,
        output_device_id: str | None = None,
        *,
        timestamp: str | None = None,
    ) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Запись системного звука уже идет.")

        ensure_com_initialized()
        speaker = self._resolve_speaker(output_device_id)
        channels = max(1, min(config.SYSTEM_CHANNELS, int(speaker.channels or config.SYSTEM_CHANNELS)))
        recording_timestamp = timestamp or timestamp_for_filename()
        output_path = config.RECORDINGS_DIR / f"system_{recording_timestamp}.wav"

        with self._lock:
            self._stop_event = threading.Event()
            self._started_event = threading.Event()
            self._error = None
            self._output_path = output_path
            self._output_device_id = speaker.id
            self._output_device_name = speaker.name
            self._sample_rate = config.SYSTEM_SAMPLE_RATE
            self._channels = channels
            self._started_at = time.perf_counter()
            self._total_frames = 0
            self._total_samples = 0
            self._sum_squares = 0.0
            self._peak = 0.0
            self._latest_rms = 0.0
            self._latest_peak = 0.0
            self._signal_seen_at = None

            self._thread = threading.Thread(
                target=self._record_loop,
                args=(speaker.id, output_path, config.SYSTEM_SAMPLE_RATE, channels),
                name="system-audio-recorder",
                daemon=True,
            )

        logger.info(
            "Starting system recording: output_device_id=%s output_device_name=%s sample_rate=%s channels=%s output=%s",
            speaker.id,
            speaker.name,
            config.SYSTEM_SAMPLE_RATE,
            channels,
            output_path,
        )

        self._thread.start()
        if not self._started_event.wait(timeout=5):
            error = self._error or "WASAPI loopback поток не запустился."
            self._stop_event.set()
            raise RuntimeError(error)

        with self._lock:
            if self._error:
                raise RuntimeError(self._error)

        return {
            "message": "Запись системного звука началась.",
            "recording": True,
            "source_type": "system",
            "file_path": str(output_path),
            "output_device_id": speaker.id,
            "output_device_name": speaker.name,
            "sample_rate": config.SYSTEM_SAMPLE_RATE,
            "channels": channels,
        }

    def stop(self) -> dict:
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                raise RuntimeError("Запись системного звука не запущена.")

        self._stop_event.set()
        thread.join(timeout=10)

        with self._lock:
            error = self._error
            output_path = self._output_path
            total_frames = self._total_frames
            total_samples = self._total_samples
            sum_squares = self._sum_squares
            peak = self._peak
            sample_rate = self._sample_rate
            channels = self._channels
            output_device_id = self._output_device_id
            output_device_name = self._output_device_name
            self._thread = None
            self._started_at = None

        if error:
            raise RuntimeError(error)

        if output_path is None or total_frames <= 0 or total_samples <= 0:
            raise RuntimeError("Системное аудио не записано. Проверьте output device и WASAPI loopback.")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("WAV-файл системного звука не был создан или оказался пустым.")

        rms = float(np.sqrt(sum_squares / total_samples)) if total_samples else 0.0
        duration_sec = float(total_frames / sample_rate) if sample_rate else 0.0
        file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 3)
        is_silence = rms < config.SILENCE_RMS_THRESHOLD and peak < config.SILENCE_PEAK_THRESHOLD
        warnings: list[str] = []

        if is_silence:
            warnings.append(
                "Системная запись похожа на тишину. Проверьте, что звук воспроизводится в Windows и выбрано правильное устройство вывода."
            )

        diagnostics = {
            "source_type": "system",
            "audio_file": str(output_path),
            "diagnostic_file": str(output_path.with_suffix(".json")),
            "output_device_id": output_device_id,
            "output_device_name": output_device_name,
            "sample_rate": sample_rate,
            "channels": channels,
            "duration_sec": round(duration_sec, 3),
            "file_size_mb": file_size_mb,
            "rms": round(rms, 6),
            "peak": round(float(peak), 6),
            "is_silence": is_silence,
            "warnings": warnings,
        }
        write_json_file(output_path.with_suffix(".json"), diagnostics)

        logger.info(
            "System recording stopped: file=%s duration=%.3fs rms=%.6f peak=%.6f silence=%s",
            output_path,
            duration_sec,
            rms,
            peak,
            is_silence,
        )

        return diagnostics

    def get_level(self) -> dict:
        with self._lock:
            started_at = self._started_at
            elapsed = time.perf_counter() - started_at if started_at is not None else 0.0
            no_signal_warning = (
                self._thread is not None
                and self._thread.is_alive()
                and elapsed >= config.SIGNAL_CHECK_SECONDS
                and self._signal_seen_at is None
            )
            warning = ""
            if no_signal_warning:
                warning = "За первые секунды системный звук не обнаружен. Проверьте воспроизведение и устройство вывода."

            return {
                "recording": self._thread is not None and self._thread.is_alive(),
                "rms": round(self._latest_rms, 6),
                "peak": round(self._latest_peak, 6),
                "level": self._level_percent(self._latest_peak),
                "elapsed_sec": round(elapsed, 2),
                "output_device_id": self._output_device_id,
                "output_device_name": self._output_device_name,
                "warning": warning,
            }

    def measure_output_level(self, output_device_id: str | None = None) -> dict:
        if self.is_recording:
            return self.get_level()

        ensure_com_initialized()
        speaker = self._resolve_speaker(output_device_id)
        channels = max(1, min(config.SYSTEM_CHANNELS, int(speaker.channels or config.SYSTEM_CHANNELS)))
        frames = max(1, int(config.SYSTEM_SAMPLE_RATE * config.LEVEL_PROBE_SECONDS))

        try:
            loopback = sc.get_microphone(id=speaker.id, include_loopback=True)
            with loopback.recorder(
                samplerate=config.SYSTEM_SAMPLE_RATE,
                channels=channels,
                blocksize=config.SYSTEM_RECORDING_BLOCKSIZE,
            ) as recorder:
                audio = recorder.record(numframes=frames)
        except Exception as exc:
            logger.exception("Failed to measure system audio level")
            raise RuntimeError(
                f"Не удалось проверить уровень системного звука. WASAPI loopback недоступен или устройство занято: {exc}"
            ) from exc

        rms, peak = compute_audio_levels(audio)
        warning = ""
        if rms < config.SILENCE_RMS_THRESHOLD and peak < config.SILENCE_PEAK_THRESHOLD:
            warning = "Системный звук очень низкий или отсутствует. Проверьте, что звук воспроизводится и выбрано правильное output-устройство."

        return {
            "recording": False,
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "level": self._level_percent(peak),
            "elapsed_sec": 0,
            "output_device_id": speaker.id,
            "output_device_name": speaker.name,
            "warning": warning,
        }

    def _record_loop(self, speaker_id: str, output_path, sample_rate: int, channels: int) -> None:
        try:
            ensure_com_initialized()
            loopback = sc.get_microphone(id=speaker_id, include_loopback=True)
            with sf.SoundFile(
                output_path,
                mode="w",
                samplerate=sample_rate,
                channels=channels,
                subtype="PCM_16",
            ) as audio_file:
                with loopback.recorder(
                    samplerate=sample_rate,
                    channels=channels,
                    blocksize=config.SYSTEM_RECORDING_BLOCKSIZE,
                ) as recorder:
                    self._started_event.set()
                    while not self._stop_event.is_set():
                        chunk = recorder.record(numframes=config.SYSTEM_RECORDING_BLOCKSIZE)
                        if chunk.size == 0:
                            continue

                        audio_file.write(chunk)
                        self._update_metrics(chunk)
        except Exception as exc:
            with self._lock:
                self._error = (
                    "Не удалось открыть или записать WASAPI loopback поток. "
                    f"Проверьте output device, частоту дискретизации и занятость устройства: {exc}"
                )
            logger.exception("System audio recorder failed")
            self._started_event.set()

    def _update_metrics(self, chunk) -> None:
        rms, peak = compute_audio_levels(chunk)
        sum_squares = float(np.sum(np.square(chunk, dtype=np.float64)))
        sample_count = int(chunk.size)
        frames = int(chunk.shape[0]) if len(chunk.shape) > 0 else 0

        with self._lock:
            self._latest_rms = rms
            self._latest_peak = peak
            self._total_frames += frames
            self._total_samples += sample_count
            self._sum_squares += sum_squares
            self._peak = max(self._peak, peak)
            if self._signal_seen_at is None and (
                rms >= config.SILENCE_RMS_THRESHOLD or peak >= config.SILENCE_PEAK_THRESHOLD
            ):
                self._signal_seen_at = time.perf_counter()

    def _resolve_speaker(self, output_device_id: str | None):
        try:
            ensure_com_initialized()
            if output_device_id:
                for speaker in sc.all_speakers():
                    if speaker.id == output_device_id:
                        return speaker
                raise RuntimeError("Выбранное output-устройство не найдено.")

            speaker = sc.default_speaker()
            if speaker is None:
                raise RuntimeError("Системное output-устройство не выбрано или не найдено.")
            return speaker
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"WASAPI loopback недоступен: {exc}") from exc

    def _level_percent(self, peak: float) -> int:
        return max(0, min(100, int(round(float(peak) * 100))))


def ensure_com_initialized() -> None:
    if os.name != "nt":
        return

    try:
        ctypes.windll.ole32.CoInitialize(None)
    except Exception:
        logger.debug("COM initialization failed or was already initialized", exc_info=True)
