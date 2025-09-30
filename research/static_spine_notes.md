# Static spine animation notes

Source: [BaseMod Wiki – Custom Character Animations](https://github.com/daviscook477/BaseMod/wiki/Custom-Character-Animations)

* Slay the Spire ships with a Spine runtime (3.7.x). Characters normally load an atlas + skeleton JSON pair via `loadAnimation`.
* Mods without skeletal animations can fake the setup by generating a trivial atlas that declares a single region covering the PNG pose.
* The matching skeleton JSON only needs one bone (`root`), one slot (`main`) and a default skin with the region attachment named after the PNG.
* All coordinates in the attachment can be zero; the runtime simply renders the region at the origin for the idle animation.
* The atlas header must echo the PNG dimensions, use `format: RGBA8888`, `filter: Linear,Linear` and `repeat: none` to match vanilla assets.
* Providing an empty `idle` animation block is sufficient—the character remains static but passes BaseMod’s validation.
