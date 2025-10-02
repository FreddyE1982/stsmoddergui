Okay, mach mir einen mod wie unten beschrieben, kartentexte müssen komplett auf deutsch sein (inklusive kartentitel). die bilder für inner card image liefere ich selbst nach.

ALLE [todo]  in digimonmoddevelopmentplan.md beziehen sich direkt auf das was im folgenden festgelegt ist und muss bei ihrer Implementierung exakt beachtet werden. Dies gilt insbesondere aber nicht ausschließlich für: alle Spielmechaniken, die verschiedenen Arten der Digitation zu funktionieren haben (unteranderem welche bestimmten Relics (= Digivices, etc). erforderlich sind und welche Kartenkombination zum außlösen der Digitation gespielt werden muss), und für alles mögliche.

Überprüfe immer ob du neue [todo] zu digimonmoddevelopmentplan.md hinzufügen musst um das beschriebene exakt umzusetzen, wenn ja, tu es! 

Der Kartenblueprintmechanismus muss für diesen Mod so erweitert werden dass optional mit angegeben werden kann zu welchem Level eine Karte gehört, damit sichergestellt werden kann dass eine Karte nur dann gespielt werden kann wenn das Digimon gerade den dazu gehörigen Level hat. (Zb. Können Champion Level Karten nicht vom Rookie Digimon gespielt werden). Karten für ein NIEDERIGERES Level als das dass das Digimon gerade hat, können von diesem natürlich gespielt werden. (zum beispiel können also wenn das Digimon gerade auf Champion Level ist alle Karten ohne Level, alle Rookie Level Karten und alle Champion Karten gespielt werden). Alle Karten die zu einem Level gehören das HÖHER ist als das aktuelle Level des Digimons müssen mit dem entsprechenden Keyword als "unspielbar" gekennzeichnet werden (bitte forsche nach wie das so umgesetzt werden kann dass es im fertigen mod tatsächlich funktioniert!...dafür muss es in basemod bereits ein fertiges keyword geben). Wenn das Level des Digimon sich auf ein höheres Level ändert, dann wird das Keyword für die unspielbarkeit von den Karten des neuen Levels entfernt. Ändert sich das Level des Digimon auf ein niedrigeres Level, dann wird das Keyword für die unspielbarkeit zu allen Karten der höheren Levels hinzugefügt (falls noch nicht vorhanden!). 

ebenso liefere ich alle anderen bild assets nach, gib mir nur eine liste aller assets die gebraucht werden mit genauer Beschreibung, benötigter Auflösung und zu verwendendem Dateinamen.
nutze so weit wie möglich unsere existierenden features / Möglichkeiten aber implementiere neue falls nötig. für relics haben wir schon funktionalität

denke bitte dran dass du KEINE binär dateien speichern kannst. wenn du bilder speicherst muss das in form von base64 encoding in text dateien als text passieren. füge das auch als regel der root AGENTS.md hinzu

this mod has NOTHING to do with our adaptive deck evolver! DO NOT USE IT OR REIMPLEMENT IT. THIS MOD DOES NOT DO DECK EVOLVING!!! 

for any online resarch please ONLY use: https://digimon.fandom.com/de/wiki/ ....you will probably need to visit it as if you are a browser instead of using curl or similar!!! we do NOT need any attack names from any digimon that are NOT part of the agumon evolution line! our mod uses the offical agumon evolution lines ONLY except for the one case as described below when a agumon evolution line digimon for a given Level does not exists!!!

if you need to create keywords do that by inheriting from our existing class "Keyword". Before you do ANYTHING please try to find a appropriate existing class to use or inherit from first!! inherit from our existing base class "Stance" to create stances (you will need that to create Levels).

Okay, mach mir einen mod wie unten beschrieben, kartentexte müssen komplett auf deutsch sein (inklusive kartentitel). die bilder für inner card image liefere ich selbst nach.
ebenso liefere ich alle anderen bild assets nach, gib mir nur eine liste aller assets die gebraucht werden mit genauer Beschreibung, benötigter Auflösung und zu verwendendem Dateinamen.
nutze so weit wie möglich unsere existierenden features / Möglichkeiten aber implementiere neue falls nötig. für relics haben wir schon funktionalität.

Alle Effekte die in Kartentexten erwähnt werden müssen auch exakt "in game" umgesetzt werden. Nach jeder Karte die du erstellst ist der Workflow folgendermaßen:

