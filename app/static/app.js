(function () {
  "use strict";

  const POLL_INTERVAL_MS = 1000;
  const CONFIG_FIELDS = [
    "operationmode",
    "propertytype",
    "manualsizing",
    "targetwidth",
    "targetheight",
    "maxfilesizemb",
    "optimizedsuffix",
  ];
  const LEVEL_TAGS = { ok: "OK", fail: "FAIL", skip: "SKIP", warning: "WARN", info: "INFO" };

  const form = document.getElementById("run-form");
  const startButton = document.getElementById("start");
  const cancelButton = document.getElementById("cancel");
  const saveDefaultButton = document.getElementById("save-default");
  const saveStatus = document.getElementById("save-status");
  const formError = document.getElementById("form-error");

  const progressCard = document.getElementById("progress-card");
  const progressBar = document.getElementById("progress-bar");
  const progressFill = document.getElementById("progress-fill");
  const progressState = document.getElementById("progress-state");
  const logBox = document.getElementById("log");
  const counters = {
    ok: document.getElementById("count-ok"),
    fail: document.getElementById("count-fail"),
    skip: document.getElementById("count-skip"),
  };

  const resultsCard = document.getElementById("results-card");
  const resultsSummary = document.getElementById("results-summary");
  const downloadZip = document.getElementById("download-zip");
  const downloadLog = document.getElementById("download-log");
  const startOverButton = document.getElementById("start-over");

  const manualSizing = document.getElementById("manualsizing");
  let currentJobId = null;
  let pollTimer = null;
  let tallies = { ok: 0, fail: 0, skip: 0 };

  function readConfig() {
    const values = {};
    CONFIG_FIELDS.forEach(function (name) {
      const field = document.getElementById(name);
      values[name] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });
    return values;
  }

  function syncManualSizing() {
    const enabled = manualSizing.checked;
    ["targetwidth", "targetheight"].forEach(function (name) {
      const field = document.getElementById(name);
      field.disabled = !enabled;
      field.closest(".setting").classList.toggle("is-disabled", !enabled);
    });
  }

  function showError(message) {
    formError.textContent = message;
    formError.hidden = false;
    formError.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearError() {
    formError.hidden = true;
    formError.textContent = "";
  }

  async function readErrorDetail(response, fallback) {
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        return body.detail;
      }
      if (Array.isArray(body.detail) && body.detail.length) {
        return body.detail.map((item) => item.msg || String(item)).join(" ");
      }
    } catch (error) {
      /* response was not JSON */
    }
    return fallback;
  }

  function appendEvents(events) {
    if (!events.length) {
      return;
    }
    const atBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
    const fragment = document.createDocumentFragment();

    events.forEach(function (event) {
      if (Object.prototype.hasOwnProperty.call(tallies, event.level)) {
        tallies[event.level] += 1;
      }

      const line = document.createElement("div");
      line.className = "log-line log-" + event.level;

      const tag = document.createElement("span");
      tag.className = "log-tag";
      tag.textContent = LEVEL_TAGS[event.level] || event.level.toUpperCase();

      const text = document.createElement("span");
      text.textContent = event.row ? "Row " + event.row + ": " + event.message : event.message;

      line.append(tag, text);
      fragment.append(line);
    });

    logBox.append(fragment);
    if (atBottom) {
      logBox.scrollTop = logBox.scrollHeight;
    }

    counters.ok.textContent = tallies.ok;
    counters.fail.textContent = tallies.fail;
    counters.skip.textContent = tallies.skip;
  }

  function updateProgress(state) {
    const percent = state.total ? Math.round((state.processed / state.total) * 100) : 0;
    progressFill.style.width = percent + "%";
    progressBar.setAttribute("aria-valuenow", String(percent));

    if (state.status === "queued") {
      progressState.textContent = "Waiting for a free slot...";
    } else if (state.status === "running") {
      progressState.textContent = state.total
        ? "Processing " + state.processed + " of " + state.total + " rows (" + percent + "%)"
        : "Reading your file...";
    } else if (state.status === "cancelled") {
      progressState.textContent = "Cancelled after " + state.processed + " rows.";
    } else if (state.status === "failed") {
      progressState.textContent = "The run could not finish.";
    } else {
      progressState.textContent = "Finished.";
      progressFill.style.width = "100%";
      progressBar.setAttribute("aria-valuenow", "100");
    }
  }

  function showResults(state) {
    cancelButton.hidden = true;
    startButton.disabled = false;
    startButton.textContent = "Start processing";

    if (state.status === "failed") {
      showError(state.error || "The run could not finish. See the log above.");
      return;
    }

    const summary = state.summary || {};
    const parts = [
      (summary.succeeded || 0) + " images processed",
      (summary.failed || 0) + " failed",
      (summary.skipped || 0) + " skipped",
    ];
    resultsSummary.textContent =
      (state.status === "cancelled" ? "Run cancelled. " : "") +
      parts.join(", ") +
      " out of " +
      (summary.total || 0) +
      " rows.";

    downloadZip.hidden = !state.has_results;
    downloadZip.href = "/api/jobs/" + state.id + "/download";
    downloadLog.hidden = !(summary.succeeded || summary.failed);
    downloadLog.href = "/api/jobs/" + state.id + "/log";

    resultsCard.hidden = false;
    resultsCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function poll(cursor) {
    let response;
    try {
      response = await fetch("/api/jobs/" + currentJobId + "?cursor=" + cursor);
    } catch (error) {
      progressState.textContent = "Lost connection to the server. Retrying...";
      pollTimer = setTimeout(function () {
        poll(cursor);
      }, POLL_INTERVAL_MS * 3);
      return;
    }

    if (!response.ok) {
      showError(await readErrorDetail(response, "This run is no longer available."));
      startButton.disabled = false;
      cancelButton.hidden = true;
      return;
    }

    const state = await response.json();
    appendEvents(state.events || []);
    updateProgress(state);

    if (state.finished) {
      showResults(state);
      return;
    }

    pollTimer = setTimeout(function () {
      poll(state.cursor);
    }, POLL_INTERVAL_MS);
  }

  function resetRunUi() {
    clearTimeout(pollTimer);
    clearError();
    tallies = { ok: 0, fail: 0, skip: 0 };
    logBox.textContent = "";
    counters.ok.textContent = "0";
    counters.fail.textContent = "0";
    counters.skip.textContent = "0";
    progressFill.style.width = "0%";
    progressBar.setAttribute("aria-valuenow", "0");
    progressState.textContent = "Starting...";
    resultsCard.hidden = true;
    downloadZip.hidden = true;
    downloadLog.hidden = true;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const sourceInput = document.getElementById("source");
    if (!sourceInput.files.length) {
      showError("Choose a source export before starting.");
      return;
    }

    resetRunUi();
    progressCard.hidden = false;
    startButton.disabled = true;
    startButton.textContent = "Starting...";

    const payload = new FormData();
    payload.append("source", sourceInput.files[0]);

    const mapInput = document.getElementById("property-map");
    if (mapInput.files.length) {
      payload.append("property_map", mapInput.files[0]);
    }

    const config = readConfig();
    Object.keys(config).forEach(function (name) {
      payload.append(name, config[name]);
    });

    let response;
    try {
      response = await fetch("/api/jobs", { method: "POST", body: payload });
    } catch (error) {
      showError("Could not reach the server. Check that it is still running.");
      startButton.disabled = false;
      startButton.textContent = "Start processing";
      progressCard.hidden = true;
      return;
    }

    if (!response.ok) {
      showError(await readErrorDetail(response, "The run could not be started."));
      startButton.disabled = false;
      startButton.textContent = "Start processing";
      progressCard.hidden = true;
      return;
    }

    const created = await response.json();
    currentJobId = created.id;
    startButton.textContent = "Processing...";
    cancelButton.hidden = false;
    cancelButton.disabled = false;
    progressCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    poll(0);
  });

  cancelButton.addEventListener("click", async function () {
    if (!currentJobId) {
      return;
    }
    cancelButton.disabled = true;
    cancelButton.textContent = "Cancelling...";
    try {
      await fetch("/api/jobs/" + currentJobId + "/cancel", { method: "POST" });
    } catch (error) {
      cancelButton.disabled = false;
      cancelButton.textContent = "Cancel";
    }
  });

  saveDefaultButton.addEventListener("click", async function () {
    saveStatus.textContent = "";
    clearError();

    let response;
    try {
      response = await fetch("/api/config/default", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(readConfig()),
      });
    } catch (error) {
      showError("Could not reach the server.");
      return;
    }

    if (!response.ok) {
      showError(await readErrorDetail(response, "These settings could not be saved."));
      return;
    }

    saveStatus.textContent = "Saved. These settings will be pre-filled next time.";
    setTimeout(function () {
      saveStatus.textContent = "";
    }, 4000);
  });

  startOverButton.addEventListener("click", function () {
    currentJobId = null;
    resetRunUi();
    progressCard.hidden = true;
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  document.querySelectorAll('input[type="file"]').forEach(function (input) {
    const label = document.querySelector('.file-chosen[data-for="' + input.id + '"]');
    input.addEventListener("change", function () {
      const chosen = input.files.length > 0;
      label.textContent = chosen ? input.files[0].name : "No file chosen";
      label.classList.toggle("is-set", chosen);
    });
  });

  manualSizing.addEventListener("change", syncManualSizing);
  syncManualSizing();
})();
