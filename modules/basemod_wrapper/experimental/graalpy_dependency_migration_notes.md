# GraalPy Dependency Migration Notes

## Overview
Switching the toolchain to GraalPy removes the JPype bridge entirely—the Python and JVM layers would run under the same GraalVM runtime. The remaining compatibility audit therefore focuses on packages that still ship with the project after JPype is retired.

## Native-extension packages that require per-target rebuilds
### Pillow
- Pillow exposes imaging primitives through CPython extension modules. GraalPy's documentation states that "Packages that use the native API must be built and installed with GraalPy, and the prebuilt wheels for CPython from pypi.org cannot be used." ([GraalPy Native Extensions](https://github.com/oracle/graalpython/blob/master/docs/user/Native-Extensions.md)).
- Action: refresh the bootstrapper so the first GraalPy launch invokes `pip install Pillow --no-binary :all:` (or an equivalent build command) using the GraalPy interpreter. Document build prerequisites (zlib, libjpeg) for modders on Windows, macOS, and Linux to avoid support churn.
- Action: cache a build provenance file (compiler, GraalPy version, Pillow version, host OS/arch) next to the compiled wheels so future upgrades can detect when to rebuild.

## Pure-Python packages that continue to work
### Pytest
- Pytest is published as pure Python and does not rely on CPython C-API calls, so it can execute on GraalPy without rebuilds. ([Pytest Installation Docs](https://docs.pytest.org/en/latest/how-to/installation.html)).
- Action: ensure `python -m pytest` is exercised with the GraalPy interpreter in CI once the migration branch exists, capturing any behavioural differences caused by GraalPy's alternative standard-library implementations.

## Additional verification steps before a GraalPy switchover
- Inventory any optional dependencies that plugin authors might install (NumPy, requests, etc.) and document their GraalPy status. Provide a supported/unsupported matrix in contributor docs so community projects know what to expect.
- Review the runtime bootstrap plans emitted by `modules.modbuilder.runtime_env`. Remove the hard-coded JPype installation commands and replace them with hooks that can inject GraalPy-specific environment validation.
- Revisit the deck analytics helpers that depend on Pillow for chart rendering. Confirm that GraalPy's sandboxed filesystem permissions allow Pillow to load fonts and write PNGs in the bundled runtime, and capture the results as automated smoke tests.
- Coordinate with documentation maintainers so every tutorial under `how to/` references the GraalPy download + setup workflow, highlighting differences from the old JPype-based installation steps.