1. Prüfe ob alle im Text der Karte erwähnten Effekte im Spiel umgesetzt werden können
1.1 für jeden auf der Karte erwähnten Effekt:
1.2 gibt es einen spimplen Mechanismus der via unserem modding framework bereits implementierbar ist?
1.3 wenn nicht...gibt es bereits ein implementiertes Keyword?
1.4. wenn nicht..kann der gewünschte Effekt durch kombination mehrerer implemtierter Keywords erreicht werden?
1.5 wenn nicht...kann der gewünschte Effekt durch implementierung eines neuen Keywords erreicht werden und ist es nicht "zu groß" / out of scope für ein Keyword?
1.6 wenn nicht...implementiere das nötige in dem du die nötigen Nachforschungen anstellst und dann eine neue Klasse in unserem mod framework erstellst (NICHT im mod direkt, damit alle mods die neue Klasse nutzen können!)

2. nach dem du die passende Methode aus Abschnitt 1 ausgewählt hast, implementiere sie! 


Character Name: "DigitalesMonster"

1. Stances: Der mod nutzt Stances die verschiedenen Digimon Leveln entsprechen, definiere die Stances passend zum Digimon Level mit passenden Max HP, Start HP, Passenden permanenten buffs und debuffs, etc.

Hier alle Informationen zu leveln und wie sie erreicht werden. digivices, armoreier, wappen als relics realisieren. wir nutzen die deutschen level namen...nicht die japanischen. 


Natürlich	Rookie	3	Basis-Bindung Tamer↔Partner	Adventure: Digivice (1999) 
DigimonWiki
 / Tamers: D-Power/D-Arc (Card Slash möglich) 
wikimon.net
+1
 / Savers: Digivice iC (Digisoul) 
wikimon.net
+1
Natürlich	Champion	4	Starke Emotion/Bindung (Wappen-Einfluss in 01)	Adventure: Digivice (+Wappenhilfe) 
DigimonWiki
 / Tamers: D-Power/D-Arc (Card Boosts) 
wikimon.net
 / Savers: iC (Digisoul-Ladung) 
Wikipedia
Natürlich	Ultra (JP Perfect)	5	Hohe Datenreife + starker Katalysator (z. B. Wappenlicht/Blue Card/Digisoul-Peak)	Adventure: Digivice + Wappen/Tag-Resonanz (sinngemäß) 
DigimonWiki
 / Tamers: D-Power/D-Arc + Blue Card (Matrix-Trigger) 
wikimon.net
 / Savers: iC (stärkeres Digisoul) 
Wikipedia
Natürlich	Mega (JP Ultimate)	6	Außergewöhnliche Resonanz/Bond; serienspezifischer Trigger	Adventure: Warp-Digitation via Digivice + Wappenkraft 
DigimonWiki
 / Tamers: Matrix/Biomerge via D-Power/D-Arc (Blue Card/Calumon-Licht als Katalysator) 
wikimon.net
 / Savers: Digivice iC Burst für Ultimate/Mega-Evo 
Wikipedia
+1
Sonderlevel	Armor (Rüstungs-Digitation)	4	Digi-Armor-Ei (Wappenmotiv)	02: D-3 + Digi-Ei 
Wikipedia
+2
DigimonWiki
+2
Methode	Jogress/DNA-Digitation (02)	+½–1	Synchronisierte Partner-Resonanz	02: D-3 (zwei Tamers; Geräte-Resonanz) 
wikimon.net
Methode	Warp-Digitation (01)	–	Direkter Sprung Rookie→Mega durch Wappenkraft/Notlage	Adventure: Digivice (1999) 
DigimonWiki
Methode	Matrix/Biomerge (Tamers)	Mega	Verschmelzung Tamer+Digimon, Blue Card/Calumon-Licht als Trigger	Tamers: D-Power/D-Arc 
wikimon.net
Moduswechsel	Burst Mode (Savers)	7	Maximales Digisoul, Kontrollfähigkeit	Savers: Digivice Burst 
Wikipedia
+1

Weitere Infos wie wir Digitationen umsetzen (hier nur einige Beispiele, setze den rest auf basis der Tabelle angelehnt an die Beispiele um)

Rookie auf Champion: Mindestens EIN beliebiges Digivice relikt in Besitz, interner Zähler zählt Ungeblockten Schaden den wir Gegnern erteilen und wenn ein bestimmter Wert erreicht wird wird die Digitation ausgeführt

Rookie auf Champion, alternative Methode: mindestens ein beliebiges Digivice relikt im Besitz, Karte "Digitieren" wird gespielt

