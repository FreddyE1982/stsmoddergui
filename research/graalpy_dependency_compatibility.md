# GraalPy Dependency Compatibility Notes

## JPype1
- The official installation guide states: "JPype works CPython 3.5 or later. Both the runtime and the development package are required." ([JPype Installation Docs](https://jpype.readthedocs.io/en/latest/install.html)).
- GraalPy's CPython C API support is experimental and not binary compatible with CPython. "Packages that use the native API must be built and installed with GraalPy, and the prebuilt wheels for CPython from pypi.org cannot be used." ([GraalPy Native Extensions Docs](https://github.com/oracle/graalpython/blob/master/docs/user/Native-Extensions.md)).
- JPype1 implements its bridge as a CPython C extension, so GraalPy cannot reuse the binary wheels we rely on today and there is no upstream GraalPy build. This effectively blocks JPype1 on GraalPy.

## Pillow
- Pillow ships native C extension modules. GraalPy documents make clear that "Packages that use the native API must be built and installed with GraalPy, and the prebuilt wheels for CPython from pypi.org cannot be used." ([GraalPy Native Extensions Docs](https://github.com/oracle/graalpython/blob/master/docs/user/Native-Extensions.md)).
- As long as a GraalPy-compatible wheel is not provided, Pillow must be rebuilt on every target system when using GraalPy's pip.

## Pytest
- Pytest is a pure-Python package and does not depend on CPython-only extensions, so it is expected to run on GraalPy without rebuilds.
