import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BASE_DIR / "app"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
UPLOADS_DIR = DATA_DIR / "uploads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
LOGS_DIR = DATA_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"
TEMP_DIR = BASE_DIR / "tmp"

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "auto")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "ru").strip() or None
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "true").strip().lower() in {"1", "true", "yes", "on"}
WHISPER_CONDITION_ON_PREVIOUS_TEXT = (
    os.getenv("WHISPER_CONDITION_ON_PREVIOUS_TEXT", "false").strip().lower() in {"1", "true", "yes", "on"}
)

GPU_COMPUTE_TYPE_CANDIDATES = tuple(
    value.strip()
    for value in os.getenv("WHISPER_GPU_COMPUTE_TYPES", "float16,int8_float16,int8").split(",")
    if value.strip()
)
CPU_COMPUTE_TYPE = os.getenv("WHISPER_CPU_COMPUTE_TYPE", "int8")

DEFAULT_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
DEFAULT_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
RECORDING_BLOCKSIZE = int(os.getenv("AUDIO_RECORDING_BLOCKSIZE", "2048"))
SYSTEM_SAMPLE_RATE = int(os.getenv("SYSTEM_AUDIO_SAMPLE_RATE", "48000"))
SYSTEM_CHANNELS = int(os.getenv("SYSTEM_AUDIO_CHANNELS", "2"))
SYSTEM_RECORDING_BLOCKSIZE = int(os.getenv("SYSTEM_AUDIO_RECORDING_BLOCKSIZE", "4096"))
LEVEL_PROBE_SECONDS = float(os.getenv("AUDIO_LEVEL_PROBE_SECONDS", "0.2"))
SIGNAL_CHECK_SECONDS = float(os.getenv("AUDIO_SIGNAL_CHECK_SECONDS", "3.0"))
SILENCE_RMS_THRESHOLD = float(os.getenv("SILENCE_RMS_THRESHOLD", "0.0015"))
SILENCE_PEAK_THRESHOLD = float(os.getenv("SILENCE_PEAK_THRESHOLD", "0.01"))

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}


def ensure_directories() -> None:
    for path in (
        DATA_DIR,
        RECORDINGS_DIR,
        UPLOADS_DIR,
        TRANSCRIPTS_DIR,
        LOGS_DIR,
        MODELS_DIR,
        TEMP_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


ensure_directories()

# Keep runtime caches and temp files in the project folder.
os.environ["TMP"] = str(TEMP_DIR)
os.environ["TEMP"] = str(TEMP_DIR)
os.environ["TMPDIR"] = str(TEMP_DIR)
os.environ["HF_HOME"] = str(MODELS_DIR / "huggingface")
os.environ["HF_HUB_CACHE"] = str(MODELS_DIR / "huggingface" / "hub")
