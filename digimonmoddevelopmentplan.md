Okay, mach mir einen mod wie unten beschrieben, kartentexte müssen komplett auf deutsch sein (inklusive kartentitel). die bilder für inner card image liefere ich selbst nach.

ALLE [todo]  in digimonmoddevelopmentplan.md beziehen sich direkt auf das was im folgenden festgelegt ist und muss bei ihrer Implementierung exakt beachtet werden. Dies gilt insbesondere aber nicht ausschließlich für: alle Spielmechaniken, die verschiedenen Arten der Digitation zu funktionieren haben (unteranderem welche bestimmten Relics (= Digivices, etc). erforderlich sind und welche Kartenkombination zum außlösen der Digitation gespielt werden muss), und für alles mögliche.

Überprüfe immer ob du neue [todo] zu digimonmoddevelopmentplan.md hinzufügen musst um das beschriebene exakt umzusetzen, wenn ja, tu es! 

Der Kartenblueprintmechanismus muss für diesen Mod so erweitert werden dass optional mit angegeben werden kann zu welchem Level eine Karte gehört, damit sichergestellt werden kann dass eine Karte nur dann gespielt werden kann wenn das Digimon gerade den dazu gehörigen Level hat. (Zb. Können Champion Level Karten nicht vom Rookie Digimon gespielt werden). Karten für ein NIEDERIGERES Level als das dass das Digimon gerade hat, können von diesem natürlich gespielt werden. (zum beispiel können also wenn das Digimon gerade auf Champion Level ist alle Karten ohne Level, alle Rookie Level Karten und alle Champion Karten gespielt werden). Alle Karten die zu einem Level gehören das HÖHER ist als das aktuelle Level des Digimons müssen mit dem entsprechenden Keyword als "unspielbar" gekennzeichnet werden (bitte forsche nach wie das so umgesetzt werden kann dass es im fertigen mod tatsächlich funktioniert!...dafür muss es in basemod bereits ein fertiges keyword geben). Wenn das Level des Digimon sich auf ein höheres Level ändert, dann wird das Keyword für die unspielbarkeit von den Karten des neuen Levels entfernt. Ändert sich das Level des Digimon auf ein niedrigeres Level, dann wird das Keyword für die unspielbarkeit zu allen Karten der höheren Levels hinzugefügt (falls noch nicht vorhanden!). 

ebenso liefere ich alle anderen bild assets nach, gib mir nur eine liste aller assets die gebraucht werden mit genauer Beschreibung, benötigter Auflösung und zu verwendendem Dateinamen.
nutze so weit wie möglich unsere existierenden features / Möglichkeiten aber implementiere neue falls nötig. für relics haben wir schon funktionalität

# Entwicklungsplan "DigitalesMonster"-Mod

Die folgenden Schritte sind als eigenständige, klar umrissene Aufgaben konzipiert. Jede Aufgabe ist mit `[todo]` markiert und baut auf den vorangehenden auf. Nach der Umsetzung aller Aufgaben ist der Mod gemäß der Spezifikation funktionsvollständig.

