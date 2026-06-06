import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
import shutil
import threading
from uuid import uuid4

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import config
from .audio_recorder import AudioRecorder
from .benchmark_service import BenchmarkService
from .queue_manager import QueueFile, QueueManager, QueueUrl
from .system_audio_recorder import SystemAudioRecorder
from .transcript_store import TranscriptStore, safe_filename_part, technical_details_for_exception
from .transcriber import AudioTranscriber, ModelLoadError
from .url_downloader import UrlDownloader
from .utils import setup_logging, timestamp_for_filename, validate_media_for_transcription


setup_logging()
logger = logging.getLogger(__name__)

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> FileResponse:
        response = await super().get_response(path, scope)
        response.headers.update(NO_CACHE_HEADERS)
        return response


app = FastAPI(title="Local Audio Transcriber")
app.mount("/static", NoCacheStaticFiles(directory=str(config.STATIC_DIR)), name="static")

recorder = AudioRecorder()
system_recorder = SystemAudioRecorder()
transcriber = AudioTranscriber()
transcript_store = TranscriptStore()
recording_lock = threading.Lock()
active_recording_mode: str | None = None
active_recording_started_at: float | None = None
last_recording_duration_sec: float | None = None
level_poll_lock = threading.Lock()
level_poll_seen: set[str] = set()
level_error_log_times: dict[tuple[str, str, str], float] = {}


class StartRecordingRequest(BaseModel):
    mode: str = "mic"
    device_id: int | None = None
    mic_device_id: int | None = None
    output_device_id: str | None = None


class SwitchMicrophoneRequest(BaseModel):
    device_id: int | None = None


class SwitchOutputDeviceRequest(BaseModel):
    output_device_id: str | None = None


class TranscribeFileRequest(BaseModel):
    file_path: str
    source_type: str | None = None
    model: str | None = None
    device: str | None = None


class OpenFolderRequest(BaseModel):
    folder: str


class QueueStartRequest(BaseModel):
    model: str | None = None
    device: str | None = None


class QueueUrlsRequest(BaseModel):
    urls: list[str]


class QueueRecordingRequest(BaseModel):
    file_path: str
    source_type: str


class QueueRecordingsRequest(BaseModel):
    files: list[QueueRecordingRequest]


class BenchmarkRunRequest(BaseModel):
    source_id: str
    model: str
    device: str
    mode: str


def process_queue_item(item: dict, model_name: str, device_preference: str) -> dict:
    source_path = Path(item["source_path"])
    result = transcriber.transcribe(source_path, model_name, device_preference)
    return transcript_store.save_success(
        source_path=source_path,
        source_filename=item["source_filename"],
        source_type=item.get("source_type") or "local_file",
        result=result,
        extra_metadata=item,
    )


def save_queue_item_error(item: dict, model_name: str, _device_preference: str, exc: Exception) -> dict:
    source_path = Path(item.get("source_path") or config.DOWNLOADS_DIR / item["source_filename"])
    return transcript_store.save_error(
        source_path=source_path,
        source_filename=item["source_filename"],
        source_type=item.get("source_type") or "local_file",
        model=model_name,
        error_message=str(exc),
        technical_details=technical_details_for_exception(exc),
        extra_metadata=item,
    )


url_downloader = UrlDownloader()
queue_manager = QueueManager(
    jobs_dir=config.JOBS_DIR,
    processor=process_queue_item,
    error_recorder=save_queue_item_error,
    media_validator=validate_media_for_transcription,
    downloader=url_downloader.download,
)
benchmark_service = BenchmarkService(
    transcriber=transcriber,
    transcript_store=transcript_store,
    media_validator=validate_media_for_transcription,
)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Application started: version=%s model=%s device=%s compute_type=%s data_dir=%s recordings_dir=%s transcripts_dir=%s jobs_dir=%s",
        config.APP_VERSION,
        config.WHISPER_MODEL,
        config.WHISPER_DEVICE,
        config.WHISPER_COMPUTE_TYPE,
        config.DATA_DIR,
        config.RECORDINGS_DIR,
        config.TRANSCRIPTS_DIR,
        config.JOBS_DIR,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html", headers=NO_CACHE_HEADERS)


