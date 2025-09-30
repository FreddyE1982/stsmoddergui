"""Dynamic proxies that provide a Pythonic façade for Java packages."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

import jpype


@lru_cache(maxsize=None)
def _jclass(name: str):
    return jpype.JClass(name)


def _modifier():
    return _jclass("java.lang.reflect.Modifier")


def _iter_methods(java_class: Any, method_name: str):
    for method in java_class.class_.getMethods():
        if method.getName() == method_name:
            yield method


def _is_functional_interface(parameter: Any) -> bool:
    if not parameter.isInterface():
        return False
    abstract_methods = [
        method
        for method in parameter.getMethods()
        if _modifier().isAbstract(method.getModifiers())
    ]
    return len(abstract_methods) == 1


def _build_callable_proxy(parameter: Any, callback: Callable[..., Any]) -> Any:
    interface_name = parameter.getName()
    abstract_methods = [
        method
        for method in parameter.getMethods()
        if _modifier().isAbstract(method.getModifiers())
    ]
    if not abstract_methods:
        raise TypeError(
            f"Interface {interface_name} does not expose an abstract method for proxying."
        )
    method_name = abstract_methods[0].getName()
    return jpype.JProxy(interface_name, dict(**{method_name: callback}))


def _convert_argument(parameter: Any, value: Any) -> Any:
    if callable(value) and _is_functional_interface(parameter):
        return _build_callable_proxy(parameter, value)
    if parameter.isArray() and isinstance(value, (list, tuple)):
        component = parameter.getComponentType()
        array_type = jpype.JArray(_jclass(component.getName()))
        return array_type(value)
    return value


class JavaCallableWrapper:
    """Wraps a callable Java attribute and performs auto conversions."""

    def __init__(self, owner: Any, name: str, callable_obj: Any) -> None:
        self._owner = owner
        self._name = name
        self._callable = callable_obj
        self._methods_cache: Optional[List[Any]] = None
        self._signature_cache: Dict[int, List[Tuple[Any, ...]]] = {}

    def _methods(self) -> List[Any]:
        if self._methods_cache is None:
            self._methods_cache = list(_iter_methods(self._owner, self._name))
        return self._methods_cache

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if kwargs:
            raise TypeError(
                f"Java callable '{self._name}' does not accept keyword arguments."
            )

        methods = self._methods()
        if not methods:
            return self._callable(*args)

        arity = len(args)
        signatures = self._signature_cache.get(arity)
        if signatures is None:
            signatures = []
            for method in methods:
                parameters = method.getParameterTypes()
                if len(parameters) == arity:
                    signatures.append(tuple(parameters))
            self._signature_cache[arity] = signatures

        for signature in signatures:
            converted = []
            try:
                for parameter, value in zip(signature, args):
                    converted.append(_convert_argument(parameter, value))
            except TypeError:
                continue
            return self._callable(*converted)

        return self._callable(*args)


class JavaClassWrapper:
    """Wrapper that exposes Java class methods as Python attributes."""

    def __init__(self, java_class: Any) -> None:
        self._class = java_class

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._class(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        attribute = getattr(self._class, item)
        if callable(attribute):
            return JavaCallableWrapper(self._class, item, attribute)
        if isinstance(attribute, jpype.JClass):
            return JavaClassWrapper(attribute)
        return attribute


class JavaPackageWrapper:
    """Recursive descriptor that gives access to Java packages."""

    def __init__(self, package: Any) -> None:
        self._package = package

    def __getattr__(self, item: str) -> Any:
        attribute = getattr(self._package, item)
        if isinstance(attribute, jpype._jpackage.JPackage):
            return JavaPackageWrapper(attribute)
        if isinstance(attribute, jpype.JClass):
            return JavaClassWrapper(attribute)
        if callable(attribute):
            return JavaCallableWrapper(self._package, item, attribute)
        return attribute


def create_package_wrapper(package_name: str) -> JavaPackageWrapper:
    return JavaPackageWrapper(jpype.JPackage(package_name))


__all__ = [
    "JavaCallableWrapper",
    "JavaClassWrapper",
    "JavaPackageWrapper",
    "create_package_wrapper",
]
