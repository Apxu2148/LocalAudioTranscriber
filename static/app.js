const startRecordButton = document.querySelector("#startRecordButton");
const stopRecordButton = document.querySelector("#stopRecordButton");
const refreshMicDevicesButton = document.querySelector("#refreshMicDevicesButton");
const refreshOutputDevicesButton = document.querySelector("#refreshOutputDevicesButton");
const recordingModeSelect = document.querySelector("#recordingModeSelect");
const micDeviceRow = document.querySelector("#micDeviceRow");
const systemDeviceRow = document.querySelector("#systemDeviceRow");
const micDeviceSelect = document.querySelector("#micDeviceSelect");
const outputDeviceSelect = document.querySelector("#outputDeviceSelect");
const recordingState = document.querySelector("#recordingState");
const recordingOutput = document.querySelector("#recordingOutput");
const micLevelBlock = document.querySelector("#micLevelBlock");
const systemLevelBlock = document.querySelector("#systemLevelBlock");
const micLevelMeterFill = document.querySelector("#micLevelMeterFill");
const micRmsValue = document.querySelector("#micRmsValue");
const micPeakValue = document.querySelector("#micPeakValue");
const micLevelWarning = document.querySelector("#micLevelWarning");
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
const audioFilePickerButton = document.querySelector("#audioFilePickerButton");
const audioFilePickerText = document.querySelector("#audioFilePickerText");
const whisperModelSelect = document.querySelector("#whisperModelSelect");
const whisperDeviceSelect = document.querySelector("#whisperDeviceSelect");
const deviceAvailabilityOutput = document.querySelector("#deviceAvailabilityOutput");
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
const queueFilePickerButton = document.querySelector("#queueFilePickerButton");
const queueFilePickerText = document.querySelector("#queueFilePickerText");
const queueAddButton = document.querySelector("#queueAddButton");
const queueStartButton = document.querySelector("#queueStartButton");
const queueStopButton = document.querySelector("#queueStopButton");
const queueClearButton = document.querySelector("#queueClearButton");
const queueRetryButton = document.querySelector("#queueRetryButton");
const queueTotal = document.querySelector("#queueTotal");
const queueCompleted = document.querySelector("#queueCompleted");
const queueFailed = document.querySelector("#queueFailed");
const queueCancelled = document.querySelector("#queueCancelled");
const queuePending = document.querySelector("#queuePending");
const queueCurrent = document.querySelector("#queueCurrent");
const queueElapsed = document.querySelector("#queueElapsed");
const queueEta = document.querySelector("#queueEta");
const queueProgress = document.querySelector("#queueProgress");
const queueProgressText = document.querySelector("#queueProgressText");
const queueOutput = document.querySelector("#queueOutput");
const queueList = document.querySelector("#queueList");
const queueUrlForm = document.querySelector("#queueUrlForm");
const queueUrlInput = document.querySelector("#queueUrlInput");
const queueUrlAddButton = document.querySelector("#queueUrlAddButton");
const queueSettingsSummary = document.querySelector("#queueSettingsSummary");
const diskFree = document.querySelector("#diskFree");
const operationOverlay = document.querySelector("#operationOverlay");
const operationOverlayTitle = document.querySelector("#operationOverlayTitle");
const operationOverlayText = document.querySelector("#operationOverlayText");
const benchmarkUploadForm = document.querySelector("#benchmarkUploadForm");
const benchmarkFileInput = document.querySelector("#benchmarkFileInput");
const benchmarkFilePickerButton = document.querySelector("#benchmarkFilePickerButton");
const benchmarkFilePickerText = document.querySelector("#benchmarkFilePickerText");
const benchmarkUploadButton = document.querySelector("#benchmarkUploadButton");
const benchmarkStatusOutput = document.querySelector("#benchmarkStatusOutput");
const benchmarkCpuResult = document.querySelector("#benchmarkCpuResult");
const benchmarkCudaResult = document.querySelector("#benchmarkCudaResult");
const benchmarkButtons = Array.from(document.querySelectorAll("[data-benchmark-device]"));

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
let latestQueueStatus = null;
let benchmarkActive = false;
let benchmarkSourceId = null;
let overlayOwner = null;
let transcriptionPhase = null;
let activeRuntimeModel = null;
let lastLoadedQueueTranscriptPath = null;
let activeMicDeviceValue = "";
let activeOutputDeviceValue = "";
let micDevicesRefreshInFlight = false;
let outputDevicesRefreshInFlight = false;
let micSwitchInFlight = false;
let outputSwitchInFlight = false;

function t(key, variables = {}) {
  return window.LATI18N?.t(key, variables) || key;
}

function translateUiText(value) {
  return window.LATI18N?.translateText(value) || value;
}

function showOperation(owner, title, text) {
  overlayOwner = owner;
  operationOverlayTitle.textContent = title;
  operationOverlayText.textContent = text;
  operationOverlay.hidden = false;
}

function hideOperation(owner) {
  if (!owner || overlayOwner === owner) {
    operationOverlay.hidden = true;
    overlayOwner = null;
  }
}

class ApiError extends Error {
  constructor(message, technicalDetails = "") {
    super(message);
    this.name = "ApiError";
    this.technicalDetails = technicalDetails;
  }
}