@app.get("/api/status")
def status() -> dict:
    transcription = transcriber.status()
    recording_elapsed_sec = (
        round(time.monotonic() - active_recording_started_at, 1)
        if active_recording_started_at is not None
        else 0
    )
    return {
        "app_version": config.APP_VERSION,
        "recording": recorder.is_recording or system_recorder.is_recording,
        "recording_mode": active_recording_mode,
        "recording_elapsed_sec": recording_elapsed_sec,
        "last_recording_duration_sec": last_recording_duration_sec,
        "mic_recording": recorder.is_recording,
        "system_recording": system_recorder.is_recording,
        "ffmpeg_found": shutil.which("ffmpeg") is not None,
        "whisper_model": config.WHISPER_MODEL,
        "whisper_models": list(config.SUPPORTED_WHISPER_MODELS),
        "whisper_model_status": model_statuses(),
        "whisper_language": config.WHISPER_LANGUAGE,
        "microphone": recorder.microphone_status(),
        "system_audio": system_recorder.output_status(),
        "transcription": transcription,
        "benchmark": benchmark_service.status(),
        "supported_formats": sorted(config.SUPPORTED_AUDIO_EXTENSIONS),
    }


@app.get("/api/models")
def models() -> dict:
    statuses = model_statuses()
    logger.info("Model local availability checked: models=%s", statuses)
    return {"models": statuses}


@app.get("/api/storage")
def storage() -> dict:
    disk = shutil.disk_usage(config.DATA_DIR)
    return {
        "disk": {
            "path": str(config.DATA_DIR),
            "free_bytes": disk.free,
            "free_gb": round(disk.free / (1024 ** 3), 1),
        },
        "recordings": {
            "path": str(config.RECORDINGS_DIR),
            "files": recent_files(config.RECORDINGS_DIR, allowed_suffixes={".wav"}),
        },
        "transcripts": {
            "path": str(config.TRANSCRIPTS_DIR),
            "files": recent_files(config.TRANSCRIPTS_DIR, allowed_suffixes={".txt"}),
        },
    }


@app.get("/api/transcripts/read")
def read_transcript(file_path: str) -> dict:
    transcript_path = validate_transcript_txt_path(file_path)
    return {
        "file_path": str(transcript_path),
        "text": transcript_path.read_text(encoding="utf-8"),
    }


@app.post("/api/folders/open")
def open_folder(payload: OpenFolderRequest) -> dict:
    folder_key = (payload.folder or "").strip().lower()
    folders = {
        "recordings": config.RECORDINGS_DIR,
        "transcripts": config.TRANSCRIPTS_DIR,
    }
    folder_path = folders.get(folder_key)
    if folder_path is None:
        raise_api_error("Неизвестная папка. Доступны: recordings, transcripts.")

    folder_path.mkdir(parents=True, exist_ok=True)
    abs_path = folder_path.resolve()
    logger.info("Open folder button requested: folder=%s path=%s", folder_key, abs_path)

    if os.name != "nt":
        raise_api_error("Открытие папки из интерфейса сейчас поддержано только в Windows.", status_code=500)

    try:
        completed = subprocess.Popen(
            ["explorer.exe", str(abs_path)],
            close_fds=True,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        logger.info("Explorer launch succeeded: folder=%s path=%s pid=%s", folder_key, abs_path, completed.pid)
    except Exception as exc:
        logger.exception("Failed to open folder in Explorer: folder=%s path=%s", folder_key, abs_path)
        raise_api_error(f"Не удалось открыть папку {abs_path}: {exc}", status_code=500)

    return {"message": f"Папка {folder_key} открыта.", "path": str(abs_path)}


@app.get("/api/audio/devices")
def audio_devices() -> dict:
    try:
        return recorder.list_input_devices()
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)


@app.get("/api/audio/output-devices")
def output_devices() -> dict:
    try:
        return system_recorder.list_output_devices()
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)


