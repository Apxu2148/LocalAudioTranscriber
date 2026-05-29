const startRecordButton = document.querySelector("#startRecordButton");
const stopRecordButton = document.querySelector("#stopRecordButton");
const refreshDevicesButton = document.querySelector("#refreshDevicesButton");
const recordingModeSelect = document.querySelector("#recordingModeSelect");
const micDeviceRow = document.querySelector("#micDeviceRow");
const systemDeviceRow = document.querySelector("#systemDeviceRow");
const micDeviceSelect = document.querySelector("#micDeviceSelect");
const outputDeviceSelect = document.querySelector("#outputDeviceSelect");
const recordingState = document.querySelector("#recordingState");
const recordingOutput = document.querySelector("#recordingOutput");
const micLevelBlock = document.querySelector("#micLevelBlock");
const systemLevelBlock = document.querySelector("#systemLevelBlock");
const micLevelBlocks = document.querySelector("#micLevelBlocks");
const micLevelMeterFill = document.querySelector("#micLevelMeterFill");
const micRmsValue = document.querySelector("#micRmsValue");
const micPeakValue = document.querySelector("#micPeakValue");
const micLevelWarning = document.querySelector("#micLevelWarning");
const systemLevelBlocks = document.querySelector("#systemLevelBlocks");
const systemLevelMeterFill = document.querySelector("#systemLevelMeterFill");
const systemRmsValue = document.querySelector("#systemRmsValue");
const systemPeakValue = document.querySelector("#systemPeakValue");
const systemLevelWarning = document.querySelector("#systemLevelWarning");
const recordingTranscribeActions = document.querySelector("#recordingTranscribeActions");
const transcribeMicRecordingButton = document.querySelector("#transcribeMicRecordingButton");
const transcribeSystemRecordingButton = document.querySelector("#transcribeSystemRecordingButton");
const transcribeAllRecordingsButton = document.querySelector("#transcribeAllRecordingsButton");
const transcribeForm = document.querySelector("#transcribeForm");
const audioFileInput = document.querySelector("#audioFileInput");
const transcribeButton = document.querySelector("#transcribeButton");
const transcribeOutput = document.querySelector("#transcribeOutput");
const benchmarkOutput = document.querySelector("#benchmarkOutput");
const transcriptText = document.querySelector("#transcriptText");
const systemStatus = document.querySelector("#systemStatus");
const modelBadge = document.querySelector("#modelBadge");

let micLevelPollInFlight = false;
let systemLevelPollInFlight = false;
let lastRecordings = [];

function setOutput(element, message, type = "info") {
  element.textContent = message;
  element.dataset.type = type;
}

function selectedMicDeviceId() {
  return micDeviceSelect.value === "" ? null : Number(micDeviceSelect.value);
}

function selectedOutputDeviceId() {
  return outputDeviceSelect.value === "" ? null : outputDeviceSelect.value;
}

function currentMode() {
  return recordingModeSelect.value;
}

function modeUsesMic() {
  return currentMode() === "mic" || currentMode() === "both";
}

function modeUsesSystem() {
  return currentMode() === "system" || currentMode() === "both";
}

function setRecordingUi(isRecording) {
  startRecordButton.disabled = isRecording;
  stopRecordButton.disabled = !isRecording;
  recordingModeSelect.disabled = isRecording;
  micDeviceSelect.disabled = isRecording;
  outputDeviceSelect.disabled = isRecording;
  refreshDevicesButton.disabled = isRecording;
  recordingState.textContent = isRecording ? "Идет запись" : "Готово";
  recordingState.dataset.active = String(isRecording);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = payload?.detail?.message || payload?.message || "Ошибка запроса.";
    throw new Error(message);
  }

  return payload;
}

function updateLevel(level, target) {
  const levelPercent = Math.max(0, Math.min(100, Number(level.level || 0)));
  const filledBlocks = Math.round(levelPercent / 10);
  target.blocks.textContent = `${"█".repeat(filledBlocks)}${"░".repeat(10 - filledBlocks)}`;
  target.fill.style.width = `${levelPercent}%`;
  target.rms.textContent = `RMS: ${Number(level.rms || 0).toFixed(6)}`;
  target.peak.textContent = `Peak: ${Number(level.peak || 0).toFixed(6)}`;

  if (level.warning) {
    setOutput(target.warning, level.warning, "warning");
  } else {
    setOutput(target.warning, "");
  }
}