function setOutput(element, message, type = "info") {
  element.textContent = translateUiText(message);
  element.dataset.type = type;
}

function setAppState(message, type = "idle") {
  recordingState.textContent = translateUiText(message);
  recordingState.dataset.type = type;
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.dataset.type = type;
  toast.textContent = translateUiText(message);
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

function selectedDevice() {
  return whisperDeviceSelect.value || "auto";
}

function currentMode() {
  return recordingModeSelect.value;
}

function updateFilePickerText(input, target, multiple = false) {
  const files = Array.from(input.files || []);
  if (!files.length) {
    target.textContent = t(multiple ? "noFilesSelected" : "noFileSelected");
    return;
  }
  target.textContent = multiple
    ? t("selectedFilesCount", { count: files.length })
    : files[0].name;
}

function resetFilePicker(input, target, multiple = false) {
  input.value = "";
  updateFilePickerText(input, target, multiple);
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

function selectHasValue(select, value) {
  return Array.from(select.options).some((option) => option.value === String(value ?? ""));
}

function setRecordingUi(recording) {
  isRecording = recording;
  startRecordButton.disabled = recording || isTranscribing || queueActive || benchmarkActive;
  stopRecordButton.disabled = !recording;
  recordingModeSelect.disabled = recording;
  micDeviceSelect.disabled = recording ? !modeUsesMic() || micSwitchInFlight : micSwitchInFlight;
  outputDeviceSelect.disabled = recording ? !modeUsesSystem() || outputSwitchInFlight : outputSwitchInFlight;
  refreshMicDevicesButton.disabled = micDevicesRefreshInFlight;
  refreshOutputDevicesButton.disabled = outputDevicesRefreshInFlight;

  if (!isTranscribing) {
    setAppState(t(recording ? "recordingActive" : "readyToRecord"), recording ? "active" : "idle");
  }
}

async function requestJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError(t("failedFetch"));
  }
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = payload?.detail?.message || payload?.message || t("requestError");
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
    recordingTimer.textContent = t("recordingNow", { value: formatElapsed(elapsed) });
    return;
  }

  recordingTimer.textContent = lastRecordingDurationSec === null
    ? t("latestRecording", { value: "--:--:--" })
    : t("latestRecording", { value: formatElapsed(lastRecordingDurationSec) });
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
  target.fill.style.width = `${levelPercent}%`;
  target.rms.textContent = t("rmsValue", { value: Number(level.rms || 0).toFixed(6) });
  target.peak.textContent = t("peakValue", { value: Number(level.peak || 0).toFixed(6) });

  const message = formatLevelMessage(kind, level);
  const details = level.warning ? `${message}\n${level.warning}` : message;
  setOutput(target.warning, details, level.has_signal ? "success" : "warning");
}

function resetLevel(target, message, type = "warning") {
  target.fill.style.width = "0%";
  target.rms.textContent = t("rmsZero");
  target.peak.textContent = t("peakZero");
  setOutput(target.warning, message, type);
}

function formatLevelMessage(kind, level) {
  const prefix = t(level.recording ? "levelRecording" : "levelIdle");
  const state = t(kind === "mic"
    ? (level.has_signal ? "micSignalPresent" : "micSignalMissing")
    : (level.has_signal ? "systemSignalPresent" : "systemSignalMissing"));
  return `${prefix} ${state}`;
}

function micLevelTarget() {
  return {
    fill: micLevelMeterFill,
    rms: micRmsValue,
    peak: micPeakValue,
    warning: micLevelWarning,
  };
}

function systemLevelTarget() {
  return {
    fill: systemLevelMeterFill,
    rms: systemRmsValue,
    peak: systemPeakValue,
    warning: systemLevelWarning,
  };
}

async function loadDevices() {
  await Promise.all([
    refreshMicDevices(false),
    refreshOutputDevices(false),
  ]);
}

async function refreshMicDevices(announce = true) {
  const previousMicValue = micDeviceSelect.value;
  const wasRecording = isRecording;
  micDevicesRefreshInFlight = true;
  setRecordingUi(isRecording);
  if (announce) {
    setOutput(recordingOutput, t("refreshingDevices"));
  }

  try {
    const inputResult = await requestJson("/api/audio/devices");
    fillMicDevices(inputResult, previousMicValue);
    if (!wasRecording) {
      activeMicDeviceValue = micDeviceSelect.value;
    }
    if (announce) {
      setOutput(recordingOutput, t("micDevicesUpdated"), "success");
    }
  } catch (error) {
    if (previousMicValue && selectHasValue(micDeviceSelect, previousMicValue)) {
      micDeviceSelect.value = previousMicValue;
    }
    setOutput(recordingOutput, `${t("refreshMicDevicesFailed")}\n${error.message}`, "error");
  } finally {
    micDevicesRefreshInFlight = false;
    setRecordingUi(isRecording);
    refreshMicLevel();
  }
}

