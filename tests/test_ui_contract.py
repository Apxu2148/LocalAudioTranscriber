import re
import unittest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


class UiContractTests(unittest.TestCase):
    def test_unified_transcription_block_and_custom_file_pickers_exist(self) -> None:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "queueSection",
            "transcriptionSources",
            "globalQueuePanel",
            "transcribeMicRecordingButton",
            "transcribeSystemRecordingButton",
            "transcribeAllRecordingsButton",
            "audioFilePickerButton",
            "audioFilePickerText",
            "refreshMicDevicesButton",
            "refreshOutputDevicesButton",
            "queueFilePickerButton",
            "queueFilePickerText",
            "queueStartButton",
            "queueClearButton",
            "queueMetrics",
            "queueProgress",
            "transcriptText",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertGreaterEqual(html.count('class="native-file-input"'), 3)
        self.assertNotIn("operation-overlay", html)

    def test_ui_uses_queue_endpoints_instead_of_direct_transcription(self) -> None:
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('"/api/queue/add-recordings"', app_js)
        self.assertIn('"/api/queue/add-files"', app_js)
        self.assertIn('"/api/queue/add-urls"', app_js)
        self.assertIn('"/api/queue/start"', app_js)
        self.assertIn("latestTechnicalItem.technical_details", app_js)
        self.assertIn("/api/transcripts/read", app_js)
        self.assertIn("loadTranscript(file.name, true)", app_js)
        self.assertIn('transcriptText.value = result.text || "";', app_js)
        self.assertNotIn('"/api/transcribe"', app_js)
        self.assertNotIn('"/api/transcribe/file"', app_js)

    def test_file_benchmark_order_and_recording_help_location(self) -> None:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index('id="recordingSection"'), html.index('id="queueSection"'))
        self.assertLess(html.index('id="transcribeForm"'), html.index('id="benchmarkSection"'))
        self.assertLess(html.index('id="queueSection"'), html.index('id="benchmarkSection"'))
        self.assertLess(html.index('id="filesSection"'), html.index('id="benchmarkSection"'))
        self.assertLess(html.index('class="recording-device-grid"'), html.index('id="helpSection"'))
        self.assertLess(html.index('id="helpSection"'), html.index('id="queueSection"'))
        self.assertIn('data-i18n="helpDeviceSummary"', html)

    def test_tour_targets_current_html_elements(self) -> None:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        tour_js = (STATIC_DIR / "tour.js").read_text(encoding="utf-8")
        selectors = re.findall(r'\["(#[A-Za-z][A-Za-z0-9_-]*)",\s*"tour', tour_js)
        self.assertGreaterEqual(len(selectors), 10)
        for selector in selectors:
            self.assertIn(f'id="{selector[1:]}"', html, selector)


if __name__ == "__main__":
    unittest.main()