function micLevelTarget() {
  return {
    blocks: micLevelBlocks,
    fill: micLevelMeterFill,
    rms: micRmsValue,
    peak: micPeakValue,
    warning: micLevelWarning,
  };
}

function systemLevelTarget() {
  return {
    blocks: systemLevelBlocks,
    fill: systemLevelMeterFill,
    rms: systemRmsValue,
    peak: systemPeakValue,
    warning: systemLevelWarning,
  };
}

async function loadDevices() {
  const previousMicValue = micDeviceSelect.value;
  const previousOutputValue = outputDeviceSelect.value;
  micDeviceSelect.innerHTML = "";
  outputDeviceSelect.innerHTML = "";
  setOutput(recordingOutput, "Обновляю список устройств...");

  try {
    const [inputResult, outputResult] = await Promise.all([
      requestJson("/api/audio/devices"),
      requestJson("/api/audio/output-devices"),
    ]);

    fillMicDevices(inputResult, previousMicValue);
    fillOutputDevices(outputResult, previousOutputValue);
    setOutput(recordingOutput, "Список устройств обновлен.");
  } catch (error) {
    setOutput(recordingOutput, error.message, "error");
  }
}

function fillMicDevices(result, previousValue) {
  if (!result.devices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Микрофоны не найдены";
    micDeviceSelect.append(option);
    return;
  }

  for (const device of result.devices) {
    const option = document.createElement("option");
    option.value = String(device.id);
    const defaultText = device.is_default ? " по умолчанию" : "";
    option.textContent = `${device.name} [${device.input_channels} ch, ${device.default_samplerate} Hz]${defaultText}`;
    micDeviceSelect.append(option);
  }

  const defaultId = result.default_device_id;
  const values = Array.from(micDeviceSelect.options).map((option) => option.value);
  if (previousValue && values.includes(previousValue)) {
    micDeviceSelect.value = previousValue;
  } else if (defaultId !== null && values.includes(String(defaultId))) {
    micDeviceSelect.value = String(defaultId);
  }
}

function fillOutputDevices(result, previousValue) {
  if (!result.devices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Output-устройства не найдены";
    outputDeviceSelect.append(option);
    return;
  }

  for (const device of result.devices) {
    const option = document.createElement("option");
    option.value = String(device.id);
    const defaultText = device.is_default_output ? " по умолчанию" : "";
    option.textContent = `${device.name} [${device.channels} ch, ${device.default_samplerate} Hz, ${device.api_name}]${defaultText}`;
    outputDeviceSelect.append(option);
  }

  const defaultId = result.default_output_device_id;
  const values = Array.from(outputDeviceSelect.options).map((option) => option.value);
  if (previousValue && values.includes(previousValue)) {
    outputDeviceSelect.value = previousValue;
  } else if (defaultId !== null && values.includes(String(defaultId))) {
    outputDeviceSelect.value = String(defaultId);
  }
}

function updateModeUi() {
  const usesMic = modeUsesMic();
  const usesSystem = modeUsesSystem();
  micDeviceRow.hidden = !usesMic;
  micLevelBlock.hidden = !usesMic;
  systemDeviceRow.hidden = !usesSystem;
  systemLevelBlock.hidden = !usesSystem;
}

async function refreshStatus() {
  try {
    const status = await requestJson("/api/status");
    const runtime = status.transcription?.runtime_device || status.transcription?.configured_device || "auto";
    const compute = status.transcription?.runtime_compute_type || status.transcription?.configured_compute_type || "auto";
    modelBadge.textContent = `Whisper ${status.whisper_model} · ${runtime}/${compute}`;
    setRecordingUi(Boolean(status.recording));

    const ffmpeg = status.ffmpeg_found ? "ffmpeg найден" : "ffmpeg не найден";
    const microphone = status.microphone?.available
      ? `микрофон: ${status.microphone.device_name}`
      : status.microphone?.message || "микрофон недоступен";
    const systemAudio = status.system_audio?.available
      ? `системный звук: ${status.system_audio.device_name}`
      : status.system_audio?.message || "системный звук недоступен";

    systemStatus.textContent = `${ffmpeg}; ${microphone}; ${systemAudio}`;
  } catch (error) {
    systemStatus.textContent = error.message;
  }
}