1. [complete] Projektgrundlage vorbereiten: Neues Mod-Paket unter Nutzung von `modules.modbuilder` anlegen, bestehenden Plugin-Manager einbinden und GraalPy-Experiment über `experimental.graalpy_runtime` aktivieren.
2. [complete] Forschungsbasis erweitern: Für jede Form der Agumon-Evolutionslinien (Adventure, Tamers, Savers inkl. Armor- und Burst-Varianten) deutsche Attackennamen und relevante Seriendetails über DigiPedia sammeln und im `research/`-Verzeichnis dokumentieren.
3. [complete] Persistente Datenfelder prüfen und erweitern: Bestehende Persistenz-Utilities (z. B. StSLib PersistFields) evaluieren und ein Speicherschema für Level-Stabilitätswerte (Start, Max, Aktuell pro Level) definieren.
4. [complete] Stance-Basisklasse prüfen: Vorhandene `Stance`-Implementierungen analysieren und ein erweiterbares Digimon-Stance-Framework entwerfen, das Plug-ins Zugriff auf alle relevanten Hooks erhält.
5. [complete] Rookie-Stance „Natürliches Rookie-Level" implementieren: HP-Werte, Grundwerte und Start-Buffs definieren, Stabilitätslogik einbinden und Charakterstart auf dieses Level festlegen.
6. [complete] Champion-Stance mit Digivice-Voraussetzungen implementieren: Stance-Werte, Stabilitätsverwaltung und Rückfallmechanik inklusive Trigger bei Stabilität ≤ 0 fertigstellen.
7. [complete] Ultra-Stance (inkl. SkullGreymon-Abzweig) implementieren: Zusätzliche Modifikatoren, Rückfallpfad und spezielle Debuffs für instabile Digitation ausarbeiten.
8. [complete] Mega- und Burst-Formen (inkl. Warp-Digitation) als Stances umsetzen: Werte, dauerhafte Buffs und Sonderlogiken (z. B. Burst Mode HP-Modifikatoren) hinterlegen.
9. [complete] Armor-Stance erstellen: Interaktion mit Digi-Eiern abbilden, alternative Level-Pipeline und Stabilitätsverhalten implementieren.
10. [complete] Jogress-/Fusion-Stance(s) (Omnimon etc.) implementieren: Zufalls- oder triggerbasierte Aktivierung und Rückkehrbedingungen definieren.
11. [complete] Level-Übergangsmanager programmieren: Karten-, Relikt- und Kampf-Trigger auswerten, Stabilitätsanpassungen ausführen und Stance-Wechsel koordinieren.
12. [complete] Stabilitäts-Persistenz verdrahten: Startwert-/Maxwert-Anpassungen bei Sieg/Niederlage erfassen und zwischen Runs speichern.
13. [todo] Gemeinsamen Kartenpool (levelunabhängige Angriffe/Blocks/Skills/Power) mit vollständigen deutschen Texten und Upgrades anlegen, einschließlich `inner_card_image`-Referenzen.
14. [todo] Level-spezifische Attack-Karten implementieren: Für jede Digimon-Form passende kanonische Attackennamen und Effekte codieren, Level-Beschränkungen und Upgrades hinzufügen.
15. [todo] Level-spezifische Skill- und Power-Karten umsetzen: Mechaniken auf Stance-Fähigkeiten abstimmen, Stabilitäts-Interaktion berücksichtigen und Upgrades anbieten.
16. [todo] DigiSoul-Buff als neues Keyword/Power implementieren: Aufladung über Angriffe, Interaktion mit Digivice-Relikten und Karten „DigiSoul aufladen!“ und „Digitieren“ sicherstellen.
17. [todo] Digimodify-System abbilden: Karten „Digimodify“ und individuelle Digimodify-Karten (z. B. „Highspeed Plugin A/B“, „Weiße Flügel“) erstellen, Triggerlogik für D-Power/D-Arc prüfen.
18. [todo] Schwarze-Digitation-Karten (Uncommon & Rare) programmieren: Zufällige Levelwechsel, HP/Stärke-Nachwirkungen und Todes-Trigger exakt implementieren.
19. [todo] Reliktfamilien erstellen: Digivices, Wappen, Armor-Eier, DigiSoul-Verstärker etc. mit passenden Effekten, Triggern und Tooltips codieren.
20. [todo] Kartenabhängige Reliktprüfungen integrieren: Sicherstellen, dass Karten nur spielbar sind, wenn alle geforderten Relikte im Besitz sind.
21. [todo] Starterdeck zusammenstellen: Enthaltene Karten (inkl. Digitationstrigger-Karten) registrieren, Balancing prüfen und Deck-Statistiken dokumentieren.
22. [todo] Freischalt- und Shop-Kartenlisten konfigurieren: Commons/Uncommons/Rares korrekt verteilen und unlock-/Belohnungslogik definieren.
23. [todo] Gemeinsame Keyword-Bibliothek erweitern: Neue Keywords (z. B. für Stabilität, DigiSoul) definieren oder bestehende wiederverwenden, Tooltips lokalisiert pflegen.
24. [todo] Charakterregistrierung vervollständigen: `DigitalesMonster` als spielbaren Charakter mit Farbe, Energieprofil, Animationen (PNG → Spine) und Startrelic(s) anmelden.
25. [todo] Kampf-Hooks implementieren: Erfolgreiche Angriffe (Spieler/Gegner) verfolgen, Stabilitätswerte aktualisieren und Rückfall-Auslöser handhaben.
26. [todo] Karten- und Reliktbeschränkungen gegen Plugin-System exportieren: Alle relevanten Klassen/Funktionen über den globalen Plugin-Manager verfügbar machen.
27. [todo] YAML-Assetmanifest erstellen: Vollständige Liste aller benötigten Texturen (inkl. `inner_card_image`, Stance-PNGs, Relikt-Icons) mit Dateinamen, Pfaden und Auflösungen liefern.
28. [todo] Dokumentation ergänzen: Mod-spezifische README/How-To aktualisieren, deutsche Kartentext-Richtlinien und Asset-Lieferhinweise festhalten.
29. [todo] Laufzeitprüfung mit GraalPy durchführen: Aktiviertes Runtime-Backend verifizieren, relevante Startskripte/Bootstrap-Anpassungen dokumentieren.
30. [todo] Manuelle Smoke-Tests planen und protokollieren: Kernflows (Digitieren, Rückfall, Schwarze Digitation, Digimodify, DigiSoul) durchspielen und Ergebnisse dokumentieren.
31. [todo] Zukunftserweiterungen in `futures.md` ergänzen: Identifizierte Erweiterungen (z. B. generische Digimon-Level-Frameworks) als langfristige Aufgaben eintragen.
32. [todo] Modulstruktur für handgeschriebene Kartenklassen festlegen: Paket `mods.digitalesmonster` aufbauen, Namenskonventionen für Attack/Skill/Power-Klassen definieren und Hilfsbasisklassen vorbereiten, ohne automatische Kartengeneratoren zu verwenden.
33. [todo] Karten-Spielbarkeitsprüfungen implementieren: Gemeinsame Utilities erstellen, die Level- und Reliktanforderungen (Digivices, Wappen, Armor-Eier, DigiSoul etc.) pro Karte verifizieren und in die Kartenbasis einbinden.
34. [todo] Kartenanzahl und Raritätsverteilung absichern: Sicherstellen, dass >75 Karten vorhanden sind, Commons/Uncommons/Rares im geforderten Verhältnis verteilt sind und Starterdeck-/Shop-Pools sauber darauf verweisen.
35. [todo] Vollständige deutsche Lokalisationspakete erzeugen: Karten-, Relikt-, Power-, Stance- und Keyword-Texte (inkl. Upgrade-Varianten) in `localization/deu/` bereitstellen und mit den Karten-/Reliktklassen verknüpfen.
36. [todo] Level- und Stabilitätsvisualisierung im UI implementieren: Aktuellen Levelnamen, Stabilitätswert und relevante Buffs über Power/Relic-Tooltips oder dedizierte UI-Overlays anzeigen und bei Stance-Wechseln aktualisieren.
37. [todo] Plugin-Exports für Digimon-spezifische Systeme erweitern: Levelmanager, Stabilitäts-Persistenz, Karten-/Reliktprüfungen und DigiSoul-Mechanik über den globalen Plugin-Manager exponieren, inklusive Dokumentation der Schnittstellen.