@app.get("/api/audio/level")
def audio_level(device_id: int | None = None) -> dict:
    log_level_poll_start("mic")
    try:
        return recorder.measure_input_level(device_id)
    except RuntimeError as exc:
        log_level_poll_error("mic", device_id, exc)
        raise_api_error(str(exc), status_code=500)


@app.get("/api/audio/output-level")
def output_audio_level(device_id: str | None = None) -> dict:
    log_level_poll_start("system")
    try:
        return system_recorder.measure_output_level(device_id)
    except RuntimeError as exc:
        log_level_poll_error("system", device_id, exc)
        raise_api_error(str(exc), status_code=500)


@app.post("/api/record/start")
def start_recording(payload: StartRecordingRequest | None = Body(default=None)) -> dict:
    request = payload or StartRecordingRequest()
    mode = normalize_recording_mode(request.mode)
    mic_device_id = request.mic_device_id if request.mic_device_id is not None else request.device_id
    output_device_id = request.output_device_id
    timestamp = timestamp_for_filename()
    recordings: list[dict] = []

    global active_recording_mode, active_recording_started_at
    with recording_lock:
        if benchmark_service.is_running:
            raise_api_error("Дождитесь завершения benchmark перед началом записи.")
        if recorder.is_recording or system_recorder.is_recording:
            raise_api_error("Запись уже идет.")
        active_recording_mode = mode

    logger.info(
        "Start recording request: mode=%s mic_device_id=%s output_device_id=%s",
        mode,
        mic_device_id,
        output_device_id,
    )

    try:
        if mode == "mic":
            recordings.append(recorder.start(mic_device_id, filename_prefix="recording", source_type="mic", timestamp=timestamp))
        elif mode == "system":
            recordings.append(system_recorder.start(output_device_id, timestamp=timestamp))
        elif mode == "both":
            recordings.append(recorder.start(mic_device_id, filename_prefix="mic", source_type="mic", timestamp=timestamp))
            recordings.append(system_recorder.start(output_device_id, timestamp=timestamp))
    except RuntimeError as exc:
        logger.exception("Failed to start recording mode=%s", mode)
        cleanup_started_recorders()
        with recording_lock:
            active_recording_mode = None
            active_recording_started_at = None
        raise_api_error(str(exc), status_code=500)

    with recording_lock:
        active_recording_started_at = time.monotonic()

    response = {
        "message": "Запись началась.",
        "recording": True,
        "mode": mode,
        "recordings": recordings,
    }
    if recordings:
        response.update(recordings[0])
    return response


@app.post("/api/record/stop")
def stop_recording() -> dict:
    diagnostics_list: list[dict] = []
    errors: list[str] = []

    global active_recording_mode, active_recording_started_at, last_recording_duration_sec
    mode = active_recording_mode

    logger.info("Stop recording request: mode=%s", mode)

    if recorder.is_recording:
        try:
            diagnostics_list.append(recorder.stop())
        except RuntimeError as exc:
            logger.exception("Failed to stop microphone recording")
            errors.append(str(exc))

    if system_recorder.is_recording:
        try:
            diagnostics_list.append(system_recorder.stop())
        except RuntimeError as exc:
            logger.exception("Failed to stop system recording")
            errors.append(str(exc))

    with recording_lock:
        active_recording_mode = None
        active_recording_started_at = None

    if not diagnostics_list and errors:
        raise_api_error("; ".join(errors), status_code=500)

    if not diagnostics_list:
        raise_api_error("Запись не запущена.")

    logger.info("Recording stop finished: mode=%s files=%s errors=%s", mode, len(diagnostics_list), errors)
    last_recording_duration_sec = max(
        (float(item.get("duration_sec") or 0) for item in diagnostics_list),
        default=0,
    )

    return {
        "message": "Запись сохранена.",
        "recording": False,
        "mode": mode,
        "file_path": diagnostics_list[0]["audio_file"],
        "file_name": Path(diagnostics_list[0]["audio_file"]).name,
        "diagnostics": diagnostics_list[0],
        "diagnostics_list": diagnostics_list,
        "errors": errors,
        "duration_sec": last_recording_duration_sec,
    }


