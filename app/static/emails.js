/** The email converter page: one export file in, HTML and screenshots out. */
(function () {
  "use strict";

  var OPTION_FIELDS = ["column_layout", "render_images"];

  var picker = document.getElementById("export");
  var chosen = document.getElementById("export-chosen");
  var limits = document.getElementById("upload-limits");
  var maxFileMb = Number(limits.dataset.maxFileMb);

  function readOptions() {
    var values = {};
    OPTION_FIELDS.forEach(function (name) {
      var field = document.getElementById(name);
      values[name] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });
    return values;
  }

  function chosenFile() {
    return picker.files && picker.files.length ? picker.files[0] : null;
  }

  JobRunner.create({
    createUrl: "/api/emails/jobs",
    unit: "emails",
    startLabel: "Convert",
    busyLabel: "Converting...",

    buildPayload: function () {
      var file = chosenFile();
      if (!file) {
        throw new Error("Choose an email export before starting.");
      }
      if (file.size > maxFileMb * 1024 * 1024) {
        throw new Error(
          "That file is over the " + maxFileMb + " MB limit. Please split the export."
        );
      }

      var payload = new FormData();
      payload.append("export", file, file.name);

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
        " converted, " +
        (summary.failed || 0) +
        " failed out of " +
        (summary.total || 0) +
        " emails.";

      if (summary.html_only) {
        sentence += " HTML only, no screenshots were requested.";
      } else if (summary.images) {
        sentence += " " + summary.images + " screenshots were rendered.";
      }
      if (summary.columns) {
        sentence += " Read from " + summary.columns + ".";
      }
      return sentence;
    },

    /** The failed records, so they can be chased without opening the log. */
    renderExtra: function (state, container) {
      var summary = state.summary || {};
      var failures = summary.failures || [];
      if (!failures.length) {
        return;
      }

      var heading = document.createElement("h3");
      heading.className = "subheading";
      heading.textContent = "These records did not convert";
      container.append(heading);

      var list = document.createElement("ul");
      list.className = "flagged-list";
      failures.forEach(function (item) {
        var row = document.createElement("li");

        var badge = document.createElement("span");
        badge.className = "badge badge-fail";
        badge.textContent = "Failed";

        var text = document.createElement("span");
        text.textContent = item.record_id + " — " + item.error;

        row.append(badge, text);
        list.append(row);
      });
      container.append(list);

      if (summary.failed > failures.length) {
        var note = document.createElement("p");
        note.className = "hint";
        note.textContent =
          "Showing the first " +
          failures.length +
          " of " +
          summary.failed +
          ". The rest are in the failures download.";
        container.append(note);
      }
    },

    onStartOver: function () {
      picker.value = "";
      showChosen();
    },

    saveDefault: { url: "/api/emails/options/default", read: readOptions },
  });

  function showChosen() {
    var file = chosenFile();
    chosen.textContent = file ? "Ready: " + file.name : "";
    chosen.classList.toggle("is-set", Boolean(file));
    chosen.hidden = !file;
  }

  picker.addEventListener("change", showChosen);
})();