async function refreshOutputDevices(announce = true) {
  const previousOutputValue = outputDeviceSelect.value;
  const wasRecording = isRecording;
  outputDevicesRefreshInFlight = true;
  setRecordingUi(isRecording);
  if (announce) {
    setOutput(recordingOutput, t("refreshingDevices"));
  }

  try {
    const outputResult = await requestJson("/api/audio/output-devices");
    fillOutputDevices(outputResult, previousOutputValue);
    if (!wasRecording) {
      activeOutputDeviceValue = outputDeviceSelect.value;
    }
    if (announce) {
      setOutput(recordingOutput, t("outputDevicesUpdated"), "success");
    }
  } catch (error) {
    if (previousOutputValue && selectHasValue(outputDeviceSelect, previousOutputValue)) {
      outputDeviceSelect.value = previousOutputValue;
    }
    setOutput(recordingOutput, `${t("refreshOutputDevicesFailed")}\n${error.message}`, "error");
  } finally {
    outputDevicesRefreshInFlight = false;
    setRecordingUi(isRecording);
    refreshSystemLevel();
  }
}

function fillMicDevices(result, previousValue) {
  micDeviceSelect.innerHTML = "";
  const devices = result.devices || [];
  if (!devices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.disabled = true;
    option.selected = true;
    option.textContent = t("microphonesNotFound");
    micDeviceSelect.append(option);
    return;
  }

  for (const device of devices) {
    const option = document.createElement("option");
    option.value = String(device.id);
    const defaultText = device.is_default ? ` ${t("defaultSuffix")}` : "";
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
  outputDeviceSelect.innerHTML = "";
  const devices = result.devices || [];
  if (!devices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.disabled = true;
    option.selected = true;
    option.textContent = t("outputDevicesNotFound");
    outputDeviceSelect.append(option);
    return;
  }

  for (const device of devices) {
    const option = document.createElement("option");
    option.value = String(device.id);
    const defaultText = device.is_default_output ? ` ${t("defaultSuffix")}` : "";
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

async function handleMicDeviceChange() {
  if (isRecording && modeUsesMic()) {
    await switchMicDevice();
    return;
  }

  activeMicDeviceValue = micDeviceSelect.value;
  refreshMicLevel();
}

async function handleOutputDeviceChange() {
  if (isRecording && modeUsesSystem()) {
    await switchOutputDevice();
    return;
  }

  activeOutputDeviceValue = outputDeviceSelect.value;
  refreshSystemLevel();
}

async function switchMicDevice() {
  if (micSwitchInFlight) {
    return;
  }

  const previousValue = activeMicDeviceValue;
  const nextValue = micDeviceSelect.value;
  micSwitchInFlight = true;
  setRecordingUi(true);

  try {
    const result = await requestJson("/api/record/switch-microphone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: nextValue === "" ? null : Number(nextValue),
      }),
    });
    activeMicDeviceValue = result.device_id === null || result.device_id === undefined
      ? ""
      : String(result.device_id);
    if (selectHasValue(micDeviceSelect, activeMicDeviceValue)) {
      micDeviceSelect.value = activeMicDeviceValue;
    }
    setOutput(recordingOutput, t("microphoneSwitched"), "success");
    showToast(t("microphoneSwitched"), "success");
    refreshMicLevel();
  } catch (error) {
    activeMicDeviceValue = previousValue;
    if (selectHasValue(micDeviceSelect, previousValue)) {
      micDeviceSelect.value = previousValue;
    }
    setOutput(recordingOutput, `${t("microphoneSwitchFailed")}\n${error.message}`, "error");
    showToast(t("microphoneSwitchFailed"), "error");
    refreshMicLevel();
  } finally {
    micSwitchInFlight = false;
    setRecordingUi(isRecording);
  }
}

async function switchOutputDevice() {
  if (outputSwitchInFlight) {
    return;
  }

  const previousValue = activeOutputDeviceValue;
  const nextValue = outputDeviceSelect.value;
  outputSwitchInFlight = true;
  setRecordingUi(true);

  try {
    const result = await requestJson("/api/record/switch-output-device", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_device_id: nextValue === "" ? null : nextValue,
      }),
    });
    activeOutputDeviceValue = result.output_device_id === null || result.output_device_id === undefined
      ? ""
      : String(result.output_device_id);
    if (selectHasValue(outputDeviceSelect, activeOutputDeviceValue)) {
      outputDeviceSelect.value = activeOutputDeviceValue;
    }
    setOutput(recordingOutput, t("outputDeviceSwitched"), "success");
    showToast(t("outputDeviceSwitched"), "success");
    refreshSystemLevel();
  } catch (error) {
    activeOutputDeviceValue = previousValue;
    if (selectHasValue(outputDeviceSelect, previousValue)) {
      outputDeviceSelect.value = previousValue;
    }
    setOutput(recordingOutput, `${t("outputDeviceSwitchFailed")}\n${error.message}`, "error");
    showToast(t("outputDeviceSwitchFailed"), "error");
    refreshSystemLevel();
  } finally {
    outputSwitchInFlight = false;
    setRecordingUi(isRecording);
  }
}

function updateModeUi() {
  micDeviceRow.dataset.active = String(modeUsesMic());
  systemDeviceRow.dataset.active = String(modeUsesSystem());
  micLevelBlock.dataset.active = String(modeUsesMic());
  systemLevelBlock.dataset.active = String(modeUsesSystem());
  setRecordingUi(isRecording);
}

