import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
import shutil
import threading

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import config
from .audio_recorder import AudioRecorder
from .system_audio_recorder import SystemAudioRecorder
from .transcriber import AudioTranscriber, ModelLoadError
from .utils import setup_logging, timestamp_for_filename, write_json_file, write_text_file


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Local Audio Transcriber")
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

recorder = AudioRecorder()
system_recorder = SystemAudioRecorder()
transcriber = AudioTranscriber()
recording_lock = threading.Lock()
active_recording_mode: str | None = None
level_poll_lock = threading.Lock()
level_poll_seen: set[str] = set()
level_error_log_times: dict[tuple[str, str, str], float] = {}


class StartRecordingRequest(BaseModel):
    mode: str = "mic"
    device_id: int | None = None
    mic_device_id: int | None = None
    output_device_id: str | None = None


class TranscribeFileRequest(BaseModel):
    file_path: str
    source_type: str | None = None
    model: str | None = None


class OpenFolderRequest(BaseModel):
    folder: str


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Application started: model=%s device=%s compute_type=%s data_dir=%s recordings_dir=%s transcripts_dir=%s",
        config.WHISPER_MODEL,
        config.WHISPER_DEVICE,
        config.WHISPER_COMPUTE_TYPE,
        config.DATA_DIR,
        config.RECORDINGS_DIR,
        config.TRANSCRIPTS_DIR,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/status")
def status() -> dict:
    transcription = transcriber.status()
    return {
        "recording": recorder.is_recording or system_recorder.is_recording,
        "recording_mode": active_recording_mode,
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
        "supported_formats": sorted(config.SUPPORTED_AUDIO_EXTENSIONS),
    }


@app.get("/api/models")
def models() -> dict:
    statuses = model_statuses()
    logger.info("Model local availability checked: models=%s", statuses)
    return {"models": statuses}


@app.get("/api/storage")
def storage() -> dict:
    return {
        "recordings": {
            "path": str(config.RECORDINGS_DIR),
            "files": recent_files(config.RECORDINGS_DIR),
        },
        "transcripts": {
            "path": str(config.TRANSCRIPTS_DIR),
            "files": recent_files(config.TRANSCRIPTS_DIR),
        },
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

    global active_recording_mode
    with recording_lock:
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
        raise_api_error(str(exc), status_code=500)

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

    global active_recording_mode
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

    if not diagnostics_list and errors:
        raise_api_error("; ".join(errors), status_code=500)

    if not diagnostics_list:
        raise_api_error("Запись не запущена.")

    logger.info("Recording stop finished: mode=%s files=%s errors=%s", mode, len(diagnostics_list), errors)

    return {
        "message": "Запись сохранена.",
        "recording": False,
        "mode": mode,
        "file_path": diagnostics_list[0]["audio_file"],
        "file_name": Path(diagnostics_list[0]["audio_file"]).name,
        "diagnostics": diagnostics_list[0],
        "diagnostics_list": diagnostics_list,
        "errors": errors,
    }


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile | None = File(default=None),
    model: str | None = Form(default=None),
) -> dict:
    selected_model = validate_whisper_model(model)

    if file is None or not file.filename:
        raise_api_error("Выберите аудиофайл для транскрибации.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in config.SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(config.SUPPORTED_AUDIO_EXTENSIONS))
        raise_api_error(f"Формат {suffix or '(без расширения)'} не поддерживается. Доступны: {allowed}.")

    upload_path = config.UPLOADS_DIR / f"upload_{timestamp_for_filename()}{suffix}"

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
        raise_api_error("Загруженный файл пустой.")

    logger.info("Uploaded file saved for transcription: file=%s model=%s", upload_path, selected_model)
    return await transcribe_path(upload_path, "transcript", selected_model)


@app.post("/api/transcribe/file")
async def transcribe_recorded_file(payload: TranscribeFileRequest) -> dict:
    audio_path = validate_local_audio_path(payload.file_path)
    transcript_prefix = transcript_prefix_for(audio_path, payload.source_type)
    selected_model = validate_whisper_model(payload.model)
    return await transcribe_path(audio_path, transcript_prefix, selected_model)


async def transcribe_path(audio_path: Path, transcript_prefix: str, model_name: str) -> dict:
    logger.info("Transcription request accepted: file=%s prefix=%s model=%s", audio_path, transcript_prefix, model_name)
    local_model = model_local_status(model_name)
    logger.info("Selected model: model=%s local_available=%s cache_path=%s", model_name, local_model["local"], local_model["path"])
    if not local_model["local"]:
        logger.info("Model is not available locally; first download may be attempted: model=%s", model_name)

    try:
        result = await run_in_threadpool(transcriber.transcribe, audio_path, model_name)
        transcript_text = result.text or "Распознаваемая речь не найдена."
        transcript_path = write_text_file(
            config.TRANSCRIPTS_DIR,
            f"{transcript_prefix}_{safe_filename_part(result.model)}",
            transcript_text,
        )
        benchmark = {
            "transcript_file": str(transcript_path),
            "audio_file": str(audio_path),
            "source_audio": str(audio_path),
            "model": result.model,
            "device": result.device,
            "compute_type": result.compute_type,
            "audio_duration_sec": round(result.audio_duration_sec, 3) if result.audio_duration_sec is not None else None,
            "transcribe_time_sec": round(result.transcribe_time_sec, 3),
            "realtime_factor": round(result.realtime_factor, 3) if result.realtime_factor is not None else None,
            "segments_count": len(result.segments),
            "load_errors": result.load_errors,
        }
        benchmark_path = write_json_file(transcript_path.with_suffix(".json"), benchmark)
    except ModelLoadError as exc:
        logger.exception(
            "Model load failed: file=%s model=%s technical_details=%s",
            audio_path,
            model_name,
            exc.technical_details,
        )
        raise_api_error(
            exc.user_message,
            status_code=500,
            extra={"technical_details": exc.technical_details},
        )
    except RuntimeError as exc:
        logger.exception("Transcription failed: file=%s model=%s", audio_path, model_name)
        raise_api_error(str(exc), status_code=500)
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        raise_api_error(f"Непредвиденная ошибка транскрибации: {exc}", status_code=500)

    logger.info(
        "Transcription saved: file=%s transcript=%s benchmark=%s model=%s device=%s compute_type=%s",
        audio_path,
        transcript_path,
        benchmark_path,
        result.model,
        result.device,
        result.compute_type,
    )

    return {
        "message": "Транскрибация завершена.",
        "text": transcript_text,
        "segments": result.segments,
        "audio_file_path": str(audio_path),
        "uploaded_file_path": str(audio_path),
        "transcript_path": str(transcript_path),
        "benchmark_path": str(benchmark_path),
        "benchmark": benchmark,
    }


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


def transcript_prefix_for(audio_path: Path, source_type: str | None) -> str:
    source = (source_type or "").strip().lower()
    stem = audio_path.stem.lower()
    if source == "system" or stem.startswith("system_"):
        return "transcript_system"
    if source == "mic" or stem.startswith("mic_") or stem.startswith("recording_"):
        return "transcript_mic"
    return "transcript"


def recent_files(directory: Path, limit: int = 5) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    for path in directory.iterdir():
        if not path.is_file() or path.name == ".gitkeep":
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


def safe_filename_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())


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
