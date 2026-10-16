/**
 * Shared front end for anything that runs as a background job.
 *
 * Every tool page has the same skeleton: a form, a progress card and a results
 * card. This module owns submitting the form, polling the job, rendering the log
 * and offering the download. A tool supplies only what is specific to it: where
 * to post, how to build the payload and how to word the summary.
 *
 * Counters are discovered from the markup. Any element with data-count="<level>"
 * is incremented when an event of that level arrives.
 */
(function (global) {
  "use strict";

  var POLL_INTERVAL_MS = 1000;
  var LEVEL_TAGS = { ok: "OK", fail: "FAIL", skip: "SKIP", warning: "WARN", info: "INFO" };

  function create(config) {
    var form = document.getElementById("run-form");
    var startButton = document.getElementById("start");
    var cancelButton = document.getElementById("cancel");
    var formError = document.getElementById("form-error");

    var progressCard = document.getElementById("progress-card");
    var progressBar = document.getElementById("progress-bar");
    var progressFill = document.getElementById("progress-fill");
    var progressState = document.getElementById("progress-state");
    var logBox = document.getElementById("log");

    var resultsCard = document.getElementById("results-card");
    var resultsSummary = document.getElementById("results-summary");
    var resultsExtra = document.getElementById("results-extra");
    var downloadZip = document.getElementById("download-zip");
    var downloadLog = document.getElementById("download-log");
    var startOverButton = document.getElementById("start-over");

    var counterNodes = {};
    Array.prototype.forEach.call(document.querySelectorAll("[data-count]"), function (node) {
      counterNodes[node.getAttribute("data-count")] = node;
    });

    var startLabel = config.startLabel || "Start";
    var busyLabel = config.busyLabel || "Working...";
    var unit = config.unit || "items";

    var currentJobId = null;
    var pollTimer = null;
    var tallies = {};

    function showError(message) {
      formError.textContent = message;
      formError.hidden = false;
      formError.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function clearError() {
      formError.hidden = true;
      formError.textContent = "";
    }

    function readErrorDetail(response, fallback) {
      return response
        .json()
        .then(function (body) {
          if (typeof body.detail === "string") {
            return body.detail;
          }
          if (Array.isArray(body.detail) && body.detail.length) {
            return body.detail
              .map(function (item) {
                return item.msg || String(item);
              })
              .join(" ");
          }
          return fallback;
        })
        .catch(function () {
          return fallback;
        });
    }

    function resetCounters() {
      tallies = {};
      Object.keys(counterNodes).forEach(function (level) {
        tallies[level] = 0;
        counterNodes[level].textContent = "0";
      });
    }

    function appendEvents(events) {
      if (!events.length) {
        return;
      }
      var atBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
      var fragment = document.createDocumentFragment();

      events.forEach(function (event) {
        if (Object.prototype.hasOwnProperty.call(tallies, event.level)) {
          tallies[event.level] += 1;
        }

        var line = document.createElement("div");
        line.className = "log-line log-" + event.level;

        var tag = document.createElement("span");
        tag.className = "log-tag";
        tag.textContent = LEVEL_TAGS[event.level] || event.level.toUpperCase();

        var text = document.createElement("span");
        text.textContent = event.row ? "Row " + event.row + ": " + event.message : event.message;

        line.append(tag, text);
        fragment.append(line);
      });

      logBox.append(fragment);
      if (atBottom) {
        logBox.scrollTop = logBox.scrollHeight;
      }

      Object.keys(counterNodes).forEach(function (level) {
        counterNodes[level].textContent = tallies[level];
      });
    }

    function updateProgress(state) {
      var percent = state.total ? Math.round((state.processed / state.total) * 100) : 0;
      progressFill.style.width = percent + "%";
      progressBar.setAttribute("aria-valuenow", String(percent));

      if (state.status === "queued") {
        progressState.textContent = "Waiting for a free slot...";
      } else if (state.status === "running") {
        progressState.textContent = state.total
          ? "Processing " +
            state.processed +
            " of " +
            state.total +
            " " +
            unit +
            " (" +
            percent +
            "%)"
          : "Getting started...";
      } else if (state.status === "cancelled") {
        progressState.textContent = "Cancelled after " + state.processed + " " + unit + ".";
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
      startButton.textContent = startLabel;

      if (state.status === "failed") {
        showError(state.error || "The run could not finish. See the log above.");
        return;
      }

      resultsSummary.textContent = config.summarise(state);

      if (resultsExtra) {
        resultsExtra.replaceChildren();
        if (config.renderExtra) {
          config.renderExtra(state, resultsExtra);
        }
      }

      downloadZip.hidden = !state.has_results;
      downloadZip.href = "/api/jobs/" + state.id + "/download";
      downloadLog.hidden = !state.has_log;
      downloadLog.href = "/api/jobs/" + state.id + "/log";

      resultsCard.hidden = false;
      resultsCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function poll(cursor) {
      fetch("/api/jobs/" + currentJobId + "?cursor=" + cursor)
        .then(function (response) {
          if (!response.ok) {
            return readErrorDetail(response, "This run is no longer available.").then(function (
              detail
            ) {
              showError(detail);
              startButton.disabled = false;
              cancelButton.hidden = true;
            });
          }
          return response.json().then(function (state) {
            appendEvents(state.events || []);
            updateProgress(state);
            if (state.finished) {
              showResults(state);
              return;
            }
            pollTimer = setTimeout(function () {
              poll(state.cursor);
            }, POLL_INTERVAL_MS);
          });
        })
        .catch(function () {
          progressState.textContent = "Lost connection to the server. Retrying...";
          pollTimer = setTimeout(function () {
            poll(cursor);
          }, POLL_INTERVAL_MS * 3);
        });
    }

    function resetRunUi() {
      clearTimeout(pollTimer);
      clearError();
      resetCounters();
      logBox.textContent = "";
      progressFill.style.width = "0%";
      progressBar.setAttribute("aria-valuenow", "0");
      progressState.textContent = "Starting...";
      resultsCard.hidden = true;
      downloadZip.hidden = true;
      downloadLog.hidden = true;
    }

    function failToStart(message) {
      showError(message);
      startButton.disabled = false;
      startButton.textContent = startLabel;
      progressCard.hidden = true;
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();

      var payload;
      try {
        payload = config.buildPayload();
      } catch (error) {
        showError(error.message);
        return;
      }
      if (!payload) {
        return;
      }

      resetRunUi();
      progressCard.hidden = false;
      startButton.disabled = true;
      startButton.textContent = "Starting...";

      fetch(config.createUrl, { method: "POST", body: payload })
        .then(function (response) {
          if (!response.ok) {
            return readErrorDetail(response, "The run could not be started.").then(failToStart);
          }
          return response.json().then(function (created) {
            currentJobId = created.id;
            startButton.textContent = busyLabel;
            cancelButton.hidden = false;
            cancelButton.disabled = false;
            cancelButton.textContent = "Cancel";
            progressCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
            poll(0);
          });
        })
        .catch(function () {
          failToStart("Could not reach the server. Check that it is still running.");
        });
    });

    cancelButton.addEventListener("click", function () {
      if (!currentJobId) {
        return;
      }
      cancelButton.disabled = true;
      cancelButton.textContent = "Cancelling...";
      fetch("/api/jobs/" + currentJobId + "/cancel", { method: "POST" }).catch(function () {
        cancelButton.disabled = false;
        cancelButton.textContent = "Cancel";
      });
    });

    startOverButton.addEventListener("click", function () {
      currentJobId = null;
      resetRunUi();
      progressCard.hidden = true;
      if (config.onStartOver) {
        config.onStartOver();
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    if (config.saveDefault) {
      var saveButton = document.getElementById("save-default");
      var saveStatus = document.getElementById("save-status");

      saveButton.addEventListener("click", function () {
        saveStatus.textContent = "";
        clearError();

        fetch(config.saveDefault.url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(config.saveDefault.read()),
        })
          .then(function (response) {
            if (!response.ok) {
              return readErrorDetail(response, "These settings could not be saved.").then(showError);
            }
            saveStatus.textContent = "Saved. These settings will be pre-filled next time.";
            setTimeout(function () {
              saveStatus.textContent = "";
            }, 4000);
          })
          .catch(function () {
            showError("Could not reach the server.");
          });
      });
    }

    resetCounters();

    return { showError: showError, clearError: clearError };
  }

  global.JobRunner = { create: create };
})(window);
