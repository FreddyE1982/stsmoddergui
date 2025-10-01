# BaseMod render hook reference

## RenderSubscriber
- Source: `mod/src/main/java/basemod/interfaces/RenderSubscriber.java` in BaseMod repository.
- Signature: `void receiveRender(SpriteBatch sb);`
- Called every frame with the active `SpriteBatch` while the dungeon or menu is rendering.
- Suitable for drawing overlay textures because it executes after the core game renders but before the batch is flushed.

## PostUpdateSubscriber
- Source: `mod/src/main/java/basemod/interfaces/PostUpdateSubscriber.java`.
- Signature: `void receivePostUpdate();`
- Invoked once per frame after the game update loop finishes.
- Useful for time-based cleanup such as expiring overlays.

## Registration
- Runtime registration happens via `BaseMod.subscribe(subscriber)` (`mod/src/main/java/basemod/BaseMod.java`).
- BaseMod keeps distinct subscriber lists for each interface and automatically adds a subscriber to the relevant lists when the object implements them.
- Unsubscribing is done through `BaseMod.unsubscribeLater(subscriber)` which schedules removal at the end of the current iteration.
