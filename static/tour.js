(function () {
  const STORAGE_KEY = "latTourSeen";
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
    ["#queueSection", "Очередь файлов", "Добавьте несколько локальных файлов и обработайте их последовательно."],
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
    card.querySelector("h2").textContent = title;
    card.querySelector("p").textContent = text;
    card.querySelector("[data-role='counter']").textContent = `Шаг ${nextIndex + 1} из ${steps.length}`;
    card.querySelector("[data-role='back']").disabled = !findStep(nextIndex - 1, -1);
    card.querySelector("[data-role='next']").textContent = findStep(nextIndex + 1, 1) ? "Далее" : "Завершить";
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
      createButton("Назад", () => showStep(activeIndex - 1, -1), true),
      createButton("Завершить", finish, true),
      createButton("Далее", () => {
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
    prompt.innerHTML = "<h2>Короткое обучение</h2><p>Хотите пройти короткое обучение по программе?</p><div class='tour-actions'></div>";
    const promptBackdrop = document.createElement("div");
    promptBackdrop.className = "tour-backdrop";
    const closePrompt = () => {
      localStorage.setItem(STORAGE_KEY, "true");
      prompt.remove();
      promptBackdrop.remove();
    };
    prompt.querySelector(".tour-actions").append(
      createButton("Не сейчас", closePrompt, true),
      createButton("Да, показать обучение", () => {
        closePrompt();
        start();
      }),
    );
    document.body.append(promptBackdrop, prompt);
  }

  document.querySelector("#restartTourButton")?.addEventListener("click", start);
  window.LocalAudioTranscriberTour = { maybePrompt, start };
})();
