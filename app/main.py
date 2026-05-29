import logging
from pathlib import Path
import shutil
import threading

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import config
from .audio_recorder import AudioRecorder
from .system_audio_recorder import SystemAudioRecorder
from .transcriber import AudioTranscriber
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


class StartRecordingRequest(BaseModel):
    mode: str = "mic"
    device_id: int | None = None
    mic_device_id: int | None = None
    output_device_id: str | None = None


class TranscribeFileRequest(BaseModel):
    file_path: str
    source_type: str | None = None


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Application started: model=%s device=%s compute_type=%s data_dir=%s",
        config.WHISPER_MODEL,
        config.WHISPER_DEVICE,
        config.WHISPER_COMPUTE_TYPE,
        config.DATA_DIR,
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
        "whisper_language": config.WHISPER_LANGUAGE,
        "microphone": recorder.microphone_status(),
        "system_audio": system_recorder.output_status(),
        "audio_level": recorder.get_level() if recorder.is_recording else None,
        "system_audio_level": system_recorder.get_level() if system_recorder.is_recording else None,
        "transcription": transcription,
        "supported_formats": sorted(config.SUPPORTED_AUDIO_EXTENSIONS),
    }


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
    try:
        return recorder.measure_input_level(device_id)
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)


@app.get("/api/audio/output-level")
def output_audio_level(device_id: str | None = None) -> dict:
    try:
        return system_recorder.measure_output_level(device_id)
    except RuntimeError as exc:
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

    logger.info("Start recording request: mode=%s mic_device_id=%s output_device_id=%s", mode, mic_device_id, output_device_id)

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
        raise_api_error(str(exc))

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
async def transcribe_audio(file: UploadFile | None = File(default=None)) -> dict:
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

    return await transcribe_path(upload_path, "transcript")


@app.post("/api/transcribe/file")
async def transcribe_recorded_file(payload: TranscribeFileRequest) -> dict:
    audio_path = validate_local_audio_path(payload.file_path)
    transcript_prefix = transcript_prefix_for(audio_path, payload.source_type)
    return await transcribe_path(audio_path, transcript_prefix)


async def transcribe_path(audio_path: Path, transcript_prefix: str) -> dict:
    try:
        result = await run_in_threadpool(transcriber.transcribe, audio_path)
        transcript_text = result.text or "Распознаваемая речь не найдена."
        transcript_path = write_text_file(config.TRANSCRIPTS_DIR, transcript_prefix, transcript_text)
        benchmark = {
            "transcript_file": str(transcript_path),
            "audio_file": str(audio_path),
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
    except RuntimeError as exc:
        raise_api_error(str(exc), status_code=500)
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        raise_api_error(f"Непредвиденная ошибка транскрибации: {exc}", status_code=500)

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


def cleanup_started_recorders() -> None:
    for item in (recorder, system_recorder):
        if item.is_recording:
            try:
                item.stop()
            except Exception:
                logger.exception("Failed to cleanup partially started recorder")


def raise_api_error(message: str, status_code: int = 400) -> None:
    logger.warning("API error %s: %s", status_code, message)
    raise HTTPException(status_code=status_code, detail={"message": message})
