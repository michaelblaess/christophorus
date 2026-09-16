#!/usr/bin/env node
/**
 * Livegang-Gate fuer Michaels Webseiten.
 *
 * Prueft den gebauten Stand in dist/ gegen die Regeln aus dem Skill
 * web-specialist. Rueckgabewert 1, sobald eine Bedingung faellt - das Gate ist
 * bewusst hart, eine Liste von Vorsaetzen haette niemand gelesen.
 *
 * Aufruf:
 *   npm run build && node pruefe-gate.mjs
 *
 * Konfiguriert wird ueber web-gate.json neben dieser Datei. Was dort nicht
 * zutrifft, wird unter "ausnahmen" mit Begruendung abgeschaltet - eine
 * Ausnahme ohne Text zaehlt als Verstoss.
 */

import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { resolveTxt } from 'node:dns/promises';

const WURZEL = process.cwd();
const KONFIG_DATEI = join(WURZEL, 'web-gate.json');

// Im gerenderten HTML gilt die cp1252-Regel nicht: der Browser liest UTF-8,
// und typografische Anfuehrungszeichen sehen dort besser aus als gerade.
// Michael hat das am 17.08.2026 so entschieden.
//
// Em- und En-Dash bleiben trotzdem drin. Sie sind kein Encoding-Problem,
// sondern ein Stilbefund - der Linter in michaels-writing-style fuehrt sie als
// Erkennungszeichen maschinell erzeugter Texte.
const VERBOTENE_ZEICHEN = [
  ['—', 'Em-Dash'],
  ['–', 'En-Dash'],
];

const befunde = [];

function pruefe(name, bestanden, hinweis = '') {
  befunde.push({ name, bestanden, hinweis });
}

function lies(pfad) {
  return readFileSync(pfad, 'utf8');
}

/** Sammelt alle HTML-Dateien unterhalb eines Ordners. */
function htmlDateien(ordner) {
  const gefunden = [];
  for (const eintrag of readdirSync(ordner)) {
    const voll = join(ordner, eintrag);
    if (statSync(voll).isDirectory()) {
      gefunden.push(...htmlDateien(voll));
    } else if (eintrag.endsWith('.html')) {
      gefunden.push(voll);
    }
  }
  return gefunden;
}

/**
 * Loest die HTML-Entities auf, die in Michaels Seiten vorkommen.
 *
 * Noetig, weil Astro das Copyright-Zeichen als &copy; ausliefert und ein
 * Vergleich gegen das Literal sonst falschen Alarm gibt.
 */