async function refreshStatus() {
  try {
    const status = await requestJson("/api/status");
    const transcription = status.transcription || {};
    const runtime = transcription.runtime_device || transcription.configured_device || "auto";
    const compute = transcription.runtime_compute_type || transcription.configured_compute_type || "auto";
    const model = transcription.active_model || transcription.loaded_model || selectedModel() || status.whisper_model;
    transcriptionPhase = transcription.phase || null;
    activeRuntimeModel = model;

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
    deviceAvailabilityOutput.textContent = transcription.cuda_available ? t("cpuGpu") : t("cpuOnly");

    appVersion.textContent = `${t("version")}: ${status.app_version || "?"}`;
    syncRecordingTimer(status);
    isTranscribing = localTranscriptionActive || Boolean(transcription.in_progress);
    if (status.recording && status.recording_mode) {
      recordingModeSelect.value = status.recording_mode;
      updateModeUi();
    }
    setRecordingUi(Boolean(status.recording));
    updateRecordingTranscribeActions(lastRecordings);

    if (isTranscribing && !queueActive && !benchmarkActive) {
      setAppState(t("transcriptionRunning"), "active");
      const downloading = transcription.phase === "loading_model" && !modelStatusByName.get(model)?.local;
      showOperation(
        "transcription",
        downloading ? t("modelDownloading", { model }) : t("transcribing"),
        downloading ? t("modelDownloadText") : `${model} · ${runtime}/${compute}\n${t("wait")}`,
      );
    } else {
      hideOperation("transcription");
    }

    const ffmpeg = status.ffmpeg_found ? t("ffmpegFound") : t("ffmpegMissing");
    systemStatus.textContent = `${availabilityText(status)}; ${ffmpeg}`;
  } catch (error) {
    systemStatus.textContent = translateUiText(error.message);
  }
}

function availabilityText(status) {
  const micAvailable = Boolean(status.microphone?.available);
  const systemAvailable = Boolean(status.system_audio?.available);

  if (micAvailable && systemAvailable) {
    return t("devicesBoth");
  }
  if (!micAvailable && systemAvailable) {
    return t("devicesSystem");
  }
  if (micAvailable && !systemAvailable) {
    return t("devicesMic");
  }
  return t("devicesNone");
}

async function refreshMicLevel() {
  if (micLevelPollInFlight) {
    return;
  }

  if (!hasSelectableDevice(micDeviceSelect)) {
    resetLevel(micLevelTarget(), t("micDeviceNotSelected"));
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
      `${t("micAccessError")}\n${error.message}`,
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
    resetLevel(systemLevelTarget(), t("systemDeviceNotSelected"));
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
      `${t("systemAccessError")}\n${error.message}`,
      "error",
    );
  } finally {
    systemLevelPollInFlight = false;
  }
}

function formatRecordingDiagnostics(diagnostics) {
  const source = t(diagnostics.source_type === "system" ? "systemAudio" : "microphone");
  const device = diagnostics.source_type === "system"
    ? `${diagnostics.output_device_name} (${diagnostics.output_device_id ?? "default"})`
    : `${diagnostics.device_name} (${diagnostics.device_id ?? "default"})`;

  const lines = [
    `${source}`,
    t("recordingDiagnosticWav", { path: diagnostics.audio_file }),
    t("recordingDiagnosticJson", { path: diagnostics.diagnostic_file }),
    t("recordingDiagnosticDevice", { device }),
    t("recordingDiagnosticDuration", { value: diagnostics.duration_sec }),
    t("rmsValue", { value: Number(diagnostics.rms).toFixed(6) }),
    t("peakValue", { value: Number(diagnostics.peak).toFixed(6) }),
  ];

  if (diagnostics.warnings?.length) {
    lines.push(...diagnostics.warnings);
  }

  return lines.join("\n");
}

function formatAllDiagnostics(diagnosticsList, errors = []) {
  const chunks = diagnosticsList.map(formatRecordingDiagnostics);
  if (errors.length) {
    chunks.push(t("diagnosticErrors", { value: errors.join("; ") }));
  }
  return chunks.join("\n\n");
}

function formatBenchmark(benchmark, benchmarkPath) {
  const speed = benchmark.realtime_factor ? `${benchmark.realtime_factor}x realtime` : t("notAvailable");
  return [
    t("benchmarkTxt", { value: benchmark.transcript_file }),
    t("benchmarkJson", { value: benchmarkPath }),
    t("benchmarkModel", { value: benchmark.model }),
    t("benchmarkDevice", { value: benchmark.device }),
    t("benchmarkComputeType", { value: benchmark.compute_type }),
    t("benchmarkAudioDuration", { value: benchmark.audio_duration_sec ?? t("notAvailable") }),
    t("benchmarkProcessingTime", { value: benchmark.transcribe_time_sec }),
    t("benchmarkSpeed", { value: speed }),
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
  const blocked = isTranscribing || queueActive || benchmarkActive;
  recordingTranscribeActions.dataset.empty = String(lastRecordings.length === 0);
  transcribeMicRecordingButton.disabled = !micRecording || blocked;
  transcribeSystemRecordingButton.disabled = !systemRecording || blocked;
  transcribeAllRecordingsButton.disabled = lastRecordings.length < 2 || blocked;
}

async function addRecordingByType(sourceType) {
  const diagnostics = lastRecordings.find((item) => item.source_type === sourceType);
  if (!diagnostics) {
    setOutput(queueOutput, t("recordingFileNotFound"), "error");
    return;
  }
  await addRecordingsToQueue([diagnostics]);
}

async function addAllRecordings() {
  if (lastRecordings.length < 2) {
    setOutput(queueOutput, t("twoRecordingsRequired"), "error");
    return;
  }
  await addRecordingsToQueue(lastRecordings);
}

async function addRecordingsToQueue(recordings) {
  try {
    const status = await requestJson("/api/queue/add-recordings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        files: recordings.map((item) => ({
          file_path: item.audio_file,
          source_type: item.source_type,
        })),
      }),
    });
    renderQueue(status);
    const message = t("recordingsAdded", { count: recordings.length });
    setOutput(queueOutput, message, "success");
    showToast(message, "success");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  }
}