@app.post("/api/record/switch-microphone")
def switch_microphone(payload: SwitchMicrophoneRequest | None = Body(default=None)) -> dict:
    request = payload or SwitchMicrophoneRequest()
    if not recorder.is_recording:
        raise_api_error("Запись микрофона не запущена.")

    try:
        return recorder.switch_input_device(request.device_id)
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)


@app.post("/api/record/switch-output-device")
def switch_output_device(payload: SwitchOutputDeviceRequest | None = Body(default=None)) -> dict:
    request = payload or SwitchOutputDeviceRequest()
    if not system_recorder.is_recording:
        raise_api_error("Запись системного звука не запущена.")

    try:
        return system_recorder.switch_output_device(request.output_device_id)
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile | None = File(default=None),
    model: str | None = Form(default=None),
    device: str | None = Form(default=None),
) -> dict:
    ensure_queue_inactive_for_direct_transcription()
    selected_model = validate_whisper_model(model)
    selected_device = validate_device_preference(device)

    if file is None or not file.filename:
        raise_api_error("Выберите аудио- или видеофайл для транскрибации.")

    source_filename = Path(file.filename).name
    upload_path = await save_upload_file(file)
    logger.info("Uploaded file saved for transcription: file=%s model=%s", upload_path, selected_model)
    return await transcribe_path(upload_path, source_filename, "local_file", selected_model, selected_device)


@app.post("/api/transcribe/file")
async def transcribe_recorded_file(payload: TranscribeFileRequest) -> dict:
    ensure_queue_inactive_for_direct_transcription()
    audio_path = validate_local_audio_path(payload.file_path)
    selected_model = validate_whisper_model(payload.model)
    selected_device = validate_device_preference(payload.device)
    return await transcribe_path(audio_path, audio_path.name, payload.source_type or "recording", selected_model, selected_device)


async def transcribe_path(
    audio_path: Path,
    source_filename: str,
    source_type: str,
    model_name: str,
    device_preference: str,
) -> dict:
    logger.info(
        "Transcription request accepted: file=%s source_filename=%s source_type=%s model=%s device=%s",
        audio_path,
        source_filename,
        source_type,
        model_name,
        device_preference,
    )
    local_model = model_local_status(model_name)
    logger.info("Selected model: model=%s local_available=%s cache_path=%s", model_name, local_model["local"], local_model["path"])
    if not local_model["local"]:
        logger.info("Model is not available locally; first download may be attempted: model=%s", model_name)

    try:
        validate_media_for_transcription(audio_path)
        result = await run_in_threadpool(transcriber.transcribe, audio_path, model_name, device_preference)
        saved = transcript_store.save_success(
            source_path=audio_path,
            source_filename=source_filename,
            source_type=source_type,
            result=result,
        )
    except ModelLoadError as exc:
        logger.exception(
            "Model load failed: file=%s model=%s technical_details=%s",
            audio_path,
            model_name,
            exc.technical_details,
        )
        save_direct_transcription_error(audio_path, source_filename, source_type, model_name, exc)
        raise_api_error(
            exc.user_message,
            status_code=500,
            extra={"technical_details": exc.technical_details},
        )
    except RuntimeError as exc:
        logger.exception("Transcription failed: file=%s model=%s", audio_path, model_name)
        save_direct_transcription_error(audio_path, source_filename, source_type, model_name, exc)
        raise_api_error(str(exc), status_code=500)
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        save_direct_transcription_error(audio_path, source_filename, source_type, model_name, exc)
        raise_api_error(f"Непредвиденная ошибка транскрибации: {exc}", status_code=500)

    logger.info(
        "Transcription saved: file=%s transcript=%s benchmark=%s model=%s device=%s compute_type=%s",
        audio_path,
        saved["transcript_path"],
        saved["benchmark_path"],
        result.model,
        result.device,
        result.compute_type,
    )

    return {
        "message": "Транскрибация завершена.",
        "audio_file_path": str(audio_path),
        "uploaded_file_path": str(audio_path),
        **saved,
    }