function entschaerft(html) {
  return html
    .replace(/&copy;/gi, '©')
    .replace(/&amp;/gi, '&')
    .replace(/&#38;/g, '&')
    .replace(/&nbsp;/gi, ' ');
}

/** Zieht den Inhalt des ersten Treffers eines Musters, sonst null. */
function ersterTreffer(html, muster) {
  const treffer = html.match(muster);
  return treffer ? treffer[1].trim() : null;
}

/** Wandelt einen Dateipfad in die Route, unter der die Seite erreichbar ist. */
function route(datei, distPfad) {
  const rel = relative(distPfad, datei).split(sep).join('/');
  return '/' + rel.replace(/index\.html$/, '').replace(/\.html$/, '');
}

async function main() {
  if (!existsSync(KONFIG_DATEI)) {
    console.error('web-gate.json fehlt. Ohne Konfiguration prueft das Gate nichts.');
    return 1;
  }
  const konfig = JSON.parse(lies(KONFIG_DATEI));
  const ausnahmen = konfig.ausnahmen ?? {};
  const distPfad = join(WURZEL, konfig.dist ?? 'dist');

  if (!existsSync(distPfad)) {
    console.error(`${konfig.dist ?? 'dist'} fehlt. Erst bauen, dann pruefen.`);
    return 1;
  }

  const dateien = htmlDateien(distPfad);
  const seiten = dateien.map((datei) => ({
    datei,
    route: route(datei, distPfad),
    html: lies(datei),
  }));

  // Die Fehlerseite ist sprachneutral und gehoert in keine Sprachzaehlung.
  const inhaltsseiten = seiten.filter((s) => !s.route.startsWith('/404'));

  pruefe('Seiten gebaut', seiten.length > 0, `${seiten.length} HTML-Dateien`);

  // --- Rechtsseiten -------------------------------------------------------
  const rechtsseiten = konfig.rechtsseiten ?? {};
  for (const [sprache, pfade] of Object.entries(rechtsseiten)) {
    for (const pfad of pfade) {
      const da = seiten.some((s) => s.route.replace(/\/$/, '').endsWith(`/${pfad}`));
      pruefe(`Rechtsseite ${sprache}/${pfad}`, da, da ? '' : 'nicht im Build gefunden');
    }
  }

  // Das Telemediengesetz ist im Mai 2024 vom Digitale-Dienste-Gesetz abgeloest
  // worden. Viele Vorlagen im Netz sind veraltet, und einmal geschrieben faellt
  // es niemandem mehr auf.
  const mitTmg = seiten.filter((s) => /\bTMG\b/.test(s.html)).map((s) => s.route);
  pruefe('Kein Verweis auf das TMG (seit 2024 DDG)', mitTmg.length === 0, mitTmg.join(', '));

  // Verlinkt sein muessen sie auch, sonst existieren sie nur formal.
  const alleRechtspfade = Object.values(rechtsseiten).flat();
  const ohneVerweis = seiten.filter(
    (s) => !alleRechtspfade.some((pfad) => s.html.includes(`${pfad}`)),
  );
  pruefe(
    'Rechtsseiten von jeder Seite verlinkt',
    ohneVerweis.length === 0,
    ohneVerweis.map((s) => s.route).join(', '),
  );

  // --- Sprachparitaet -----------------------------------------------------
  const sprachen = Object.entries(konfig.sprachen ?? {});
  if (sprachen.length > 1) {
    const [, hauptPrefix] = sprachen[0];
    const zaehlung = sprachen.map(([kuerzel, prefix]) => {
      const anzahl = inhaltsseiten.filter((s) =>
        prefix ? s.route.startsWith(`/${prefix}/`) : !sprachen.some(([, p]) => p && s.route.startsWith(`/${p}/`)),
      ).length;
      return { kuerzel, anzahl };
    });
    const gleich = new Set(zaehlung.map((z) => z.anzahl)).size === 1;
    pruefe(
      'Sprachparitaet',
      gleich,
      zaehlung.map((z) => `${z.kuerzel}: ${z.anzahl}`).join(', '),
    );
    void hauptPrefix;
  }

  // --- Metadaten je Seite -------------------------------------------------
  const titel = new Map();
  const beschreibungen = new Map();
  const ohneCanonical = [];
  const ohneHreflang = [];

  for (const seite of seiten) {
    const t = ersterTreffer(seite.html, /<title>([^<]*)<\/title>/i);
    const d = ersterTreffer(seite.html, /<meta\s+name=["']description["']\s+content=["']([^"']*)["']/i);
    if (t) titel.set(seite.route, entschaerft(t));
    if (d) beschreibungen.set(seite.route, entschaerft(d));
    // Die Fehlerseite wird nicht indexiert und braucht daher weder eine
    // kanonische Adresse noch Sprachverweise.
    if (seite.route.startsWith('/404')) continue;
    if (!/<link[^>]+rel=["']canonical["']/i.test(seite.html)) ohneCanonical.push(seite.route);
    if (sprachen.length > 1 && !/hreflang=/i.test(seite.html)) ohneHreflang.push(seite.route);
  }

  // Eindeutig muss je Sprache sein, nicht global. Zwei Sprachfassungen
  // derselben Seite duerfen denselben Titel tragen, zwei deutsche nicht.
  const jeSprache = (karte) =>
    sprachen.map(([kuerzel, prefix]) => {
      const teil = new Map(
        [...karte].filter(([r]) =>
          prefix ? r.startsWith(`/${prefix}/`) : !sprachen.some(([, p]) => p && r.startsWith(`/${p}/`)),
        ),
      );
      return { kuerzel, teil };
    });

  pruefe('Titel auf jeder Seite', titel.size === seiten.length,
    `${titel.size} von ${seiten.length}`);
  for (const { kuerzel, teil } of jeSprache(titel)) {
    pruefe(`Titel eindeutig (${kuerzel})`, new Set(teil.values()).size === teil.size, doppelte(teil));
  }
  pruefe('Beschreibung auf jeder Seite', beschreibungen.size === seiten.length,
    `${beschreibungen.size} von ${seiten.length}`);
  for (const { kuerzel, teil } of jeSprache(beschreibungen)) {
    pruefe(`Beschreibung eindeutig (${kuerzel})`, new Set(teil.values()).size === teil.size, doppelte(teil));
  }
  pruefe('Canonical gesetzt', ohneCanonical.length === 0, ohneCanonical.join(', '));
  if (sprachen.length > 1) {
    pruefe('hreflang gesetzt', ohneHreflang.length === 0, ohneHreflang.join(', '));
  }

  // --- Pflichtbausteine im Markup ----------------------------------------
  const ohneToggle = seiten.filter((s) => !s.html.includes(konfig.themeToggleKennung ?? 'data-theme-toggle'));
  pruefe('Hell/Dunkel-Umschalter', ohneToggle.length === 0, ohneToggle.map((s) => s.route).join(', '));

  if (konfig.copyright) {
    const kern = konfig.copyright.slice(0, 24);
    const ohne = seiten.filter((s) => !entschaerft(s.html).includes(kern));
    pruefe('Copyright-Zeile', ohne.length === 0, ohne.map((s) => s.route).join(', '));
  }

  // --- Auslieferung -------------------------------------------------------
  const robots = join(distPfad, 'robots.txt');
  pruefe('robots.txt', existsSync(robots));
  if (existsSync(robots)) {
    pruefe('robots.txt nennt die Sitemap', /sitemap/i.test(lies(robots)));
  }
  pruefe('sitemap', existsSync(join(distPfad, 'sitemap-index.xml')) || existsSync(join(distPfad, 'sitemap.xml')));
  pruefe('404-Seite', existsSync(join(distPfad, '404.html')));
  const favicon = readdirSync(distPfad).some((d) => d.startsWith('favicon'));
  pruefe('Favicon', favicon);

  // --- Encoding -----------------------------------------------------------
  // Standardmaessig an. Wer die typografischen Zeichen im gerenderten HTML
  // bewusst zulaesst, setzt zeichenpruefung auf false und begruendet es in
  // RECHT.md - die cp1252-Regel der CLAUDE.md zielt auf Dateien, die durch
  // Windows-Werkzeuge laufen, nicht auf UTF-8-deklariertes Markup.
  if (konfig.zeichenpruefung !== false) {
    const mitVerbotenen = [];
    for (const seite of seiten) {
      for (const [zeichen, name] of VERBOTENE_ZEICHEN) {
        if (seite.html.includes(zeichen)) mitVerbotenen.push(`${seite.route} (${name})`);
      }
    }
    pruefe(
      'Keine cp1252-kritischen Zeichen',
      mitVerbotenen.length === 0,
      mitVerbotenen.slice(0, 8).join(', ') + (mitVerbotenen.length > 8 ? ` und ${mitVerbotenen.length - 8} weitere` : ''),
    );
  }

  // --- Einwilligung -------------------------------------------------------
  if (konfig.zaehlung) {
    const ohneBanner = seiten.filter((s) => !s.html.includes('cookieconsent') && !s.html.includes('data-einwilligung-oeffnen'));
    pruefe('Einwilligung eingebunden', ohneBanner.length === 0, ohneBanner.map((s) => s.route).join(', '));
    pruefe(
      'Einwilligung im Browser geprueft',
      existsSync(join(WURZEL, 'pruefe-einwilligung.mjs')),
      'pruefe-einwilligung.mjs muss zusaetzlich laufen, das Gate sieht nur das Markup',
    );
  }

  // --- Menschliche Gates --------------------------------------------------
  const rechtDatei = join(WURZEL, 'RECHT.md');
  if (!existsSync(rechtDatei)) {
    pruefe('RECHT.md vorhanden', false, 'Bildrechte und Marken kann kein Skript pruefen');
  } else {
    const recht = lies(rechtDatei);
    const offen = (recht.match(/^\s*-\s*\[ \]/gm) ?? []).length;
    pruefe('RECHT.md vollstaendig abgehakt', offen === 0, offen ? `${offen} offene Punkte` : '');
  }

  // --- DMARC --------------------------------------------------------------
  if (konfig.domain && !ausnahmen.dmarc) {
    try {
      const eintraege = await resolveTxt(`_dmarc.${konfig.domain}`);
      const text = eintraege.flat().join('');
      pruefe('DMARC gesetzt', text.includes('v=DMARC1'), text.slice(0, 60));
    } catch {
      pruefe('DMARC gesetzt', false, `kein TXT-Eintrag unter _dmarc.${konfig.domain}`);
    }
  } else if (ausnahmen.dmarc) {
    pruefe('DMARC (Ausnahme)', typeof ausnahmen.dmarc === 'string' && ausnahmen.dmarc.length > 10, ausnahmen.dmarc);
  }

  // --- Ausgabe ------------------------------------------------------------
  const gefallen = befunde.filter((b) => !b.bestanden);
  for (const b of befunde) {
    const marke = b.bestanden ? 'ok  ' : 'FEHL';
    console.log(`${marke} ${b.name}${b.hinweis ? ` - ${b.hinweis}` : ''}`);
  }
  console.log(`\n${befunde.length - gefallen.length} von ${befunde.length} Bedingungen erfüllt.`);
  return gefallen.length === 0 ? 0 : 1;
}

/** Nennt die Werte, die mehrfach vorkommen - fuer Titel und Beschreibungen. */
function doppelte(karte) {
  const zaehler = new Map();
  for (const wert of karte.values()) zaehler.set(wert, (zaehler.get(wert) ?? 0) + 1);
  return [...zaehler.entries()]
    .filter(([, n]) => n > 1)
    .map(([wert, n]) => `"${wert.slice(0, 40)}" ${n}x`)
    .join(', ');
}

main().then((code) => process.exit(code));
