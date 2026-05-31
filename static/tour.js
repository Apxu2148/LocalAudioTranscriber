(function () {
  const STORAGE_KEY = "latTourSeen";
  const english = {
    "Общий статус": "Overall status",
    "Здесь отображается состояние локального сервера, устройств и ffmpeg.": "This shows the state of the local server, devices, and ffmpeg.",
    "Режим записи": "Recording mode",
    "Выберите микрофон, системный звук или запись двух отдельных файлов.": "Choose microphone, system audio, or two separate recording files.",
    "Микрофон": "Microphone",
    "Выберите микрофон, с которого нужно записывать голос и окружающие звуки.": "Choose the microphone used to record voice and ambient sound.",
    "Системный звук": "System audio",
    "Выберите устройство вывода Windows для записи звука через WASAPI loopback.": "Choose a Windows output device for WASAPI loopback recording.",
    "Индикаторы уровня": "Level meters",
    "Проверьте движение индикаторов перед началом записи.": "Check that the meters move before recording.",
    "Запись": "Recording",
    "Этими кнопками запускается и останавливается запись WAV-файлов.": "These buttons start and stop WAV recording.",
    "Таймер записи": "Recording timer",
    "Во время записи здесь видна текущая длительность. После остановки сохраняется итог.": "The current duration is shown while recording and the final duration remains after stopping.",
    "Модель Whisper": "Whisper model",
    "Выберите баланс скорости, качества и требований к памяти.": "Choose the balance between speed, quality, and memory usage.",
    "Доступность модели": "Model availability",
    "Интерфейс предупредит, если модель еще нужно скачать.": "The interface warns you when a model still needs to be downloaded.",
    "Последняя запись": "Latest recording",
    "Эти кнопки транскрибируют файлы, созданные последней записью.": "These buttons transcribe files created by the latest recording.",
    "Отдельный файл": "Single file",
    "Здесь можно транскрибировать один локальный аудио- или видеофайл.": "Transcribe one local audio or video file here.",
    "Поддерживаемые форматы": "Supported formats",
    "Поддерживаются .wav, .mp3, .m4a и .mp4. У MP4 анализируется только звук.": ".wav, .mp3, .m4a, and .mp4 are supported. Only the audio track is analyzed for MP4.",
    "Папки": "Folders",
    "Откройте recordings и transcripts, чтобы найти записи и результаты.": "Open recordings and transcripts to find recordings and results.",
    "Очередь файлов": "File and URL queue",
    "Добавьте локальные файлы или публичные ссылки и обработайте их последовательно.": "Add local files or public URLs and process them sequentially.",
    "Помощь": "Help",
    "В этом блоке собраны подсказки по устройствам, моделям и диагностике.": "This block contains device, model, and troubleshooting hints.",
    "Правовое использование": "Legal use",
    "Работайте только с материалами, к которым у вас есть законный доступ.": "Only use content that you may legally access.",
    "Назад": "Back",
    "Далее": "Next",
    "Завершить": "Finish",
    "Короткое обучение": "Quick tour",
    "Хотите пройти короткое обучение по программе?": "Would you like a quick tour of the application?",
    "Не сейчас": "Not now",
    "Да, показать обучение": "Yes, start the tour",
  };
  const tr = (text) => window.LATI18N?.getLanguage() === "en" ? (english[text] || text) : text;
  const steps = [
    ["#systemStatus", "Общий статус", "Здесь отображается состояние локального сервера, устройств и ffmpeg."],
    ["#recordingModeSelect", "Режим записи", "Выберите микрофон, системный звук или запись двух отдельных файлов."],
    ["#micDeviceSelect", "Микрофон", "Выберите микрофон, с которого нужно записывать голос и окружающие звуки."],
    ["#outputDeviceSelect", "Системный звук", "Выберите устройство вывода Windows для записи звука через WASAPI loopback."],
    [".level-grid", "Индикаторы уровня", "Проверьте движение индикаторов перед началом записи."],
    ["#startRecordButton", "Запись", "Этими кнопками запускается и останавливается запись WAV-файлов."],
    ["#recordingTimer", "Таймер записи", "Во время записи здесь видна текущая длительность. После остановки сохраняется итог."],
    ["#whisperModelSelect", "Модель Whisper", "Выберите баланс скорости, качества и требований к памяти."],
    ["#modelDownloadWarning", "Доступность модели", "Интерфейс предупредит, если модель еще нужно скачать."],
    ["#recordingTranscribeActions", "Последняя запись", "Эти кнопки транскрибируют файлы, созданные последней записью."],
    ["#transcribeForm", "Отдельный файл", "Здесь можно транскрибировать один локальный аудио- или видеофайл."],
    ["#supportedFormats", "Поддерживаемые форматы", "Поддерживаются .wav, .mp3, .m4a и .mp4. У MP4 анализируется только звук."],
    [".storage-grid", "Папки", "Откройте recordings и transcripts, чтобы найти записи и результаты."],
    ["#queueSection", "Очередь файлов", "Добавьте локальные файлы или публичные ссылки и обработайте их последовательно."],
    [".help-block", "Помощь", "В этом блоке собраны подсказки по устройствам, моделям и диагностике."],
    ["#legalUsage", "Правовое использование", "Работайте только с материалами, к которым у вас есть законный доступ."],
  ];

  let activeIndex = -1;
  let highlighted = null;
  let savedStyles = null;
  let backdrop = null;
  let card = null;

  function createButton(text, onClick, secondary = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    if (secondary) {
      button.dataset.secondary = "true";
    }
    button.addEventListener("click", onClick);
    return button;
  }

  function removeHighlight() {
    if (!highlighted || !savedStyles) {
      return;
    }
    highlighted.style.position = savedStyles.position;
    highlighted.style.zIndex = savedStyles.zIndex;
    highlighted.style.boxShadow = savedStyles.boxShadow;
    highlighted.style.borderRadius = savedStyles.borderRadius;
    highlighted = null;
    savedStyles = null;
  }

  function finish() {
    removeHighlight();
    backdrop?.remove();
    card?.remove();
    backdrop = null;
    card = null;
    activeIndex = -1;
    localStorage.setItem(STORAGE_KEY, "true");
  }

  function findStep(index, direction) {
    let nextIndex = index;
    while (nextIndex >= 0 && nextIndex < steps.length) {
      const element = document.querySelector(steps[nextIndex][0]);
      if (element) {
        return [nextIndex, element];
      }
      nextIndex += direction;
    }
    return null;
  }

  function showStep(index, direction = 1) {
    const match = findStep(index, direction);
    if (!match) {
      finish();
      return;
    }

    removeHighlight();
    const [nextIndex, element] = match;
    activeIndex = nextIndex;
    highlighted = element;
    savedStyles = {
      position: element.style.position,
      zIndex: element.style.zIndex,
      boxShadow: element.style.boxShadow,
      borderRadius: element.style.borderRadius,
    };
    if (window.getComputedStyle(element).position === "static") {
      element.style.position = "relative";
    }
    element.style.zIndex = "1002";
    element.style.boxShadow = "0 0 0 4px #f0c14b, 0 0 0 9999px rgba(24, 32, 42, 0.62)";
    element.style.borderRadius = "6px";
    element.scrollIntoView({ behavior: "smooth", block: "center" });

    const [, title, text] = steps[nextIndex];
    card.querySelector("h2").textContent = tr(title);
    card.querySelector("p").textContent = tr(text);
    card.querySelector("[data-role='counter']").textContent = window.LATI18N?.getLanguage() === "en"
      ? `Step ${nextIndex + 1} of ${steps.length}`
      : `Шаг ${nextIndex + 1} из ${steps.length}`;
    card.querySelector("[data-role='back']").disabled = !findStep(nextIndex - 1, -1);
    card.querySelector("[data-role='next']").textContent = tr(findStep(nextIndex + 1, 1) ? "Далее" : "Завершить");
  }

  function start() {
    finish();
    backdrop = document.createElement("div");
    backdrop.className = "tour-backdrop";
    card = document.createElement("section");
    card.className = "tour-card";
    card.innerHTML = "<small data-role='counter'></small><h2></h2><p></p><div class='tour-actions'></div>";
    const actions = card.querySelector(".tour-actions");
    actions.append(
      createButton(tr("Назад"), () => showStep(activeIndex - 1, -1), true),
      createButton(tr("Завершить"), finish, true),
      createButton(tr("Далее"), () => {
        if (findStep(activeIndex + 1, 1)) {
          showStep(activeIndex + 1, 1);
        } else {
          finish();
        }
      }),
    );
    actions.children[0].dataset.role = "back";
    actions.children[2].dataset.role = "next";
    document.body.append(backdrop, card);
    showStep(0);
  }

  function maybePrompt() {
    if (localStorage.getItem(STORAGE_KEY) === "true") {
      return;
    }

    const prompt = document.createElement("section");
    prompt.className = "tour-prompt";
    prompt.innerHTML = `<h2>${tr("Короткое обучение")}</h2><p>${tr("Хотите пройти короткое обучение по программе?")}</p><div class='tour-actions'></div>`;
    const promptBackdrop = document.createElement("div");
    promptBackdrop.className = "tour-backdrop";
    const closePrompt = () => {
      localStorage.setItem(STORAGE_KEY, "true");
      prompt.remove();
      promptBackdrop.remove();
    };
    prompt.querySelector(".tour-actions").append(
      createButton(tr("Не сейчас"), closePrompt, true),
      createButton(tr("Да, показать обучение"), () => {
        closePrompt();
        start();
      }),
    );
    document.body.append(promptBackdrop, prompt);
  }

  document.querySelector("#restartTourButton")?.addEventListener("click", start);
  document.addEventListener("lat-language-change", () => {
    if (activeIndex >= 0) {
      showStep(activeIndex);
    }
  });
  window.LocalAudioTranscriberTour = { maybePrompt, start };
})();
