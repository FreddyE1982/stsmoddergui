# Jogress- / Fusion-Stances – Referenznotizen

Quellen:

- [Omegamon (Omnimon) – Wikimon](https://wikimon.net/Omegamon) – deutsches Fandom führt Gigantisches Schwert (Grey Sword) und Giga-Kanone (Garuru Cannon) als Kernangriffe.
- [Imperialdramon Paladin Mode – Wikimon](https://wikimon.net/Imperialdramon_Paladin_Mode) – verknüpft den Jogress von Imperialdramon Fighter Mode und Omnimon.

Kerndaten für das Mod-Design:

- **Omnimon** entsteht als Jogress-Fusion von WarGreymon und MetalGarurumon. Deutsche Attackennamen laut DigiPedia: *Gigantisches Schwert* und *Giga-Kanone*. Stabilitätsfantasie: extrem hohe Leistung, aber DigiSoul-Burn.
- **Imperialdramon Paladin Mode** bildet eine seltene Weiterentwicklung, die Omnimon mit Imperialdramon Fighter Mode vereint. Die Form verwendet das *Omega-Schwert* und erzeugt Licht-basierte Schockwellen.
- Jogress-Aktivierungen erfolgen in den Serien häufig über Digivices (DNA Digivice / D-3) und benötigen Synchronität sowie Ereignistrigger (gleichzeitige Angriffe, vereinte DigiSoul). Fürs Gameplay bedeutet das: Karten- oder Relikttrigger sollten aktiviertes Digivice, aufgeladene DigiSoul und passende Partnerdaten voraussetzen.
- Rückfallbedingungen: Bei DigiSoul-Erschöpfung zerfällt die Fusion typischerweise in die vorherigen Mega-Formen. Ein geplanter Fallback auf Warp-/Ultra-Stances hält das Thema konsistent.
- Zufallsaktivierung: In *Digimon Adventure 02* löst der Jogress teils spontan während der Gefechte aus. Ein kleiner Zufallsfaktor (z. B. 20 % Zusatzchance, wenn die Bedingungen sonst knapp verfehlt werden) unterstützt dieses Seriengefühl.

Gameplay-Übertrag:

- Fusionen sollten aktivierte Partner-Metadaten im Stance-Context prüfen (z. B. `fusion_partners={"war_greymon": True, "metal_garurumon": True}`).
- Ein Jogress-Pipeline-Dict im Kontext (`fusion_pipeline`) speichert Triggerquelle, Zufallswurf, aktive Effekte und Rückfallziel.
- Stabilitätskosten: Hohe Einstiegskosten, massiver per-turn-Drain, automatische DigiSoul-Reduktion. Rückkehrbedingung: DigiSoul ≤ 0 oder Stabilität unter Grenzwert.
- Belohnung: Temporäre Powers (z. B. `digitalesmonster:gigantisches_schwert`) und vergrößerte HP-/Blockwerte.

Diese Notizen fließen in den Level-Übergangsmanager und neue Stances ein.
