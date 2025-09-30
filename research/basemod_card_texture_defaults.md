# BaseMod card texture defaults

Source: https://github.com/daviscook477/BaseMod/blob/master/mod/src/main/java/basemod/abstracts/CustomCard.java

## Observations

- `CustomCard` stores optional texture path fields (`textureBackgroundSmallImg`, `textureBackgroundLargeImg`, etc.).
- `getBackgroundSmallTexture` and `getBackgroundLargeTexture` return BaseMod-provided textures when the card does not supply a background path. The lookup switches on `this.type` and pulls from `BaseMod.getAttackBgTexture`, `BaseMod.getPowerBgTexture`, or `BaseMod.getSkillBgTexture`.
- Orb textures default via `BaseMod.getEnergyOrbTexture` / `getEnergyOrbPortraitTexture` when no per-card orb path is provided.
- Banner textures default to `null` unless explicitly set. Portrait frame regions default to core ImageMaster regions when no custom frames are provided (see `setDisplayRarity`).

## Confirmation

This means that as long as only the inner card art is supplied to BaseMod, it will fall back to the base game's card frames/backgrounds for the registered color. Only the colour needs to provide frame textures; individual cards can omit them.
