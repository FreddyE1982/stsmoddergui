# Load and play your bundled character mod

You already have a runnable JAR thanks to `Character.createMod` and the `compileandbundle`
helpers shown in the other recipes. The remaining question is: how do you boot the game
with that package active? This guide covers both supported launch flows – the classic
ModTheSpire launcher and Slay the Spire's Steam Workshop driven mod manager – so your
team can test builds regardless of their preferred workflow.

## 1. Produce the distributable JAR with the high-level bundler

1. Keep using the turnkey builders – `Deck`, `Character`, and `Character.createMod` – to
   assemble the project. When you are ready to test, call the bundler with `bundle=True`
   so the helper writes the ModTheSpire manifest, copies Python support files and emits
   the final JAR in one pass.

   ```python
   from pathlib import Path

   from modules.modbuilder import Character

   class Buddy(Character):
       ...  # as defined in the basic character walkthrough

   output_dir = Path("dist")
   bundle_path = Buddy.createMod(
       output_dir,
       assets_root=Path("resources/Buddy"),
       python_source=Path("python"),
       bundle=True,
   )
   print(f"Your mod jar lives at {bundle_path}")
   ```

2. The call above returns the directory containing your compiled `.jar`. Copy that file to
your clipboard – both launchers expect to find it inside the game's `mods/` folder.

## 2. Launch through ModTheSpire's desktop app

1. Download the latest ModTheSpire release and drop `ModTheSpire.jar` (plus `MTS.cmd`
   on Windows or `MTS.sh` on Linux) into the Slay the Spire install directory.
2. Create a `mods` subfolder next to the launcher (if it does not already exist) and copy
   your bundled `.jar` into the folder alongside dependencies such as `BaseMod.jar`.
3. Double-click `MTS.cmd`/`MTS.sh` (or run `java -jar ModTheSpire.jar` with Java 8).
   The ModTheSpire window lists every JAR inside `mods/`. Tick your mod and press **Play**
   to boot the game with the bundle enabled.
4. Whenever you rebuild the mod, replace the JAR in `mods/` and rerun ModTheSpire.
   The launcher remembers your previous selection so regression testing stays quick.

## 3. Launch through the Steam Workshop mod manager

1. Ask teammates to subscribe to the ModTheSpire and BaseMod utilities on the Steam
   Workshop. Steam keeps both utilities updated and exposes a Mods toggle screen inside
   the game.
2. Copy your freshly built `.jar` into `%STEAMLIBRARY%/steamapps/common/SlayTheSpire/mods`
   (the same location ModTheSpire uses). Workshop subscriptions ensure the loader and
   BaseMod appear automatically in the in-game mod list.
3. Start Slay the Spire from Steam. On the title screen choose **Mods** (or the **Play
   with Mods** button on the launcher). A checklist displays all subscribed and locally
   installed JARs. Tick your mod, ensure dependencies such as BaseMod stay enabled, then
   click **Play** to launch the modded client.
4. When Steam finishes updating a workshop item or you replace your mod's JAR, restart the
   game and retick the mod if the manager prompts you. That guarantees everyone is testing
   against the same build.

## 4. Verify the mod is live in-game

- The title screen shows "Modded" under the version number when ModTheSpire loads your
  project correctly.
- Custom characters created through `Character.createMod` appear in the character select
  carousel. Load a new run, confirm starter decks, and run through combat to validate
  card behaviours exposed by `Deck.statistics()` in your build scripts.
- Use the mod manager to disable the package temporarily if you need to compare behaviour
  with the vanilla game.

With both launchers covered, everyone on the team can validate new builds without touching
low-level BaseMod plumbing.