async function addLocalFilesToQueue(files, input, pickerText, multiple = false) {
  if (!files.length) {
    setOutput(queueOutput, t(multiple ? "selectAtLeastOneFile" : "selectFile"), "error");
    return;
  }
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  try {
    renderQueue(await requestJson("/api/queue/add-files", { method: "POST", body: formData }));
    resetFilePicker(input, pickerText, multiple);
    const message = t("filesAdded", { count: files.length });
    setOutput(queueOutput, message, "success");
    showToast(message, "success");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  }
}

function transcriptFileName(value) {
  const text = String(value || "");
  return text.split(/[\\/]/).filter(Boolean).pop() || text;
}

async function loadTranscript(filePath, announce = false) {
  const transcriptName = transcriptFileName(filePath);
  try {
    const result = await requestJson(`/api/transcripts/read?file_path=${encodeURIComponent(transcriptName)}`);
    transcriptText.value = result.text || "";
    lastLoadedQueueTranscriptPath = filePath;
    if (announce) {
      setOutput(transcribeOutput, t("transcriptLoaded", { name: transcriptName }), "success");
    }
  } catch (error) {
    setOutput(transcribeOutput, error.message, "error");
  }
}

function maybeLoadLatestQueueTranscript(status) {
  const completedItem = [...(status.items || [])].reverse().find((item) => item.status === "completed" && item.transcript_path);
  if (completedItem?.transcript_path && completedItem.transcript_path !== lastLoadedQueueTranscriptPath) {
    loadTranscript(completedItem.transcript_path);
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
    diskFree.textContent = t("diskFree", { value: storage.disk?.free_gb ?? "?" });
    recordingsPath.textContent = storage.recordings.path;
    transcriptsPath.textContent = storage.transcripts.path;
    renderFileList(recordingsFileList, storage.recordings.files, t("recordingsEmpty"));
    renderFileList(transcriptsFileList, storage.transcripts.files, t("transcriptsEmpty"), true);
  } catch (error) {
    renderFileList(recordingsFileList, [], error.message);
    renderFileList(transcriptsFileList, [], error.message);
  }
}

function renderFileList(target, files, emptyMessage, clickableTranscripts = false) {
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
    const name = clickableTranscripts && file.name.toLowerCase().endsWith(".txt")
      ? document.createElement("button")
      : document.createElement("span");
    const meta = document.createElement("small");
    name.textContent = file.name;
    if (name instanceof HTMLButtonElement) {
      name.type = "button";
      name.className = "file-link";
      name.addEventListener("click", () => loadTranscript(file.name, true));
    }
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
  return date.toLocaleString(window.LATI18N?.getLanguage() === "en" ? "en-US" : "ru-RU");
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
    modelAvailabilityOutput.textContent = t("modelStatusError", { message: translateUiText(error.message) });
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
    option.textContent = `${status.name} — ${translateUiText(status.description)} (${status.local ? t("modelLocal") : t("modelMissing")})`;
  }

  updateModelAvailabilityUi();
}

function updateModelAvailabilityUi() {
  const status = modelStatusByName.get(selectedModel());
  if (!status) {
    modelAvailabilityOutput.textContent = t("modelChecking");
    modelDownloadWarning.textContent = "";
    modelDownloadWarning.dataset.type = "info";
    return;
  }

  modelAvailabilityOutput.textContent = `${status.name} — ${status.local ? t("modelLocal") : t("modelMissing")}. ${translateUiText(status.size_label)}.`;

  if (status.local) {
    modelDownloadWarning.textContent = t("modelReady");
    modelDownloadWarning.dataset.type = "success";
    return;
  }

  const heavyWarning = status.name === "medium"
    ? t("mediumDownloadWarning")
    : status.name === "large-v3"
      ? t("largeDownloadWarning")
      : "";
  modelDownloadWarning.textContent = [
    t("modelNeedsDownload"),
    heavyWarning,
    heavyWarning ? t("downloadRequirementsWarning") : "",
  ].filter(Boolean).join("\n");
  modelDownloadWarning.dataset.type = status.name === "medium" || status.name === "large-v3" ? "warning" : "info";
}

function warnAboutSelectedModelDownload() {
  const status = modelStatusByName.get(selectedModel());
  if (status && !status.local) {
    showToast(t("modelDownloadToast"), "warning");
  }
}

function queueStatusLabel(status) {
  return {
    pending: t("statusPending"),
    downloading: t("statusDownloading"),
    downloaded: t("statusDownloaded"),
    analyzing: t("statusAnalyzing"),
    extracting_audio: t("statusExtracting"),
    transcribing: t("statusTranscribing"),
    completed: t("statusCompleted"),
    error: t("statusError"),
    cancelled: t("statusCancelled"),
  }[status] || status;
}

