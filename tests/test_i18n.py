import re
import unittest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def dictionary_keys(content: str, language: str) -> set[str]:
    if language == "ru":
        block = content.split("ru: {", 1)[1].split("    en: {", 1)[0]
    else:
        block = content.split("    en: {", 1)[1].split("  };", 1)[0]
    return set(re.findall(r"^\s{6}([A-Za-z][A-Za-z0-9_]*):", block, flags=re.MULTILINE))


class I18nTests(unittest.TestCase):
    def test_ru_en_dictionary_keys_match_and_default_language_is_preserved(self) -> None:
        content = (STATIC_DIR / "i18n.js").read_text(encoding="utf-8")
        self.assertIn('const DEFAULT_LANGUAGE = "ru"', content)
        self.assertIn('const STORAGE_KEY = "latUiLanguage"', content)
        ru_keys = dictionary_keys(content, "ru")
        en_keys = dictionary_keys(content, "en")
        self.assertEqual(ru_keys, en_keys)
        for key in (
            "transcriptionTitle",
            "addLatestMic",
            "startTranscription",
            "clearGlobalQueue",
            "chooseFile",
            "noFileSelected",
            "tourSourcesText",
            "refreshMicDevices",
            "refreshOutputDevices",
            "micDevicesUpdated",
            "outputDevicesUpdated",
            "refreshMicDevicesFailed",
            "refreshOutputDevicesFailed",
            "microphoneSwitched",
            "outputDeviceSwitched",
            "microphoneSwitchFailed",
            "outputDeviceSwitchFailed",
            "helpDeviceSummary",
            "helpSystemOutputText",
            "helpDeviceNamesText",
            "helpLoopbackLimitText",
            "helpSilentSystemTitle",
            "helpSilentSystemWindows",
            "helpSilentSystemMeetingApp",
            "helpSilentSystemSameDevice",
            "helpSilentSystemRefresh",
            "helpSilentSystemTryAnother",
            "helpSilentSystemRuntime",
            "helpOwnVoiceText",
        ):
            self.assertIn(key, en_keys)

    def test_html_and_dynamic_i18n_keys_exist_in_both_dictionaries(self) -> None:
        i18n = (STATIC_DIR / "i18n.js").read_text(encoding="utf-8")
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        keys = dictionary_keys(i18n, "en")
        html_keys = set(re.findall(r'data-i18n(?:-title|-aria-label|-placeholder)?="([A-Za-z][A-Za-z0-9_]*)"', html))
        app_keys = set(re.findall(r'(?<![A-Za-z0-9_$])t\("([A-Za-z][A-Za-z0-9_]*)"', app_js))
        self.assertFalse((html_keys | app_keys) - keys)

    def test_user_facing_static_markup_and_app_logic_do_not_embed_russian(self) -> None:
        for filename in ("index.html", "app.js", "tour.js"):
            content = (STATIC_DIR / filename).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"[А-Яа-яЁё]", content), filename)


if __name__ == "__main__":
    unittest.main()
