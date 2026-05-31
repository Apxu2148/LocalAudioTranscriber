(function () {
  const DEFAULT_LANGUAGE = "ru";
  const STORAGE_KEY = "latUiLanguage";
  const translations = {
    ru: {
      interface: "Интерфейс",
      version: "Версия",
      settingsTitle: "Настройки транскрибации",
      settingsNote: "Эти настройки применяются к последней записи, выбранному файлу и очереди. Для очереди они фиксируются в момент запуска.",
      model: "Модель Whisper",
      device: "Устройство",
      auto: "Авто",
      checkingGpu: "Проверяю доступность CPU/GPU...",
      cpuOnly: "Доступно только CPU. CUDA доступна: нет. Auto выберет CPU.",
      cpuGpu: "Доступно CPU и GPU. CUDA доступна: да. Auto выберет GPU/CUDA.",
      recording: "Запись аудио",
      transcribe: "Транскрибация аудиофайла",
      transcribeGlobal: "Используются глобальные настройки модели и устройства из верхней части страницы.",
      queueTitle: "Очередь файлов и ссылок",
      queueNote: "Локальные файлы и публичные ссылки обрабатываются последовательно одним worker-потоком.",
      queueUrls: "Добавить ссылки в очередь, по одной на строку",
      addUrls: "Добавить ссылки в очередь",
      queueSnapshot: "Очередь будет обработана с настройками: модель {model}, устройство {device}.",
      queueFrozen: "Настройки очереди фиксируются в момент запуска. Во время обработки изменить модель или устройство нельзя.",
      benchmarkTitle: "Бенчмарк производительности",
      benchmarkNote: "Cold Run включает загрузку модели. Warm Run переиспользует модель после успешного Cold Run для того же файла, модели и устройства.",
      benchmarkFile: "Файл для benchmark",
      benchmarkPrepare: "Подготовить файл",
      noResults: "Результатов пока нет.",
      diskChecking: "Диск: проверяю свободное место...",
      diskFree: "Диск: свободно {value} GB",
      tourButton: "Пройти обучение",
      operation: "Выполняется операция",
      wait: "Пожалуйста, дождитесь завершения.",
      transcribing: "Идет транскрибация...",
      modelDownloading: "Скачивается модель {model}...",
      modelDownloadText: "Это может занять несколько минут.\nНе закрывайте программу.\nПосле загрузки автоматически начнется транскрибация.",
      queueRunning: "Обрабатывается очередь...",
      queueOverlay: "Очередь: {done} из {total}\nТекущий элемент: {item}\nЭтап: {stage}",
      benchmarkRunning: "Выполняется benchmark...",
      urlDownloading: "Скачивается аудио по ссылке...",
      failedFetch: "Не удалось получить данные от локального сервера. Обновите страницу Ctrl+F5 или перезапустите run.bat.",
      urlAdded: "Ссылки добавлены в очередь: {count}.",
      recordingNow: "Запись идет: {value}",
      latestRecording: "Последняя запись: {value}",
      queueProgress: "Очередь выполнена на {value}%",
      queueEtaWaiting: "Оценка появится после обработки первых файлов.",
      none: "нет",
      ffmpegFound: "ffmpeg найден",
      ffmpegMissing: "ffmpeg не найден",
      devicesBoth: "Микрофон доступен, системный звук доступен",
      devicesSystem: "Микрофон недоступен, системный звук доступен",
      devicesMic: "Микрофон доступен, системный звук недоступен",
      devicesNone: "Микрофон и системный звук недоступны",
      modelNeedsDownload: "Модель еще не скачана. При первой загрузке потребуется интернет и свободное место на диске.",
      benchmarkPrepared: "Файл benchmark подготовлен: {name}",
      benchmarkStarted: "Benchmark запущен: {device} / {mode}.",
      modelLocal: "доступна локально",
      modelMissing: "не скачана, потребуется загрузка из интернета",
      modelChecking: "Локальная доступность модели пока не проверена.",
      modelReady: "Модель доступна локально. Интернет для этой модели не нужен.",
      statusPending: "Ожидает",
      statusDownloading: "Скачивается",
      statusDownloaded: "Скачано",
      statusAnalyzing: "Анализируется",
      statusExtracting: "Извлекается аудио",
      statusTranscribing: "Транскрибируется",
      statusCompleted: "Готово",
      statusError: "Ошибка",
      statusCancelled: "Отменено",
      tourRepeat: "Обучение можно пройти повторно в любой момент по кнопке в верхней части окна.",
    },
    en: {
      interface: "Interface",
      version: "Version",
      settingsTitle: "Transcription settings",
      settingsNote: "These settings apply to the latest recording, the selected file, and the queue. Queue settings are frozen when processing starts.",
      model: "Whisper model",
      device: "Device",
      auto: "Auto",
      checkingGpu: "Checking CPU/GPU availability...",
      cpuOnly: "Only CPU is available. CUDA available: no. Auto will select CPU.",
      cpuGpu: "CPU and GPU are available. CUDA available: yes. Auto will select GPU/CUDA.",
      recording: "Audio recording",
      transcribe: "Audio transcription",
      transcribeGlobal: "The global model and device settings from the top of the page are used.",
      queueTitle: "File and URL queue",
      queueNote: "Local files and public URLs are processed sequentially by one worker thread.",
      queueUrls: "Add URLs to the queue, one per line",
      addUrls: "Add URLs to queue",
      queueSnapshot: "The queue will use: model {model}, device {device}.",
      queueFrozen: "Queue settings are frozen when processing starts. The model and device cannot be changed while it runs.",
      benchmarkTitle: "Performance benchmark",
      benchmarkNote: "Cold Run includes model loading. Warm Run reuses the model after a successful Cold Run for the same file, model, and device.",
      benchmarkFile: "Benchmark file",
      benchmarkPrepare: "Prepare file",
      noResults: "No results yet.",
      diskChecking: "Disk: checking free space...",
      diskFree: "Disk: {value} GB free",
      tourButton: "Start tour",
      operation: "Operation in progress",
      wait: "Please wait until the operation completes.",
      transcribing: "Transcription in progress...",
      modelDownloading: "Downloading model {model}...",
      modelDownloadText: "This may take several minutes.\nDo not close the application.\nTranscription will start automatically after the download.",
      queueRunning: "Processing queue...",
      queueOverlay: "Queue: {done} of {total}\nCurrent item: {item}\nStage: {stage}",
      benchmarkRunning: "Running benchmark...",
      urlDownloading: "Downloading audio from URL...",
      failedFetch: "Could not reach the local server. Refresh with Ctrl+F5 or restart run.bat.",
      urlAdded: "URLs added to queue: {count}.",
      recordingNow: "Recording: {value}",
      latestRecording: "Latest recording: {value}",
      queueProgress: "Queue progress: {value}%",
      queueEtaWaiting: "An estimate will appear after the first files are processed.",
      none: "none",
      ffmpegFound: "ffmpeg found",
      ffmpegMissing: "ffmpeg not found",
      devicesBoth: "Microphone available, system audio available",
      devicesSystem: "Microphone unavailable, system audio available",
      devicesMic: "Microphone available, system audio unavailable",
      devicesNone: "Microphone and system audio unavailable",
      modelNeedsDownload: "The model has not been downloaded yet. The first load requires internet access and free disk space.",
      benchmarkPrepared: "Benchmark file prepared: {name}",
      benchmarkStarted: "Benchmark started: {device} / {mode}.",
      modelLocal: "available locally",
      modelMissing: "not downloaded; an internet download is required",
      modelChecking: "Local model availability has not been checked yet.",
      modelReady: "The model is available locally. Internet access is not required for this model.",
      statusPending: "Pending",
      statusDownloading: "Downloading",
      statusDownloaded: "Downloaded",
      statusAnalyzing: "Analyzing",
      statusExtracting: "Extracting audio",
      statusTranscribing: "Transcribing",
      statusCompleted: "Completed",
      statusError: "Error",
      statusCancelled: "Cancelled",
      tourRepeat: "You can repeat the tour at any time using the button at the top of the window.",
    },
  };

  const staticPairs = {
    "Проверка окружения...": "Checking environment...",
    "Версия: загрузка...": "Version: loading...",
    "Запись аудио": "Audio recording",
    "Готово к записи": "Ready to record",
    "Режим записи": "Recording mode",
    "Микрофон": "Microphone",
    "Системный звук": "System audio",
    "Микрофон + системный звук": "Microphone + system audio",
    "Устройство вывода": "Output device",
    "Обновить устройства": "Refresh devices",
    "Уровень микрофона": "Microphone level",
    "Уровень системного звука": "System audio level",
    "Начать запись": "Start recording",
    "Остановить запись": "Stop recording",
    "Последняя запись: --:--:--": "Latest recording: --:--:--",
    "Транскрибация последней записи": "Transcribe latest recording",
    "Транскрибация аудиофайла": "Audio transcription",
    "Используются глобальные настройки модели и устройства из верхней части страницы.": "The global model and device settings from the top of the page are used.",
    "Эти кнопки используют файлы, созданные при последней записи.": "These buttons use files created during the latest recording.",
    "Транскрибировать микрофон": "Transcribe microphone",
    "Транскрибировать системный звук": "Transcribe system audio",
    "Транскрибировать оба файла": "Transcribe both files",
    "Транскрибация выбранного файла": "Transcribe selected file",
    "Файл": "File",
    "Транскрибировать выбранный файл": "Transcribe selected file",
    "Аудио- и видеофайлы": "Audio and video files",
    "Добавить файлы в очередь": "Add files to queue",
    "Запустить очередь": "Start queue",
    "Остановить после текущей задачи": "Stop after current task",
    "Очистить очередь": "Clear queue",
    "Повторить ошибочные задачи": "Retry failed tasks",
    "Всего задач": "Total tasks",
    "Готово": "Completed",
    "Ошибок": "Errors",
    "Ожидает": "Pending",
    "Выполняется": "Running",
    "Прошло времени": "Elapsed",
    "Примерно осталось": "Estimated remaining",
    "Файлы": "Files",
    "Аудиозаписи сохраняются в:": "Recordings are saved in:",
    "Транскрипты сохраняются в:": "Transcripts are saved in:",
    "Открыть папку recordings": "Open recordings folder",
    "Открыть папку transcripts": "Open transcripts folder",
    "Последние 5 файлов": "Latest 5 files",
    "Технические подробности": "Technical details",
    "Модель": "Model",
    "Устройство": "Device",
    "Скорость": "Speed",
    "Транскрибация выполняется": "Transcription in progress",
    "Транскрибация завершена": "Transcription completed",
    "Ошибка транскрибации": "Transcription error",
    "Идет запись": "Recording",
    "Запись завершена": "Recording completed",
    "Ошибка записи": "Recording error",
    "Готово к записи": "Ready to record",
    "Очередь запущена.": "Queue started.",
    "Очередь очищена.": "Queue cleared.",
    "Очередь остановится после текущей задачи.": "The queue will stop after the current task.",
    "Ошибочные задачи возвращены в ожидание.": "Failed tasks returned to pending.",
    "Очередь пока пуста.": "The queue is empty.",
    "Результатов пока нет.": "No results yet.",
    "Оценка появится после обработки первых файлов.": "An estimate will appear after the first files are processed.",
    "Оценка появится после анализа файлов.": "An estimate will appear after files are analyzed.",
    "самая быстрая, качество ниже": "fastest, lower quality",
    "быстрая": "fast",
    "баланс скорости и качества": "balanced speed and quality",
    "выше качество, медленнее": "higher quality, slower",
    "максимальное качество, высокие требования к памяти": "maximum quality, high memory requirements",
    "Помощь: если звук не записывается или транскрибация не начинается": "Help: recording or transcription troubleshooting",
    "Если микрофон не работает": "If the microphone does not work",
    "Если системный звук не записывается": "If system audio is not recorded",
    "Если антивирус показывает предупреждение": "If antivirus displays a warning",
    "Если транскрибация долго не начинается": "If transcription takes a long time to start",
    "Если нет NVIDIA GPU": "If NVIDIA GPU is unavailable",
    "Правовое и этичное использование": "Legal and ethical use",
    "Используйте приложение только для аудио, видео и файлов, к которым у вас есть законный доступ.": "Use this application only for audio, video, and files that you may legally access.",
    "Не используйте приложение для скрытой записи чужих разговоров, перехвата сообщений, обхода ограничений доступа или распространения чужих материалов без разрешения правообладателя.": "Do not use this application for covert recording, intercepting messages, bypassing access restrictions, or distributing content without permission.",
    "Откройте Параметры Windows → Конфиденциальность и безопасность → Микрофон.": "Open Windows Settings → Privacy & security → Microphone.",
    "Включите доступ к микрофону.": "Enable microphone access.",
    "Включите доступ к микрофону для классических приложений.": "Enable microphone access for desktop applications.",
    "После изменения разрешений перезапустите приложение.": "Restart the application after changing permissions.",
    "Выберите правильный микрофон в списке устройств.": "Choose the correct microphone in the device list.",
    "Проверьте, двигается ли индикатор уровня микрофона.": "Check whether the microphone level meter moves.",
    "Убедитесь, что звук реально воспроизводится в Windows.": "Make sure audio is actually playing in Windows.",
    "Если индикатор системного звука не двигается, попробуйте другое output-устройство.": "If the system audio meter does not move, try another output device.",
    "Проверьте громкость Windows и громкость приложения-источника.": "Check Windows volume and the source application volume.",
    "При первом запуске модель Whisper может скачиваться несколько минут.": "The Whisper model may take several minutes to download on first use.",
    "Проверьте интернет.": "Check your internet connection.",
    "На CPU транскрибация может быть медленнее, чем на GPU.": "Transcription may be slower on CPU than on GPU.",
  };
  const prefixPairs = {
    "Не удалось скачать аудио по ссылке:": "Could not download audio from URL:",
    "GPU/CUDA недоступна или модель не смогла загрузиться на GPU.": "GPU/CUDA is unavailable or the model could not load on the GPU.",
    "Выберите Авто или CPU.": "Select Auto or CPU.",
    "Технические подробности:": "Technical details:",
    "Не удалось получить данные от локального сервера.": "Could not reach the local server.",
  };

  const originals = new WeakMap();
  let language = localStorage.getItem(STORAGE_KEY) === "en" ? "en" : DEFAULT_LANGUAGE;

  function t(key, variables = {}) {
    let value = translations[language][key] || translations[DEFAULT_LANGUAGE][key] || key;
    for (const [name, replacement] of Object.entries(variables)) {
      value = value.replaceAll(`{${name}}`, String(replacement));
    }
    return value;
  }

  function translateText(value) {
    if (language === "ru") {
      return value;
    }
    if (staticPairs[value]) {
      return staticPairs[value];
    }
    let translated = value;
    for (const [source, replacement] of Object.entries(prefixPairs)) {
      translated = translated.replace(source, replacement);
    }
    return translated;
  }

  function apply(root = document.body) {
    if (!root) {
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.nodeValue.trim() || ["SCRIPT", "STYLE"].includes(node.parentElement?.tagName)) {
        continue;
      }
      if (!originals.has(node)) {
        originals.set(node, node.nodeValue);
      }
      const original = originals.get(node);
      const trimmed = original.trim();
      node.nodeValue = original.replace(trimmed, translateText(trimmed));
    }

    for (const element of root.querySelectorAll("[data-i18n]")) {
      element.textContent = t(element.dataset.i18n);
    }
  }

  function setLanguage(nextLanguage) {
    language = nextLanguage === "en" ? "en" : DEFAULT_LANGUAGE;
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    apply();
    document.dispatchEvent(new CustomEvent("lat-language-change", { detail: { language } }));
  }

  const select = document.querySelector("#uiLanguageSelect");
  if (select) {
    select.value = language;
    select.addEventListener("change", () => setLanguage(select.value));
  }
  document.documentElement.lang = language;
  apply();
  window.LATI18N = { DEFAULT_LANGUAGE, STORAGE_KEY, translations, t, translateText, apply, setLanguage, getLanguage: () => language };
})();
