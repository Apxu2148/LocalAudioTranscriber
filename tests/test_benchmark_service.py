import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.benchmark_service import BenchmarkService
from app.transcript_store import TranscriptStore


PROJECT_TMP = Path(__file__).resolve().parents[1] / "tmp"


class FakeTranscriber:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.cached: tuple[str, str] | None = None

    def clear_model(self) -> None:
        self.clear_calls += 1
        self.cached = None

    def is_model_cached(self, model: str, device: str) -> bool:
        return self.cached == (model, device)

    def transcribe(self, _path: Path, model: str, device: str):
        self.cached = (model, device)
        return SimpleNamespace(
            text="benchmark",
            segments=[],
            model=model,
            device=device,
            compute_type="int8",
            audio_duration_sec=10,
            model_load_time_sec=0.1,
            transcription_time_sec=1,
        )


class BenchmarkServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefix = f"codex_benchmark_{uuid4().hex}"
        self.source = PROJECT_TMP / f"{self.prefix}.wav"
        self.source.write_bytes(b"test")
        self.transcriber = FakeTranscriber()
        self.service = BenchmarkService(
            transcriber=self.transcriber,
            transcript_store=TranscriptStore(PROJECT_TMP),
        )
        self.source_id = self.service.register_source(self.source, f"{self.prefix}.wav")["source_id"]

    def tearDown(self) -> None:
        self.service.wait(timeout=1)
        for path in PROJECT_TMP.glob(f"{self.prefix}*"):
            path.unlink(missing_ok=True)

    def test_cold_then_warm_reuses_loaded_model(self) -> None:
        self.service.start(source_id=self.source_id, model="small", device="cpu", mode="cold")
        self.service.wait(timeout=2)
        self.assertFalse(self.service.is_running)
        self.assertEqual(1, self.transcriber.clear_calls)
        self.assertEqual("completed", self.service.status()["status"])

        self.service.start(source_id=self.source_id, model="small", device="cpu", mode="warm")
        self.service.wait(timeout=2)
        self.assertFalse(self.service.is_running)
        result = self.service.status()["results"]["cpu"]
        self.assertEqual("warm", result["benchmark_mode"])
        self.assertIn("total_wall_time_sec", result)
        self.assertIn("save_time_sec", result)

    def test_warm_requires_matching_cold_run(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Cold Run"):
            self.service.start(source_id=self.source_id, model="small", device="cpu", mode="warm")


if __name__ == "__main__":
    unittest.main()
