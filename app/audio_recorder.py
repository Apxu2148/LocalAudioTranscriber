import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf

from . import config
from .utils import compute_audio_levels, timestamp_for_filename, write_json_file


logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._writer_queue: queue.Queue[np.ndarray | None] | None = None
        self._writer_thread: threading.Thread | None = None
        self._writer_error: str | None = None
        self._output_path: Path | None = None

        self._device_id: int | None = None
        self._device_name = ""
        self._sample_rate = config.DEFAULT_SAMPLE_RATE
        self._channels = config.DEFAULT_CHANNELS
        self._started_at: float | None = None
        self._last_status = ""
        self._dropped_chunks = 0

        self._total_frames = 0
        self._total_samples = 0
        self._sum_squares = 0.0
        self._peak = 0.0
        self._latest_rms = 0.0
        self._latest_peak = 0.0
        self._signal_seen_at: float | None = None
        self._device_switch_events: list[dict[str, Any]] = []

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._stream is not None

    def list_input_devices(self) -> dict:
        default_id = self._default_input_index()
        devices: list[dict[str, Any]] = []

        try:
            for index, device in enumerate(sd.query_devices()):
                input_channels = int(device.get("max_input_channels", 0))
                if input_channels < 1:
                    continue

                device_index = int(device.get("index", index))
                devices.append(
                    {
                        "id": device_index,
                        "index": device_index,
                        "name": str(device.get("name", f"Input device {device_index}")),
                        "input_channels": input_channels,
                        "default_samplerate": int(device.get("default_samplerate") or config.DEFAULT_SAMPLE_RATE),
                        "is_default": default_id is not None and device_index == default_id,
                    }
                )
        except Exception as exc:
            logger.exception("Failed to list input devices")
            raise RuntimeError(f"Не удалось получить список устройств записи: {exc}") from exc

        return {"default_device_id": default_id, "devices": devices}

    def microphone_status(self) -> dict:
        try:
            device_id, device_info = self._resolve_input_device(None)
            return {
                "available": True,
                "device_index": device_id,
                "device_name": device_info.get("name", "Default input"),
                "sample_rate": int(device_info.get("default_samplerate") or config.DEFAULT_SAMPLE_RATE),
            }
        except RuntimeError as exc:
            return {"available": False, "message": str(exc)}

    def start(
        self,
        device_id: int | str | None = None,
        *,
        filename_prefix: str = "recording",
        source_type: str = "mic",
        timestamp: str | None = None,
    ) -> dict:
        with self._lock:
            if self._stream is not None:
                raise RuntimeError("Запись уже идет.")

        resolved_device_id, device_info = self._resolve_input_device(device_id)
        sample_rate = int(device_info.get("default_samplerate") or config.DEFAULT_SAMPLE_RATE)
        channels = min(config.DEFAULT_CHANNELS, int(device_info.get("max_input_channels", 1)))
        channels = max(1, channels)
        recording_timestamp = timestamp or timestamp_for_filename()
        output_path = config.RECORDINGS_DIR / f"{filename_prefix}_{recording_timestamp}.wav"
        writer_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=512)
        writer_thread = threading.Thread(
            target=self._writer_loop,
            args=(output_path, sample_rate, channels, writer_queue),
            name="audio-writer",
            daemon=True,
        )

        with self._lock:
            self._writer_queue = writer_queue
            self._writer_thread = writer_thread
            self._writer_error = None
            self._output_path = output_path
            self._device_id = resolved_device_id
            self._device_name = str(device_info.get("name", "Default input"))
            self._sample_rate = sample_rate
            self._channels = channels
            self._started_at = time.perf_counter()
            self._last_status = ""
            self._dropped_chunks = 0
            self._total_frames = 0
            self._total_samples = 0
            self._sum_squares = 0.0
            self._peak = 0.0
            self._latest_rms = 0.0
            self._latest_peak = 0.0
            self._signal_seen_at = None
            self._device_switch_events = []

        logger.info(
            "Starting %s recording: device_id=%s device_name=%s sample_rate=%s channels=%s output=%s",
            source_type,
            resolved_device_id,
            device_info.get("name"),
            sample_rate,
            channels,
            output_path,
        )

        writer_thread.start()

        try:
            stream = sd.InputStream(
                device=resolved_device_id,
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                blocksize=config.RECORDING_BLOCKSIZE,
                callback=self._audio_callback,
            )
            stream.start()
        except Exception as exc:
            self._stop_writer()
            with self._lock:
                self._stream = None
                self._started_at = None
            logger.exception("Failed to start microphone recording stream")
            raise RuntimeError(
                f"Не удалось начать запись с микрофона. Проверьте выбранное устройство, разрешения Windows и антивирус: {exc}"
            ) from exc

        if not stream.active:
            self._stop_writer()
            with self._lock:
                self._stream = None
                self._started_at = None
            raise RuntimeError("Поток записи не запустился. Проверьте выбранный микрофон.")

        with self._lock:
            self._stream = stream

        return {
            "message": "Запись началась.",
            "recording": True,
            "source_type": source_type,
            "file_path": str(output_path),
            "device_id": resolved_device_id,
            "device_name": self._device_name,
            "sample_rate": sample_rate,
            "channels": channels,
        }

    def stop(self) -> dict:
        with self._lock:
            if self._stream is None:
                raise RuntimeError("Запись не запущена.")
            stream = self._stream

        try:
            stream.stop()
            stream.close()
        except Exception as exc:
            logger.exception("Failed to stop microphone recording stream")
            raise RuntimeError(f"Не удалось остановить запись: {exc}") from exc
        finally:
            with self._lock:
                self._stream = None

        self._stop_writer()

        with self._lock:
            writer_error = self._writer_error
            output_path = self._output_path
            total_frames = self._total_frames
            total_samples = self._total_samples
            sum_squares = self._sum_squares
            peak = self._peak
            sample_rate = self._sample_rate
            channels = self._channels
            device_id = self._device_id
            device_name = self._device_name
            last_status = self._last_status
            dropped_chunks = self._dropped_chunks
            device_switch_events = list(self._device_switch_events)
            self._started_at = None

        if writer_error:
            raise RuntimeError(f"Не удалось сохранить WAV-файл: {writer_error}")

        if output_path is None or total_frames <= 0 or total_samples <= 0:
            raise RuntimeError("Аудио не записано. Проверьте микрофон и попробуйте снова.")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("WAV-файл не был создан или оказался пустым.")

        rms = float(np.sqrt(sum_squares / total_samples)) if total_samples else 0.0
        duration_sec = float(total_frames / sample_rate) if sample_rate else 0.0
        file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 3)
        is_silence = self._is_silence(rms, peak)
        warnings: list[str] = []

        if is_silence:
            warnings.append("Запись похожа на тишину. Проверьте выбранный микрофон и уровень входного сигнала.")
        if dropped_chunks:
            warnings.append(f"Во время записи потеряно аудиоблоков: {dropped_chunks}.")
        if last_status:
            warnings.append(f"Статус аудиопотока: {last_status}.")

        diagnostics = {
            "source_type": "mic",
            "audio_file": str(output_path),
            "diagnostic_file": str(output_path.with_suffix(".json")),
            "device_id": device_id,
            "device_name": device_name,
            "input_device_id": device_id,
            "input_device_name": device_name,
            "sample_rate": sample_rate,
            "channels": channels,
            "duration_sec": round(duration_sec, 3),
            "file_size_mb": file_size_mb,
            "rms": round(rms, 6),
            "peak": round(float(peak), 6),
            "is_silence": is_silence,
            "warnings": warnings,
            "device_switch_events": device_switch_events,
        }
        write_json_file(output_path.with_suffix(".json"), diagnostics)

        logger.info(
            "Microphone recording stopped: file=%s duration=%.3fs rms=%.6f peak=%.6f silence=%s dropped_chunks=%s",
            output_path,
            duration_sec,
            rms,
            peak,
            is_silence,
            dropped_chunks,
        )

        return diagnostics

    def switch_input_device(self, device_id: int | str | None = None) -> dict:
        with self._lock:
            old_stream = self._stream
            if old_stream is None:
                raise RuntimeError("Запись микрофона не запущена.")
            previous_device = {
                "id": self._device_id,
                "name": self._device_name,
            }
            sample_rate = self._sample_rate
            channels = self._channels

        new_device = {
            "id": device_id,
            "name": "",
        }
        new_stream: sd.InputStream | None = None

        try:
            resolved_device_id, device_info = self._resolve_input_device(device_id)
            if int(device_info.get("max_input_channels", 0)) < channels:
                raise RuntimeError("Выбранный микрофон не поддерживает формат текущей записи.")

            new_device = {
                "id": resolved_device_id,
                "name": str(device_info.get("name", "Default input")),
            }
            new_stream = sd.InputStream(
                device=resolved_device_id,
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                blocksize=config.RECORDING_BLOCKSIZE,
                callback=self._audio_callback,
            )
            new_stream.start()
            if not new_stream.active:
                raise RuntimeError("Новый поток микрофона не запустился.")
        except Exception as exc:
            if new_stream is not None:
                try:
                    new_stream.stop()
                    new_stream.close()
                except Exception:
                    logger.debug("Failed to close failed microphone switch stream", exc_info=True)
            message = str(exc)
            self._record_device_switch_event("mic", previous_device, new_device, "error", message)
            logger.exception("Failed to switch microphone recording stream")
            raise RuntimeError(f"Не удалось переключить микрофон: {message}") from exc

        with self._lock:
            if self._stream is not old_stream:
                try:
                    new_stream.stop()
                    new_stream.close()
                except Exception:
                    logger.debug("Failed to close stale microphone switch stream", exc_info=True)
                message = "Текущий поток микрофона уже изменился."
                self._append_device_switch_event_locked(
                    self._device_switch_event("mic", previous_device, new_device, "error", message)
                )
                raise RuntimeError(message)

            self._stream = new_stream
            self._device_id = new_device["id"]
            self._device_name = str(new_device["name"])
            self._append_device_switch_event_locked(
                self._device_switch_event("mic", previous_device, new_device, "success")
            )

        try:
            old_stream.stop()
            old_stream.close()
        except Exception:
            logger.warning("Old microphone stream did not close cleanly after switch", exc_info=True)

        logger.info(
            "Microphone recording stream switched: previous_device=%s new_device=%s",
            previous_device,
            new_device,
        )
        return {
            "track": "mic",
            "recording": True,
            "device_id": new_device["id"],
            "device_name": new_device["name"],
            "previous_device": previous_device,
            "new_device": new_device,
        }

    def get_level(self) -> dict:
        with self._lock:
            started_at = self._started_at
            elapsed = time.perf_counter() - started_at if started_at is not None else 0.0
            has_signal = not self._is_silence(self._latest_rms, self._latest_peak)
            no_signal_warning = (
                self._stream is not None
                and elapsed >= config.SIGNAL_CHECK_SECONDS
                and self._signal_seen_at is None
            )

            warning = ""
            if no_signal_warning:
                warning = "За первые секунды записи входной сигнал не обнаружен. Проверьте микрофон."

            return {
                "recording": self._stream is not None,
                "available": True,
                "source_type": "mic",
                "rms": round(self._latest_rms, 6),
                "peak": round(self._latest_peak, 6),
                "level": self._level_percent(self._latest_rms, self._latest_peak),
                "has_signal": has_signal,
                "elapsed_sec": round(elapsed, 2),
                "device_id": self._device_id,
                "device_name": self._device_name,
                "warning": warning,
            }

    def measure_input_level(self, device_id: int | str | None = None) -> dict:
        if self.is_recording:
            return self.get_level()

        resolved_device_id, device_info = self._resolve_input_device(device_id)
        sample_rate = int(device_info.get("default_samplerate") or config.DEFAULT_SAMPLE_RATE)
        channels = min(config.DEFAULT_CHANNELS, int(device_info.get("max_input_channels", 1)))
        channels = max(1, channels)
        frames = max(1, int(sample_rate * config.LEVEL_PROBE_SECONDS))

        try:
            audio = sd.rec(
                frames,
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                device=resolved_device_id,
                blocking=True,
            )
        except Exception as exc:
            logger.exception("Failed to measure input level")
            raise RuntimeError(
                f"Не удалось проверить уровень микрофона. Проверьте разрешения Windows, антивирус и выбранное устройство: {exc}"
            ) from exc

        rms, peak = compute_audio_levels(audio)
        has_signal = not self._is_silence(rms, peak)
        warning = ""
        if not has_signal:
            warning = "Сигнал микрофона очень низкий или отсутствует."

        return {
            "recording": False,
            "available": True,
            "source_type": "mic",
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "level": self._level_percent(rms, peak),
            "has_signal": has_signal,
            "elapsed_sec": 0,
            "device_id": resolved_device_id,
            "device_name": str(device_info.get("name", "Default input")),
            "warning": warning,
        }

    def _audio_callback(self, indata, frames, callback_time, status) -> None:
        if status:
            status_text = str(status)
            with self._lock:
                self._last_status = status_text
            logger.warning("Audio stream status: %s", status_text)

        chunk = indata.copy()
        rms, peak = compute_audio_levels(chunk)
        sum_squares = float(np.sum(np.square(chunk, dtype=np.float64)))
        sample_count = int(chunk.size)

        with self._lock:
            self._latest_rms = rms
            self._latest_peak = peak
            self._total_frames += int(frames)
            self._total_samples += sample_count
            self._sum_squares += sum_squares
            self._peak = max(self._peak, peak)
            if self._signal_seen_at is None and not self._is_silence(rms, peak):
                self._signal_seen_at = time.perf_counter()
            writer_queue = self._writer_queue

        if writer_queue is None:
            return

        try:
            writer_queue.put_nowait(chunk)
        except queue.Full:
            with self._lock:
                self._dropped_chunks += 1
            logger.warning("Audio writer queue is full; dropped one chunk")

    def _writer_loop(
        self,
        output_path: Path,
        sample_rate: int,
        channels: int,
        writer_queue: queue.Queue[np.ndarray | None],
    ) -> None:
        try:
            with sf.SoundFile(
                output_path,
                mode="w",
                samplerate=sample_rate,
                channels=channels,
                subtype="PCM_16",
            ) as audio_file:
                while True:
                    chunk = writer_queue.get()
                    if chunk is None:
                        break
                    audio_file.write(chunk)
        except Exception as exc:
            with self._lock:
                self._writer_error = str(exc)
            logger.exception("Audio writer failed")

    def _stop_writer(self) -> None:
        with self._lock:
            writer_queue = self._writer_queue
            writer_thread = self._writer_thread
            self._writer_queue = None
            self._writer_thread = None

        if writer_queue is not None:
            try:
                writer_queue.put(None, timeout=2)
            except queue.Full:
                pass

        if writer_thread is not None and writer_thread.is_alive():
            writer_thread.join(timeout=10)

    def _record_device_switch_event(
        self,
        track: str,
        previous_device: dict[str, Any],
        new_device: dict[str, Any],
        result: str,
        error: str | None = None,
    ) -> None:
        event = self._device_switch_event(track, previous_device, new_device, result, error)
        with self._lock:
            self._append_device_switch_event_locked(event)

    def _append_device_switch_event_locked(self, event: dict[str, Any]) -> None:
        self._device_switch_events.append(event)

    def _device_switch_event(
        self,
        track: str,
        previous_device: dict[str, Any],
        new_device: dict[str, Any],
        result: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event": "device_switch",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "track": track,
            "previous_device": previous_device,
            "new_device": new_device,
            "result": result,
        }
        if error:
            event["error"] = error
        return event

    def _resolve_input_device(self, device_id: int | str | None) -> tuple[int | None, dict]:
        parsed_device_id = self._parse_device_id(device_id)

        try:
            if parsed_device_id is None:
                default_id = self._default_input_index()
                if default_id is not None:
                    device_info = sd.query_devices(default_id)
                    return self._validate_input_device(default_id, device_info)
                device_info = sd.query_devices(kind="input")
                return None, self._validate_input_device(None, device_info)[1]

            device_info = sd.query_devices(parsed_device_id)
            return self._validate_input_device(parsed_device_id, device_info)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Микрофон не найден или недоступен: {exc}") from exc

    def _validate_input_device(self, device_id: int | None, device_info: dict) -> tuple[int | None, dict]:
        if int(device_info.get("max_input_channels", 0)) < 1:
            raise RuntimeError("Выбранное устройство не поддерживает запись звука.")
        return device_id, device_info

    def _default_input_index(self) -> int | None:
        default_devices = sd.default.device

        if hasattr(default_devices, "input"):
            input_index = default_devices.input
        elif isinstance(default_devices, (list, tuple)):
            input_index = default_devices[0]
        elif hasattr(default_devices, "__getitem__"):
            input_index = default_devices[0]
        else:
            input_index = default_devices

        try:
            input_index = int(input_index)
        except (TypeError, ValueError):
            return None

        return input_index if input_index >= 0 else None

    def _parse_device_id(self, device_id: int | str | None) -> int | None:
        if device_id is None or device_id == "":
            return None

        try:
            parsed = int(device_id)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Некорректный идентификатор устройства записи.") from exc

        return parsed if parsed >= 0 else None

    def _is_silence(self, rms: float, peak: float) -> bool:
        return rms < config.SILENCE_RMS_THRESHOLD and peak < config.SILENCE_PEAK_THRESHOLD

    def _level_percent(self, rms: float, peak: float) -> int:
        rms_reference = max(config.LEVEL_RMS_REFERENCE, 0.000001)
        peak_reference = max(config.LEVEL_PEAK_REFERENCE, 0.000001)
        scaled = max(float(rms) / rms_reference, float(peak) / peak_reference)
        return max(0, min(100, int(round(scaled * 100))))
