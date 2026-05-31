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
const whisperModelSelect = document.querySelector("#whisperModelSelect");
const modelAvailabilityOutput = document.querySelector("#modelAvailabilityOutput");
const modelDownloadWarning = document.querySelector("#modelDownloadWarning");
const transcribeButton = document.querySelector("#transcribeButton");
const transcribeOutput = document.querySelector("#transcribeOutput");
const transcribeTechnicalDetails = document.querySelector("#transcribeTechnicalDetails");
const transcribeTechnicalText = document.querySelector("#transcribeTechnicalText");
const benchmarkOutput = document.querySelector("#benchmarkOutput");
const transcriptText = document.querySelector("#transcriptText");
const systemStatus = document.querySelector("#systemStatus");
const modelBadge = document.querySelector("#modelBadge");
const runtimeModel = document.querySelector("#runtimeModel");
const runtimeDevice = document.querySelector("#runtimeDevice");
const runtimeCompute = document.querySelector("#runtimeCompute");
const runtimeSpeed = document.querySelector("#runtimeSpeed");
const recordingsPath = document.querySelector("#recordingsPath");
const transcriptsPath = document.querySelector("#transcriptsPath");
const recordingsFileList = document.querySelector("#recordingsFileList");
const transcriptsFileList = document.querySelector("#transcriptsFileList");
const openRecordingsButton = document.querySelector("#openRecordingsButton");
const openTranscriptsButton = document.querySelector("#openTranscriptsButton");
const toastRegion = document.querySelector("#toastRegion");
const appVersion = document.querySelector("#appVersion");
const recordingTimer = document.querySelector("#recordingTimer");
const queueAddForm = document.querySelector("#queueAddForm");
const queueFileInput = document.querySelector("#queueFileInput");
const queueAddButton = document.querySelector("#queueAddButton");
const queueStartButton = document.querySelector("#queueStartButton");
const queueStopButton = document.querySelector("#queueStopButton");
const queueClearButton = document.querySelector("#queueClearButton");
const queueRetryButton = document.querySelector("#queueRetryButton");
const queueTotal = document.querySelector("#queueTotal");
const queueCompleted = document.querySelector("#queueCompleted");
const queueFailed = document.querySelector("#queueFailed");
const queuePending = document.querySelector("#queuePending");
const queueCurrent = document.querySelector("#queueCurrent");
const queueElapsed = document.querySelector("#queueElapsed");
const queueEta = document.querySelector("#queueEta");
const queueProgress = document.querySelector("#queueProgress");
const queueProgressText = document.querySelector("#queueProgressText");
const queueOutput = document.querySelector("#queueOutput");
const queueList = document.querySelector("#queueList");

let micLevelPollInFlight = false;
let systemLevelPollInFlight = false;
let lastRecordings = [];
let isTranscribing = false;
let localTranscriptionActive = false;
let isRecording = false;
let modelStatusByName = new Map();
let recordingStartedAtMs = null;
let lastRecordingDurationSec = null;
let queueActive = false;
let previousQueueStatus = "empty";

class ApiError extends Error {
  constructor(message, technicalDetails = "") {
    super(message);
    this.name = "ApiError";
    this.technicalDetails = technicalDetails;
  }
}

function setOutput(element, message, type = "info") {
  element.textContent = message;
  element.dataset.type = type;
}

function setAppState(message, type = "idle") {
  recordingState.textContent = message;
  recordingState.dataset.type = type;
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.dataset.type = type;
  toast.textContent = message;
  toastRegion.append(toast);

  window.setTimeout(() => {
    toast.dataset.hiding = "true";
    window.setTimeout(() => toast.remove(), 180);
  }, 4200);
}

function selectedMicDeviceId() {
  return micDeviceSelect.value === "" ? null : Number(micDeviceSelect.value);
}

function selectedOutputDeviceId() {
  return outputDeviceSelect.value === "" ? null : outputDeviceSelect.value;
}

