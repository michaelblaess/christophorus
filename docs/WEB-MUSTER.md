# Web-Muster aus christo.web

Was sich beim Bau der Weboberfläche von Christophorus bewährt hat, aufgeschrieben für die
Übernahme in andere Webprojekte (Anlass war RDE.Web mit ASP.NET Core MVC, Bootstrap 5 und
Tabulator). Die Muster sind absichtlich ohne FastHTML-Wissen lesbar: was hier "Route" heißt,
ist dort ein Controller, was "Fragment" heißt, ein PartialView.

Stand 17.09.2026, alles am laufenden Programm geprüft.

## 1. Ein Reiter ist eine eigene Adresse

Die sieben Reiter (Monatsliste, Jahresliste, Kalender, Jahr, Blacklist, Belege, Arbeitszeit)
sind keine Zustände im Browser, sondern sieben Adressen. Das kostet einen Seitenaufbau beim
Wechsel und spart alles andere: Der Link ist teilbar, der Zurück-Knopf funktioniert, ein
Neuladen landet wieder an derselben Stelle, und kein Reiter hält heimlich veraltete Daten.

Der Zeitraum steht im Abfrageteil (`?jahr=2026&monat=5`), nicht in der Sitzung. Die
Pfeilnavigation ist damit ein gewöhnlicher Link.

## 2. Tabellen kommen als Daten, nicht als HTML

Jede Tabelle ist ein leeres `<div>`, das Tabulator aus einer JSON-Route füllt
(`/api/fahrten`, `/api/blacklist`, `/api/belege`). Vorteile im Alltag:

- Nach einer Änderung lädt nur die Tabelle neu, nicht die Seite.
- Die Suche filtert ohne Serveranfrage über die schon geladenen Zeilen.
- Die Formatierung (Tausenderpunkt, deutsches Datum) entsteht **serverseitig** und liegt
  fertig in der Zeile. Der Browser formatiert nichts nach, also gibt es auch keine zweite
  Wahrheit über das Zahlenformat.

Die Zeile trägt zusätzlich Merkmale für die Darstellung (`privatfahrt`, `warnung`), aus denen
der `rowFormatter` die Klassen setzt. Fachlogik bleibt damit auf dem Server.

## 3. Dialoge sind Serverfragmente, Fehler stehen am Feld

Ein Klick auf eine Zeile holt den Bearbeiten-Dialog als HTML-Stück und hängt es in ein
festes `<div id="dialog">`. Abschicken geht an dieselbe Route zurück:

- **Alles in Ordnung:** Antwort ist ein leerer Dialog plus ein Ereignis im Kopf
  (`HX-Trigger: datenGeaendert`). Der Dialog verschwindet, die Tabelle lädt neu.
- **Eingabefehler:** Antwort ist derselbe Dialog mit den eingegebenen Werten und einem
  Fehlertext je Feld. Kein Datenverlust, keine Fehlerliste oben ohne Bezug.

Geprüft wird ausschließlich auf dem Server. Eine zweite Prüfung im Browser wäre eine zweite
Stelle, an der die Regeln stehen, und die beiden laufen früher oder später auseinander.

## 4. Ein Ereignis für alle Änderungen

Statt `fahrtGespeichert`, `fahrtGeloescht`, `sperrtagGespeichert` gibt es genau ein Ereignis
`datenGeaendert`. Der Browser hört einmal darauf und lädt Tabelle und Kennzahlen neu. Die
serverseitig gezeichneten Ansichten (Kalender, Jahr) haben keine Tabelle und laden die ganze
Seite - das ist billiger als Teilaktualisierungen für Ansichten, die man selten ändert.

## 5. Suche, die deutsche Zahlen versteht

Das Suchfeld filtert über alle sichtbaren Spalten. Zwei Kleinigkeiten machen den Unterschied:

- Eine reine Ziffernfolge darf Tausenderpunkte überspringen: `17977` findet `17.977`.
- Der Treffer wird im Text markiert (`<mark>`), nicht nur die Zeile gezeigt.

`Esc` leert das Feld. Die Kennzahlen unter der Tabelle rechnen weiter über den ganzen
Zeitraum, nicht über die Treffer - sonst sieht man eine Monatssumme, die es nicht gibt.

## 6. Themes als CSS-Variablen, eine einzige Stilebene

