# BaseMod summary

BaseMod is the community driven modding library for Slay the Spire.  It
extends the base game with hooks for:

* Adding custom characters, cards, relics, and events.
* Registering new keywords, powers, and potions.
* Injecting subscribers into the game's update and render loops.
* Saving and loading mod state via the `CustomSavable` interface.

The Java entry point is the static class `basemod.BaseMod`.  Most modders
interact with the library through static methods such as `addCard`,
`addRelic`, `subscribe`, and `registerModBadge`.

BaseMod also provides a large collection of interfaces inside the
`basemod.interfaces` package.  Implementations are registered via
`BaseMod.subscribe`.

The wrapper developed in this task mirrors all of these features by using
JPype to load the Java classes at runtime.
