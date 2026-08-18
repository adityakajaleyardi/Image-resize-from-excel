/** The folder images page: choosing a folder of images, then handing them to a job. */
(function () {
  "use strict";

  var OPTION_FIELDS = ["operation_mode", "max_file_size_mb"];

  var IMAGE_PATTERN = /\.(jpe?g|png|bmp|gif|webp|tiff?|ico)$/i;

  var LOOKUPS = [
    { id: "unit-mapping", field: "unit_mapping" },
    { id: "unit-summary", field: "unit_summary" },
    { id: "property-list", field: "property_list" },
  ];

  var picker = document.getElementById("image-folder");
  var selectionBox = document.getElementById("selection");
  var selectionSummary = document.getElementById("selection-summary");
  var selectionNote = document.getElementById("selection-note");
  var selectionList = document.getElementById("selection-list");
  var clearButton = document.getElementById("clear-selection");

  var limits = document.getElementById("upload-limits");
  var maxFiles = Number(limits.dataset.maxFiles);
  var maxFileMb = Number(limits.dataset.maxFileMb);
  var maxTotalMb = Number(limits.dataset.maxTotalMb);

  var selected = [];

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  /** The path the library keys on: everything below the folder the user picked. */
  function keyPathOf(file) {
    var full = file.webkitRelativePath || file.name;
    var parts = full.split("/");
    return parts.length > 1 ? parts.slice(1).join("/") : full;
  }

  function totalBytes() {
    return selected.reduce(function (sum, file) {
      return sum + file.size;
    }, 0);
  }

  function renderSelection(ignoredCount, misplacedCount) {
    if (!selected.length) {
      selectionBox.hidden = true;
      return;
    }

    var total = totalBytes();
    selectionSummary.textContent =
      selected.length + (selected.length === 1 ? " image" : " images") + ", " + formatSize(total);

    var notes = [];
    if (ignoredCount) {
      notes.push(
        ignoredCount + (ignoredCount === 1 ? " other file was" : " other files were") + " ignored"
      );
    }
    if (misplacedCount) {
      notes.push(
        misplacedCount +
          (misplacedCount === 1 ? " image is" : " images are") +
          " not filed as property code / document type / image, so they will be skipped"
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
      item.textContent = keyPathOf(file) + " (" + formatSize(file.size) + ")";
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

  function collect() {
    var all = Array.prototype.slice.call(picker.files || []);
    selected = all.filter(function (file) {
      return IMAGE_PATTERN.test(file.name) && !file.name.startsWith(".");
    });

    // The library only accepts <property>/<doc type>/<file>. Warn early rather
    // than letting the run report everything as ignored.
    var misplaced = selected.filter(function (file) {
      return keyPathOf(file).split("/").length !== 3;
    });

    renderSelection(all.length - selected.length, misplaced.length);
  }

  function readOptions() {
    var values = {};
    OPTION_FIELDS.forEach(function (name) {
      values[name] = document.getElementById(name).value;
    });
    return values;
  }

  function lookupFile(id) {
    var input = document.getElementById(id);
    return input.files && input.files.length ? input.files[0] : null;
  }

  JobRunner.create({
    createUrl: "/api/folder/jobs",
    unit: "images",
    startLabel: "Process",
    busyLabel: "Processing...",

    buildPayload: function () {
      if (!selected.length) {
        throw new Error("Choose a folder containing images before starting.");
      }
      if (selected.length > maxFiles) {
        throw new Error(
          "You selected " +
            selected.length +
            " images. Please process at most " +
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
        payload.append("paths", file.webkitRelativePath || file.name);
      });

      LOOKUPS.forEach(function (lookup) {
        var file = lookupFile(lookup.id);
        if (file) {
          payload.append(lookup.field, file, file.name);
        }
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
        (summary.succeeded || 0) +
        " processed, " +
        (summary.skipped || 0) +
        " with no matching units, " +
        (summary.failed || 0) +
        " failed out of " +
        (summary.total || 0) +
        " images.";
      if (summary.written) {
        sentence += " " + summary.written + " files were written.";
      }
      return sentence;
    },

    onStartOver: function () {
      selected = [];
      picker.value = "";
      LOOKUPS.forEach(function (lookup) {
        document.getElementById(lookup.id).value = "";
        var chosen = document.getElementById(lookup.id + "-chosen");
        chosen.textContent = "";
        chosen.hidden = true;
      });
      renderSelection(0, 0);
    },

    saveDefault: { url: "/api/folder/options/default", read: readOptions },
  });

  picker.addEventListener("change", collect);

  clearButton.addEventListener("click", function () {
    selected = [];
    picker.value = "";
    renderSelection(0, 0);
  });

  LOOKUPS.forEach(function (lookup) {
    var input = document.getElementById(lookup.id);
    var chosen = document.getElementById(lookup.id + "-chosen");
    input.addEventListener("change", function () {
      var file = lookupFile(lookup.id);
      chosen.textContent = file ? "Ready: " + file.name : "";
      chosen.classList.toggle("is-set", Boolean(file));
      chosen.hidden = !file;
    });
  });
})();
