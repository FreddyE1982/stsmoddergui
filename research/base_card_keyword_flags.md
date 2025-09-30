# Base game keyword field mapping

Reference summary of the primary boolean fields on `AbstractCard` that drive keyword behaviour. Useful when wiring the
Python blueprint helpers to JVM data structures.

| Keyword | Field(s) to toggle | Notes |
| --- | --- | --- |
| Innate | `AbstractCard.isInnate` | Card starts in opening hand once per combat. |
| Ethereal | `AbstractCard.isEthereal` | Exhausts if still in hand at end of turn. |
| Exhaust | `AbstractCard.exhaust` | Exhausts immediately when played. |
| Retain | `AbstractCard.selfRetain` and `AbstractCard.retain` | Keeps the card in hand between turns. Set both so the retention applies immediately and persists automatically. |

These flags live directly on the base game `AbstractCard` class and therefore work without StSLib present. Mods can still
layer StSLib conveniences (e.g. common keyword icons) on top by toggling the appropriate fields in tandem.
