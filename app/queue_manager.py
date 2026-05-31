import copy
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .utils import audio_duration_seconds, timestamp_for_filename, write_json_file_atomic


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "error", "cancelled"}
ACTIVE_STATUSES = {"downloading", "downloaded", "analyzing", "extracting_audio", "transcribing"}


@dataclass(frozen=True)
class QueueFile:
    source_path: Path
    source_filename: str
    source_type: str = "local_file"


@dataclass(frozen=True)
class QueueUrl:
    source_url: str


class QueueManager:
    def __init__(
        self,
        *,
        jobs_dir: Path,
        processor: Callable[[dict, str, str], dict],
        error_recorder: Callable[[dict, str, str, Exception], dict] | None = None,
        duration_reader: Callable[[Path], float | None] = audio_duration_seconds,
        media_validator: Callable[[Path], None] | None = None,
        downloader: Callable[[str], dict] | None = None,
    ) -> None:
        self.jobs_dir = jobs_dir
        self.processor = processor
        self.error_recorder = error_recorder
        self.duration_reader = duration_reader
        self.media_validator = media_validator or (lambda _path: None)
        self.downloader = downloader

        self._lock = threading.RLock()
        self._items: list[dict] = []
        self._job_id: str | None = None
        self._job_path: Path | None = None
        self._created_at: str | None = None
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._model: str | None = None
        self._device_preference: str | None = None
        self._status = "empty"
        self._current_index: int | None = None
        self._stop_after_current = False
        self._worker: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_locked()

    def add_files(self, files: list[QueueFile]) -> dict:
        if not files:
            raise RuntimeError("Выберите хотя бы один файл для очереди.")

        with self._lock:
            self._ensure_inactive_locked("Нельзя добавлять файлы во время обработки очереди.")
            if self._job_id is None:
                self._create_job_locked()

            start_index = len(self._items) + 1
            for offset, queue_file in enumerate(files):
                self._items.append(
                    {
                        "index": start_index + offset,
                        "source_type": queue_file.source_type,
                        "source_path": str(queue_file.source_path),
                        "source_filename": queue_file.source_filename,
                        "status": "pending",
                        "audio_duration_sec": None,
                        "processing_time_sec": None,
                        "realtime_factor": None,
                        "transcript_path": None,
                        "json_path": None,
                        "error_message": None,
                        "technical_details": None,
                    }
                )

            self._status = "pending"
            self._finished_at = None
            self._persist_locked()
            logger.info(
                "Queue files added: job_id=%s added=%s total=%s job_json=%s",
                self._job_id,
                len(files),
                len(self._items),
                self._job_path,
            )
            return self._status_snapshot_locked()

    def add_urls(self, urls: list[QueueUrl]) -> dict:
        if not urls:
            raise RuntimeError("Добавьте хотя бы одну ссылку для очереди.")

        with self._lock:
            self._ensure_inactive_locked("Нельзя добавлять ссылки во время обработки очереди.")
            if self._job_id is None:
                self._create_job_locked()

            start_index = len(self._items) + 1
            for offset, queue_url in enumerate(urls):
                source_url = queue_url.source_url.strip()
                if not source_url:
                    raise RuntimeError("Пустые ссылки нельзя добавить в очередь.")
                index = start_index + offset
                self._items.append(
                    {
                        "index": index,
                        "source_type": "url",
                        "source_url": source_url,
                        "source_title": None,
                        "source_platform": "unknown",
                        "source_path": None,
                        "source_filename": f"url_{index:03d}",
                        "downloaded_audio_path": None,
                        "status": "pending",
                        "audio_duration_sec": None,
                        "processing_time_sec": None,
                        "realtime_factor": None,
                        "transcript_path": None,
                        "json_path": None,
                        "error_message": None,
                        "technical_details": None,
                    }
                )

            self._status = "pending"
            self._finished_at = None
            self._persist_locked()
            logger.info("Queue URLs added: job_id=%s added=%s total=%s", self._job_id, len(urls), len(self._items))
            return self._status_snapshot_locked()

    def start(self, model: str, device_preference: str = "auto") -> dict:
        with self._lock:
            self._ensure_inactive_locked("Очередь уже выполняется.")
            if not any(item["status"] == "pending" for item in self._items):
                raise RuntimeError("В очереди нет ожидающих задач.")

            self._model = model
            self._device_preference = device_preference
            self._started_at = self._started_at or self._now()
            self._finished_at = None
            self._stop_after_current = False
            self._status = "running"
            self._persist_locked()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="local-file-queue",
                daemon=True,
            )
            self._worker.start()
            logger.info(
                "Queue started: job_id=%s model=%s device=%s items=%s",
                self._job_id,
                model,
                device_preference,
                len(self._items),
            )
            return self._status_snapshot_locked()

    def stop_after_current(self) -> dict:
        with self._lock:
            if not self._is_running_locked():
                raise RuntimeError("Очередь сейчас не выполняется.")
            self._stop_after_current = True
            self._persist_locked()
            logger.info("Queue stop-after-current requested: job_id=%s", self._job_id)
            return self._status_snapshot_locked()

    def clear(self) -> dict:
        with self._lock:
            self._ensure_inactive_locked("Нельзя очистить очередь во время обработки.")
            logger.info("Queue cleared: job_id=%s items=%s", self._job_id, len(self._items))
            self._items = []
            self._job_id = None
            self._job_path = None
            self._created_at = None
            self._started_at = None
            self._finished_at = None
            self._model = None
            self._device_preference = None
            self._status = "empty"
            self._current_index = None
            self._stop_after_current = False
            self._worker = None
            return self._status_snapshot_locked()

    def retry_errors(self) -> dict:
        with self._lock:
            self._ensure_inactive_locked("Нельзя повторить задачи во время обработки очереди.")
            failed_items = [item for item in self._items if item["status"] == "error"]
            if not failed_items:
                raise RuntimeError("В очереди нет ошибочных задач для повтора.")

            for item in failed_items:
                item.update(
                    {
                        "status": "pending",
                        "processing_time_sec": None,
                        "realtime_factor": None,
                        "transcript_path": None,
                        "json_path": None,
                        "error_message": None,
                        "technical_details": None,
                    }
                )
            self._status = "pending"
            self._finished_at = None
            self._persist_locked()
            logger.info("Queue failed items prepared for retry: job_id=%s items=%s", self._job_id, len(failed_items))
            return self._status_snapshot_locked()

    def status(self) -> dict:
        with self._lock:
            return self._status_snapshot_locked()

    def wait(self, timeout: float | None = None) -> None:
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout=timeout)

    def _worker_loop(self) -> None:
        while True:
            with self._lock:
                item = next((entry for entry in self._items if entry["status"] == "pending"), None)
                if item is None:
                    self._finish_locked("completed")
                    return

                self._current_index = item["index"]
                self._persist_locked()
                item_snapshot = copy.deepcopy(item)
                model = self._model or ""
                device_preference = self._device_preference or "auto"
                logger.info(
                    "Queue task started: job_id=%s index=%s source=%s model=%s device=%s",
                    self._job_id,
                    item["index"],
                    item.get("source_path") or item.get("source_url"),
                    model,
                    device_preference,
                )

            try:
                source_path = self._prepare_source(item, item_snapshot)
                with self._lock:
                    item["status"] = "analyzing"
                    self._persist_locked()
                    item_snapshot = copy.deepcopy(item)
                duration = self.duration_reader(source_path)
                with self._lock:
                    item["audio_duration_sec"] = self._rounded(duration) or item.get("audio_duration_sec")
                    self._persist_locked()

                self.media_validator(source_path)
                if source_path.suffix.lower() == ".mp4":
                    with self._lock:
                        item["status"] = "extracting_audio"
                        self._persist_locked()

                with self._lock:
                    item["status"] = "transcribing"
                    self._persist_locked()
                    item_snapshot = copy.deepcopy(item)

                result = self.processor(item_snapshot, model, device_preference)
                with self._lock:
                    item.update(
                        {
                            "status": "completed",
                            "audio_duration_sec": result.get("audio_duration_sec", item["audio_duration_sec"]),
                            "processing_time_sec": result.get("processing_time_sec"),
                            "realtime_factor": result.get("realtime_factor"),
                            "transcript_path": result.get("transcript_path"),
                            "json_path": result.get("json_path") or result.get("benchmark_path"),
                            "error_message": None,
                            "technical_details": None,
                        }
                    )
                    self._persist_locked()
                    logger.info(
                        "Queue task completed: job_id=%s index=%s transcript=%s json=%s duration=%s processing_time=%s realtime_factor=%s",
                        self._job_id,
                        item["index"],
                        item["transcript_path"],
                        item["json_path"],
                        item["audio_duration_sec"],
                        item["processing_time_sec"],
                        item["realtime_factor"],
                    )
            except Exception as exc:
                error_metadata: dict = {}
                if self.error_recorder is not None:
                    try:
                        error_metadata = self.error_recorder(item_snapshot, model, device_preference, exc)
                    except Exception:
                        logger.exception("Failed to save queue task error JSON")

                with self._lock:
                    item.update(
                        {
                            "status": "error",
                            "transcript_path": error_metadata.get("transcript_path"),
                            "json_path": error_metadata.get("json_path") or error_metadata.get("benchmark_path"),
                            "error_message": str(exc),
                            "technical_details": str(getattr(exc, "technical_details", "") or exc),
                        }
                    )
                    self._persist_locked()
                    logger.exception(
                        "Queue task failed: job_id=%s index=%s file=%s",
                        self._job_id,
                        item["index"],
                        item.get("source_path") or item.get("source_url"),
                    )

            with self._lock:
                self._current_index = None
                if self._stop_after_current:
                    for pending_item in self._items:
                        if pending_item["status"] == "pending":
                            pending_item["status"] = "cancelled"
                    self._finish_locked("cancelled")
                    return
                self._persist_locked()

    def _finish_locked(self, status: str) -> None:
        self._current_index = None
        self._status = status
        self._finished_at = self._now()
        self._worker = None
        self._persist_locked()
        logger.info(
            "Queue finished: job_id=%s status=%s completed=%s failed=%s cancelled=%s",
            self._job_id,
            status,
            self._count_locked("completed"),
            self._count_locked("error"),
            self._count_locked("cancelled"),
        )

    def _create_job_locked(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        base_id = timestamp_for_filename()
        job_id = base_id
        counter = 2
        while (self.jobs_dir / f"job_{job_id}.json").exists():
            job_id = f"{base_id}_{counter}"
            counter += 1

        self._job_id = job_id
        self._job_path = self.jobs_dir / f"job_{job_id}.json"
        self._created_at = self._now()
        self._status = "pending"
        logger.info("Queue created: job_id=%s job_json=%s", self._job_id, self._job_path)

    def _status_snapshot_locked(self) -> dict:
        payload = self._job_payload_locked()
        total_items = payload["total_items"]
        finished_items = payload["completed_items"] + payload["failed_items"] + payload["cancelled_items"]
        elapsed_sec = self._elapsed_seconds_locked()
        eta_sec, eta_message = self._eta_locked()
        current_item = next((item for item in self._items if item["index"] == self._current_index), None)
        return {
            **payload,
            "job_path": str(self._job_path) if self._job_path else None,
            "pending_items": self._count_locked("pending"),
            "running_items": sum(1 for item in self._items if item["status"] in ACTIVE_STATUSES),
            "current_file": current_item["source_filename"] if current_item else None,
            "current_item": copy.deepcopy(current_item),
            "elapsed_sec": elapsed_sec,
            "eta_sec": eta_sec,
            "eta_message": eta_message,
            "progress_percent": round((finished_items / total_items) * 100, 1) if total_items else 0,
            "stop_after_current": self._stop_after_current,
        }

    def _job_payload_locked(self) -> dict:
        return {
            "job_id": self._job_id,
            "created_at": self._created_at,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "model": self._model,
            "device_preference": self._device_preference,
            "status": self._status,
            "total_items": len(self._items),
            "completed_items": self._count_locked("completed"),
            "failed_items": self._count_locked("error"),
            "cancelled_items": self._count_locked("cancelled"),
            "items": copy.deepcopy(self._items),
        }

    def _persist_locked(self) -> None:
        if self._job_path is None:
            return
        write_json_file_atomic(self._job_path, self._job_payload_locked())

    def _eta_locked(self) -> tuple[float | None, str]:
        completed = [
            item
            for item in self._items
            if item["status"] == "completed"
            and item.get("audio_duration_sec")
            and item.get("processing_time_sec")
        ]
        remaining = [item for item in self._items if item["status"] not in TERMINAL_STATUSES]
        if not remaining:
            return 0, ""
        if not completed:
            return None, "Оценка появится после обработки первых файлов."

        total_audio = sum(float(item["audio_duration_sec"]) for item in completed)
        total_processing = sum(float(item["processing_time_sec"]) for item in completed)
        remaining_durations = [item.get("audio_duration_sec") for item in remaining]
        if total_audio <= 0 or total_processing <= 0 or any(duration is None for duration in remaining_durations):
            return None, "Оценка появится после анализа файлов."

        average_speed = total_audio / total_processing
        eta = sum(float(duration) for duration in remaining_durations) / average_speed
        return round(eta, 1), ""

    def _elapsed_seconds_locked(self) -> float:
        if not self._started_at:
            return 0
        start = datetime.fromisoformat(self._started_at)
        end = datetime.fromisoformat(self._finished_at) if self._finished_at else datetime.now().astimezone()
        return round(max(0.0, (end - start).total_seconds()), 1)

    def _prepare_source(self, item: dict, item_snapshot: dict) -> Path:
        if item_snapshot.get("source_type") != "url":
            return Path(item_snapshot["source_path"])

        downloaded_path = item_snapshot.get("downloaded_audio_path")
        if downloaded_path and Path(downloaded_path).exists():
            return Path(downloaded_path)
        if self.downloader is None:
            raise RuntimeError("Сервис скачивания URL не настроен.")

        with self._lock:
            item["status"] = "downloading"
            self._persist_locked()
        metadata = self.downloader(item_snapshot["source_url"])
        source_path = Path(metadata["source_path"])
        if not source_path.exists():
            raise RuntimeError("Скачанный аудиофайл не найден.")

        with self._lock:
            item.update(
                {
                    "source_path": str(source_path),
                    "downloaded_audio_path": str(source_path),
                    "source_title": metadata.get("source_title"),
                    "source_platform": metadata.get("source_platform") or "unknown",
                    "source_filename": metadata.get("source_title") or item["source_filename"],
                    "audio_duration_sec": self._rounded(metadata.get("audio_duration_sec")),
                    "status": "downloaded",
                }
            )
            self._persist_locked()
        return source_path

    def _ensure_inactive_locked(self, message: str) -> None:
        if self._is_running_locked():
            raise RuntimeError(message)

    def _is_running_locked(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _count_locked(self, status: str) -> int:
        return sum(1 for item in self._items if item["status"] == status)

    @staticmethod
    def _rounded(value: float | None) -> float | None:
        return round(value, 3) if value is not None else None

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
