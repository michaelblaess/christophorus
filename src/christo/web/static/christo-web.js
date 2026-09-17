/* Christophorus Web: Theme-Auswahl, Tabellen (Tabulator), Suche, Dialog.
   Welche Tabelle entsteht, entscheidet data-ansicht am .app-Element. */
(function () {
  "use strict";

  var app = document.querySelector(".app");
  if (!app) return;
  var ansicht = app.dataset.ansicht || "";
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
  function passt(zeile, felder) {
    var suchtext = felder.map(function (f) { return zeile[f]; }).join(" ").toLocaleLowerCase("de-DE");
    var kurz = begriff.toLocaleLowerCase("de-DE");
    return suchtext.indexOf(kurz) >= 0 || suchtext.split(".").join("").indexOf(kurz.split(".").join("")) >= 0;
  }

  // --- Spalten je Ansicht --------------------------------------------------
  var mitMarke = function (c) { return markiere(c.getValue()); };
  var grau = function (c) { return '<span class="gedaempft">' + markiere(c.getValue()) + "</span>"; };
  var warnzeichen = function (c) {
    return c.getValue() ? '<span title="' + escapeHtml(c.getValue()) + '">▲</span>' : "";
  };

  var FAHRTENSPALTEN = [
    { title: "", field: "warnung", width: 32, hozAlign: "center", formatter: warnzeichen },
    { title: "Datum", field: "datum", width: 116, formatter: mitMarke },
    { title: "Tag", field: "tag", width: 54, formatter: grau },
    { title: "Fahrzeit", field: "zeit", width: 148, formatter: grau },
    { title: "Ziel", field: "ziel", minWidth: 240, formatter: mitMarke },
    { title: "Reisezweck", field: "zweck", minWidth: 170, formatter: mitMarke },
    { title: "km Anfang", field: "kmAnfang", width: 112, hozAlign: "right", headerHozAlign: "right", formatter: grau },
    { title: "km Ende", field: "kmEnde", width: 104, hozAlign: "right", headerHozAlign: "right", formatter: grau },
    { title: "geschäftl.", field: "geschaeftlich", width: 118, hozAlign: "right", headerHozAlign: "right", formatter: mitMarke },
    { title: "privat", field: "privat", width: 90, hozAlign: "right", headerHozAlign: "right", formatter: mitMarke }
  ];

  var ANSICHTEN = {
    liste: {
      quelle: function () { return "/api/fahrten?jahr=" + jahr + "&monat=" + monat; },
      spalten: FAHRTENSPALTEN,
      suchfelder: ["datum", "tag", "zeit", "ziel", "zweck", "kmAnfang", "kmEnde", "geschaeftlich", "privat"],
      leer: "Keine Fahrt passt zur Suche.",
      oeffnen: function (d) { return "/fahrten/" + d.id + "/bearbeiten"; },
      zeile: function (el, d) {
        el.classList.toggle("wt-warn", !!d.warnung);
        el.classList.toggle("privatfahrt", !!d.privatfahrt);
      }
    },
    jahresliste: {
      quelle: function () { return "/api/fahrten?jahr=" + jahr; },
      spalten: FAHRTENSPALTEN,
      suchfelder: ["datum", "tag", "zeit", "ziel", "zweck", "kmAnfang", "kmEnde", "geschaeftlich", "privat"],
      leer: "Keine Fahrt passt zur Suche.",
      gruppe: "monat",
      oeffnen: function (d) { return "/fahrten/" + d.id + "/bearbeiten"; },
      zeile: function (el, d) {
        el.classList.toggle("wt-warn", !!d.warnung);
        el.classList.toggle("privatfahrt", !!d.privatfahrt);
      }
    },
    blacklist: {
      quelle: function () { return "/api/blacklist"; },
      spalten: [
        { title: "Datum", field: "datum", width: 130, formatter: mitMarke },
        { title: "Grund", field: "grund", minWidth: 300, formatter: mitMarke },
        { title: "Belege", field: "belege", width: 90, hozAlign: "right", headerHozAlign: "right", formatter: grau }
      ],
      suchfelder: ["datum", "grund"],
      leer: "Kein Sperrtag passt zur Suche.",
      oeffnen: function (d) { return "/blacklist/" + d.id + "/bearbeiten"; }
    },
    belege: {
      quelle: function () { return "/api/belege"; },
      spalten: [
        { title: "Art", field: "art", width: 100, formatter: grau },
        { title: "Datum", field: "datum", width: 116, formatter: mitMarke },
        { title: "Zeit", field: "zeit", width: 72, formatter: grau },
        { title: "Bezug", field: "bezug", minWidth: 280, formatter: mitMarke },
        { title: "Bemerkung", field: "bemerkung", width: 130, hozAlign: "right", headerHozAlign: "right", formatter: mitMarke },
        {
          title: "Datei", field: "datei", minWidth: 220,
          formatter: function (c) {
            var d = c.getRow().getData();
            if (!d.vorhanden) return '<span class="schwere-warning" title="Datei nicht gefunden">▲ ' + markiere(c.getValue()) + "</span>";
            return '<a href="/belege/' + d.id + '/datei" target="_blank" rel="noopener">' + markiere(c.getValue()) + "</a>";
          }
        }
      ],
      suchfelder: ["art", "datum", "bezug", "bemerkung", "datei"],
      leer: "Kein Beleg passt zur Suche."
    }
  };

  // --- Tabelle -------------------------------------------------------------
  var tabelle = null;
  var konfig = ANSICHTEN[ansicht];
  if (konfig && document.getElementById("tabelle")) {
    var optionen = {
      ajaxURL: konfig.quelle(),
      layout: "fitColumns",
      height: "100%",
      headerSortElement: "",
      columnDefaults: { headerSort: false },
      placeholder: konfig.leer,
      columns: konfig.spalten
    };
    if (konfig.gruppe) {
      optionen.groupBy = konfig.gruppe;
      optionen.groupHeader = function (wert, anzahl) {
        return escapeHtml(wert) + '<span class="gedaempft"> · ' + anzahl + (anzahl === 1 ? " Fahrt" : " Fahrten") + "</span>";
      };
    }
    if (konfig.zeile) {
      optionen.rowFormatter = function (row) { konfig.zeile(row.getElement(), row.getData()); };
    }
    tabelle = new Tabulator("#tabelle", optionen);

    if (konfig.oeffnen) {
      tabelle.on("rowClick", function (e, row) {
        htmx.ajax("GET", konfig.oeffnen(row.getData()), { target: "#dialog", swap: "outerHTML" });
      });
    }
  }

  function suchen(wert) {
    begriff = wert.trim();
    if (!tabelle) return;
    if (begriff) {
      tabelle.setFilter(function (zeile) { return passt(zeile, konfig.suchfelder); });
    } else {
      tabelle.clearFilter();
    }
    tabelle.redraw(true);
  }
  var eingabe = document.getElementById("suche");
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

  // Nach jeder Aenderung: Tabelle und Uebersicht neu laden. Serverseitig gezeichnete
  // Ansichten (Kalender, Jahr) holen die ganze Seite, das ist billiger als Teilstuecke.
  document.body.addEventListener("datenGeaendert", function () {
    if (!tabelle) { location.reload(); return; }
    tabelle.setData(konfig.quelle()).then(function () { suchen(begriff); });
    if (document.getElementById("uebersicht")) {
      var ziel = "/uebersicht?jahr=" + jahr + (ansicht === "jahresliste" ? "&art=jahr" : "&monat=" + monat);
      htmx.ajax("GET", ziel, { target: "#uebersicht", swap: "outerHTML" });
    }
  });
})();