function selectedModel() {
  return whisperModelSelect.value || "small";
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

function hasSelectableDevice(select) {
  return Array.from(select.options).some((option) => !option.disabled && option.value !== "");
}

function setRecordingUi(recording) {
  isRecording = recording;
  startRecordButton.disabled = recording || isTranscribing || queueActive;
  stopRecordButton.disabled = !recording;
  recordingModeSelect.disabled = recording;
  micDeviceSelect.disabled = recording;
  outputDeviceSelect.disabled = recording;
  refreshDevicesButton.disabled = recording;

  if (!isTranscribing) {
    setAppState(recording ? "Идет запись" : "Готово к записи", recording ? "active" : "idle");
  }
}

async function requestJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError("Не удалось получить данные от локального сервера. Обновите страницу Ctrl+F5 или перезапустите run.bat.");
  }
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = payload?.detail?.message || payload?.message || "Ошибка запроса.";
    const technicalDetails = payload?.detail?.technical_details || payload?.technical_details || "";
    throw new ApiError(message, technicalDetails);
  }

  return payload;
}

function formatElapsed(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return [hours, minutes, remainder].map((value) => String(value).padStart(2, "0")).join(":");
}

function updateRecordingTimerUi() {
  if (recordingStartedAtMs !== null) {
    const elapsed = (Date.now() - recordingStartedAtMs) / 1000;
    recordingTimer.textContent = `Запись идет: ${formatElapsed(elapsed)}`;
    return;
  }

  recordingTimer.textContent = lastRecordingDurationSec === null
    ? "Последняя запись: --:--:--"
    : `Последняя запись: ${formatElapsed(lastRecordingDurationSec)}`;
}

function syncRecordingTimer(status) {
  if (status.recording) {
    const elapsed = Number(status.recording_elapsed_sec || 0);
    recordingStartedAtMs = Date.now() - elapsed * 1000;
  } else {
    recordingStartedAtMs = null;
    if (status.last_recording_duration_sec !== null && status.last_recording_duration_sec !== undefined) {
      lastRecordingDurationSec = Number(status.last_recording_duration_sec);
    }
  }
  updateRecordingTimerUi();
}

function updateLevel(level, target, kind) {
  const levelPercent = Math.max(0, Math.min(100, Number(level.level || 0)));
  const filledBlocks = Math.round(levelPercent / 10);
  target.blocks.textContent = `${"█".repeat(filledBlocks)}${"░".repeat(10 - filledBlocks)}`;
  target.fill.style.width = `${levelPercent}%`;
  target.rms.textContent = `RMS: ${Number(level.rms || 0).toFixed(6)}`;
  target.peak.textContent = `Peak: ${Number(level.peak || 0).toFixed(6)}`;

  const message = formatLevelMessage(kind, level);
  const details = level.warning ? `${message}\n${level.warning}` : message;
  setOutput(target.warning, details, level.has_signal ? "success" : "warning");
}

function resetLevel(target, message, type = "warning") {
  target.blocks.textContent = "░░░░░░░░░░";
  target.fill.style.width = "0%";
  target.rms.textContent = "RMS: 0.000000";
  target.peak.textContent = "Peak: 0.000000";
  setOutput(target.warning, message, type);
}

function formatLevelMessage(kind, level) {
  const recordingPrefix = level.recording ? "Идет запись." : "Запись не ведется.";

  if (kind === "mic") {
    return level.has_signal
      ? `${recordingPrefix} Микрофон слышит звук.`
      : `${recordingPrefix} Микрофон не слышит звук.`;
  }

  return level.has_signal
    ? `${recordingPrefix} Системный звук слышен.`
    : `${recordingPrefix} Системный звук не слышен.`;
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
    option.disabled = true;
    option.selected = true;
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
    option.disabled = true;
    option.selected = true;
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
  micDeviceRow.dataset.active = String(modeUsesMic());
  systemDeviceRow.dataset.active = String(modeUsesSystem());
  micLevelBlock.dataset.active = String(modeUsesMic());
  systemLevelBlock.dataset.active = String(modeUsesSystem());
}

