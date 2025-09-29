# Futures

A forward-looking log of ideas and enhancements inferred while working on
the project.

## JPype bootstrap improvements

* Automate discovery of Slay the Spire installation directories on major
  operating systems.
* Provide a CLI helper that writes the BaseMod configuration file after
  prompting the user for paths.

## Plugin ecosystem

* Implement lazy plugin discovery using entry points or a manifest file
  so users can drop plugins into a directory and have them auto-loaded.
* Offer lifecycle hooks (before/after JVM start, before/after plugin
  activation) so third-party code can react to runtime events.

## Testing strategy

* Add integration tests that spin up a stub JVM (for example using a
  mock JAR) to validate the reflection and proxy helpers without requiring
  the actual game binaries.
