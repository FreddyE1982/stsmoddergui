from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.basemod_wrapper import UnifiedSpireAPI


class DummyField:
    def __init__(self) -> None:
        self.calls = []

    def set(self, card, value) -> None:
        self.calls.append((card, bool(value)))


class DummyCallable:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, card, amount: int) -> None:
        self.calls.append((card, int(amount)))


class DummyEnv:
    def __init__(self) -> None:
        self.resolutions = {}

    def package(self, name: str):  # pragma: no cover - trivial namespace
        return SimpleNamespace()

    def resolve(self, path: str):
        try:
            return self.resolutions[path]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(path) from exc


def build_api() -> tuple[UnifiedSpireAPI, DummyField, DummyCallable, DummyCallable]:
    env = DummyEnv()
    retain_field = DummyField()
    exhaustive_setter = DummyCallable()
    exhaustive_upgrader = DummyCallable()
    mapping = UnifiedSpireAPI._BOOLEAN_KEYWORDS["retain"]
    env.resolutions[mapping] = retain_field
    for key, path in UnifiedSpireAPI._NUMERIC_KEYWORDS["exhaustive"].items():
        env.resolutions[path] = exhaustive_setter if key == "setter" else exhaustive_upgrader
    api = UnifiedSpireAPI(env)
    return api, retain_field, exhaustive_setter, exhaustive_upgrader


def test_apply_keyword_sets_base_attributes():
    api, retain_field, _, _ = build_api()
    card = SimpleNamespace(
        isInnate=False,
        isEthereal=False,
        exhaust=False,
        retain=False,
        selfRetain=False,
    )

    api.apply_keyword(card, "inate")
    api.apply_keyword(card, "Ethereal")
    api.apply_keyword(card, "EXHAUST")
    api.apply_keyword(card, "retain")

    assert card.isInnate is True
    assert card.isEthereal is True
    assert card.exhaust is True
    assert card.retain is True
    assert card.selfRetain is True
    assert retain_field.calls[-1] == (card, True)


def test_apply_keyword_supports_numeric_amounts():
    api, _, setter, upgrader = build_api()
    card = SimpleNamespace()

    api.apply_keyword(card, "stslib:exhaustive", amount=2, upgrade=1)

    assert setter.calls == [(card, 2)]
    assert upgrader.calls == [(card, 1)]


def test_numeric_keywords_require_amount():
    api, _, _, _ = build_api()
    card = SimpleNamespace()

    with pytest.raises(ValueError):
        api.apply_keyword(card, "exhaustive")


def test_unknown_keyword_raises():
    api, _, _, _ = build_api()
    card = SimpleNamespace()

    with pytest.raises(KeyError):
        api.apply_keyword(card, "totallymadeup")


def test_keyword_fields_list_base_and_stslib_paths():
    api, _, _, _ = build_api()

    fields = api.keyword_fields()

    assert "innate" in fields and "AbstractCard.isInnate" in fields["innate"]
    assert "retain" in fields and "AlwaysRetainField" in fields["retain"]
    assert "exhaustive" in fields and "ExhaustiveVariable" in fields["exhaustive"]