async function refreshStatus() {
  try {
    const status = await requestJson("/api/status");
    const transcription = status.transcription || {};
    const runtime = transcription.runtime_device || transcription.configured_device || "auto";
    const compute = transcription.runtime_compute_type || transcription.configured_compute_type || "auto";
    const model = transcription.active_model || transcription.loaded_model || selectedModel() || status.whisper_model;

    modelBadge.textContent = `Whisper ${model} · ${runtime}/${compute}`;
    updateRuntimeDetails({
      model,
      device: runtime,
      compute_type: compute,
      realtime_factor: null,
    });

    if (!whisperModelSelect.dataset.initialized && status.whisper_models?.includes(status.whisper_model)) {
      whisperModelSelect.value = status.whisper_model;
      whisperModelSelect.dataset.initialized = "true";
    }
    if (status.whisper_model_status) {
      applyModelStatuses(status.whisper_model_status);
    }

    appVersion.textContent = `Версия: ${status.app_version || "неизвестна"}`;
    syncRecordingTimer(status);
    isTranscribing = localTranscriptionActive || Boolean(transcription.in_progress);
    setRecordingUi(Boolean(status.recording));
    updateRecordingTranscribeActions(lastRecordings);

    if (isTranscribing) {
      setAppState("Транскрибация выполняется", "active");
    }

    const ffmpeg = status.ffmpeg_found ? "ffmpeg найден" : "ffmpeg не найден";
    systemStatus.textContent = `${availabilityText(status)}; ${ffmpeg}`;
  } catch (error) {
    systemStatus.textContent = error.message;
  }
}

function availabilityText(status) {
  const micAvailable = Boolean(status.microphone?.available);
  const systemAvailable = Boolean(status.system_audio?.available);

  if (micAvailable && systemAvailable) {
    return "Микрофон доступен, системный звук доступен";
  }
  if (!micAvailable && systemAvailable) {
    return "Микрофон недоступен, системный звук доступен";
  }
  if (micAvailable && !systemAvailable) {
    return "Микрофон доступен, системный звук недоступен";
  }
  return "Микрофон и системный звук недоступны";
}

async function refreshMicLevel() {
  if (micLevelPollInFlight) {
    return;
  }

  if (!hasSelectableDevice(micDeviceSelect)) {
    resetLevel(micLevelTarget(), "Устройство микрофона не выбрано.");
    return;
  }

  micLevelPollInFlight = true;
  try {
    const deviceId = selectedMicDeviceId();
    const query = deviceId === null ? "" : `?device_id=${encodeURIComponent(deviceId)}`;
    const level = await requestJson(`/api/audio/level${query}`);
    updateLevel(level, micLevelTarget(), "mic");
  } catch (error) {
    resetLevel(
      micLevelTarget(),
      `Нет доступа к микрофону. Проверьте разрешения Windows и антивирус.\n${error.message}`,
      "error",
    );
  } finally {
    micLevelPollInFlight = false;
  }
}

