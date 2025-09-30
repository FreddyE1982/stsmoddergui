# Slay the Spire base power constructor cheatsheet

The table summarises the constructor signatures for the most commonly used
player and enemy powers referenced by the keyword runtime. Source material is
the BaseMod and Slay the Spire open-source references mirrored in the
`research/stslib_*` snapshots already tracked in this repository.

| Power | Constructor signature | Notes |
| --- | --- | --- |
| StrengthPower | `(AbstractCreature owner, int amount)` | Negative amounts reduce strength. |
| DexterityPower | `(AbstractCreature owner, int amount)` | Works on player and monsters. |
| FocusPower | `(AbstractCreature owner, int amount)` | Defect-specific orb modifier. |
| ArtifactPower | `(AbstractCreature owner, int amount)` | Prevents debuffs, stacks additively. |
| IntangiblePlayerPower | `(AbstractCreature owner, int amount)` | Player-only intangible. |
| IntangiblePower | `(AbstractCreature owner, int amount)` | Monster intangible (e.g. Transient). |
| WeakPower | `(AbstractCreature owner, int amount, boolean isSourceMonster)` | `isSourceMonster` false when applied by the player. |
| VulnerablePower | `(AbstractCreature owner, int amount, boolean isSourceMonster)` | Works like Weak. |
| FrailPower | `(AbstractCreature owner, int amount)` | No source flag required. |
| PoisonPower | `(AbstractCreature owner, AbstractCreature source, int amount)` | `source` identifies the attacker for artifact interactions. |
| ConstrictedPower | `(AbstractCreature owner, AbstractCreature source, int amount)` | Primarily used by Snecko. |
| ShackledPower | `(AbstractCreature owner, int amount)` | Temporarily reduces strength. |
| LockOnPower | `(AbstractCreature owner, int amount)` | Orb targeting debuff. |
| SlowPower | `(AbstractCreature owner, int amount)` | Stacks by the number of cards played. |
| ThornsPower | `(AbstractCreature owner, int amount)` | Damages attackers on contact. |
| PlatedArmorPower | `(AbstractCreature owner, int amount)` | Grants block at end of turn. |
| MetallicizePower | `(AbstractCreature owner, int amount)` | Adds block each turn without decaying. |

For powers with optional boolean flags, the keyword runtime defaults to
`False`, matching the standard behaviour when the player applies the debuff to
enemies. When creating custom powers, register the expected constructor
signature via the forthcoming metadata registry described in `futures.md` so
the runtime can instantiate modded powers deterministically.
