# Slay the Spire stance implementation notes

This memo summarises the mechanics that BaseMod expects when registering custom stances.  It condenses the official BaseMod wiki guidance plus in-game observations so the Python wrapper can provide first-class stance helpers.

## AbstractStance contract

Custom stances extend `com.megacrit.cardcrawl.stances.AbstractStance`.  Core methods:

- `public void updateDescription()` – refreshes the stance description text used in tooltips and relic interactions.  The value normally references localized strings pulled from the "Stances" JSON file.
- `public void updateAnimation()` – drives particle effects and stance visuals each frame.
- `public void onEnterStance()` and `public void onExitStance()` – fire when the stance is entered or left.  They normally enqueue VFX actions and sound effects via `AbstractDungeon.actionManager` and `AbstractDungeon.effectsQueue`.
- `public float atDamageGive(float damage, DamageInfo.DamageType type)` and `public float atDamageReceive(float damage, DamageInfo.DamageType type)` – allow the stance to modify outgoing and incoming damage.  These hooks must honour `type` (ATTACK/THORNS/HP_LOSS) just like the base game stances.
- `public void onPlayCard(AbstractCard card)` – optional, triggered for every card played while the stance is active.
- `public void atStartOfTurn()` / `atStartOfTurnPostDraw()` – optional lifecycle hooks used by watcher stances.

Instances must set `this.name`, `this.ID`, and `this.c` (the colour tint).  `this.ID` should be unique across the mod (usually `mod_id:StanceName`).  `this.name` and `this.ID` feed tooltips and power checks.

## BaseMod integration

BaseMod exposes `BaseMod.addCustomStance(String id, Supplier<AbstractStance> factory, Supplier<Texture> outlineTexture, Supplier<Texture> innerTexture)` in current releases.  Older builds used `addStance` plus manual `StanceAuraEffect` registration.  Regardless of the entrypoint, the registration must provide:

- A unique stance ID string matching the custom class `ID` attribute.
- A factory that creates a fresh stance instance on demand.
- Optionally VFX providers that return textures used by the stance aura and particle trails.

The Watcher uses localized strings from `CardCrawlGame.languagePack.getStanceString(ID)`.  Mods should supply matching entries under `resources/<modid>/localization/{language}/Stance-Strings.json`.

## Gameplay wiring tips

- Combat code queries `AbstractDungeon.player.stance.ID`.  Ensure the ID remains stable across instances.
- `AbstractDungeon.player.switchStance(id)` handles queueing the exit/enter calls and is the preferred way to change stances.
- Actions such as `ChangeStanceAction` and `EruptionAction` rely on the `STANCE_STRINGS` map inside `AbstractStance`.  Registering through BaseMod automatically updates the registry.
- Particle effects typically reuse Watcher stances as a template (see `CalmStance`, `WrathStance`, `DivinityStance`).
- Remember to update power interactions such as `LikeWater` that check for stance IDs.

## Localization payload shape

```json
{
  "ID": "modid:Fluid",
  "NAME": "Fluid",
  "DESCRIPTION": "#yCalm but #yperilous. The first attack each turn costs #b0 and deals #b50% more damage."
}
```

## Testing checklist

1. Register the stance during mod initialisation.
2. Add automated tests that:
   - Switch to the stance using `ChangeStanceAction`.
   - Assert `AbstractDungeon.player.stance` equals the custom ID.
   - Verify damage hooks apply correctly to ATTACK damage.
   - Ensure the stance exits cleanly when switching back to `Neutral`.