function updateQueueSettingsSummary(status = null) {
  queueSettingsSummary.textContent = t("queueSnapshot", {
    model: status?.model || selectedModel(),
    device: status?.device_preference || selectedDevice(),
  });
}

function renderQueue(status) {
  latestQueueStatus = status;
  queueActive = status.status === "running";
  const total = Number(status.total_items || 0);
  const completed = Number(status.completed_items || 0);
  const failed = Number(status.failed_items || 0);
  const cancelled = Number(status.cancelled_items || 0);
  const pending = Number(status.pending_items || 0);
  const progress = Number(status.progress_percent || 0);
  const finished = completed + failed + cancelled;

  queueTotal.textContent = String(total);
  queueCompleted.textContent = String(completed);
  queueFailed.textContent = String(failed);
  queueCancelled.textContent = String(cancelled);
  queuePending.textContent = String(pending);
  queueCurrent.textContent = status.current_file || t("none");
  queueElapsed.textContent = formatElapsed(status.elapsed_sec);
  queueEta.textContent = status.eta_sec === null || status.eta_sec === undefined
    ? (translateUiText(status.eta_message) || t("queueEtaWaiting"))
    : formatElapsed(status.eta_sec);
  queueProgress.value = progress;
  queueProgressText.textContent = t("queueProgress", { done: finished, total, value: Math.round(progress) });

  queueList.innerHTML = "";
  if (!status.items?.length) {
    const item = document.createElement("li");
    item.textContent = t("queueEmpty");
    queueList.append(item);
  } else {
    for (const queueItem of status.items) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      const state = document.createElement("small");
      const sourceLabel = queueItem.source_type === "url"
        ? t("queueSourceUrl", {
          name: queueItem.source_title || queueItem.source_filename,
          platform: queueItem.source_platform || "unknown",
        })
        : t("queueSourceFile", {
          name: queueItem.source_filename,
          type: queueItem.source_type === "mic"
            ? t("microphone")
            : queueItem.source_type === "system"
              ? t("systemAudio")
              : t("localFile"),
        });
      name.textContent = `${queueItem.index}. ${sourceLabel}`;
      state.textContent = queueStatusLabel(queueItem.status);
      state.dataset.type = queueItem.status;
      item.title = translateUiText(queueItem.error_message || queueItem.source_url || queueItem.source_path);
      item.append(name, state);
      queueList.append(item);
    }
  }

  queueAddButton.disabled = queueActive;
  queueFileInput.disabled = queueActive;
  queueFilePickerButton.disabled = queueActive;
  queueUrlAddButton.disabled = queueActive;
  queueUrlInput.disabled = queueActive;
  queueStartButton.disabled = queueActive || pending === 0;
  queueStopButton.disabled = !queueActive || Boolean(status.stop_after_current);
  queueClearButton.disabled = queueActive || total === 0;
  queueRetryButton.disabled = queueActive || failed === 0;
  whisperModelSelect.disabled = queueActive;
  whisperDeviceSelect.disabled = queueActive;
  transcribeButton.disabled = queueActive || isTranscribing;
  setRecordingUi(isRecording);
  updateRecordingTranscribeActions(lastRecordings);
  updateQueueSettingsSummary(queueActive ? status : null);

  if (queueActive) {
    const current = status.current_item || {};
    const modelLoading = transcriptionPhase === "loading_model" && !modelStatusByName.get(activeRuntimeModel)?.local;
    showOperation(
      "queue",
      current.status === "downloading"
        ? t("urlDownloading")
        : modelLoading
          ? t("modelDownloading", { model: activeRuntimeModel })
          : t("queueRunning"),
      modelLoading ? t("modelDownloadText") : t("queueOverlay", {
        done: finished,
        total,
        item: status.current_file || "-",
        stage: queueStatusLabel(current.status || "pending"),
      }),
    );
  } else {
    hideOperation("queue");
  }

  if (previousQueueStatus === "running" && status.status === "completed") {
    const message = t("queueCompletedSummary", { completed, failed, cancelled });
    setOutput(queueOutput, message, failed ? "warning" : "success");
    showToast(message, failed ? "warning" : "success");
    refreshStorage();
  } else if (previousQueueStatus === "running" && status.status === "cancelled") {
    setOutput(queueOutput, t("queueStopped"), "warning");
    showToast(t("queueStopped"), "warning");
  }

  const latestCompletedItem = [...(status.items || [])]
    .reverse()
    .find((item) => item.status === "completed");
  if (status.model) {
    runtimeModel.textContent = status.model;
  }
  if (status.device_preference) {
    runtimeDevice.textContent = status.device_preference;
  }
  if (latestCompletedItem?.realtime_factor !== null && latestCompletedItem?.realtime_factor !== undefined) {
    runtimeSpeed.textContent = `${latestCompletedItem.realtime_factor}x`;
  }
  const latestTechnicalItem = [...(status.items || [])]
    .reverse()
    .find((item) => item.technical_details);
  if (latestTechnicalItem) {
    showTechnicalDetails(translateUiText(latestTechnicalItem.technical_details));
  } else {
    hideTechnicalDetails();
  }
  maybeLoadLatestQueueTranscript(status);
  previousQueueStatus = status.status;
  updateLongOperationControls();
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

