# Repository authoring guidelines
- Always favour the highest-level helpers exposed by the project when extending gameplay guides or code samples.
- In particular, use `modules.modbuilder.Deck`, `modules.modbuilder.Character`, and `modules.basemod_wrapper.keywords.Keyword` (
plus their documented helpers) instead of low-level BaseMod plumbing whenever possible.
- Documentation in this repository should explicitly demonstrate the Deck/Character/Keyword workflow so that future contributors
 reach for those abstractions first.
- When adding new teaching material remember to point readers back to the ready-made bundling helpers such as `Character.createMod` and `Deck.statistics()` so tutorials stay aligned with the automation surface.
- Binary assets must never be committed. When image placeholders are required, encode them as base64 strings inside text files and document their purpose.
