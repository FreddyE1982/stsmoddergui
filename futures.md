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

## Interface signature caching

Cache inspected Java method signatures to speed up repeated calls to heavily
used BaseMod hooks.  Usage: extend ``JavaCallableWrapper`` with a lookup table so
plugins do not incur repeated reflection overhead.
