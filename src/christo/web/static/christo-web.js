/* Christophorus Web: Theme-Auswahl, Fahrtenliste (Tabulator), Suche, Dialog. */
(function () {
  "use strict";

  var app = document.querySelector(".app");
  if (!app) return;
  var jahr = app.dataset.jahr;
  var monat = app.dataset.monat;

  // --- Theme ---------------------------------------------------------------
  var auswahl = document.getElementById("theme");
  if (auswahl && window.WebThemes) {
    auswahl.innerHTML = WebThemes.selectable
      .map(function (t) {
        return '<option value="' + t.name + '">' + t.title + (WebThemes.dark[t.name] ? "" : " (hell)") + "</option>";
      })
      .join("");
    auswahl.value = document.documentElement.getAttribute("data-web-theme");
    auswahl.addEventListener("change", function () {
      WebThemes.apply(auswahl.value);
      try { localStorage.setItem("christo-theme", auswahl.value); } catch (e) { /* ohne Speicher weiter */ }
    });
  }

  // --- Suche ---------------------------------------------------------------
  var begriff = "";
  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function markiere(text) {
    var roh = escapeHtml(text);
    if (!begriff) return roh;
    // Reine Ziffern duerfen Tausenderpunkte ueberspringen: "17977" markiert "17.977"
    var muster = /^\d+$/.test(begriff)
      ? begriff.split("").join("\\.?")
      : begriff.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return roh.replace(new RegExp(muster, "gi"), function (m) { return "<mark>" + m + "</mark>"; });
  }
  function passt(zeile) {
    var suchtext = [zeile.datum, zeile.tag, zeile.zeit, zeile.ziel, zeile.zweck, zeile.kmAnfang, zeile.kmEnde,
      zeile.geschaeftlich, zeile.privat].join(" ").toLocaleLowerCase("de-DE");
    var kurz = begriff.toLocaleLowerCase("de-DE");
    return suchtext.indexOf(kurz) >= 0 || suchtext.split(".").join("").indexOf(kurz.split(".").join("")) >= 0;
  }

  // --- Tabelle -------------------------------------------------------------
  var mitMarke = function (c) { return markiere(c.getValue()); };
  var grau = function (c) { return '<span class="gedaempft">' + markiere(c.getValue()) + "</span>"; };
  var tabelle = new Tabulator("#tabelle", {
    ajaxURL: "/api/fahrten?jahr=" + jahr + "&monat=" + monat,
    layout: "fitColumns",
    height: "100%",
    headerSortElement: "",
    columnDefaults: { headerSort: false },
    placeholder: "Keine Fahrt passt zur Suche.",
    rowFormatter: function (row) {
      var d = row.getData();
      row.getElement().classList.toggle("wt-warn", !!d.warnung);
      row.getElement().classList.toggle("privatfahrt", !!d.privatfahrt);
    },
    columns: [
      { title: "", field: "warnung", width: 32, hozAlign: "center",
        formatter: function (c) { return c.getValue() ? '<span title="' + escapeHtml(c.getValue()) + '">▲</span>' : ""; } },
      { title: "Datum", field: "datum", width: 116, formatter: mitMarke },
      { title: "Tag", field: "tag", width: 54, formatter: grau },
      { title: "Fahrzeit", field: "zeit", width: 148, formatter: grau },
      { title: "Ziel", field: "ziel", minWidth: 260, formatter: mitMarke },
      { title: "Reisezweck", field: "zweck", minWidth: 180, formatter: mitMarke },
      { title: "km Anfang", field: "kmAnfang", width: 112, hozAlign: "right", headerHozAlign: "right", formatter: grau },
      { title: "km Ende", field: "kmEnde", width: 104, hozAlign: "right", headerHozAlign: "right", formatter: grau },
      { title: "geschäftl.", field: "geschaeftlich", width: 118, hozAlign: "right", headerHozAlign: "right", formatter: mitMarke },
      { title: "privat", field: "privat", width: 90, hozAlign: "right", headerHozAlign: "right", formatter: mitMarke }
    ]
  });

  tabelle.on("rowClick", function (e, row) {
    htmx.ajax("GET", "/fahrten/" + row.getData().id + "/bearbeiten", { target: "#dialog", swap: "outerHTML" });
  });

  var eingabe = document.getElementById("suche");
  function suchen(wert) {
    begriff = wert.trim();
    if (begriff) { tabelle.setFilter(passt); } else { tabelle.clearFilter(); }
    tabelle.redraw(true);
  }
  if (eingabe) {
    eingabe.addEventListener("input", function () { suchen(eingabe.value); });
    eingabe.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { eingabe.value = ""; suchen(""); }
    });
  }

  // --- Dialog --------------------------------------------------------------
  window.schliesseDialog = function () {
    var dialog = document.getElementById("dialog");
    if (dialog) dialog.outerHTML = '<div id="dialog"></div>';
  };
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && document.querySelector(".dialog-hintergrund")) window.schliesseDialog();
  });
  document.body.addEventListener("click", function (e) {
    if (e.target && e.target.classList.contains("dialog-hintergrund")) window.schliesseDialog();
  });

  // Nach dem Speichern: Liste und Uebersicht neu laden
  document.body.addEventListener("fahrtGespeichert", function () {
    tabelle.setData("/api/fahrten?jahr=" + jahr + "&monat=" + monat).then(function () { suchen(begriff); });
    htmx.ajax("GET", "/uebersicht?jahr=" + jahr + "&monat=" + monat, { target: "#uebersicht", swap: "outerHTML" });
  });
})();