Alle Farben kommen aus Variablen (`--wt-bg-primary`, `--wt-accent-fill`, `--wt-red` und so
weiter), die das Hilfsprojekt web-themes erzeugt. Kein einziger Farbwert steht im eigenen
Stylesheet. Das Umschalten setzt ein Attribut am `<html>`-Element, mehr nicht.

Wichtig für Bootstrap-Projekte: Tabler belegt `data-theme` selbst. Das eigene Theme braucht
deshalb ein eigenes Attribut (`data-web-theme`), und `data-bs-theme` wird zusätzlich auf hell
oder dunkel gesetzt, damit die Bausteine von Bootstrap mitziehen.

## 7. Namen können mit dem Framework kollidieren

Die Kalenderfelder hießen zuerst `.tag`. Tabler hat unter demselben Namen eine
Badge-Komponente mit `display: inline-flex`, also liefen die Einträge im Tagesfeld
nebeneinander statt untereinander. Das Fehlerbild sah nach einem Layoutfehler aus, nicht nach
einer Namenskollision.

Gegenmittel: eigene Klassennamen vor dem Einbau gegen das Framework-Stylesheet prüfen, und
im Zweifel ein Präfix nehmen (`kalendertag-*`). Ein kurzer `grep` über die Vendor-CSS-Datei
findet das in Sekunden.

## 8. Downloads über ein Formular, nicht über einen Link

Der Export ist eine Auswahl (Excel, JSON, Markdown) plus Knopf in einem `<form method="get">`.
Der Browser lädt die Datei herunter und lässt die Seite stehen. Die Datei entsteht in einem
temporären Verzeichnis und geht als Antwort mit
`Content-Disposition: attachment; filename*=UTF-8''...` raus - der Stern und die Kodierung
sind nötig, sobald Umlaute im Dateinamen stehen.

## 9. Deutsche Formate rein wie raus

Eingabe und Ausgabe sprechen dieselbe Sprache: Datum `TT.MM.JJJJ`, Kilometer mit
Tausenderpunkt, Liter mit Komma. Die Umrechnung steht an genau einer Stelle
(`services/formatting.py`) und wird von Oberfläche, Web und Tests gemeinsam benutzt.

Beim Lesen wird großzügig geparst (`1.500` und `1500` und `1 500`), beim Schreiben streng
formatiert. Fehlertexte sagen, was zu tun ist ("Datum bitte als TT.MM.JJJJ eintragen, zum
Beispiel 16.05.2026"), nicht, was falsch war.

## 10. Vorgabewerte müssen zu denen passen, die der Kern liest

Die Einstellungsmaske las einen Schalter mit dem Vorgabewert "aus", während die
Plausibilitätsprüfung denselben Schlüssel mit "an" liest. Ergebnis: Die Maske zeigte einen
leeren Haken, und das erste Speichern hätte die Toleranz unbemerkt abgeschaltet.

Die Vorgabewerte gehören deshalb neben den Schalter geschrieben und werden von einem Test
gegen die Werte des Kerns gehalten. Das ist kein Sonderfall dieser Anwendung: Überall, wo
eine Maske Einstellungen mit Standardwerten anzeigt, ist das die stillste Fehlerquelle.

## 11. Arbeitskopie statt gleichzeitigem Zugriff

Die Weboberfläche arbeitet auf einer Kopie der Datenbank, angelegt über die Backup-API von
SQLite (konsistent, auch wenn die andere Anwendung gerade schreibt). Das nimmt dem Projekt
die ganze Frage nach Sperren und Nebenläufigkeit ab, solange die Web-Version ein Werkzeug
zum Ansehen und Ausprobieren ist. Die Belege liegen weiterhin beim Original und werden von
dort ausgeliefert, nur lesend und nur über die IDs, die in der Datenbank stehen.

## 12. Was sich im Browser beweisen lässt, nicht behaupten

Zu jedem Reiter gehört ein Durchlauf im echten Browser (playwright-core mit Edge headless),
der klickt, speichert, löscht und dabei Konsolenfehler sowie externe Anfragen mitschreibt.
Zwei Dinge hat erst dieser Durchlauf gezeigt: die Namenskollision aus Punkt 7 und ein
`<details>`-Block ohne `<summary>`, der im Browser das Wort "Details" statt der eigenen
Beschriftung anzeigte. Beides war in den Tests unsichtbar, weil beides korrektes HTML ist.