Digitation auf Armor: D3 Digivice Relikt im Besitz, Armor Ei Relikt im Besitz, gespielt werden Karten: Karte "Digitieren" + Karte "Armor Ei erstrahle!"

Rookie auf Mega (Warp Digitation): irgend ein digivice relikt im besitz, Wappen im Besitz, gespielt werden Karten: Karte "Digitieren", + Karte "Wappen"

Rookie ist das niedrigste Level das wir implementieren! wir starten jeden Kampf auf Rookie Level.


Über Levelstabilität:

Für jedes Level gibt es einen eigenen über Kämpfe und Spiele hinaus persistenten Stabilitätswert. Beim ersten Spiel startet der auf einem zum Level passenden Startwert und hat einen zum Level passenden anfänglichen MAX wert.
Jeder gewonnene Kampf steigert den Startwert um 1, jeder verlorene Kampf senkt den Startwert um 1 (nur für entsprechendes Level!)
Jeder gewonnene Kampf steigert den MaxWert um 1, jeder verlorene Kampf senkt den MaxWert um 1 (nur für entsprechendes Level!)
Jeder ERFOLGREICHE Angriff ( = mindestens 1 ungeblockter schaden erreicht den gegner) im Spielerzug steigert den aktuellen Stabilitätswert um eins, jeder ERFOLGREICHE Angriff im Gegnerzug (= mindestens 1 ungeblockter Schaden auf den Spieler) senkt den aktuellen Stabilitätswert um 1

Sinkt der Stabilitätswert des aktuell aktiven Levels auf 0 dann digitiert das Digimon zurück auf was auch immer das tatsächliche vorherige Level war. 


Über Kartenspielbarkeit:

Es gibt Karten die auf jedem Level spielbar sind, es handelt sich dabei um "very basic" Angriffe, Blocks, Skills und Powers.

Es gibt Karten die nur auf dem passenden Level spielbar sind, dabei handelt es sich um Attack, Skill, Power Karten die von ihrer Stärke her zur Stärke des entsprechenden Levels passen. 

Für Attack karten werden die zum entsprechenden Level passenden KANONISCHEN DEUTSCHEN Angriffsnamen verwendet

Es gibt eine UNCOMMON Karte "Schwarze Digitation"...wird die Karte gespielt dann digitiert das Digimon sofort auf ein zufälliges Level, aber seine HP und Stärke werden am Ende jedes Zugs halbiert

Es gibt eine RARE Karte "Schwarze Digitation", wird die Karte gespielt dann digitiert das Digimon sofort auf ein zufälliges Level und macht 100 Schaden auf alle Gegner. Am Ende des nächsten Zugs stirbt das Digimon

Für die Level aus Tamers gibt es zusätzlich Karten wie "Highspeed Plugin B", "Highspeed Plugin A", "Weiße Flügel" und viele weitere Karten mit passenden Effekten..diese Karten sind "Digimodify Karten". Sie können nur wie folgt gespielt werden: 

D-Power oder D-Arc Digivice im Besitz, gespielt werden Karten: Karte "Digitieren" + Karte "Digimodify" + die gewünschte Karte vom typ "Digimodify Karte" (NICHT verwechseln mit der benötigten Karte "Digimodify" für die auslösung des Digimodify Vorgangs)

Andere Spezial Mechanismen werden ähnlich wie bis hier beschrieben umgesetzt. 



DigiSoul ist ein Buff der bis zu einem bestimmten Wert nach und nach aufgeladen werden muss durch erfolgreiche Angriffe, dann kann mit dem passenden digivice relikt, der karte "digitieren" + karte "DigiSoul aufladen!" digitiert werden., die Blue Card (Blaue Karte) ist eine tatsächliche Karte!!! 

StarterDeck: Enthält je zwei Exemplare für Attack, Power, Skill Karten die jedes Level verwenden kann, je eine Karte für jede Digitationsbestandteile die Karten sind (also Karte "Digitieren" und die entsprechenden anderen Karten die für die jeweiligen Digitationen gespielt werden müssen)

Unlockables / Shop / Kampfbelohnungskarten: Alle weiteren Karten, weitere Examplare der Karten die für die diversen Digitationen gebraucht werden, etc. Die diversen Level spezifischen Karten

JEDE Karte in diesem Mod muss upgradebar sein! 