@app.post("/api/queue/add-files")
async def queue_add_files(files: list[UploadFile] = File(...)) -> dict:
    ensure_benchmark_inactive()
    if queue_manager.is_running:
        raise_api_error("Нельзя добавлять файлы во время обработки очереди.")
    if not files:
        raise_api_error("Выберите хотя бы один файл для очереди.")

    validate_upload_filenames(files)
    queue_files: list[QueueFile] = []
    for file in files:
        source_filename = Path(file.filename or "").name
        upload_path = await save_upload_file(file)
        queue_files.append(QueueFile(source_path=upload_path, source_filename=source_filename))

    try:
        return queue_manager.add_files(queue_files)
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/add-recordings")
def queue_add_recordings(payload: QueueRecordingsRequest) -> dict:
    ensure_benchmark_inactive()
    if queue_manager.is_running:
        raise_api_error("Нельзя добавлять записи во время обработки очереди.")
    if not payload.files:
        raise_api_error("Выберите хотя бы одну запись для очереди.")

    queue_files: list[QueueFile] = []
    for recording in payload.files:
        source_type = recording.source_type.strip().lower()
        if source_type not in {"mic", "system"}:
            raise_api_error("Тип записи должен быть mic или system.")
        source_path = validate_recording_audio_path(recording.file_path)
        queue_files.append(
            QueueFile(
                source_path=source_path,
                source_filename=source_path.name,
                source_type=source_type,
            )
        )

    try:
        return queue_manager.add_files(queue_files)
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/add-urls")
def queue_add_urls(payload: QueueUrlsRequest) -> dict:
    ensure_benchmark_inactive()
    try:
        urls = [QueueUrl(source_url=url) for url in payload.urls if url.strip()]
        return queue_manager.add_urls(urls)
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/start")
def queue_start(payload: QueueStartRequest | None = Body(default=None)) -> dict:
    ensure_benchmark_inactive()
    if recorder.is_recording or system_recorder.is_recording:
        raise_api_error("Остановите запись перед запуском очереди.")
    if transcriber.status()["in_progress"]:
        raise_api_error("Дождитесь завершения текущей транскрибации.")

    request = payload or QueueStartRequest()
    selected_model = validate_whisper_model(request.model)
    selected_device = validate_device_preference(request.device)
    try:
        return queue_manager.start(selected_model, selected_device)
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/stop-after-current")
def queue_stop_after_current() -> dict:
    try:
        return queue_manager.stop_after_current()
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/clear")
def queue_clear() -> dict:
    ensure_benchmark_inactive()
    try:
        return queue_manager.clear()
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.post("/api/queue/retry-errors")
def queue_retry_errors() -> dict:
    ensure_benchmark_inactive()
    try:
        return queue_manager.retry_errors()
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.get("/api/queue/status")
def queue_status() -> dict:
    return queue_manager.status()


@app.post("/api/benchmark/upload")
async def benchmark_upload(file: UploadFile | None = File(default=None)) -> dict:
    ensure_benchmark_can_start()
    if file is None or not file.filename:
        raise_api_error("Выберите локальный файл для benchmark.")
    source_filename = Path(file.filename).name
    upload_path = await save_upload_file(file)
    return benchmark_service.register_source(upload_path, source_filename)


@app.post("/api/benchmark/run")
def benchmark_run(payload: BenchmarkRunRequest) -> dict:
    ensure_benchmark_can_start()
    selected_model = validate_whisper_model(payload.model)
    selected_device = validate_device_preference(payload.device)
    if selected_device == "auto":
        raise_api_error("Для benchmark выберите cpu или cuda.")
    try:
        return benchmark_service.start(
            source_id=payload.source_id,
            model=selected_model,
            device=selected_device,
            mode=payload.mode,
        )
    except RuntimeError as exc:
        raise_api_error(str(exc))


@app.get("/api/benchmark/status")
def benchmark_status() -> dict:
    return benchmark_service.status()


