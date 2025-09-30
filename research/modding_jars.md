# Core modding jar download notes

- **BaseMod.jar** and **StSLib.jar** can be fetched directly from the latest GitHub
  releases:
  - https://github.com/daviscook477/BaseMod/releases/latest/download/BaseMod.jar
  - https://github.com/kiooeht/StSLib/releases/latest/download/StSLib.jar
- **ModTheSpire.jar** is packaged inside a zip archive. Download the latest
  release from https://github.com/kiooeht/ModTheSpire/releases/latest/download/ModTheSpire.zip
  and extract the `ModTheSpire.jar` entry.
- The proprietary `desktop-1.0.jar` needs to be copied from a local Slay the
  Spire installation. Place it in `modules/basemod_wrapper/lib` or set the
  `STS_DESKTOP_JAR` environment variable to its full path before running the
  tests that rely on compilation.
