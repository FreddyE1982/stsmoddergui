# GraalPy runtime preparation notes

## Pillow rebuild requirements
- GraalPy cannot consume CPython wheels for native-extension packages. The `java_backend` integration therefore rebuilds Pillow from source using `pip install --no-binary :all: Pillow` within the GraalPy interpreter.
- Linux hosts require development headers for `libjpeg`, `zlib`, and `freetype` to complete the build. On Debian-based systems install `libjpeg-dev zlib1g-dev libfreetype6-dev`. On Fedora use `libjpeg-turbo-devel zlib-devel freetype-devel`.
- Windows builders need the Visual Studio Build Tools (MSVC) plus the Windows 10 SDK. Pillow's official docs list the [binary prerequisites](https://pillow.readthedocs.io/en/stable/installation.html#windows-installation) that must be installed prior to compiling from source.

## GraalPy interpreter discovery
- The experimental activation flow searches `GRAALPY_HOME`, standard `bin/` and `Scripts/` folders, and the current `$PATH` for an executable named `graalpy`, `graalpy.exe`, or `graalpy.bat`.
- When no interpreter is found the provisioning helper installs the `graalpy` PyPI distribution via `python -m pip install graalpy` before re-running the discovery procedure.

## Build provenance manifest
- Successful activations write `lib/graalpy/pillow_build.json` storing the GraalPy version, Pillow version, OS, architecture, and interpreter location.
- Tooling can inspect the manifest to detect version drifts and trigger rebuilds when the GraalPy toolchain or host architecture changes.