async function refreshSystemLevel() {
  if (systemLevelPollInFlight) {
    return;
  }

  if (!hasSelectableDevice(outputDeviceSelect)) {
    resetLevel(systemLevelTarget(), "Устройство системного звука не выбрано.");
    return;
  }

  systemLevelPollInFlight = true;
  try {
    const deviceId = selectedOutputDeviceId();
    const query = deviceId === null ? "" : `?device_id=${encodeURIComponent(deviceId)}`;
    const level = await requestJson(`/api/audio/output-level${query}`);
    updateLevel(level, systemLevelTarget(), "system");
  } catch (error) {
    resetLevel(
      systemLevelTarget(),
      `Нет доступа к системному звуку. Проверьте выбранное устройство вывода.\n${error.message}`,
      "error",
    );
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

function updateRuntimeDetails(benchmark) {
  if (!benchmark) {
    return;
  }

  runtimeModel.textContent = benchmark.model || selectedModel();
  runtimeDevice.textContent = benchmark.device || "auto";
  runtimeCompute.textContent = benchmark.compute_type || "auto";
  if (benchmark.realtime_factor !== null && benchmark.realtime_factor !== undefined) {
    runtimeSpeed.textContent = `${benchmark.realtime_factor}x`;
  }
}

function updateRecordingTranscribeActions(recordings) {
  lastRecordings = recordings || [];
  const micRecording = lastRecordings.find((item) => item.source_type === "mic");
  const systemRecording = lastRecordings.find((item) => item.source_type === "system");
  recordingTranscribeActions.dataset.empty = String(lastRecordings.length === 0);
  transcribeMicRecordingButton.disabled = !micRecording || isTranscribing || queueActive;
  transcribeSystemRecordingButton.disabled = !systemRecording || isTranscribing || queueActive;
  transcribeAllRecordingsButton.disabled = lastRecordings.length < 2 || isTranscribing || queueActive;
}

async function transcribeRecordedDiagnostics(diagnostics) {
  const result = await requestJson("/api/transcribe/file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: diagnostics.audio_file,
      source_type: diagnostics.source_type,
      model: selectedModel(),
    }),
  });

  transcriptText.value = result.text;
  updateRuntimeDetails(result.benchmark);
  setOutput(transcribeOutput, `Текст сохранен: ${result.transcript_path}`, "success");
  setOutput(benchmarkOutput, formatBenchmark(result.benchmark, result.benchmark_path), "success");
  await refreshStatus();
  await refreshModelStatuses();
  await refreshStorage();
  return result;
}

async function transcribeRecordingByType(sourceType) {
  const diagnostics = lastRecordings.find((item) => item.source_type === sourceType);
  if (!diagnostics) {
    setOutput(transcribeOutput, "Файл записи не найден.", "error");
    return;
  }

  await runTranscription(async () => {
    setOutput(transcribeOutput, "Транскрибирую записанный файл...");
    setOutput(benchmarkOutput, "");
    await transcribeRecordedDiagnostics(diagnostics);
  });
}

async function transcribeAllRecordings() {
  if (lastRecordings.length < 2) {
    setOutput(transcribeOutput, "Для этого режима нужно два файла записи.", "error");
    return;
  }

  await runTranscription(async () => {
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
  });
}

async function runTranscription(callback) {
  warnAboutSelectedModelDownload();
  hideTechnicalDetails();
  localTranscriptionActive = true;
  isTranscribing = true;
  transcribeButton.disabled = true;
  transcribeMicRecordingButton.disabled = true;
  transcribeSystemRecordingButton.disabled = true;
  transcribeAllRecordingsButton.disabled = true;
  setAppState("Транскрибация выполняется", "active");
  showToast("Транскрибация началась", "info");

  try {
    await callback();
    setAppState("Транскрибация завершена", "success");
    showToast("Транскрибация завершена", "success");
  } catch (error) {
    setAppState("Ошибка транскрибации", "error");
    setOutput(transcribeOutput, error.message, "error");
    showTechnicalDetails(error.technicalDetails);
    showToast("Ошибка транскрибации", "error");
  } finally {
    localTranscriptionActive = false;
    isTranscribing = false;
    transcribeButton.disabled = queueActive;
    updateRecordingTranscribeActions(lastRecordings);
    await refreshStatus();
  }
}

function showTechnicalDetails(details) {
  if (!details) {
    hideTechnicalDetails();
    return;
  }
  transcribeTechnicalText.textContent = details;
  transcribeTechnicalDetails.hidden = false;
}

function hideTechnicalDetails() {
  transcribeTechnicalText.textContent = "";
  transcribeTechnicalDetails.hidden = true;
  transcribeTechnicalDetails.open = false;
}

