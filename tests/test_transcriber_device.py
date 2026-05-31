import unittest
from unittest.mock import patch

from app.transcriber import AudioTranscriber


class TranscriberDeviceTests(unittest.TestCase):
    def test_explicit_cuda_unavailable_returns_readable_error(self) -> None:
        transcriber = AudioTranscriber()
        with patch.object(transcriber, "_cuda_device_count", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "GPU/CUDA"):
                transcriber._get_model("small", "cuda")

    def test_cpu_preference_skips_cuda_and_is_cached(self) -> None:
        transcriber = AudioTranscriber()
        fake_model = object()
        with patch.object(transcriber, "_try_load_model", return_value=fake_model) as loader:
            self.assertIs(fake_model, transcriber._get_model("small", "cpu"))
        self.assertEqual("cpu", loader.call_args.args[1])

    def test_normalizes_auto_cpu_and_cuda(self) -> None:
        transcriber = AudioTranscriber()
        for device in ("auto", "cpu", "cuda"):
            self.assertEqual(device, transcriber._normalize_device_preference(device))
        with self.assertRaisesRegex(RuntimeError, "auto, cpu, cuda"):
            transcriber._normalize_device_preference("invalid")


if __name__ == "__main__":
    unittest.main()
