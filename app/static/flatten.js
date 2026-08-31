/** The PDF flatten page: choosing a folder, then handing the PDFs to a job. */
(function () {
  "use strict";

  var OPTION_FIELDS = [
    "engine",
    "verify",
    "verify_dpi",
    "tolerance",
    "allow_raster",
    "raster_dpi",
    "flatten_annots",
  ];

  var picker = document.getElementById("pdf-folder");
  var filePicker = document.getElementById("pdf-files");
  var selectionBox = document.getElementById("selection");
  var selectionSummary = document.getElementById("selection-summary");
  var selectionNote = document.getElementById("selection-note");
  var selectionList = document.getElementById("selection-list");
  var clearButton = document.getElementById("clear-selection");

  var limits = document.getElementById("upload-limits");
  var maxFiles = Number(limits.dataset.maxFiles);
  var maxFileMb = Number(limits.dataset.maxFileMb);
  var maxTotalMb = Number(limits.dataset.maxTotalMb);

  var engine = document.getElementById("engine");
  var verify = document.getElementById("verify");
  var allowRaster = document.getElementById("allow_raster");

  var selected = [];

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function relativePathOf(file) {
    return file.webkitRelativePath || file.name;
  }

  function totalBytes() {
    return selected.reduce(function (sum, file) {
      return sum + file.size;
    }, 0);
  }

  function renderSelection(ignoredCount) {
    if (!selected.length) {
      selectionBox.hidden = true;
      return;
    }

    var total = totalBytes();
    selectionSummary.textContent =
      selected.length + (selected.length === 1 ? " PDF" : " PDFs") + ", " + formatSize(total);

    var notes = [];
    if (ignoredCount) {
      notes.push(
        ignoredCount + (ignoredCount === 1 ? " other file was" : " other files were") + " ignored"
      );
    }
    if (selected.length > maxFiles) {
      notes.push("that is more than the " + maxFiles + " allowed in one batch");
    }
    if (total > maxTotalMb * 1024 * 1024) {
      notes.push("that is over the " + maxTotalMb + " MB limit for one batch");
    }
    var oversized = selected.filter(function (file) {
      return file.size > maxFileMb * 1024 * 1024;
    });
    if (oversized.length) {
      notes.push(
        oversized.length +
          (oversized.length === 1 ? " file is" : " files are") +
          " over the " +
          maxFileMb +
          " MB limit for a single file"
      );
    }

    selectionNote.textContent = notes.length ? notes.join("; ") + "." : "";
    selectionNote.hidden = !notes.length;

    selectionList.replaceChildren();
    selected.slice(0, 12).forEach(function (file) {
      var item = document.createElement("li");
      item.textContent = relativePathOf(file) + " (" + formatSize(file.size) + ")";
      selectionList.append(item);
    });
    if (selected.length > 12) {
      var more = document.createElement("li");
      more.className = "muted";
      more.textContent = "and " + (selected.length - 12) + " more...";
      selectionList.append(more);
    }

    selectionBox.hidden = false;
  }

  function collect(input) {
    var all = Array.prototype.slice.call(input.files || []);
    var pdfs = all.filter(function (file) {
      return /\.pdf$/i.test(file.name);
    });
    selected = pdfs;
    renderSelection(all.length - pdfs.length);
  }

  function readOptions() {
    var values = {};
    OPTION_FIELDS.forEach(function (name) {
      var field = document.getElementById(name);
      values[name] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });
    return values;
  }

  function syncOptionState() {
    var verifying = verify.checked;
    ["verify_dpi", "tolerance"].forEach(function (name) {
      var field = document.getElementById(name);
      field.disabled = !verifying;
      field.closest(".setting").classList.toggle("is-disabled", !verifying);
    });

    var rasterUsed = engine.value === "raster" || allowRaster.checked;
    var rasterField = document.getElementById("raster_dpi");
    rasterField.disabled = !rasterUsed;
    rasterField.closest(".setting").classList.toggle("is-disabled", !rasterUsed);

    // Picking the raster engine outright makes the fallback switch meaningless.
    allowRaster.disabled = engine.value !== "auto";
    allowRaster.closest(".setting").classList.toggle("is-disabled", engine.value !== "auto");
  }

  JobRunner.create({
    createUrl: "/api/flatten/jobs",
    unit: "files",
    startLabel: "Flatten",
    busyLabel: "Flattening...",

    buildPayload: function () {
      if (!selected.length) {
        throw new Error("Choose a folder containing PDFs before starting.");
      }
      if (selected.length > maxFiles) {
        throw new Error(
          "You selected " +
            selected.length +
            " PDFs. Please flatten at most " +
            maxFiles +
            " at a time."
        );
      }
      if (totalBytes() > maxTotalMb * 1024 * 1024) {
        throw new Error(
          "The selection is " +
            formatSize(totalBytes()) +
            ", which is over the " +
            maxTotalMb +
            " MB limit. Please split it into smaller batches."
        );
      }

      var payload = new FormData();
      selected.forEach(function (file) {
        payload.append("files", file, file.name);
        payload.append("paths", relativePathOf(file));
      });

      var options = readOptions();
      Object.keys(options).forEach(function (name) {
        payload.append(name, options[name]);
      });
      return payload;
    },

    summarise: function (state) {
      var summary = state.summary || {};
      var sentence =
        (state.status === "cancelled" ? "Run cancelled. " : "") +
        (summary.flattened || 0) +
        " flattened, " +
        (summary.review || 0) +
        " need review, " +
        (summary.failed || 0) +
        " failed out of " +
        (summary.total || 0) +
        " PDFs.";
      if (summary.skipped) {
        sentence += " " + summary.skipped + " were not started.";
      }
      return sentence;
    },

    renderExtra: function (state, container) {
      var flagged = (state.summary || {}).flagged || [];
      if (!flagged.length) {
        return;
      }

      var heading = document.createElement("h3");
      heading.className = "subheading";
      heading.textContent = "Check these";
      container.append(heading);

      var list = document.createElement("ul");
      list.className = "flagged-list";
      flagged.forEach(function (item) {
        var row = document.createElement("li");

        var badge = document.createElement("span");
        badge.className =
          "badge " + (item.status === "Failed" ? "badge-fail" : "badge-warning");
        badge.textContent = item.status;

        var text = document.createElement("span");
        text.textContent = item.detail ? item.name + " — " + item.detail : item.name;

        row.append(badge, text);
        list.append(row);
      });
      container.append(list);
    },

    onStartOver: function () {
      selected = [];
      picker.value = "";
      filePicker.value = "";
      renderSelection(0);
    },

    saveDefault: { url: "/api/flatten/options/default", read: readOptions },
  });

  picker.addEventListener("change", function () {
    filePicker.value = "";
    collect(picker);
  });

  filePicker.addEventListener("change", function () {
    picker.value = "";
    collect(filePicker);
  });

  clearButton.addEventListener("click", function () {
    selected = [];
    picker.value = "";
    filePicker.value = "";
    renderSelection(0);
  });

  [engine, verify, allowRaster].forEach(function (field) {
    field.addEventListener("change", syncOptionState);
  });
  syncOptionState();
})();
