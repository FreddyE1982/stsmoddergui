# Slay the Spire base game keyword quick reference

Source: https://slay-the-spire.fandom.com/wiki/Keyword (retrieved 2024-05-29)

| Keyword | Typical effect | Common usage |
| --- | --- | --- |
| Block | Prevent incoming damage until the end of the turn. | Awarded by defensive skills like "Defend"; scales with Dexterity. |
| Strength | Increases outgoing attack damage by the granted amount. | Applied by cards like "Inflame" and "Spot Weakness". |
| Dexterity | Increases Block gained from cards by the granted amount. | Granted by cards like "Leg Sweep" and powers like "Footwork". |
| Focus | Increases Orb passive and evoke effects. | Used by Defect powers such as "Defragment". |
| Artifact | Negates a single debuff for each stack. | Provided by cards like "Panacea" or relics like "Orichalcum". |
| Energy | Extra energy for the current turn. | Granted by skills like "Adrenaline". |
| Card Draw | Draw additional cards immediately. | Enabled by cards like "Battle Trance". |
| Weak | Debuff that reduces enemy attack damage by 25%. | Applied by cards like "Leg Sweep" or "Crippling Cloud". |
| Vulnerable | Debuff increasing damage taken by 50%. | Applied by cards like "Bash" or "Uppercut". |
| Frail | Debuff reducing Block gain by 25%. | Applied by cards like "Crippling Cloud". |
| Poison | Deals damage at the end of the victim's turn and decreases each tick. | Applied by Silent cards like "Deadly Poison". |

These are the core keywords most frequently referenced when scripting straightforward powers or skills. They map cleanly to `ApplyPowerAction` invocations when writing automation helpers.