function updateLongOperationControls() {
  const active = isTranscribing || queueActive || benchmarkActive;
  whisperModelSelect.disabled = active;
  whisperDeviceSelect.disabled = active;
  transcribeButton.disabled = active;
  audioFileInput.disabled = active;
  audioFilePickerButton.disabled = active;
  queueAddButton.disabled = active;
  queueFileInput.disabled = active;
  queueFilePickerButton.disabled = active;
  queueUrlAddButton.disabled = active;
  queueUrlInput.disabled = active;
  queueStartButton.disabled = active || Number(latestQueueStatus?.pending_items || 0) === 0;
  queueClearButton.disabled = active || Number(latestQueueStatus?.total_items || 0) === 0;
  queueRetryButton.disabled = active || Number(latestQueueStatus?.failed_items || 0) === 0;
  benchmarkUploadButton.disabled = active;
  benchmarkFileInput.disabled = active;
  benchmarkFilePickerButton.disabled = active;
  for (const button of benchmarkButtons) {
    button.disabled = active || !benchmarkSourceId;
  }
  setRecordingUi(isRecording);
  updateRecordingTranscribeActions(lastRecordings);
}

function formatBenchmarkResult(result) {
  if (!result) {
    return t("noResults");
  }
  return [
    `${result.device?.toUpperCase()} / ${result.benchmark_mode}`,
    t("benchmarkTotalWallTime", { value: result.total_wall_time_sec ?? "-" }),
    t("benchmarkModelLoadTime", { value: result.model_load_time_sec ?? "-" }),
    t("benchmarkTranscriptionTime", { value: result.transcription_time_sec ?? "-" }),
    t("benchmarkSaveTime", { value: result.save_time_sec ?? "-" }),
    t("benchmarkAudioDuration", { value: result.audio_duration_sec ?? "-" }),
    t("benchmarkRealtimeFactorTotal", { value: result.realtime_factor_total ?? "-" }),
    t("benchmarkPureModelFactor", { value: result.realtime_factor_transcription_only ?? "-" }),
    t("benchmarkComputeType", { value: result.compute_type ?? "-" }),
    t("benchmarkTxt", { value: result.transcript_path ?? "-" }),
    t("benchmarkJson", { value: result.json_path ?? "-" }),
  ].join("\n");
}

function renderBenchmark(status) {
  benchmarkActive = Boolean(status.running);
  benchmarkCpuResult.textContent = formatBenchmarkResult(status.results?.cpu);
  benchmarkCudaResult.textContent = formatBenchmarkResult(status.results?.cuda);
  if (benchmarkActive) {
    const current = status.current || {};
    const modelLoading = transcriptionPhase === "loading_model" && !modelStatusByName.get(activeRuntimeModel)?.local;
    showOperation(
      "benchmark",
      modelLoading ? t("modelDownloading", { model: activeRuntimeModel }) : t("benchmarkRunning"),
      modelLoading ? t("modelDownloadText") : `${(current.device || "").toUpperCase()} / ${current.mode || ""}\n${current.model || ""}\n${t("wait")}`,
    );
    setOutput(benchmarkStatusOutput, t("benchmarkRunning"));
  } else {
    hideOperation("benchmark");
    if (status.last_error) {
      setOutput(benchmarkStatusOutput, status.last_error, "error");
    }
  }
  updateLongOperationControls();
}

async function refreshBenchmarkStatus() {
  try {
    renderBenchmark(await requestJson("/api/benchmark/status"));
  } catch (error) {
    setOutput(benchmarkStatusOutput, error.message, "error");
  }
}

startRecordButton.addEventListener("click", async () => {
  setOutput(recordingOutput, t("startingRecording"));
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
    activeMicDeviceValue = micDeviceSelect.value;
    activeOutputDeviceValue = outputDeviceSelect.value;
    recordingStartedAtMs = Date.now();
    updateRecordingTimerUi();
    setAppState(t("recordingActive"), "active");
    showToast(t("recordingStarted"), "success");
    const paths = result.recordings.map((item) => `${item.source_type}: ${item.file_path}`).join("\n");
    setOutput(recordingOutput, `${t("recordingInProgress")}\n${paths}`, "success");
  } catch (error) {
    setRecordingUi(false);
    setAppState(t("recordingError"), "error");
    setOutput(recordingOutput, error.message, "error");
    showToast(t("recordingError"), "error");
  }
});

stopRecordButton.addEventListener("click", async () => {
  setOutput(recordingOutput, t("savingRecording"));
  stopRecordButton.disabled = true;

  try {
    const result = await requestJson("/api/record/stop", { method: "POST" });
    setRecordingUi(false);
    setAppState(t("recordingCompleted"), "success");
    showToast(t("recordingCompleted"), "success");
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
    setAppState(t("recordingError"), "error");
    setOutput(recordingOutput, error.message, "error");
    showToast(t("recordingError"), "error");
  }
});

