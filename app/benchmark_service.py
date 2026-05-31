import copy
import logging
import threading
import time
from pathlib import Path
from uuid import uuid4

from .transcript_store import TranscriptStore


logger = logging.getLogger(__name__)


class BenchmarkService:
    def __init__(
        self,
        *,
        transcriber,
        transcript_store: TranscriptStore,
        media_validator=None,
    ) -> None:
        self.transcriber = transcriber
        self.transcript_store = transcript_store
        self.media_validator = media_validator or (lambda _path: None)
        self._lock = threading.RLock()
        self._sources: dict[str, dict] = {}
        self._results: dict[str, dict] = {}
        self._warm_ready: set[tuple[str, str, str]] = set()
        self._worker: threading.Thread | None = None
        self._current: dict | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    def register_source(self, source_path: Path, source_filename: str) -> dict:
        source_id = uuid4().hex
        source = {
            "source_id": source_id,
            "source_path": str(source_path),
            "source_filename": source_filename,
        }
        with self._lock:
            self._sources[source_id] = source
        return copy.deepcopy(source)

    def start(self, *, source_id: str, model: str, device: str, mode: str) -> dict:
        normalized_device = (device or "").strip().lower()
        normalized_mode = (mode or "").strip().lower()
        if normalized_device not in {"cpu", "cuda"}:
            raise RuntimeError("Benchmark поддерживает только устройства cpu и cuda.")
        if normalized_mode not in {"cold", "warm"}:
            raise RuntimeError("Режим benchmark должен быть cold или warm.")

        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("Benchmark уже выполняется.")
            source = self._sources.get(source_id)
            if source is None:
                raise RuntimeError("Сначала выберите и загрузите файл для benchmark.")
            if not Path(source["source_path"]).exists():
                raise RuntimeError("Файл benchmark больше не найден. Выберите его повторно.")
            cache_key = (source_id, model, normalized_device)
            if normalized_mode == "warm" and cache_key not in self._warm_ready:
                raise RuntimeError("Сначала выполните Cold Run для этого файла, модели и устройства.")
            if normalized_mode == "warm" and not self.transcriber.is_model_cached(model, normalized_device):
                raise RuntimeError("Модель уже выгружена из памяти. Повторите Cold Run перед Warm Run.")

            current = {
                **copy.deepcopy(source),
                "model": model,
                "device": normalized_device,
                "mode": normalized_mode,
                "status": "running",
                "started_at": time.perf_counter(),
            }
            self._current = current
            self._last_error = None
            self._worker = threading.Thread(
                target=self._run,
                args=(current, cache_key),
                name="benchmark-worker",
                daemon=True,
            )
            self._worker.start()
            return self._status_locked()

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def wait(self, timeout: float | None = None) -> None:
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout=timeout)

    def _run(self, current: dict, cache_key: tuple[str, str, str]) -> None:
        try:
            source_path = Path(current["source_path"])
            self.media_validator(source_path)
            if current["mode"] == "cold":
                self.transcriber.clear_model()
            result = self.transcriber.transcribe(source_path, current["model"], current["device"])
            saved = self.transcript_store.save_benchmark(
                source_path=source_path,
                source_filename=current["source_filename"],
                result=result,
                benchmark_mode=current["mode"],
                benchmark_device=current["device"],
                operation_started_at=current["started_at"],
            )
            saved["total_wall_time_sec"] = round(time.perf_counter() - current["started_at"], 3)
            duration = saved.get("audio_duration_sec")
            saved["realtime_factor_total"] = (
                round(saved["total_wall_time_sec"] / duration, 3)
                if duration
                else None
            )
            with self._lock:
                self._warm_ready.add(cache_key)
                self._results[current["device"]] = saved
                self._current = {**current, "status": "completed"}
                self._worker = None
            logger.info(
                "Benchmark completed: model=%s device=%s mode=%s json=%s",
                current["model"],
                current["device"],
                current["mode"],
                saved["json_path"],
            )
        except Exception as exc:
            logger.exception(
                "Benchmark failed: model=%s device=%s mode=%s",
                current["model"],
                current["device"],
                current["mode"],
            )
            with self._lock:
                self._last_error = str(exc)
                self._current = {**current, "status": "error", "error_message": str(exc)}
                self._worker = None

    def _status_locked(self) -> dict:
        running = self._worker is not None and self._worker.is_alive()
        current = copy.deepcopy(self._current)
        if current:
            current.pop("started_at", None)
        return {
            "status": "running" if running else (current or {}).get("status", "idle"),
            "running": running,
            "current": current,
            "results": copy.deepcopy(self._results),
            "last_error": self._last_error,
        }