async function refreshStorage() {
  try {
    const storage = await requestJson("/api/storage");
    recordingsPath.textContent = storage.recordings.path;
    transcriptsPath.textContent = storage.transcripts.path;
    renderFileList(recordingsFileList, storage.recordings.files, "В папке recordings пока нет файлов.");
    renderFileList(transcriptsFileList, storage.transcripts.files, "В папке transcripts пока нет файлов.");
  } catch (error) {
    renderFileList(recordingsFileList, [], error.message);
    renderFileList(transcriptsFileList, [], error.message);
  }
}

function renderFileList(target, files, emptyMessage) {
  target.innerHTML = "";

  if (!files.length) {
    const item = document.createElement("li");
    item.className = "empty";
    item.textContent = emptyMessage;
    target.append(item);
    return;
  }

  for (const file of files) {
    const item = document.createElement("li");
    const name = document.createElement("span");
    const meta = document.createElement("small");
    name.textContent = file.name;
    meta.textContent = `${formatDateTime(file.modified)} · ${file.size_mb} MB`;
    item.title = file.path;
    item.append(name, meta);
    target.append(item);
  }
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
}

async function openFolder(folder) {
  try {
    const result = await requestJson("/api/folders/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder }),
    });
    showToast(result.message, "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function refreshModelStatuses() {
  try {
    const payload = await requestJson("/api/models");
    applyModelStatuses(payload.models || []);
  } catch (error) {
    modelAvailabilityOutput.textContent = `Не удалось проверить локальные модели: ${error.message}`;
    modelDownloadWarning.textContent = "";
    modelDownloadWarning.dataset.type = "warning";
  }
}

function applyModelStatuses(statuses) {
  modelStatusByName = new Map(statuses.map((item) => [item.name, item]));

  for (const option of whisperModelSelect.options) {
    const status = modelStatusByName.get(option.value);
    if (!status) {
      continue;
    }
    option.textContent = `${status.name} — ${status.description} (${status.message})`;
  }

  updateModelAvailabilityUi();
}

function updateModelAvailabilityUi() {
  const status = modelStatusByName.get(selectedModel());
  if (!status) {
    modelAvailabilityOutput.textContent = "Локальная доступность модели пока не проверена.";
    modelDownloadWarning.textContent = "";
    modelDownloadWarning.dataset.type = "info";
    return;
  }

  modelAvailabilityOutput.textContent = `${status.name} — ${status.message}. ${status.size_label}.`;

  if (status.local) {
    modelDownloadWarning.textContent = "Модель доступна локально. Интернет для этой модели не нужен.";
    modelDownloadWarning.dataset.type = "success";
    return;
  }

  const heavyWarning = status.name === "medium"
    ? "Medium: потребуется скачать примерно 1.5 GB."
    : status.name === "large-v3"
      ? "Large-v3: потребуется скачать примерно 3.1 GB."
      : "";
  modelDownloadWarning.textContent = [
    "Модель еще не скачана. При первой загрузке потребуется интернет и свободное место на диске.",
    heavyWarning,
    heavyWarning ? "Убедитесь, что интернет работает и на диске достаточно свободного места." : "",
  ].filter(Boolean).join("\n");
  modelDownloadWarning.dataset.type = status.name === "medium" || status.name === "large-v3" ? "warning" : "info";
}

function warnAboutSelectedModelDownload() {
  const status = modelStatusByName.get(selectedModel());
  if (status && !status.local) {
    showToast("Модель еще не скачана. Может потребоваться загрузка из интернета.", "warning");
  }
}

const queueStatusLabels = {
  pending: "Ожидает",
  analyzing: "Анализируется",
  extracting_audio: "Извлекается аудио",
  transcribing: "Транскрибируется",
  completed: "Готово",
  error: "Ошибка",
  cancelled: "Отменено",
};

function renderQueue(status) {
  queueActive = status.status === "running";
  const total = Number(status.total_items || 0);
  const completed = Number(status.completed_items || 0);
  const failed = Number(status.failed_items || 0);
  const pending = Number(status.pending_items || 0);
  const progress = Number(status.progress_percent || 0);

  queueTotal.textContent = String(total);
  queueCompleted.textContent = String(completed);
  queueFailed.textContent = String(failed);
  queuePending.textContent = String(pending);
  queueCurrent.textContent = status.current_file || "нет";
  queueElapsed.textContent = formatElapsed(status.elapsed_sec);
  queueEta.textContent = status.eta_sec === null || status.eta_sec === undefined
    ? (status.eta_message || "Оценка появится после обработки первых файлов.")
    : formatElapsed(status.eta_sec);
  queueProgress.value = progress;
  queueProgressText.textContent = `Очередь выполнена на ${Math.round(progress)}%`;

  queueList.innerHTML = "";
  if (!status.items?.length) {
    const item = document.createElement("li");
    item.innerHTML = "<span>Очередь пока пуста.</span>";
    queueList.append(item);
  } else {
    for (const queueItem of status.items) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      const state = document.createElement("small");
      name.textContent = `${queueItem.index}. ${queueItem.source_filename}`;
      state.textContent = queueStatusLabels[queueItem.status] || queueItem.status;
      state.dataset.type = queueItem.status;
      item.title = queueItem.error_message || queueItem.source_path;
      item.append(name, state);
      queueList.append(item);
    }
  }

  queueAddButton.disabled = queueActive;
  queueFileInput.disabled = queueActive;
  queueStartButton.disabled = queueActive || pending === 0;
  queueStopButton.disabled = !queueActive || Boolean(status.stop_after_current);
  queueClearButton.disabled = queueActive || total === 0;
  queueRetryButton.disabled = queueActive || failed === 0;
  whisperModelSelect.disabled = queueActive;
  transcribeButton.disabled = queueActive || isTranscribing;
  setRecordingUi(isRecording);
  updateRecordingTranscribeActions(lastRecordings);

  if (previousQueueStatus === "running" && status.status === "completed") {
    const message = `Очередь завершена. Готово: ${completed}, ошибок: ${failed}.`;
    setOutput(queueOutput, message, failed ? "warning" : "success");
    showToast(message, failed ? "warning" : "success");
    refreshStorage();
  } else if (previousQueueStatus === "running" && status.status === "cancelled") {
    setOutput(queueOutput, "Очередь остановлена после текущей задачи.", "warning");
    showToast("Очередь остановлена после текущей задачи.", "warning");
  }

  previousQueueStatus = status.status;
}