async function refreshMicLevel() {
  if (micLevelPollInFlight || !modeUsesMic() || micDeviceSelect.options.length === 0) {
    return;
  }

  micLevelPollInFlight = true;
  try {
    const deviceId = selectedMicDeviceId();
    const query = deviceId === null ? "" : `?device_id=${encodeURIComponent(deviceId)}`;
    const level = await requestJson(`/api/audio/level${query}`);
    updateLevel(level, micLevelTarget());
  } catch (error) {
    setOutput(micLevelWarning, error.message, "error");
  } finally {
    micLevelPollInFlight = false;
  }
}

async function refreshSystemLevel() {
  if (systemLevelPollInFlight || !modeUsesSystem() || outputDeviceSelect.options.length === 0) {
    return;
  }

  systemLevelPollInFlight = true;
  try {
    const deviceId = selectedOutputDeviceId();
    const query = deviceId === null ? "" : `?device_id=${encodeURIComponent(deviceId)}`;
    const level = await requestJson(`/api/audio/output-level${query}`);
    updateLevel(level, systemLevelTarget());
  } catch (error) {
    setOutput(systemLevelWarning, error.message, "error");
  } finally {
    systemLevelPollInFlight = false;
  }
}

function formatRecordingDiagnostics(diagnostics) {
  const source = diagnostics.source_type === "system" ? "Системный звук" : "Микрофон";
  const device = diagnostics.source_type === "system"
    ? `${diagnostics.output_device_name} (${diagnostics.output_device_id ?? "default"})`
    : `${diagnostics.device_name} (${diagnostics.device_id ?? "default"})`;

  const lines = [
    `${source}`,
    `Файл WAV: ${diagnostics.audio_file}`,
    `Диагностика JSON: ${diagnostics.diagnostic_file}`,
    `Устройство: ${device}`,
    `Длительность: ${diagnostics.duration_sec} сек`,
    `RMS: ${Number(diagnostics.rms).toFixed(6)}`,
    `Peak: ${Number(diagnostics.peak).toFixed(6)}`,
  ];

  if (diagnostics.warnings?.length) {
    lines.push(...diagnostics.warnings);
  }

  return lines.join("\n");
}

function formatAllDiagnostics(diagnosticsList, errors = []) {
  const chunks = diagnosticsList.map(formatRecordingDiagnostics);
  if (errors.length) {
    chunks.push(`Ошибки: ${errors.join("; ")}`);
  }
  return chunks.join("\n\n");
}

function formatBenchmark(benchmark, benchmarkPath) {
  const speed = benchmark.realtime_factor ? `${benchmark.realtime_factor}x realtime` : "н/д";
  return [
    `TXT: ${benchmark.transcript_file}`,
    `JSON: ${benchmarkPath}`,
    `Модель: ${benchmark.model}`,
    `Устройство: ${benchmark.device}`,
    `Compute type: ${benchmark.compute_type}`,
    `Длительность аудио: ${benchmark.audio_duration_sec ?? "н/д"} сек`,
    `Время обработки: ${benchmark.transcribe_time_sec} сек`,
    `Скорость: ${speed}`,
  ].join("\n");
}

function updateRecordingTranscribeActions(recordings) {
  lastRecordings = recordings || [];
  const micRecording = lastRecordings.find((item) => item.source_type === "mic");
  const systemRecording = lastRecordings.find((item) => item.source_type === "system");
  recordingTranscribeActions.hidden = lastRecordings.length === 0;
  transcribeMicRecordingButton.hidden = !micRecording;
  transcribeSystemRecordingButton.hidden = !systemRecording;
  transcribeAllRecordingsButton.hidden = lastRecordings.length < 2;
}

async function transcribeRecordedDiagnostics(diagnostics) {
  const result = await requestJson("/api/transcribe/file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: diagnostics.audio_file,
      source_type: diagnostics.source_type,
    }),
  });

  transcriptText.value = result.text;
  setOutput(transcribeOutput, `Текст сохранен: ${result.transcript_path}`, "success");
  setOutput(benchmarkOutput, formatBenchmark(result.benchmark, result.benchmark_path), "success");
  await refreshStatus();
  return result;
}

