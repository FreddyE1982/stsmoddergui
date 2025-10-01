from __future__ import annotations

from types import SimpleNamespace


class StubActionManager:
    def __init__(self) -> None:
        self.actions = []

    def addToBottom(self, action) -> None:
        self.actions.append(action)

    def pop(self):
        return self.actions.pop(0)

    def clear(self) -> None:
        self.actions.clear()


class StubDamageAction:
    def __init__(self, target, info, effect) -> None:
        self.target = target
        self.info = info
        self.effect = effect


class StubDamageAllEnemiesAction:
    def __init__(self, player, amounts, damage_type, effect) -> None:
        self.player = player
        self.amounts = list(amounts)
        self.damage_type = damage_type
        self.effect = effect


class StubGainBlockAction:
    def __init__(self, target, source, amount) -> None:
        self.target = target
        self.source = source
        self.amount = amount


class StubDrawCardAction:
    def __init__(self, player, amount) -> None:
        self.player = player
        self.amount = amount


class StubGainEnergyAction:
    def __init__(self, amount) -> None:
        self.amount = amount


class StubApplyPowerAction:
    def __init__(self, target, source, power, amount) -> None:
        self.target = target
        self.source = source
        self.power = power
        self.amount = amount


class StubDamageInfo:
    class DamageType:
        NORMAL = "NORMAL"

    def __init__(self, source, amount, damage_type) -> None:
        self.source = source
        self.base = amount
        self.output = amount
        self.type = damage_type


class StubCustomCard:
    def __init__(self, card_id, name, img, cost, description, card_type, color, rarity, target) -> None:
        self.cardID = card_id
        self.name = name
        self.rawDescription = description
        self.cost = cost
        self.type = card_type
        self.color = color
        self.rarity = rarity
        self.target = target
        self.baseDamage = 0
        self.damage = 0
        self.baseBlock = 0
        self.block = 0
        self.baseMagicNumber = 0
        self.magicNumber = 0
        self.multiDamage = []
        self.damageTypeForTurn = StubDamageInfo.DamageType.NORMAL
        self.isMultiDamage = False
        self.upgraded = False
        self.exhaust = False
        self.isInnate = False
        self.isEthereal = False
        self.retain = False
        self.selfRetain = False

    def initializeDescription(self) -> None:
        self.description = self.rawDescription

    def upgradeName(self) -> None:
        self.upgraded = True

    def upgradeDamage(self, amount: int) -> None:
        self.baseDamage += amount
        self.damage = self.baseDamage

    def upgradeBlock(self, amount: int) -> None:
        self.baseBlock += amount
        self.block = self.baseBlock

    def upgradeMagicNumber(self, amount: int) -> None:
        self.baseMagicNumber += amount
        self.magicNumber = self.baseMagicNumber


class StubRelicTier:
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    BOSS = "BOSS"
    SHOP = "SHOP"

    @staticmethod
    def valueOf(name: str):
        return getattr(StubRelicTier, name)


class StubLandingSound:
    FLAT = "FLAT"
    SOLID = "SOLID"
    CLINK = "CLINK"
    MAGICAL = "MAGICAL"

    @staticmethod
    def valueOf(name: str):
        return getattr(StubLandingSound, name)


class StubRelicType:
    SHARED = "SHARED"
    RED = "RED"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"
    CUSTOM = "CUSTOM"

    @staticmethod
    def valueOf(name: str):
        return getattr(StubRelicType, name)


class StubCustomRelic:
    def __init__(self, relic_id: str, image: str, tier: object, sound: object) -> None:
        self.relicId = relic_id
        self.imgUrl = image
        self.tier = tier
        self.landing_sound = sound
        self.counter = 0
        self.grayscale = False
        self.name = relic_id
        self.description = ""
        self.flavorText = ""

    def makeCopy(self):
        return type(self)(self.relicId, self.imgUrl, self.tier, self.landing_sound)


class StubColor:
    def __init__(self, r: float, g: float, b: float, a: float) -> None:
        self.r = r
        self.g = g
        self.b = b
        self.a = a


class StubTexture:
    def __init__(self, path: str) -> None:
        self.path = path


class StubAbstractStance:
    stances: dict[str, "StubAbstractStance"] = {}

    def __init__(self) -> None:
        self.ID = ""
        self.name = ""
        self.description = ""
        self.c = None
        self.auraColor = None
        self.particleColor = None

    def updateDescription(self) -> None:  # pragma: no cover - behavioural placeholder
        return None

    def updateAnimation(self) -> None:  # pragma: no cover - behavioural placeholder
        return None

    def onEnterStance(self) -> None:  # pragma: no cover - behavioural placeholder
        return None

    def onExitStance(self) -> None:  # pragma: no cover - behavioural placeholder
        return None


class StubStanceAuraEffect:
    STANCE_COLORS: dict[str, StubColor] = {}
    PARTICLE_COLORS: dict[str, StubColor] = {}
    PARTICLE_TEXTURES: dict[str, StubTexture] = {}


class StubStanceParticleEffect:
    PARTICLE_COLORS: dict[str, StubColor] = {}


class StubStanceHelper:
    stanceMap: dict[str, object] = {}
    nameMap: dict[str, str] = {}


class StubStrengthPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Strength"


class StubWeakPower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Weak"


class StubPoisonPower:
    def __init__(self, owner, source, amount) -> None:
        self.owner = owner
        self.source = source
        self.amount = amount
        self.name = "Poison"


class StubDexterityPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Dexterity"


class StubArtifactPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Artifact"


class StubFocusPower:
    def __init__(self, owner, amount) -> None:
        self.owner = owner
        self.amount = amount
        self.name = "Focus"


class StubVulnerablePower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Vulnerable"


class StubFrailPower:
    def __init__(self, owner, amount, is_source_monster) -> None:
        self.owner = owner
        self.amount = amount
        self.is_source_monster = is_source_monster
        self.name = "Frail"


class StubCardColor:
    RED = "RED"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"

    @staticmethod
    def valueOf(name: str):
        return getattr(StubCardColor, name)


class StubSpire:
    def __init__(self) -> None:
        self.calls = []
        self._actions: dict[str, type] = {}

    def apply_keyword(self, card, keyword, *, amount=None, upgrade=None) -> None:
        self.calls.append(
            {
                "card": card,
                "keyword": keyword,
                "amount": amount,
                "upgrade": upgrade,
            }
        )

    def register_action(self, name: str, action_cls):
        self._actions[name] = action_cls

    def action(self, name: str):
        try:
            return self._actions[name]
        except KeyError as exc:
            raise KeyError(f"Stub action '{name}' has not been registered.") from exc

    def reset(self) -> None:
        self.calls.clear()
        self._actions.clear()

