/** The image tool page. Everything generic lives in job-runner.js. */
(function () {
  "use strict";

  var CONFIG_FIELDS = [
    "operationmode",
    "propertytype",
    "manualsizing",
    "targetwidth",
    "targetheight",
    "maxfilesizemb",
    "optimizedsuffix",
  ];

  var manualSizing = document.getElementById("manualsizing");

  function readConfig() {
    var values = {};
    CONFIG_FIELDS.forEach(function (name) {
      var field = document.getElementById(name);
      values[name] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });
    return values;
  }

  function syncManualSizing() {
    var enabled = manualSizing.checked;
    ["targetwidth", "targetheight"].forEach(function (name) {
      var field = document.getElementById(name);
      field.disabled = !enabled;
      field.closest(".setting").classList.toggle("is-disabled", !enabled);
    });
  }

  JobRunner.create({
    createUrl: "/api/images/jobs",
    unit: "rows",
    startLabel: "Start",
    busyLabel: "Processing...",

    buildPayload: function () {
      var sourceInput = document.getElementById("source");
      if (!sourceInput.files.length) {
        throw new Error("Choose a source export before starting.");
      }

      var payload = new FormData();
      payload.append("source", sourceInput.files[0]);

      var mapInput = document.getElementById("property-map");
      if (mapInput.files.length) {
        payload.append("property_map", mapInput.files[0]);
      }

      var config = readConfig();
      Object.keys(config).forEach(function (name) {
        payload.append(name, config[name]);
      });
      return payload;
    },

    summarise: function (state) {
      var summary = state.summary || {};
      return (
        (state.status === "cancelled" ? "Run cancelled. " : "") +
        (summary.succeeded || 0) +
        " images processed, " +
        (summary.failed || 0) +
        " failed, " +
        (summary.skipped || 0) +
        " skipped out of " +
        (summary.total || 0) +
        " rows."
      );
    },

    saveDefault: { url: "/api/images/config/default", read: readConfig },
  });

  document.querySelectorAll('input[type="file"]').forEach(function (input) {
    var label = document.querySelector('.file-chosen[data-for="' + input.id + '"]');
    input.addEventListener("change", function () {
      var chosen = input.files.length > 0;
      label.textContent = chosen ? input.files[0].name : "No file chosen";
      label.classList.toggle("is-set", chosen);
    });
  });

  manualSizing.addEventListener("change", syncManualSizing);
  syncManualSizing();
})();