async def save_upload_file(file: UploadFile) -> Path:
    source_filename = Path(file.filename or "").name
    suffix = validate_supported_suffix(source_filename)
    upload_stem = safe_filename_part(Path(source_filename).stem, max_length=72)
    upload_path = config.UPLOADS_DIR / f"upload__{timestamp_for_filename()}__{uuid4().hex[:8]}__{upload_stem}{suffix}"

    try:
        with upload_path.open("wb") as output_file:
            while chunk := await file.read(1024 * 1024):
                output_file.write(chunk)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise_api_error(f"Не удалось сохранить загруженный файл: {exc}", status_code=500)
    finally:
        await file.close()

    if not upload_path.exists():
        raise_api_error("Загруженный файл не найден после сохранения.", status_code=500)
    if upload_path.stat().st_size == 0:
        upload_path.unlink(missing_ok=True)
        raise_api_error("Загруженный файл пустой.")

    return upload_path


def validate_upload_filenames(files: list[UploadFile]) -> None:
    for file in files:
        if not file.filename:
            raise_api_error("У одного из выбранных файлов отсутствует имя.")
        validate_supported_suffix(file.filename)


def validate_supported_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in config.SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
        raise_api_error(f"Формат {suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")
    return suffix


def ensure_queue_inactive_for_direct_transcription() -> None:
    if queue_manager.is_running:
        raise_api_error("Дождитесь завершения очереди перед одиночной транскрибацией.")
    ensure_benchmark_inactive()


def ensure_benchmark_inactive() -> None:
    if benchmark_service.is_running:
        raise_api_error("Дождитесь завершения benchmark.")


def ensure_benchmark_can_start() -> None:
    ensure_benchmark_inactive()
    if queue_manager.is_running:
        raise_api_error("Дождитесь завершения очереди перед запуском benchmark.")
    if recorder.is_recording or system_recorder.is_recording:
        raise_api_error("Остановите запись перед запуском benchmark.")
    if transcriber.status()["in_progress"]:
        raise_api_error("Дождитесь завершения текущей транскрибации.")


def save_direct_transcription_error(
    audio_path: Path,
    source_filename: str,
    source_type: str,
    model_name: str,
    exc: Exception,
) -> None:
    try:
        transcript_store.save_error(
            source_path=audio_path,
            source_filename=source_filename,
            source_type=source_type,
            model=model_name,
            error_message=str(exc),
            technical_details=technical_details_for_exception(exc),
        )
    except Exception:
        logger.exception("Failed to save transcription error JSON")


def normalize_recording_mode(mode: str) -> str:
    normalized = (mode or "mic").strip().lower()
    if normalized not in {"mic", "system", "both"}:
        raise_api_error("Некорректный режим записи. Доступны: mic, system, both.")
    return normalized


def validate_whisper_model(model_name: str | None) -> str:
    selected_model = (model_name or config.WHISPER_MODEL).strip()
    if selected_model not in config.SUPPORTED_WHISPER_MODELS:
        allowed = ", ".join(config.SUPPORTED_WHISPER_MODELS)
        raise_api_error(f"Модель Whisper '{selected_model}' недоступна. Доступны: {allowed}.")
    return selected_model


def validate_device_preference(device: str | None) -> str:
    selected_device = (device or config.WHISPER_DEVICE or "auto").strip().lower()
    if selected_device not in {"auto", "cpu", "cuda"}:
        raise_api_error("Устройство должно быть одним из значений: auto, cpu, cuda.")
    return selected_device


def validate_local_audio_path(file_path: str) -> Path:
    try:
        audio_path = Path(file_path).resolve()
        data_dir = config.DATA_DIR.resolve()
        if not audio_path.is_relative_to(data_dir):
            raise RuntimeError("Можно транскрибировать только файлы внутри папки data проекта.")
        if not audio_path.exists():
            raise RuntimeError("Файл не найден.")
        if audio_path.suffix.lower() not in config.SUPPORTED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
            raise RuntimeError(f"Формат {audio_path.suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")
        return audio_path
    except RuntimeError as exc:
        raise_api_error(str(exc))