Der mod muss insgesamt so viele Karten haben wie nötig ist um das alles perfekt umzusetzen. Das wird sehr wahrscheinlich irgendwas >75 Karten sein. Sorge dafür dass auf jedenfall das Korrekte verhältnis von Common / Uncommon / Rare erreicht wird.


.inner_card_image MUSS für die inneren kartenbilder genutzt werden.

stelle eine yaml zur verfügung in der alle bild assets mit Dateinamen und pfaden bereits vorgegeben sind so dass der Nutzer nur noch die tatsächlichen Dateien in die richtigen pfade richtig benannt kopieren muss wenn er den mod kompilieren will. wir nutzen für alle stances / alles was spine/atlas nutzt jeweils eine PNG!!! (also hat jedes level eine eigene PNG die für die Erstellung des jeweils benötigten spine/atlas genutzt wird)


KARTENTEXTE dürfen NUR die Keywords der Karte und die Effekte der Karte enthalten und beschreiben, da auf den Karten nur sehr wenig Platz für Texte ist. Es geht nicht mehr rein als in etwa:

"Behalten, Erschöpfen. 3 Schaden auf ein beliebiges Ziel. +3 temporäre HP. +2 Energie im nächsten Zug"

Erstelle einen neuen Kartentyp "Digimon" (in dem du von der Klasse "CardType" erbst). Diese Karten stellen jeweils ein Digimon dar das NICHT zur Agumondigitationslinie gehört.
Karten vom Typ Digimon können keinen Schaden oder Block austeilen. Sie haben lediglich Buff/Debuff Effekte auf den Spieler. Dabei hat eine Digimon Karte entweder nur postive Effekte oder sie hat positive Effekte in Verbindung mit einem leichteren negativen Effekt.
Die Effekte einer Digimon Karte müssen immer zum entsprechenden Digimon gehören. Wird eine Karte vom Typ Digimon zerstört (Exhausted) dann werden ihre Effekte sofort aufgehoben. 
Als Beispiel hier mal die Karte "Patamon" und das "Reasoning" dahinter:

Patamon ist ein kleines Digimon auf dem Rookie Level, dass nicht sonderlich stark ist. Sein einziger Vorteil ist dass es fliegen kann:

Kartentyp: "Digimon"
Kartentitel: "Patamon"
Effekte: + 1 temporäre HP für den aktuellen Kampf, + 1 Geschicklichkeit
Energiekosten: 1

Hier ein weiteres Beispiel für eine Digimon Karte. Diesmal ist es "Palmon". Palmon ist ein Rookie Level Digimon. Es ist für ein Rookie Digimon mittelstark. Seine Attacke ist "Giftiger Efeu".

Kartentyp: "Digimon"
Kartentitel: "Palmon"
Energiekosten: 2
Effekte: + 1 temporäre HP für den aktuellen Kampf, alle Attacken des Spielers wirken + 1 Gift Debuff auf alle Gegner

Noch ein Beispiel: WereGarurumon. WereGarurumon ist ein Ultra Digimon (in der deutschen Fassung ist Ultra das Level direkt unter dem stärksten Level namens "Mega") vom Typ Serum. Seine Attacke ist Wolfskralle.

Kartentyp: "Digimon"
Kartentitel: "WereGarurumon"
Energiekosten: 4
Effekte: + 3 temporäre HP für den aktuellen Kampf, die nächsten drei Runden wird am Ende der Runde 1 HP geheilt, alle Attacken des Spielers haben + 2 Schaden

Und noch ein Beispiel: MetalGarurumon ist ein Digimon auf dem Mega Level vom Typ Serum. Seine Attacke ist "Metallische Wolfskralle"

Kartentyp: "Digimon"
Kartentitel: "MetalGarurumon"
Energiekosten: 5
Effekte: + 5 temporäre HP für den aktuellen Kampf, alle Attacken des Spielers haben + 5 Schaden, der Block aller Gegner wird zerstört, am Ende der nächsten Runde werden 5 HP geheilt.

DNA Digitation setzen wir folgendermaßen um:

1. Spieler muss ein das D3 digivice relikt (das digivice aus digimon adventure 02) besitzen
2. DNA Digitation durchführen: Spieler spielt Karten: Karte "Digitation" + je nach dem zu welchem Digimon digitiert werden soll die passende Karte vom Typ "Digimon". Bis auf weiteres setzen wir nur die DNA Digitationen um die in Digimon Adventure 02 vorkommen und wo einer der Digitationspartner ein Digimon der Augumonlinie ist. (Recherchiere das!)



