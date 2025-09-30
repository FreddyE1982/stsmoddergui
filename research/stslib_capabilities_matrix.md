# StSLib Capability Matrix

Comprehensive catalogue of the mechanics, hooks, fields, icons and helpers shipped with [StSLib](https://github.com/kiooeht/StSLib). Use it as a quick reference when wiring the Python-first wrapper to JVM-side helpers or when preparing documentation for plugin authors.

## Core requirements

- **Dependencies**: BaseMod and ModTheSpire must be present before StSLib features can be invoked. 【F:research/stslib_readme.md†L1-L9】
- **Namespace prefix**: Keyword and dynamic variable identifiers are always prefixed with `stslib:` to avoid collisions with mod-defined strings. 【F:research/stslib_Keywords.md†L1-L24】

## Keyword and field catalogue

| Keyword | Behaviour | Field / helper |
| --- | --- | --- |
| Autoplay | Card plays itself on draw. | `AutoplayField.autoplay` (boolean). 【F:research/stslib_Keywords.md†L1-L11】【F:research/stslib_AutoplayField.java†L1-L14】 |
| Exhaustive | Limits card uses per combat. | `ExhaustiveVariable.setBaseValue`, with upgrade helpers and auto-decrement. 【F:research/stslib_Keywords.md†L1-L15】【F:research/stslib_ExhaustiveVariable.java†L1-L46】 |
| Fleeting | Purges card on use, removing it from the deck. | `FleetingField.fleeting`. 【F:research/stslib_Keywords.md†L1-L15】 |
| Grave | Starts combat in discard pile. | `GraveField.grave`. 【F:research/stslib_Keywords.md†L4-L13】 |
| Persist | Keeps card in play for N uses per turn. | `PersistFields.setBaseValue`, `PersistFields.upgrade`, `PersistFields.decrement`. 【F:research/stslib_Keywords.md†L4-L13】【F:research/stslib_PersistFields.java†L1-L33】 |
| Purge | Removes until combat end without exhausting. | `PurgeField.purge`. 【F:research/stslib_Keywords.md†L6-L14】 |
| Refund | Refunds spent energy up to the listed amount. | `RefundVariable.setBaseValue`. 【F:research/stslib_Keywords.md†L6-L15】 |
| Retain | Keeps card in hand between turns. | `AlwaysRetainField.alwaysRetain`. 【F:research/stslib_Keywords.md†L7-L15】 |
| Snecko | Randomises card cost when drawn. | `SneckoField.snecko`. 【F:research/stslib_Keywords.md†L7-L15】 |
| Soulbound | Prevents removing the card from the deck. | `SoulboundField.soulbound`. 【F:research/stslib_Keywords.md†L8-L16】 |
| Startup | Triggers at combat start without drawing. | `StartupCard` interface. 【F:research/stslib_Keywords.md†L9-L16】 |

### Dynamic variables

| Variable | Key | Purpose | Helper |
| --- | --- | --- | --- |
| Exhaustive | `!stslib:ex!` | Shows remaining uses before auto-exhausting. | `ExhaustiveVariable.setBaseValue`, `ExhaustiveVariable.upgrade`, `ExhaustiveVariable.increment`. 【F:research/stslib_Keywords.md†L15-L24】【F:research/stslib_ExhaustiveVariable.java†L1-L52】 |
| Persist | `!stslib:ps!` (via Persist fields) | Renders the current persist count. | `PersistFields.setBaseValue`, `PersistFields.upgrade`. 【F:research/stslib_PersistFields.java†L13-L27】 |
| Refund | `!stslib:rf!` | Displays refund amount in card text. | `RefundVariable.setBaseValue` utilities. 【F:research/stslib_Keywords.md†L6-L16】 |

## Card-level interfaces and helpers

- **Branching upgrades** – implement `BranchingUpgradesCard` and override `upgrade`, `baseUpgrade`, and `branchUpgrade` to present multiple smithing paths. 【F:research/stslib_Cards.md†L1-L32】
- **Spawn control** – implement `SpawnModificationCard` to vet card reward generation (`canSpawn`), swap rolled cards (`replaceWith`), and post-process rewards (`onRewardListCreated`). 【F:research/stslib_Cards.md†L33-L119】
- **Startup hooks** – implement `StartupCard` for cards that fire at combat start (pairs naturally with the `Startup` keyword). 【F:research/stslib_Keywords.md†L9-L16】
- **Common keyword icons** – toggle `CommonKeywordIconsField.useIcons` so Innate/Ethereal/Retain/Purge/Exhaust keywords render compact icon badges automatically. 【F:research/stslib_Cards.md†L34-L62】

## Combat modifiers

### Damage modifiers

- Extend `AbstractDamageModifier` to inject pre/post damage behaviour, add tooltips, mutate descriptors, or bind inherent damage types. 【F:research/stslib_Damage-Modifiers.md†L1-L87】
- Use `DamageModifierManager.addModifier(card, mod)` for inherent card behaviour or `BindingHelper` to manually bind damage sequences. 【F:research/stslib_Damage-Modifiers.md†L88-L158】
- Powers can implement `DamageModApplyingPower` (and relics `DamageModApplyingRelic`) to push modifiers dynamically; StSLib invokes `shouldPushMods`, `modsToPush`, and `onAddedDamageModsToDamageInfo` hooks automatically. 【F:research/stslib_Damage-Modifiers.md†L159-L228】

### Block modifiers

- Extend `AbstractBlockModifier` and register via `BlockModifierManager.addModifier(card, modifier)` to apply persistent block behaviours and UI badges. 【F:research/stslib_Block-Modifiers.md†L1-L60】
- Use `GainCustomBlockAction` for manual binding or rely on auto-binding in `GainBlockAction`. The Block Manager renders FIFO icons for stacked block types. 【F:research/stslib_Block-Modifiers.md†L60-L118】

## Hooks and extension interfaces

### Power hooks

| Interface | Trigger |
| --- | --- |
| `BeforeRenderIntentPower` | Skip or override intent rendering. |
| `BetterOnApplyPowerPower` | Inspect and veto power applications with mutable stack counts. |
| `BetterOnExhaustPower` | Capture card exhaustion with source pile context. |
| `OnLoseBlockPower` / `OnLoseTempHpPower` / `OnMyBlockBrokenPower` | Respond to defensive resource loss. |
| `OnPlayerDeathPower` | Intercept player death events. |
| `OnReceivePowerPower` | Vet inbound buffs/debuffs. |
| `HealthBarRenderPower`, `InvisiblePower`, `TwoAmountPower` | Presentation helpers (HP bar overlays, invisible powers, dual values). |
| `DamageModApplyingPower`, `OnCreateBlockInstancePower` | Apply damage/block modifiers during info construction. |
| `OnDrawPileShufflePower`, `OnCreateCardInterface` | React to draw pile shuffles or runtime card creation. 【F:research/stslib_Power-Hooks.md†L1-L37】

### Relic hooks

| Interface | Trigger |
| --- | --- |
| `ClickableRelic` | Adds right-click activation to relics. |
| `OnChannelRelic`, `OnLoseBlockRelic`, `OnLoseTempHpRelic` | React to channel/block/temp HP events. |
| `BeforeRenderIntentRelic` | Intent rendering veto. |
| `BetterOnLoseHpRelic`, `BetterOnSmithRelic`, `BetterOnUsePotionRelic` | Richer context versions of common relic hooks. |
| `SuperRareRelic` | Adjusts rarity weighting beyond `RARE`. |
| `OnReceivePowerRelic`, `OnApplyPowerRelic`, `OnAnyPowerAppliedRelic` | Inspect and negate power interactions. |
| `OnAfterUseCardRelic`, `OnSkipCardRelic`, `OnRemoveCardFromMasterDeckRelic` | Mirror card lifecycle events. |
| `OnPlayerDeathRelic` | Prevent fatal damage. |
| `DamageModApplyingRelic`, `OnCreateBlockInstanceRelic` | Push damage/block modifiers from relics. |
| `CardRewardSkipButtonRelic` | Inject skip buttons with side effects. |
| `OnCreateCardInterface` | Process dynamically created cards. 【F:research/stslib_Relic-Hooks.md†L1-L25】

## Actions and combat utilities

StSLib ships prebuilt `AbstractGameAction` helpers to remove boilerplate:

| Action | Purpose |
| --- | --- |
| `StunMonsterAction` | Skip the monster's next action. |
| `FetchAction`, `MoveCardsAction`, `MultiGroupMoveAction` | Shuttle cards between piles with optional multi-pile selection UIs. |
| `AddTemporaryHPAction`, `RemoveAllTemporaryHPAction` | Manage temporary HP for players and monsters. |
| `EvokeSpecificOrbAction`, `TriggerPassiveAction` | Invoke orb behaviour directly. |
| `SelectCardsAction`, `SelectCardsInHandAction`, `MultiGroupSelectAction` | Build grid-based selection flows. |
| `DamageCallbackAction` | Execute callbacks with unblocked damage totals (Wallop-like logic). 【F:research/stslib_Actions.md†L1-L15】

## Targeting extensions

- Register custom `CardTarget` enums with `TargetingHandler` implementations to aim cards at arbitrary entities (self, allies, map nodes, etc.).
- Override `updateHovered`, `getHovered`, `clearHovered`, and `hasTarget` to drive targeting arrows and keyboard support.
- Call `SelfOrEnemyTargeting.getTarget(card)` (or your equivalent) inside `use` and always fall back gracefully for automation effects like Mayhem. 【F:research/stslib_Custom-Targeting.md†L1-L96】

## UI, icons and flavor support

- **Flavor text** – add `FLAVOR` entries to `CardStrings` and optionally recolour tooltips with `AbstractCardFlavorFields.boxColor` / `textColor`; potion flavour uses `PotionFlavorFields`. 【F:research/stslib_Flavor-Text.md†L1-L36】
- **Custom icons** – extend `AbstractCustomIcon`, register with `CustomIconHelper.addCustomIcon`, and embed `[ModID:Icon]` tokens in card, keyword, relic, or power JSON. 【F:research/stslib_Icons.md†L1-L80】
- **Common keyword badges** – toggle `CommonKeywordIconsField.useIcons` to render Innate/Ethereal/Retain/Purge/Exhaust icons automatically. 【F:research/stslib_Cards.md†L34-L62】

## Suggested workflow

1. **Register dynamic assets early** – load custom icons, dynamic variables, and targeting handlers during BaseMod setup before cards reference them.
2. **Compose behaviour via modifiers** – prefer damage/block modifiers and the hook interfaces rather than bespoke patches; they compose cleanly with other mods using StSLib conventions.
3. **Expose automation hooks** – when integrating with the Python wrapper, surface these tables directly to plugin authors so they can query capabilities at runtime (e.g., via the repo-wide plugin manifest).

This matrix mirrors the current state of upstream documentation captured in `/research`. Regenerate or expand it whenever StSLib introduces new interfaces or keywords so downstream tooling stays accurate.
