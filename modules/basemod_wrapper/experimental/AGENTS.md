# Experimental extension guidelines

- This directory defines the optional `experimental` submodule of `modules.basemod_wrapper`.
- Every feature implemented here **must** live inside its own submodule (or
  nested package) and expose `activate()` / `deactivate()` callables so it can
  be toggled through `modules.basemod_wrapper.experimental.on/off`.
- Callers activate behaviour by importing `modules.basemod_wrapper.experimental`
  and invoking `experimental.on("feature_name")`. To disable, call
  `experimental.off("feature_name")`.
- Avoid global side effects at import time; experimental features should only
  change runtime behaviour when activated.
- Document new submodules directly in their module docstrings so downstream
  users understand what toggling them does and how to extend them.
