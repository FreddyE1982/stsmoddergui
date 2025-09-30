# StSModdingToolCardImagesCreator quick reference

Source: https://github.com/JohnnyBazooka89/StSModdingToolCardImagesCreator (README)

## Key behaviours

- Accepts source images with aspect ratio 25:19. Images sized 500x380 or larger yield six outputs: small and portrait variants for attack, skill, and power cards.
- For images between 500x380 and 250x190 it produces three outputs (attack, skill, power) without portrait variants.
- Recommended workflow: provide a 500x380 image (or optionally an additional 250x190 variant to improve downscaled quality) inside the `cards` folder, run `run.bat`, then copy generated files from `images/Attacks`, `images/Skills`, and `images/Powers`.
- Output file names follow `<input_name>_<type>.png` (e.g. `Example_Attack.png`, `Example_Attack_P.png`).

## Implications for automation

- Our pipeline must validate a 500x380 source image to guarantee both portrait and standard outputs.
- The tool is packaged as a Maven project; building the jar requires invoking `mvn package`. Runtime expects placing source files under a `cards` directory relative to execution.
