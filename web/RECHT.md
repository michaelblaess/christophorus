# Rechteprüfung Christophorus (GitHub Pages)

Diese Datei ist Teil des Livegang-Gates. `pruefe-gate.mjs` zählt die offenen Kästchen und
fällt durch, solange eines davon leer ist. Was hier steht, kann kein Skript prüfen.

Jeder Haken braucht ein Datum und einen Befund.

## Bilder

- [x] **Jedes Bild einzeln geöffnet und angesehen.** 16.09.2026: Auf der Seite sind nur das
      Logo (`christophorus.png`), die daraus erzeugten Favicons und das Vorschaubild
      (`social-preview.png`). Keine Fotos. Das Logo hat Michael mit Nano Banana (Google Gemini)
      erzeugt, freigestellt wurde es lokal. Kein fremdes Motiv, kein Text im Bild.
- [x] **Beigaben und Verpackungen geprüft.** 16.09.2026: entfällt, es gibt keine Produktfotos.
- [x] **Handschriften, Namen, Unterschriften, Absender geprüft.** 16.09.2026: keine im Bild.
      Das Vorschaubild trägt nur den Projektnamen und eine Unterzeile.
- [x] **Entfernte Bilder sind auch aus dem Build verschwunden.** 16.09.2026: entfällt, statische
      Seite ohne Build-Werkzeug. `docs/` enthält genau die Dateien, die das Erzeugerskript und
      die Designvorlage anlegen.

## Marken und Namen

- [x] **Alle im Text genannten Marken stehen im Markenhinweis.** 16.09.2026: Genannt werden
      GitHub, Windows, macOS, Linux, Python, Textual, Excel und Apache. Hinweis im Impressum
      deckt GitHub, Windows, macOS, Linux, Python und Textual. Excel und Apache stehen nur
      beschreibend für Dateiformat und Lizenzname. Keine Markenlogos auf der Seite, die
      Plattformen sind reiner Text.
- [x] **Sonderfälle bedacht.** 16.09.2026: keine olympischen Begriffe, keine Personennamen außer
      dem Anbieter und Linus Torvalds im Markenhinweis.
- [x] **Eigener Projektname über TMview geprüft.** 16.09.2026, Positivkontrolle `codenames`
      mit 16 Treffern: `christophorus` 54 Treffer weltweit, in DE/EU keine eingetragene oder
      angemeldete Marke in den Klassen 9 oder 42. Eingetragen sind u.a. Mineralwasser, Wein,
      Apotheke und Kliniken. PyPI frei, auf GitHub kein gleichnamiges Softwareprojekt. Befund,
      keine Freigabe.
- [x] **Fremde Marken nicht im Domainnamen.** 16.09.2026: Adresse
      `michaelblaess.github.io/christophorus`, GitHub stellt die Subdomain für Pages selbst bereit.

## Texte und Zitate

- [x] **Keine übernommenen Textpassagen.** 16.09.2026: Texte selbst geschrieben. Haftung für
      Links und Streitbeilegung folgen sinngemäß dem Impressum von michaelblaess.de.
- [x] **Zitate aus dem gepflegten Pool.** 16.09.2026: entfällt, die Seite enthält kein Zitat.

## Rechtstexte

- [x] **Impressum nach § 5 DDG.** 16.09.2026: Anbieter, Anschrift und E-Mail wie auf
      michaelblaess.de, dazu Verantwortlicher nach § 18 Abs. 2 MStV, Hinweis auf das private,
      nicht-kommerzielle Projekt, Haftungsausschluss für die Software und Markenhinweis.
      Gate meldet keinen TMG-Verweis.
- [x] **Datenschutzerklärung nennt jeden eingebundenen Dienst.** 16.09.2026: einziger Dienst ist
      das Hosting bei GitHub Pages. Wortlaut zur IP-Protokollierung aus den GitHub Docs
      ("What is GitHub Pages?"), Verantwortlicher GitHub B.V. und DPF-Zertifizierung aus dem
      GitHub General Privacy Statement, beide am 16.09.2026 gelesen. Keine Cookies, kein
      Tracking, keine fremden Server, Local Storage nur für die Theme-Wahl.
- [x] **Einwilligung im Browser nachgewiesen.** 16.09.2026: entfällt, es gibt nichts
      einwilligungspflichtiges (`zaehlung: false`). Stattdessen die Aussagen der
      Datenschutzerklärung im Browser gemessen (Chromium, Seite unter `/christophorus/`
      ausgeliefert): alle 7 Seiten ohne Cookie, ohne Local- und Session-Storage, ohne Anfrage an
      einen fremden Host, ohne Konsolenfehler, alle internen Links 200. Nach einem Klick auf den
      Theme-Schalter genau ein Eintrag `theme` im Local Storage, weiterhin kein Cookie.

## Abweichungen vom Gate

- Abweichung: keine Domain in `web-gate.json`, damit keine DMARC-Prüfung.
- Begründung: Die Seite liegt auf einer github.io-Subdomain ohne eigenes Postfach. Kontakt
  läuft über mail@michaelblaess.de, dessen Domain separat betrieben wird.
- Datum: 16.09.2026
