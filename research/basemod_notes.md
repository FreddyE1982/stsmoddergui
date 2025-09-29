# BaseMod research notes

- BaseMod is the de-facto community framework for Slay the Spire mods.  It
  provides hooks for cards, relics, potions, characters and keywords.
- The API expects mods to implement numerous listener interfaces such as
  `EditCardsSubscriber` or `PostInitializeSubscriber`.  Our wrapper handles these
  single-method interfaces automatically via JPype proxies.
- BaseMod integrates with the ModTheSpire loader.  The relevant packages live
  under `com.evacipated.cardcrawl.modthespire`.
- The framework interacts with the game classes in `com.megacrit.cardcrawl` and
  uses libGDX utilities from `com.badlogic.gdx`.
- The release jar is published alongside ModTheSpire; the latest download link
  uses ``https://github.com/daviscook477/BaseMod/releases/latest/download/BaseMod.jar``.