async function transcribeRecordingByType(sourceType) {
  const diagnostics = lastRecordings.find((item) => item.source_type === sourceType);
  if (!diagnostics) {
    setOutput(transcribeOutput, "Файл записи не найден.", "error");
    return;
  }

  setOutput(transcribeOutput, "Транскрибирую записанный файл...");
  setOutput(benchmarkOutput, "");
  await transcribeRecordedDiagnostics(diagnostics);
}

async function transcribeAllRecordings() {
  if (lastRecordings.length < 2) {
    setOutput(transcribeOutput, "Для этого режима нужно два файла записи.", "error");
    return;
  }

  setOutput(transcribeOutput, "Транскрибирую оба файла по очереди...");
  setOutput(benchmarkOutput, "");
  const summaries = [];
  const texts = [];

  for (const diagnostics of lastRecordings) {
    const result = await transcribeRecordedDiagnostics(diagnostics);
    summaries.push(`${diagnostics.source_type}: ${result.transcript_path}`);
    texts.push(`### ${diagnostics.source_type}\n${result.text}`);
  }

  transcriptText.value = texts.join("\n\n");
  setOutput(transcribeOutput, summaries.join("\n"), "success");
}

startRecordButton.addEventListener("click", async () => {
  setOutput(recordingOutput, "Запускаю запись...");
  updateRecordingTranscribeActions([]);
  startRecordButton.disabled = true;

  try {
    const result = await requestJson("/api/record/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: currentMode(),
        mic_device_id: selectedMicDeviceId(),
        output_device_id: selectedOutputDeviceId(),
      }),
    });
    setRecordingUi(true);
    const paths = result.recordings.map((item) => `${item.source_type}: ${item.file_path}`).join("\n");
    setOutput(recordingOutput, `Запись идет.\n${paths}`, "success");
  } catch (error) {
    setRecordingUi(false);
    setOutput(recordingOutput, error.message, "error");
  }
});

stopRecordButton.addEventListener("click", async () => {
  setOutput(recordingOutput, "Сохраняю запись...");
  stopRecordButton.disabled = true;

  try {
    const result = await requestJson("/api/record/stop", { method: "POST" });
    setRecordingUi(false);
    const diagnosticsList = result.diagnostics_list || [result.diagnostics];
    const hasWarnings = diagnosticsList.some((item) => item?.warnings?.length) || Boolean(result.errors?.length);
    setOutput(recordingOutput, formatAllDiagnostics(diagnosticsList, result.errors), hasWarnings ? "warning" : "success");
    updateRecordingTranscribeActions(diagnosticsList);
  } catch (error) {
    setRecordingUi(false);
    setOutput(recordingOutput, error.message, "error");
  }
});

refreshDevicesButton.addEventListener("click", loadDevices);
recordingModeSelect.addEventListener("change", () => {
  updateModeUi();
  refreshMicLevel();
  refreshSystemLevel();
});
micDeviceSelect.addEventListener("change", refreshMicLevel);
outputDeviceSelect.addEventListener("change", refreshSystemLevel);
transcribeMicRecordingButton.addEventListener("click", () => transcribeRecordingByType("mic"));
transcribeSystemRecordingButton.addEventListener("click", () => transcribeRecordingByType("system"));
transcribeAllRecordingsButton.addEventListener("click", transcribeAllRecordings);

transcribeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = audioFileInput.files[0];
  if (!file) {
    setOutput(transcribeOutput, "Выберите аудиофайл.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  transcribeButton.disabled = true;
  transcriptText.value = "";
  setOutput(transcribeOutput, "Транскрибирую аудио...");
  setOutput(benchmarkOutput, "");

  try {
    const result = await requestJson("/api/transcribe", {
      method: "POST",
      body: formData,
    });

    transcriptText.value = result.text;
    setOutput(transcribeOutput, `Текст сохранен: ${result.transcript_path}`, "success");
    setOutput(benchmarkOutput, formatBenchmark(result.benchmark, result.benchmark_path), "success");
    await refreshStatus();
  } catch (error) {
    setOutput(transcribeOutput, error.message, "error");
  } finally {
    transcribeButton.disabled = false;
  }
});

async function boot() {
  updateModeUi();
  await loadDevices();
  await refreshStatus();
  await refreshMicLevel();
  await refreshSystemLevel();
}

boot();
setInterval(refreshMicLevel, 500);
setInterval(refreshSystemLevel, 500);
setInterval(refreshStatus, 5000);
