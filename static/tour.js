(function () {
  const STORAGE_KEY = "latTourSeen";
  const steps = [
    ["#transcriptionSettings", "tourSettingsTitle", "tourSettingsText"],
    ["#recordingSection", "tourRecordingTitle", "tourRecordingText"],
    ["#transcriptionSources", "tourSourcesTitle", "tourSourcesText"],
    ["#globalQueuePanel", "tourQueueTitle", "tourQueueText"],
    ["#queueMetricsProgress", "tourMetricsTitle", "tourMetricsText"],
    ["#transcriptText", "tourResultTitle", "tourResultText"],
    ["#filesSection", "tourFilesTitle", "tourFilesText"],
    ["#urlLimitations", "tourUrlTitle", "tourUrlText"],
    ["#benchmarkSection", "tourBenchmarkTitle", "tourBenchmarkText"],
    ["#uiLanguageSelect", "tourLanguageTitle", "tourLanguageText"],
    ["#helpSection", "tourHelpTitle", "tourHelpText"],
    ["#restartTourButton", "tourReplayTitle", "tourReplayText"],
  ];

  let activeIndex = -1;
  let highlighted = null;
  let savedStyles = null;
  let backdrop = null;
  let card = null;

  const t = (key, variables = {}) => window.LATI18N?.t(key, variables) || key;

  function createButton(key, onClick, secondary = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = t(key);
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

    const [, titleKey, textKey] = steps[nextIndex];
    card.querySelector("h2").textContent = t(titleKey);
    card.querySelector("p").textContent = t(textKey);
    card.querySelector("[data-role='counter']").textContent = t("tourCounter", {
      current: nextIndex + 1,
      total: steps.length,
    });
    card.querySelector("[data-role='back']").disabled = !findStep(nextIndex - 1, -1);
    card.querySelector("[data-role='next']").textContent = t(findStep(nextIndex + 1, 1) ? "tourNext" : "tourFinish");
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
      createButton("tourBack", () => showStep(activeIndex - 1, -1), true),
      createButton("tourFinish", finish, true),
      createButton("tourNext", () => {
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
    prompt.innerHTML = `<h2>${t("tourPromptTitle")}</h2><p>${t("tourPromptText")}</p><div class="tour-actions"></div>`;
    const promptBackdrop = document.createElement("div");
    promptBackdrop.className = "tour-backdrop";
    const closePrompt = () => {
      localStorage.setItem(STORAGE_KEY, "true");
      prompt.remove();
      promptBackdrop.remove();
    };
    prompt.querySelector(".tour-actions").append(
      createButton("tourNotNow", closePrompt, true),
      createButton("tourStart", () => {
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
  window.LocalAudioTranscriberTour = { maybePrompt, start, steps };
})();
