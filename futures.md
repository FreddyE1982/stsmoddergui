# Futures roadmap

## Module level plugin discovery

Implement automatic discovery of plugin entry points via naming conventions or
package metadata.  This would allow dropping plugin modules into a dedicated
folder without touching the core code.  Usage: call
``PLUGIN_MANAGER.auto_discover("plugins")`` once implemented.

## JVM dependency caching strategy

Persist downloaded jars with version tracking to avoid unnecessary re-downloads
when different wrapper versions are required.  Usage: expand
``ensure_basemod_jar`` to accept a version string and maintain a local manifest.

## Desktop jar discovery helper

Provide a small helper that scans common Steam install directories and honours
environment variables to automatically locate ``desktop-1.0.jar``. Usage: expose
``ensure_desktop_jar()`` that either returns a valid path or raises a helpful
error instructing users how to obtain the jar.

## Interface signature caching

Cache inspected Java method signatures to speed up repeated calls to heavily
used BaseMod hooks.  Usage: extend ``JavaCallableWrapper`` with a lookup table so
plugins do not incur repeated reflection overhead.

## LimeWire decryption pipeline

Build a Python implementation of the LimeWire content decrypter so that the encrypted jars downloaded during bundling can be unwrapped automatically. Usage: mirror the `GE#getContentItemDecryptionKeys` flow in Python, deriving AES keys from the passphrase and decrypting the AES-CTR stream into usable game jars.

## StSLib feature matrix generation

Generate runtime documentation for every exposed StSLib hook, action and interface by introspecting the loaded JVM classes. Usage: extend ``UnifiedSpireAPI`` with an ``introspect()`` helper that emits Markdown files inside ``research/`` summarising constructor signatures and expected usage patterns. This keeps the Python façade aligned with future StSLib releases.

## Unified keyword profiles

Allow describing complex keyword setups declaratively via JSON/YAML manifest files. Usage: add ``UnifiedSpireAPI.load_keywords(path: Path)`` that consumes manifests, registers keywords, and applies card field defaults to reduce boilerplate for large mods.