refreshMicDevicesButton.addEventListener("click", () => refreshMicDevices(true));
refreshOutputDevicesButton.addEventListener("click", () => refreshOutputDevices(true));
recordingModeSelect.addEventListener("change", () => {
  updateModeUi();
  refreshMicLevel();
  refreshSystemLevel();
});
micDeviceSelect.addEventListener("change", handleMicDeviceChange);
outputDeviceSelect.addEventListener("change", handleOutputDeviceChange);
whisperModelSelect.addEventListener("change", () => {
  runtimeModel.textContent = selectedModel();
  updateModelAvailabilityUi();
  updateQueueSettingsSummary();
});
whisperDeviceSelect.addEventListener("change", updateQueueSettingsSummary);
transcribeMicRecordingButton.addEventListener("click", () => addRecordingByType("mic"));
transcribeSystemRecordingButton.addEventListener("click", () => addRecordingByType("system"));
transcribeAllRecordingsButton.addEventListener("click", addAllRecordings);
openRecordingsButton.addEventListener("click", () => openFolder("recordings"));
openTranscriptsButton.addEventListener("click", () => openFolder("transcripts"));
audioFilePickerButton.addEventListener("click", () => audioFileInput.click());
queueFilePickerButton.addEventListener("click", () => queueFileInput.click());
benchmarkFilePickerButton.addEventListener("click", () => benchmarkFileInput.click());
audioFileInput.addEventListener("change", () => updateFilePickerText(audioFileInput, audioFilePickerText));
queueFileInput.addEventListener("change", () => updateFilePickerText(queueFileInput, queueFilePickerText, true));
benchmarkFileInput.addEventListener("change", () => updateFilePickerText(benchmarkFileInput, benchmarkFilePickerText));
queueAddForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = Array.from(queueFileInput.files || []);
  await addLocalFilesToQueue(files, queueFileInput, queueFilePickerText, true);
});
queueUrlForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const urls = queueUrlInput.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
  if (!urls.length) {
    setOutput(queueOutput, t("selectAtLeastOneUrl"), "error");
    return;
  }
  queueUrlAddButton.disabled = true;
  try {
    renderQueue(await requestJson("/api/queue/add-urls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    }));
    queueUrlInput.value = "";
    const message = t("urlAdded", { count: urls.length });
    setOutput(queueOutput, message, "success");
    showToast(message, "success");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  } finally {
    queueUrlAddButton.disabled = queueActive;
  }
});
queueStartButton.addEventListener("click", async () => {
  warnAboutSelectedModelDownload();
  try {
    renderQueue(await requestJson("/api/queue/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: selectedModel(), device: selectedDevice() }),
    }));
    setOutput(queueOutput, t("queueStarted"));
    showToast(t("queueStarted"), "info");
  } catch (error) {
    setOutput(queueOutput, error.message, "error");
    showToast(error.message, "error");
  }
});
queueStopButton.addEventListener("click", () => postQueueAction("/api/queue/stop-after-current", t("queueWillStop")));
queueClearButton.addEventListener("click", () => postQueueAction("/api/queue/clear", t("queueCleared")));
queueRetryButton.addEventListener("click", () => postQueueAction("/api/queue/retry-errors", t("queueRetried")));

benchmarkUploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = benchmarkFileInput.files[0];
  if (!file) {
    setOutput(benchmarkStatusOutput, t("selectBenchmarkFile"), "error");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  benchmarkUploadButton.disabled = true;
  try {
    const result = await requestJson("/api/benchmark/upload", { method: "POST", body: formData });
    benchmarkSourceId = result.source_id;
    setOutput(benchmarkStatusOutput, t("benchmarkPrepared", { name: result.source_filename }), "success");
  } catch (error) {
    benchmarkSourceId = null;
    setOutput(benchmarkStatusOutput, error.message, "error");
  } finally {
    updateLongOperationControls();
  }
});

for (const button of benchmarkButtons) {
  button.addEventListener("click", async () => {
    try {
      const device = button.dataset.benchmarkDevice;
      const mode = button.dataset.benchmarkMode;
      renderBenchmark(await requestJson("/api/benchmark/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_id: benchmarkSourceId, model: selectedModel(), device, mode }),
      }));
      setOutput(benchmarkStatusOutput, t("benchmarkStarted", { device, mode }));
    } catch (error) {
      setOutput(benchmarkStatusOutput, error.message, "error");
    }
  });
}

transcribeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await addLocalFilesToQueue(Array.from(audioFileInput.files || []), audioFileInput, audioFilePickerText);
});

async function boot() {
  updateFilePickerText(audioFileInput, audioFilePickerText);
  updateFilePickerText(queueFileInput, queueFilePickerText, true);
  updateFilePickerText(benchmarkFileInput, benchmarkFilePickerText);
  updateModeUi();
  await loadDevices();
  await refreshStatus();
  await refreshModelStatuses();
  await refreshStorage();
  await refreshQueueStatus();
  await refreshBenchmarkStatus();
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
setInterval(refreshBenchmarkStatus, 1000);

document.addEventListener("lat-language-change", () => {
  updateFilePickerText(audioFileInput, audioFilePickerText);
  updateFilePickerText(queueFileInput, queueFilePickerText, true);
  updateFilePickerText(benchmarkFileInput, benchmarkFilePickerText);
  updateQueueSettingsSummary(queueActive ? latestQueueStatus : null);
  if (latestQueueStatus) {
    renderQueue(latestQueueStatus);
  }
  refreshStatus();
  refreshBenchmarkStatus();
  refreshStorage();
  refreshModelStatuses();
});
