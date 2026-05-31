import unittest
from pathlib import Path


class I18nTests(unittest.TestCase):
    def test_ru_en_dictionary_and_default_language_exist(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "static" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn('const DEFAULT_LANGUAGE = "ru"', content)
        self.assertIn('const STORAGE_KEY = "latUiLanguage"', content)
        self.assertIn("ru: {", content)
        self.assertIn("en: {", content)
        for key in ("settingsTitle", "queueTitle", "benchmarkTitle", "modelDownloading", "failedFetch"):
            self.assertGreaterEqual(content.count(f"{key}:"), 2, key)


if __name__ == "__main__":
    unittest.main()