def validate_recording_audio_path(file_path: str) -> Path:
    try:
        audio_path = Path(file_path).resolve()
        recordings_dir = config.RECORDINGS_DIR.resolve()
        if not audio_path.is_relative_to(recordings_dir):
            raise RuntimeError("Можно добавлять только записи из папки data/recordings.")
        if not audio_path.is_file():
            raise RuntimeError("Файл записи не найден.")
        if audio_path.suffix.lower() not in config.SUPPORTED_AUDIO_EXTENSIONS:
            allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
            raise RuntimeError(f"Формат {audio_path.suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")
        return audio_path
    except RuntimeError as exc:
        raise_api_error(str(exc))


def validate_transcript_txt_path(file_path: str) -> Path:
    try:
        requested_name = (file_path or "").strip()
        requested_path = Path(requested_name)
        if not requested_name or requested_name != requested_path.name or ":" in requested_name:
            raise RuntimeError("Можно читать только TXT-файлы из папки data/transcripts.")
        if requested_path.suffix.lower() != ".txt":
            raise RuntimeError("Можно читать только TXT-файлы транскриптов.")
        transcript_path = (config.TRANSCRIPTS_DIR / requested_name).resolve()
        transcripts_dir = config.TRANSCRIPTS_DIR.resolve()
        if not transcript_path.is_relative_to(transcripts_dir):
            raise RuntimeError("Можно читать только TXT-файлы из папки data/transcripts.")
        if not transcript_path.is_file():
            raise RuntimeError("TXT-файл транскрипта не найден.")
        return transcript_path
    except RuntimeError as exc:
        raise_api_error(str(exc))


def recent_files(directory: Path, limit: int = 5, allowed_suffixes: set[str] | None = None) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    normalized_suffixes = {suffix.lower() for suffix in allowed_suffixes} if allowed_suffixes is not None else None

    for path in directory.iterdir():
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if normalized_suffixes is not None and path.suffix.lower() not in normalized_suffixes:
            continue
        files.append(path)

    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    result = []
    for path in files[:limit]:
        stat = path.stat()
        result.append(
            {
                "name": path.name,
                "path": str(path),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 3),
            }
        )

    return result


def model_statuses() -> list[dict]:
    return [model_local_status(model_name) for model_name in config.SUPPORTED_WHISPER_MODELS]


def model_local_status(model_name: str) -> dict:
    model_dir = config.MODELS_DIR / "faster-whisper" / f"models--Systran--faster-whisper-{model_name}"
    snapshots_dir = model_dir / "snapshots"
    snapshot_paths = sorted(snapshots_dir.glob("*")) if snapshots_dir.exists() else []
    complete_snapshots = [
        path
        for path in snapshot_paths
        if path.is_dir() and (path / "model.bin").exists() and (path / "config.json").exists()
    ]
    local = bool(complete_snapshots)
    cache_path = complete_snapshots[-1] if local else model_dir
    info = config.WHISPER_MODEL_INFO.get(model_name, {})
    return {
        "name": model_name,
        "local": local,
        "status": "available" if local else "missing",
        "message": "доступна локально" if local else "не скачана, потребуется загрузка из интернета",
        "path": str(cache_path),
        "size_label": info.get("size_label", ""),
        "description": info.get("description", ""),
    }


def log_level_poll_start(source: str) -> None:
    with level_poll_lock:
        if source in level_poll_seen:
            return
        level_poll_seen.add(source)
    logger.info("Audio level polling started: source=%s interval_ms=500", source)


def log_level_poll_error(source: str, device_id: int | str | None, exc: RuntimeError) -> None:
    key = (source, str(device_id), str(exc))
    now = time.monotonic()
    with level_poll_lock:
        last_logged = level_error_log_times.get(key, 0.0)
        if now - last_logged < 15:
            return
        level_error_log_times[key] = now
    logger.warning("Audio level polling failed: source=%s device_id=%s error=%s", source, device_id, exc)


def cleanup_started_recorders() -> None:
    for item in (recorder, system_recorder):
        if item.is_recording:
            try:
                item.stop()
            except Exception:
                logger.exception("Failed to cleanup partially started recorder")


def raise_api_error(message: str, status_code: int = 400, extra: dict | None = None) -> None:
    logger.warning("API error %s: %s", status_code, message)
    detail = {"message": message}
    if extra:
        detail.update(extra)
    raise HTTPException(status_code=status_code, detail=detail)