async function refreshQueueStatus() {
  try {
    renderQueue(await requestJson("/api/queue/status"));
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
  }
}

async function postQueueAction(url, successMessage) {
  try {
    const status = await requestJson(url, { method: "POST" });
    renderQueue(status);
    if (successMessage) {
      setOutput(queueOutput, successMessage, "success");
      showToast(successMessage, "success");
    }
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  }
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
    recordingStartedAtMs = Date.now();
    updateRecordingTimerUi();
    setAppState("Идет запись", "active");
    showToast("Запись началась", "success");
    const paths = result.recordings.map((item) => `${item.source_type}: ${item.file_path}`).join("\n");
    setOutput(recordingOutput, `Запись идет.\n${paths}`, "success");
  } catch (error) {
    setRecordingUi(false);
    setAppState("Ошибка записи", "error");
    setOutput(recordingOutput, error.message, "error");
    showToast("Ошибка записи", "error");
  }
});

stopRecordButton.addEventListener("click", async () => {
  setOutput(recordingOutput, "Сохраняю запись...");
  stopRecordButton.disabled = true;

  try {
    const result = await requestJson("/api/record/stop", { method: "POST" });
    setRecordingUi(false);
    setAppState("Запись завершена", "success");
    showToast("Запись завершена", "success");
    const diagnosticsList = result.diagnostics_list || [result.diagnostics];
    recordingStartedAtMs = null;
    lastRecordingDurationSec = Number(result.duration_sec || Math.max(...diagnosticsList.map((item) => item.duration_sec || 0)));
    updateRecordingTimerUi();
    const hasWarnings = diagnosticsList.some((item) => item?.warnings?.length) || Boolean(result.errors?.length);
    setOutput(recordingOutput, formatAllDiagnostics(diagnosticsList, result.errors), hasWarnings ? "warning" : "success");
    updateRecordingTranscribeActions(diagnosticsList);
    await refreshStorage();
  } catch (error) {
    setRecordingUi(false);
    setAppState("Ошибка записи", "error");
    setOutput(recordingOutput, error.message, "error");
    showToast("Ошибка записи", "error");
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
whisperModelSelect.addEventListener("change", () => {
  runtimeModel.textContent = selectedModel();
  updateModelAvailabilityUi();
});
transcribeMicRecordingButton.addEventListener("click", () => transcribeRecordingByType("mic"));
transcribeSystemRecordingButton.addEventListener("click", () => transcribeRecordingByType("system"));
transcribeAllRecordingsButton.addEventListener("click", transcribeAllRecordings);
openRecordingsButton.addEventListener("click", () => openFolder("recordings"));
openTranscriptsButton.addEventListener("click", () => openFolder("transcripts"));
queueAddForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = Array.from(queueFileInput.files || []);
  if (!files.length) {
    setOutput(queueOutput, "Выберите хотя бы один файл для очереди.", "error");
    return;
  }

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  queueAddButton.disabled = true;
  setOutput(queueOutput, "Добавляю файлы в очередь...");
  try {
    renderQueue(await requestJson("/api/queue/add-files", { method: "POST", body: formData }));
    queueFileInput.value = "";
    setOutput(queueOutput, `Файлы добавлены в очередь: ${files.length}.`, "success");
    showToast("Файлы добавлены в очередь.", "success");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  } finally {
    queueAddButton.disabled = queueActive;
  }
});
queueStartButton.addEventListener("click", async () => {
  warnAboutSelectedModelDownload();
  try {
    renderQueue(await requestJson("/api/queue/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: selectedModel() }),
    }));
    setOutput(queueOutput, "Очередь запущена.");
    showToast("Очередь запущена.", "info");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  }
});
queueStopButton.addEventListener("click", () => postQueueAction("/api/queue/stop-after-current", "Очередь остановится после текущей задачи."));
queueClearButton.addEventListener("click", () => postQueueAction("/api/queue/clear", "Очередь очищена."));
queueRetryButton.addEventListener("click", () => postQueueAction("/api/queue/retry-errors", "Ошибочные задачи возвращены в ожидание."));

transcribeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = audioFileInput.files[0];
  if (!file) {
    setOutput(transcribeOutput, "Выберите аудиофайл.", "error");
    return;
  }

  await runTranscription(async () => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("model", selectedModel());

    transcriptText.value = "";
    setOutput(transcribeOutput, "Транскрибирую аудио...");
    setOutput(benchmarkOutput, "");

    const result = await requestJson("/api/transcribe", {
      method: "POST",
      body: formData,
    });

    transcriptText.value = result.text;
    updateRuntimeDetails(result.benchmark);
    setOutput(transcribeOutput, `Текст сохранен: ${result.transcript_path}`, "success");
    setOutput(benchmarkOutput, formatBenchmark(result.benchmark, result.benchmark_path), "success");
    await refreshModelStatuses();
    await refreshStorage();
  });
});

async function boot() {
  updateModeUi();
  await loadDevices();
  await refreshStatus();
  await refreshModelStatuses();
  await refreshStorage();
  await refreshQueueStatus();
  await refreshMicLevel();
  await refreshSystemLevel();
  window.LocalAudioTranscriberTour?.maybePrompt();
}

boot();
setInterval(refreshMicLevel, 500);
setInterval(refreshSystemLevel, 500);
setInterval(refreshStatus, 5000);
setInterval(refreshStorage, 10000);
setInterval(updateRecordingTimerUi, 1000);
setInterval(refreshQueueStatus, 1000);
