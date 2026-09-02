"""SRD-derived monster and NPC roster for validation play.

The factories in this module prioritize mechanically useful SRD coverage for
AI evaluation. Each creature preserves the SRD stat identity that the current
engine can represent directly: ability scores, hit dice, armor, movement,
creature type, senses, weapons, basic spellcasting, and condition immunities.
Special traits that require dedicated handlers are recorded in metadata instead
of being silently approximated as different behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.actions_functional import (
    register_spell,
    setup_standard_actions,
    update_weapon_templates,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import BaseItem
from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponSlot
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import SenseMode, SensesType
from dnd.classes.barbarian import RecklessAttack
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.materialization import (
    CreatureBuildContext,
    CreaturePossessionMode,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    creature_factory,
    get_content_declaration,
)
from dnd.types.abilities import AbilityName
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition,
    CreaturePossessionGrant,
    apply_creature_possessions,
)
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.entity import Entity, EntityConfig
from dnd.monsters.multiattack_definitions import (
    MultiattackConfigurationDefinition,
    SRD_MULTIATTACK_CONFIGURATIONS_BY_CONTENT_ID,
)
from dnd.monsters.traits import (
    AggressiveMoveAction,
    DivineEminenceAction,
    LeadershipAction,
    MultiattackAction,
    NaturalAttack,
    register_aggressive,
    register_brave,
    register_brute,
    register_cunning_action,
    register_dark_devotion,
    register_dire_wolf_bite_prone_rider,
    register_divine_eminence,
    register_ghoul_claws_paralysis,
    register_keen_hearing_and_sight,
    register_keen_hearing_and_smell,
    register_leadership,
    register_martial_advantage,
    register_multiattack,
    register_natural_bite,
    register_pack_tactics,
    register_parry,
    register_rampage,
    register_reckless,
    register_sneak_attack,
    register_sunlight_sensitivity,
    register_surprise_attack,
    register_undead_fortitude,
    register_wolf_bite_prone_rider,
)
from dnd.spells.abjuration import (
    LesserRestoration,
    MageArmor,
    Sanctuary,
    ShieldOfFaith,
    register_counterspell_reaction,
    register_shield_reaction,
)
from dnd.spells.conjuration import MistyStep, SpiritGuardians
from dnd.spells.enchantment import Bless, Command, HoldPerson
from dnd.spells.evocation import (
    ConeOfCold,
    CureWounds,
    FireBolt,
    Fireball,
    GuidingBolt,
    IceStorm,
    MagicMissile,
    SacredFlame,
)
from dnd.spells.illusion import GreaterInvisibility
from dnd.spells.necromancy import InflictWounds


HitDieValue = Literal[4, 6, 8, 10, 12]
WeaponDieValue = Literal[4, 6, 8, 10, 12, 20]
_VISUAL_SCALE_BY_SIZE: dict[Size, float] = {
    Size.TINY: 0.68,
    Size.SMALL: 0.82,
    Size.MEDIUM: 1.0,
    Size.LARGE: 1.28,
    Size.HUGE: 1.55,
    Size.GARGANTUAN: 2.0,
}


def _register_configured_multiattack(
    entity: Entity,
    content_id: str,
) -> None:
    """Install one exact typed stat-block Multiattack configuration."""
    declaration = SRD_MULTIATTACK_CONFIGURATIONS_BY_CONTENT_ID[content_id]
    configuration = MultiattackConfigurationDefinition.model_validate(
        declaration.definition_payload,
    )
    register_multiattack(
        entity,
        declaration.descriptor.display_name,
        tuple(
            (step.weapon_slot, step.count)
            for step in configuration.steps
        ),
        configured_action_ref=declaration.ref,
    )


class SrdCreatureParameters(BaseModel):
    """Current SRD creature roots have no authored construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _SrdCreatureFacts(BaseModel):
    """Private declaration inputs; the bound descriptor is the public catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    creature_id: str
    display_name: str
    description: str
    challenge_rating: str
    source_anchor: str
    role_tags: tuple[str, ...]
    represented_traits: tuple[str, ...] = ()
    sort_order: int


def _configure_commoner(context: CreatureBuildContext) -> Entity:
    """Create an SRD Commoner."""
    entity = _create_srd_entity(
        context=context,
        description="A noncombatant pressed into danger.",
        abilities=(10, 10, 10, 10, 10, 10),
        hit_die_value=8,
        hit_die_count=1,
        proficiency_bonus=2,
    )
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.club",
            entity.uuid,
        ),
    )
    return entity


def _configure_bandit(context: CreatureBuildContext) -> Entity:
    """Create an SRD Bandit."""
    entity = _create_srd_entity(
        context=context,
        description="A lightly armored raider with melee and crossbow pressure.",
        abilities=(11, 12, 12, 10, 10, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.scimitar",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.light_crossbow",
            entity.uuid,
        ),
    )
    return entity


def _configure_cultist(context: CreatureBuildContext) -> Entity:
    """Create an SRD Cultist."""
    entity = _create_srd_entity(
        context=context,
        description="A zealot with a scimitar and social skill pressure.",
        abilities=(11, 12, 10, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"deception": True, "religion": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.scimitar",
            entity.uuid,
        ),
    )
    register_dark_devotion(entity)
    return entity


def _configure_guard(context: CreatureBuildContext) -> Entity:
    """Create an SRD Guard."""
    entity = _create_srd_entity(
        context=context,
        description="A defensive sentry with shielded spear pressure.",
        abilities=(13, 12, 12, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"perception": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.chain_shirt",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.spear",
            entity.uuid,
        ),
        shield=(
            context.possession_mode
            == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )
    return entity


def _configure_tribal_warrior(context: CreatureBuildContext) -> Entity:
    """Create an SRD Tribal Warrior."""
    entity = _create_srd_entity(
        context=context,
        description="A light skirmisher that pressures pack-melee scenarios.",
        abilities=(13, 11, 12, 8, 11, 8),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.spear",
            entity.uuid,
        ),
    )
    register_pack_tactics(entity)
    return entity


def _configure_kobold(context: CreatureBuildContext) -> Entity:
    """Create an SRD Kobold."""
    entity = _create_srd_entity(
        context=context,
        description="A fragile darkvision skirmisher.",
        abilities=(7, 15, 9, 8, 7, 8),
        hit_die_value=6,
        hit_die_count=2,
        proficiency_bonus=2,
        size=Size.SMALL,
        weight=35,
        darkvision=True,
    )
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.dagger",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.kobold_sling",
            entity.uuid,
        ),
    )
    register_pack_tactics(entity)
    register_sunlight_sensitivity(entity)
    return entity


def _configure_acolyte(context: CreatureBuildContext) -> Entity:
    """Create an SRD Acolyte-style low priest."""
    entity = _create_srd_entity(
        context=context,
        description="A junior divine caster useful for low-CR support tests.",
        abilities=(10, 10, 10, 10, 14, 11),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 3},
        skills={"medicine": True, "religion": True},
    )
    for spell_type in (SacredFlame, Bless, CureWounds):
        register_spell(entity, spell_type, caster_level=1)
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.club",
            entity.uuid,
        ),
    )
    return entity


def _configure_scout(context: CreatureBuildContext) -> Entity:
    """Create an SRD Scout."""
    entity = _create_srd_entity(
        context=context,
        description="A perception-heavy ranged scout.",
        abilities=(11, 14, 12, 11, 13, 11),
        hit_die_value=8,
        hit_die_count=3,
        proficiency_bonus=2,
        skills={"nature": True, "perception": True, "stealth": True, "survival": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.shortsword",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.longbow",
            entity.uuid,
        ),
    )
    register_keen_hearing_and_sight(entity)
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.scout.shortsword",
    )
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.scout.longbow",
    )
    return entity


def _configure_thug(context: CreatureBuildContext) -> Entity:
    """Create an SRD Thug."""
    entity = _create_srd_entity(
        context=context,
        description="A durable low-CR bruiser with crossbow fallback.",
        abilities=(15, 11, 14, 10, 10, 11),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        skills={"intimidation": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.mace",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.heavy_crossbow",
            entity.uuid,
        ),
    )
    register_pack_tactics(entity)
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.thug",
    )
    return entity


def _configure_spy(context: CreatureBuildContext) -> Entity:
    """Create an SRD Spy."""
    entity = _create_srd_entity(
        context=context,
        description="A mobile infiltrator with shortsword and hand-crossbow pressure.",
        abilities=(10, 15, 10, 12, 14, 16),
        hit_die_value=8,
        hit_die_count=6,
        proficiency_bonus=2,
        skills={"deception": True, "insight": True, "investigation": True, "perception": True, "persuasion": True, "sleight_of_hand": True, "stealth": True},
    )
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.shortsword",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.spy_hand_crossbow",
            entity.uuid,
        ),
    )
    register_cunning_action(entity)
    register_sneak_attack(entity)
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.spy",
    )
    return entity


def _configure_berserker(context: CreatureBuildContext) -> Entity:
    """Create an SRD Berserker."""
    entity = _create_srd_entity(
        context=context,
        description="A high-HP axe charger for melee pressure tests.",
        abilities=(16, 12, 17, 9, 11, 9),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=2,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.greataxe",
            entity.uuid,
        ),
    )
    register_reckless(entity)
    return entity


def _configure_bandit_captain(context: CreatureBuildContext) -> Entity:
    """Create an SRD Bandit Captain."""
    entity = _create_srd_entity(
        context=context,
        description="A durable duelist leader with melee and thrown-dagger pressure.",
        abilities=(15, 16, 14, 14, 11, 14),
        hit_die_value=8,
        hit_die_count=10,
        proficiency_bonus=2,
        skills={"athletics": True, "deception": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.studded_leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.scimitar",
            entity.uuid,
        ),
        offhand=_default_possession(
            context,
            "weapon.dagger",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.bandit_captain_thrown_dagger",
            entity.uuid,
        ),
    )
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.bandit_captain.melee",
    )
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.bandit_captain.ranged",
    )
    register_parry(entity)
    return entity


def _configure_priest(context: CreatureBuildContext) -> Entity:
    """Create an SRD Priest."""
    entity = _create_srd_entity(
        context=context,
        description="A divine support caster with healing, radiant pressure, and aura options.",
        abilities=(10, 10, 12, 13, 16, 13),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 4, 2: 3, 3: 2},
        skills={"medicine": True, "persuasion": True, "religion": True},
    )
    for spell_type in (
        SacredFlame,
        CureWounds,
        GuidingBolt,
        Sanctuary,
        LesserRestoration,
        SpiritGuardians,
    ):
        register_spell(entity, spell_type, caster_level=5)
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.chain_shirt",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.mace",
            entity.uuid,
        ),
    )
    register_divine_eminence(entity)
    return entity


def _configure_cult_fanatic(context: CreatureBuildContext) -> Entity:
    """Create an SRD Cult Fanatic."""
    entity = _create_srd_entity(
        context=context,
        description="A low-mid control caster with dagger fallback.",
        abilities=(11, 14, 12, 10, 13, 14),
        hit_die_value=8,
        hit_die_count=6,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 4, 2: 3},
        skills={"deception": True, "persuasion": True, "religion": True},
    )
    for spell_type in (
        SacredFlame,
        Command,
        InflictWounds,
        ShieldOfFaith,
        HoldPerson,
    ):
        register_spell(entity, spell_type, caster_level=4)
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.leather",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.dagger",
            entity.uuid,
        ),
    )
    register_dark_devotion(entity)
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.cult_fanatic",
    )
    return entity


def _configure_knight(context: CreatureBuildContext) -> Entity:
    """Create an SRD Knight."""
    entity = _create_srd_entity(
        context=context,
        description="A plate-armored heavy melee combatant.",
        abilities=(16, 11, 14, 11, 11, 15),
        hit_die_value=8,
        hit_die_count=8,
        proficiency_bonus=2,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.plate",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.greatsword",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.heavy_crossbow",
            entity.uuid,
        ),
    )
    register_brave(entity)
    register_leadership(entity)
    register_parry(entity)
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.knight",
    )
    return entity


def _configure_veteran(context: CreatureBuildContext) -> Entity:
    """Create an SRD Veteran."""
    entity = _create_srd_entity(
        context=context,
        description="A disciplined martial enemy with melee and heavy-crossbow modes.",
        abilities=(16, 13, 14, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=2,
        skills={"athletics": True, "perception": True},
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.splint",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.longsword",
            entity.uuid,
        ),
        offhand=_default_possession(
            context,
            "weapon.shortsword",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.heavy_crossbow",
            entity.uuid,
        ),
    )
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.veteran.melee",
    )
    _register_configured_multiattack(
        entity,
        "action.monster.multiattack.veteran.ranged",
    )
    return entity


def _configure_mage(context: CreatureBuildContext) -> Entity:
    """Create an SRD Mage."""
    entity = _create_srd_entity(
        context=context,
        description="A high-slot arcane caster for resource and counterspell pressure.",
        abilities=(9, 14, 11, 17, 12, 11),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=3,
        spellcasting_ability="intelligence",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
        skills={"arcana": True, "history": True},
    )
    for spell_type in (
        FireBolt,
        MagicMissile,
        MageArmor,
        MistyStep,
        Fireball,
        GreaterInvisibility,
        IceStorm,
        ConeOfCold,
    ):
        register_spell(entity, spell_type, caster_level=9)
    register_shield_reaction(entity)
    register_counterspell_reaction(entity)
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.dagger",
            entity.uuid,
        ),
    )
    return entity


def _configure_orc(context: CreatureBuildContext) -> Entity:
    """Create an SRD Orc."""
    entity = _create_srd_entity(
        context=context,
        description="A strong darkvision charger with axe and javelin pressure.",
        abilities=(16, 12, 16, 7, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"intimidation": True},
        darkvision=True,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.greataxe",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.thrown_javelin",
            entity.uuid,
        ),
    )
    register_aggressive(entity)
    return entity


def _configure_hobgoblin(context: CreatureBuildContext) -> Entity:
    """Create an SRD Hobgoblin."""
    entity = _create_srd_entity(
        context=context,
        description="A heavily armored goblinoid soldier with sword and bow.",
        abilities=(13, 12, 12, 10, 10, 9),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        darkvision=True,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.chain_mail",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.longsword",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.longbow",
            entity.uuid,
        ),
        shield=(
            context.possession_mode
            == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )
    register_martial_advantage(entity)
    return entity


def _configure_bugbear(context: CreatureBuildContext) -> Entity:
    """Create an SRD Bugbear."""
    entity = _create_srd_entity(
        context=context,
        description="A stealthy goblinoid bruiser.",
        abilities=(15, 14, 13, 8, 11, 9),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        skills={"stealth": True, "survival": True},
        darkvision=True,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.creature.bugbear_morningstar",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.thrown_javelin",
            entity.uuid,
        ),
        shield=(
            context.possession_mode
            == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )
    register_brute(entity)
    register_surprise_attack(entity)
    return entity


def _configure_gnoll(context: CreatureBuildContext) -> Entity:
    """Create an SRD Gnoll."""
    entity = _create_srd_entity(
        context=context,
        description="A shielded savage with spear and longbow choices.",
        abilities=(14, 12, 11, 6, 10, 7),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        darkvision=True,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.spear",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.longbow",
            entity.uuid,
        ),
        shield=(
            context.possession_mode
            == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        ),
    )
    register_natural_bite(entity)
    register_rampage(entity)
    return entity


def _configure_ogre(context: CreatureBuildContext) -> Entity:
    """Create an SRD Ogre."""
    entity = _create_srd_entity(
        context=context,
        description="A large giant with high HP and heavy bludgeoning pressure.",
        abilities=(19, 8, 16, 5, 7, 7),
        hit_die_value=10,
        hit_die_count=7,
        proficiency_bonus=2,
        creature_type=CreatureType.GIANT,
        size=Size.LARGE,
        weight=600,
        movement=40,
        darkvision=True,
    )
    _equip(
        entity,
        armor=_default_possession(
            context,
            "armor.hide",
            entity.uuid,
        ),
        melee=_default_possession(
            context,
            "weapon.creature.ogre_greatclub",
            entity.uuid,
        ),
        ranged=_default_possession(
            context,
            "weapon.creature.ogre_thrown_javelin",
            entity.uuid,
        ),
    )
    return entity


def _configure_wolf(context: CreatureBuildContext) -> Entity:
    """Create an SRD Wolf."""
    entity = _create_srd_entity(
        context=context,
        description="A fast beast with natural bite pressure.",
        abilities=(12, 15, 12, 3, 12, 6),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        creature_type=CreatureType.BEAST,
        movement=40,
        skills={"perception": True, "stealth": True},
    )
    register_keen_hearing_and_smell(entity)
    register_pack_tactics(entity)
    register_wolf_bite_prone_rider(entity)
    return entity


def _configure_dire_wolf(context: CreatureBuildContext) -> Entity:
    """Create an SRD Dire Wolf."""
    entity = _create_srd_entity(
        context=context,
        description="A large fast beast for melee-pack and pursuit tests.",
        abilities=(17, 15, 15, 3, 12, 7),
        hit_die_value=10,
        hit_die_count=5,
        proficiency_bonus=2,
        creature_type=CreatureType.BEAST,
        size=Size.LARGE,
        movement=50,
        weight=250,
        skills={"perception": True, "stealth": True},
    )
    register_keen_hearing_and_smell(entity)
    register_pack_tactics(entity)
    register_dire_wolf_bite_prone_rider(entity)
    return entity


def _configure_zombie(context: CreatureBuildContext) -> Entity:
    """Create an SRD Zombie."""
    entity = _create_srd_entity(
        context=context,
        description="A slow undead body that stresses pursuit and poison immunity.",
        abilities=(13, 6, 16, 3, 6, 5),
        hit_die_value=8,
        hit_die_count=3,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        movement=20,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Poisoned", immunity_name="Zombie")
    register_undead_fortitude(entity)
    return entity


def _configure_ogre_zombie(context: CreatureBuildContext) -> Entity:
    """Create an SRD Ogre Zombie."""
    entity = _create_srd_entity(
        context=context,
        description="A large undead bruiser with huge HP and slow cognition.",
        abilities=(19, 6, 18, 3, 6, 5),
        hit_die_value=10,
        hit_die_count=9,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        size=Size.LARGE,
        weight=650,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Poisoned", immunity_name="Ogre Zombie")
    _equip(
        entity,
        melee=_default_possession(
            context,
            "weapon.creature.ogre_zombie_morningstar",
            entity.uuid,
        ),
    )
    register_undead_fortitude(entity)
    return entity


def _configure_ghoul(context: CreatureBuildContext) -> Entity:
    """Create an SRD Ghoul."""
    entity = _create_srd_entity(
        context=context,
        description="A fast undead attacker with bite and claw modes.",
        abilities=(13, 15, 10, 7, 10, 6),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Charmed", immunity_name="Ghoul")
    entity.add_condition_immunity("Exhaustion", immunity_name="Ghoul")
    entity.add_condition_immunity("Poisoned", immunity_name="Ghoul")
    register_ghoul_claws_paralysis(entity)
    return entity


_SRD_CREATURE_FACTS: tuple[_SrdCreatureFacts, ...] = (
    _SrdCreatureFacts(creature_id="commoner", display_name="Commoner", description="A noncombatant pressed into danger.", challenge_rating="0", source_anchor="SRD 5.1 (CC-BY-4.0), p. 398, Appendix MM-B: Commoner", role_tags=("civilian", "melee"), sort_order=10),
    _SrdCreatureFacts(creature_id="bandit", display_name="Bandit", description="A lightly armored raider with melee and crossbow pressure.", challenge_rating="1/8", source_anchor="SRD 5.1 (CC-BY-4.0), p. 396, Appendix MM-B: Bandit", role_tags=("humanoid", "melee", "ranged"), sort_order=20),
    _SrdCreatureFacts(creature_id="cultist", display_name="Cultist", description="A zealot with a scimitar and social skill pressure.", challenge_rating="1/8", source_anchor="SRD 5.1 (CC-BY-4.0), p. 398, Appendix MM-B: Cultist", role_tags=("humanoid", "melee", "social"), represented_traits=("Dark Devotion",), sort_order=30),
    _SrdCreatureFacts(creature_id="guard", display_name="Guard", description="A defensive sentry with shielded spear pressure.", challenge_rating="1/8", source_anchor="SRD 5.1 (CC-BY-4.0), p. 399, Appendix MM-B: Guard", role_tags=("defender", "humanoid", "shield"), sort_order=40),
    _SrdCreatureFacts(creature_id="tribal_warrior", display_name="Tribal Warrior", description="A light skirmisher that pressures pack-melee scenarios.", challenge_rating="1/8", source_anchor="SRD 5.1 (CC-BY-4.0), p. 402, Appendix MM-B: Tribal Warrior", role_tags=("humanoid", "melee", "pack"), represented_traits=("Pack Tactics",), sort_order=50),
    _SrdCreatureFacts(creature_id="kobold", display_name="Kobold", description="A fragile darkvision skirmisher.", challenge_rating="1/8", source_anchor="SRD 5.1 (CC-BY-4.0), p. 324, Monsters A-Z: Kobold", role_tags=("darkvision", "humanoid", "ranged", "small"), represented_traits=("Pack Tactics", "Sunlight Sensitivity"), sort_order=60),
    _SrdCreatureFacts(creature_id="acolyte", display_name="Acolyte", description="A junior divine caster useful for low-CR support tests.", challenge_rating="1/4", source_anchor="SRD 5.1 (CC-BY-4.0), p. 395, Appendix MM-B: Acolyte", role_tags=("caster", "humanoid", "support"), represented_traits=("Spellcasting",), sort_order=70),
    _SrdCreatureFacts(creature_id="scout", display_name="Scout", description="A perception-heavy ranged scout.", challenge_rating="1/2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 401, Appendix MM-B: Scout", role_tags=("humanoid", "perception", "ranged"), represented_traits=("Keen Hearing and Sight", "Multiattack"), sort_order=80),
    _SrdCreatureFacts(creature_id="thug", display_name="Thug", description="A durable low-CR bruiser with crossbow fallback.", challenge_rating="1/2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 402, Appendix MM-B: Thug", role_tags=("bruiser", "humanoid", "ranged"), represented_traits=("Pack Tactics", "Multiattack"), sort_order=90),
    _SrdCreatureFacts(creature_id="spy", display_name="Spy", description="A mobile infiltrator with shortsword and hand-crossbow pressure.", challenge_rating="1", source_anchor="SRD 5.1 (CC-BY-4.0), p. 402, Appendix MM-B: Spy", role_tags=("humanoid", "ranged", "skirmisher"), represented_traits=("Cunning Action", "Sneak Attack", "Multiattack"), sort_order=100),
    _SrdCreatureFacts(creature_id="berserker", display_name="Berserker", description="A high-HP axe charger for melee pressure tests.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 397, Appendix MM-B: Berserker", role_tags=("bruiser", "humanoid", "melee"), represented_traits=("Reckless",), sort_order=110),
    _SrdCreatureFacts(creature_id="bandit_captain", display_name="Bandit Captain", description="A durable duelist leader with melee and thrown-dagger pressure.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 397, Appendix MM-B: Bandit Captain", role_tags=("duelist", "humanoid", "leader"), represented_traits=("Multiattack", "Parry"), sort_order=120),
    _SrdCreatureFacts(creature_id="priest", display_name="Priest", description="A divine support caster with healing, radiant pressure, and aura options.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 401, Appendix MM-B: Priest", role_tags=("caster", "healing", "humanoid", "support"), represented_traits=("Spellcasting", "Divine Eminence"), sort_order=130),
    _SrdCreatureFacts(creature_id="cult_fanatic", display_name="Cult Fanatic", description="A low-mid control caster with dagger fallback.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 398, Appendix MM-B: Cult Fanatic", role_tags=("caster", "control", "humanoid"), represented_traits=("Spellcasting", "Dark Devotion", "Multiattack"), sort_order=140),
    _SrdCreatureFacts(creature_id="knight", display_name="Knight", description="A plate-armored heavy melee combatant.", challenge_rating="3", source_anchor="SRD 5.1 (CC-BY-4.0), p. 400, Appendix MM-B: Knight", role_tags=("elite", "heavy-armor", "humanoid"), represented_traits=("Brave", "Leadership", "Parry", "Multiattack"), sort_order=150),
    _SrdCreatureFacts(creature_id="veteran", display_name="Veteran", description="A disciplined martial enemy with melee and heavy-crossbow modes.", challenge_rating="3", source_anchor="SRD 5.1 (CC-BY-4.0), p. 403, Appendix MM-B: Veteran", role_tags=("elite", "humanoid", "weapon-modes"), represented_traits=("Multiattack",), sort_order=160),
    _SrdCreatureFacts(creature_id="mage", display_name="Mage", description="A high-slot arcane caster for resource and counterspell pressure.", challenge_rating="6", source_anchor="SRD 5.1 (CC-BY-4.0), p. 400, Appendix MM-B: Mage", role_tags=("arcane", "caster", "counterspell", "humanoid"), represented_traits=("Spellcasting", "Shield reaction", "Counterspell reaction"), sort_order=170),
    _SrdCreatureFacts(creature_id="orc", display_name="Orc", description="A strong darkvision charger with axe and javelin pressure.", challenge_rating="1/2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 339, Monsters A-Z: Orc", role_tags=("charger", "darkvision", "humanoid"), represented_traits=("Aggressive",), sort_order=180),
    _SrdCreatureFacts(creature_id="hobgoblin", display_name="Hobgoblin", description="A heavily armored goblinoid soldier with sword and bow.", challenge_rating="1/2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 322, Monsters A-Z: Hobgoblin", role_tags=("darkvision", "humanoid", "ranged", "shield"), represented_traits=("Martial Advantage",), sort_order=190),
    _SrdCreatureFacts(creature_id="bugbear", display_name="Bugbear", description="A stealthy goblinoid bruiser.", challenge_rating="1", source_anchor="SRD 5.1 (CC-BY-4.0), p. 266, Monsters A-Z: Bugbear", role_tags=("bruiser", "darkvision", "humanoid", "stealth"), represented_traits=("Brute", "Surprise Attack"), sort_order=200),
    _SrdCreatureFacts(creature_id="gnoll", display_name="Gnoll", description="A shielded savage with spear and longbow choices.", challenge_rating="1/2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 314, Monsters A-Z: Gnoll", role_tags=("darkvision", "humanoid", "ranged", "shield"), represented_traits=("Bite", "Rampage"), sort_order=210),
    _SrdCreatureFacts(creature_id="ogre", display_name="Ogre", description="A large giant with high HP and heavy bludgeoning pressure.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 336, Monsters A-Z: Ogre", role_tags=("bruiser", "darkvision", "giant", "large"), sort_order=220),
    _SrdCreatureFacts(creature_id="wolf", display_name="Wolf", description="A fast beast with natural bite pressure.", challenge_rating="1/4", source_anchor="SRD 5.1 (CC-BY-4.0), p. 393, Appendix MM-A: Wolf", role_tags=("beast", "fast", "pack"), represented_traits=("Keen Hearing and Smell", "Pack Tactics", "Bite prone rider"), sort_order=230),
    _SrdCreatureFacts(creature_id="dire_wolf", display_name="Dire Wolf", description="A large fast beast for melee-pack and pursuit tests.", challenge_rating="1", source_anchor="SRD 5.1 (CC-BY-4.0), p. 371, Appendix MM-A: Dire Wolf", role_tags=("beast", "fast", "large", "pack"), represented_traits=("Keen Hearing and Smell", "Pack Tactics", "Bite prone rider"), sort_order=240),
    _SrdCreatureFacts(creature_id="zombie", display_name="Zombie", description="A slow undead body that stresses pursuit and poison immunity.", challenge_rating="1/4", source_anchor="SRD 5.1 (CC-BY-4.0), p. 356, Monsters A-Z: Zombie", role_tags=("melee", "slow", "undead"), represented_traits=("Poison immunity", "Undead Fortitude"), sort_order=250),
    _SrdCreatureFacts(creature_id="ogre_zombie", display_name="Ogre Zombie", description="A large undead bruiser with huge HP and slow cognition.", challenge_rating="2", source_anchor="SRD 5.1 (CC-BY-4.0), p. 357, Monsters A-Z: Ogre Zombie", role_tags=("bruiser", "large", "undead"), represented_traits=("Poison immunity", "Undead Fortitude"), sort_order=260),
    _SrdCreatureFacts(creature_id="ghoul", display_name="Ghoul", description="A fast undead attacker with bite and claw modes.", challenge_rating="1", source_anchor="SRD 5.1 (CC-BY-4.0), p. 312, Monsters A-Z: Ghoul", role_tags=("condition-threat", "melee", "undead"), represented_traits=("Poison immunity", "condition immunities", "Claws paralysis rider"), sort_order=270),
)

_CONFIGURE_SRD_CREATURE_BY_ID = MappingProxyType({
    "commoner": _configure_commoner,
    "bandit": _configure_bandit,
    "cultist": _configure_cultist,
    "guard": _configure_guard,
    "tribal_warrior": _configure_tribal_warrior,
    "kobold": _configure_kobold,
    "acolyte": _configure_acolyte,
    "scout": _configure_scout,
    "thug": _configure_thug,
    "spy": _configure_spy,
    "berserker": _configure_berserker,
    "bandit_captain": _configure_bandit_captain,
    "priest": _configure_priest,
    "cult_fanatic": _configure_cult_fanatic,
    "knight": _configure_knight,
    "veteran": _configure_veteran,
    "mage": _configure_mage,
    "orc": _configure_orc,
    "hobgoblin": _configure_hobgoblin,
    "bugbear": _configure_bugbear,
    "gnoll": _configure_gnoll,
    "ogre": _configure_ogre,
    "wolf": _configure_wolf,
    "dire_wolf": _configure_dire_wolf,
    "zombie": _configure_zombie,
    "ogre_zombie": _configure_ogre_zombie,
    "ghoul": _configure_ghoul,
})


def _equipped(
    item_id: str,
    slot: EquipmentSlot,
) -> CreaturePossessionGrant:
    """Author one starter item equipped by an SRD creature root."""
    return CreaturePossessionGrant(
        item_id=item_id,
        disposition=CreaturePossessionDisposition.EQUIPPED,
        equipment_slot=slot,
    )


def _intrinsic(
    item_id: str,
    slot: EquipmentSlot,
) -> CreaturePossessionGrant:
    """Author one body-owned intrinsic equipped in every deployment mode."""
    return CreaturePossessionGrant(
        item_id=item_id,
        disposition=CreaturePossessionDisposition.INTRINSIC,
        equipment_slot=slot,
    )


SRD_CREATURE_POSSESSION_GRANTS_BY_ID = MappingProxyType({
    "commoner": (
        _equipped("weapon.club", WeaponSlot.MELEE_MAIN),
    ),
    "bandit": (
        _equipped("armor.leather", BodyPart.BODY),
        _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.light_crossbow", WeaponSlot.RANGED_MAIN),
    ),
    "cultist": (
        _equipped("armor.leather", BodyPart.BODY),
        _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
    ),
    "guard": (
        _equipped("armor.chain_shirt", BodyPart.BODY),
        _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
        _equipped("shield.shield", WeaponSlot.MELEE_OFF),
    ),
    "tribal_warrior": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
    ),
    "kobold": (
        _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
        _equipped(
            "weapon.creature.kobold_sling",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "acolyte": (
        _equipped("weapon.club", WeaponSlot.MELEE_MAIN),
    ),
    "scout": (
        _equipped("armor.leather", BodyPart.BODY),
        _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
    ),
    "thug": (
        _equipped("armor.leather", BodyPart.BODY),
        _equipped("weapon.mace", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
    ),
    "spy": (
        _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        _equipped(
            "weapon.creature.spy_hand_crossbow",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "berserker": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped("weapon.greataxe", WeaponSlot.MELEE_MAIN),
    ),
    "bandit_captain": (
        _equipped("armor.studded_leather", BodyPart.BODY),
        _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.dagger", WeaponSlot.MELEE_OFF),
        _equipped(
            "weapon.creature.bandit_captain_thrown_dagger",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "priest": (
        _equipped("armor.chain_shirt", BodyPart.BODY),
        _equipped("weapon.mace", WeaponSlot.MELEE_MAIN),
    ),
    "cult_fanatic": (
        _equipped("armor.leather", BodyPart.BODY),
        _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
    ),
    "knight": (
        _equipped("armor.plate", BodyPart.BODY),
        _equipped("weapon.greatsword", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
    ),
    "veteran": (
        _equipped("armor.splint", BodyPart.BODY),
        _equipped("weapon.longsword", WeaponSlot.MELEE_MAIN),
        _equipped("weapon.shortsword", WeaponSlot.MELEE_OFF),
        _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
    ),
    "mage": (
        _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
    ),
    "orc": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped("weapon.greataxe", WeaponSlot.MELEE_MAIN),
        _equipped(
            "weapon.creature.thrown_javelin",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "hobgoblin": (
        _equipped("armor.chain_mail", BodyPart.BODY),
        _equipped("weapon.longsword", WeaponSlot.MELEE_MAIN),
        _equipped("shield.shield", WeaponSlot.MELEE_OFF),
        _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
    ),
    "bugbear": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped(
            "weapon.creature.bugbear_morningstar",
            WeaponSlot.MELEE_MAIN,
        ),
        _equipped("shield.shield", WeaponSlot.MELEE_OFF),
        _equipped(
            "weapon.creature.thrown_javelin",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "gnoll": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
        _equipped("shield.shield", WeaponSlot.MELEE_OFF),
        _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
    ),
    "ogre": (
        _equipped("armor.hide", BodyPart.BODY),
        _equipped(
            "weapon.creature.ogre_greatclub",
            WeaponSlot.MELEE_MAIN,
        ),
        _equipped(
            "weapon.creature.ogre_thrown_javelin",
            WeaponSlot.RANGED_MAIN,
        ),
    ),
    "wolf": (
        _intrinsic(
            "armor.creature.wolf_natural",
            BodyPart.BODY,
        ),
        _intrinsic(
            "weapon.creature.wolf_bite",
            WeaponSlot.MELEE_MAIN,
        ),
    ),
    "dire_wolf": (
        _intrinsic(
            "armor.creature.dire_wolf_natural",
            BodyPart.BODY,
        ),
        _intrinsic(
            "weapon.creature.dire_wolf_bite",
            WeaponSlot.MELEE_MAIN,
        ),
    ),
    "zombie": (
        _intrinsic(
            "weapon.creature.zombie_slam",
            WeaponSlot.MELEE_MAIN,
        ),
    ),
    "ogre_zombie": (
        _equipped(
            "weapon.creature.ogre_zombie_morningstar",
            WeaponSlot.MELEE_MAIN,
        ),
    ),
    "ghoul": (
        _intrinsic(
            "weapon.creature.ghoul_claws",
            WeaponSlot.MELEE_MAIN,
        ),
        _intrinsic(
            "weapon.creature.ghoul_bite",
            WeaponSlot.MELEE_OFF,
        ),
    ),
})


def construct_srd_creature(
    context: CreatureBuildContext,
    creature_id: str,
) -> Entity:
    """Construct one SRD mechanical root under the caller's exact identity.

    NeuroDragon configured-creature definitions reuse this seam to add
    presentation-owned possessions without making the SRD pack depend on the
    downstream NeuroDragon pack. The requested ref therefore belongs to the
    caller while the mechanical structure and possessions stay single-source.
    """
    configure = _CONFIGURE_SRD_CREATURE_BY_ID.get(creature_id)
    if configure is None:
        raise KeyError(f"Unknown SRD creature id {creature_id!r}")
    entity = configure(
        context.model_copy(update={
            "possession_mode": (
                CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
            ),
        }),
    )
    apply_creature_possessions(
        entity,
        SRD_CREATURE_POSSESSION_GRANTS_BY_ID[creature_id],
        possession_mode=context.possession_mode,
    )
    return entity

_ROOT_OWNED_ACTION_TYPES_BY_CREATURE_ID = MappingProxyType({
    "bandit_captain": (MultiattackAction,),
    "berserker": (RecklessAttack,),
    "cult_fanatic": (MultiattackAction,),
    "gnoll": (NaturalAttack,),
    "knight": (LeadershipAction, MultiattackAction),
    "orc": (AggressiveMoveAction,),
    "priest": (DivineEminenceAction,),
    "scout": (MultiattackAction,),
    "spy": (MultiattackAction,),
    "thug": (MultiattackAction,),
    "veteran": (MultiattackAction,),
})
_MULTIATTACK_CONFIGURATION_IDS_BY_CREATURE_ID = MappingProxyType({
    "bandit_captain": (
        "action.monster.multiattack.bandit_captain.melee",
        "action.monster.multiattack.bandit_captain.ranged",
    ),
    "cult_fanatic": ("action.monster.multiattack.cult_fanatic",),
    "knight": ("action.monster.multiattack.knight",),
    "scout": (
        "action.monster.multiattack.scout.shortsword",
        "action.monster.multiattack.scout.longbow",
    ),
    "spy": ("action.monster.multiattack.spy",),
    "thug": ("action.monster.multiattack.thug",),
    "veteran": (
        "action.monster.multiattack.veteran.melee",
        "action.monster.multiattack.veteran.ranged",
    ),
})


def _root_owned_action_dependencies(
    creature_id: str,
) -> tuple[ContentDependency, ...]:
    """Declare non-universal actions installed by one SRD stat block."""
    behavior_dependencies = tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                action_type
            ].ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Installed by this exact SRD creature composition.",
        )
        for action_type in _ROOT_OWNED_ACTION_TYPES_BY_CREATURE_ID.get(
            creature_id,
            (),
        )
    )
    configuration_dependencies = tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=SRD_MULTIATTACK_CONFIGURATIONS_BY_CONTENT_ID[
                content_id
            ].ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=(
                "Exact authored Multiattack configuration installed by this "
                "SRD creature composition."
            ),
        )
        for content_id in _MULTIATTACK_CONFIGURATION_IDS_BY_CREATURE_ID.get(
            creature_id,
            (),
        )
    )
    return behavior_dependencies + configuration_dependencies


def _declare_srd_creature(
    facts: _SrdCreatureFacts,
    configure: Callable[[CreatureBuildContext], Entity],
) -> ContentDeclaration:
    descriptor = ContentDescriptorSpec(
        display_name=facts.display_name,
        description=facts.description,
        tags=tuple(sorted({
            "creature",
            "srd",
            f"cr_{facts.challenge_rating.replace('/', '_')}",
            *facts.role_tags,
            *(f"trait:{trait.casefold().replace(' ', '_')}" for trait in facts.represented_traits),
        })),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=f"creature.{facts.creature_id}",
            portrait_key=f"creature.{facts.creature_id}",
            visual_variant_key=facts.creature_id,
            ui_group="creatures.srd",
        ),
        ordering=ContentOrdering(
            sort_group="creatures.srd",
            sort_order=facts.sort_order,
        ),
    )
    provenance = ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=facts.source_anchor,
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Playable current-engine representation. Descriptor trait tags "
            "identify the implemented package without claiming full stat-block parity."
        ),
    )

    def factory(
        raw_context: object,
        parameters: SrdCreatureParameters,
    ) -> Entity:
        _ = parameters
        context = CreatureBuildContext.model_validate(raw_context)
        return construct_srd_creature(context, facts.creature_id)

    factory.__name__ = f"_build_{facts.creature_id}"
    factory.__qualname__ = factory.__name__
    declared_factory = creature_factory(
        pack_id="content.srd_5_1_cc",
        content_id=f"creature.{facts.creature_id}",
        version=1,
        parameters=SrdCreatureParameters,
        descriptor=descriptor,
        provenance=provenance,
        dependencies=(
            *_root_owned_action_dependencies(facts.creature_id),
        ),
    )(factory)
    return get_content_declaration(declared_factory)


def _build_srd_creature_declarations() -> tuple[ContentDeclaration, ...]:
    ids = tuple(facts.creature_id for facts in _SRD_CREATURE_FACTS)
    displays = tuple(facts.display_name for facts in _SRD_CREATURE_FACTS)
    orders = tuple(facts.sort_order for facts in _SRD_CREATURE_FACTS)
    if (
        len(ids) != 27
        or len(ids) != len(set(ids))
        or len(displays) != len(set(displays))
        or len(orders) != len(set(orders))
        or set(ids) != set(_CONFIGURE_SRD_CREATURE_BY_ID)
    ):
        raise RuntimeError(
            "SRD creature declarations require 27 unique identities, display "
            "names, order values, and matching private configuration helpers",
        )
    return tuple(
        _declare_srd_creature(
            facts,
            _CONFIGURE_SRD_CREATURE_BY_ID[facts.creature_id],
        )
        for facts in _SRD_CREATURE_FACTS
    )


SRD_CREATURE_DECLARATIONS = _build_srd_creature_declarations()
SRD_CREATURE_DECLARATIONS_BY_ID = MappingProxyType({
    declaration.ref.content_id.removeprefix("creature."): declaration
    for declaration in SRD_CREATURE_DECLARATIONS
})
SRD_CREATURE_RECIPES_BY_ID = MappingProxyType({
    creature_id: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for creature_id, declaration in SRD_CREATURE_DECLARATIONS_BY_ID.items()
})


def _create_srd_entity(
    *,
    context: CreatureBuildContext,
    description: str,
    abilities: tuple[int, int, int, int, int, int],
    hit_die_value: HitDieValue,
    hit_die_count: int,
    proficiency_bonus: int,
    skills: Optional[dict[str, bool]] = None,
    spellcasting_ability: Optional[AbilityName] = None,
    spell_slots: Optional[dict[int, int]] = None,
    creature_type: CreatureType = CreatureType.HUMANOID,
    size: Size = Size.MEDIUM,
    weight: int = 150,
    movement: int = 30,
    darkvision: bool = False,
    immunities: tuple[DamageType, ...] = (),
) -> Entity:
    """Create a configured entity using shared SRD roster defaults."""
    entity_uuid = context.runtime_entity_uuid
    strength, dexterity, constitution, intelligence, wisdom, charisma = abilities
    skill_config = {
        skill_name: SkillConfig(proficiency=True)
        for skill_name, enabled in (skills or {}).items()
        if enabled
    }
    entity = Entity.create(
        name=context.display_name,
        source_entity_uuid=entity_uuid,
        description=description,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=constitution),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=wisdom),
                charisma=AbilityConfig(ability_score=charisma),
            ),
            skill_set=SkillSetConfig(**skill_config),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=hit_die_value,
                        hit_dice_count=hit_die_count,
                        mode="average",
                        ignore_first_level=False,
                    )
                ],
                immunities=list(immunities),
            ),
            action_economy=ActionEconomyConfig(
                movement=movement,
                spell_slots=spell_slots or {},
            ),
            spellcasting=SpellcastingConfig(spellcasting_ability=spellcasting_ability) if spellcasting_ability else None,
            proficiency_bonus=proficiency_bonus,
            position=context.position,
            faction=context.faction,
            weight=weight,
            creature_type=creature_type,
            size=size,
            appearance=_default_srd_appearance(creature_type, size),
        ),
        content_ref=context.requested_ref,
    )
    setup_standard_actions(entity)
    if darkvision:
        entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
    return entity


def _default_possession(
    context: CreatureBuildContext,
    item_id: str,
    source_entity_uuid: UUID,
) -> BaseItem | None:
    """Materialize an authored loadout item only when deployment permits it."""
    if (
        context.possession_mode
        == CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ):
        return None
    return build_authored_item(item_id, source_entity_uuid)


def _equip(
    entity: Entity,
    *,
    armor: BaseItem | None = None,
    melee: BaseItem | None = None,
    offhand: BaseItem | None = None,
    ranged: BaseItem | None = None,
    shield: bool = False,
) -> None:
    """Equip common SRD loadout pieces on an entity."""
    placements: list[tuple[BaseItem, EquipmentSlot | None]] = []
    if armor is not None:
        placements.append((armor, BodyPart.BODY))
    if melee is not None:
        placements.append((melee, WeaponSlot.MELEE_MAIN))
    if offhand is not None:
        placements.append((offhand, WeaponSlot.MELEE_OFF))
    if shield:
        placements.append(
            (build_authored_item("shield.shield", entity.uuid), WeaponSlot.MELEE_OFF)
        )
    if ranged is not None:
        placements.append((ranged, WeaponSlot.RANGED_MAIN))
    if placements:
        entity.install_initial_items(tuple(placements))
        update_weapon_templates(entity)


def _default_srd_appearance(creature_type: CreatureType, size: Size) -> AppearanceConfig:
    """Return the temporary presentation contract for an SRD creature.

    Humanoids use NeuroClient's layered paper doll so their equipped gear drives
    their appearance. Other creature families retain normal animation behavior
    through a conspicuous placeholder until full-entity manifests are assigned.

    Args:
        creature_type: Rules-level creature classification.
        size: Rules-level creature size.

    Returns:
        Presentation metadata independent from the creature's grid footprint.
    """
    visual_scale = _VISUAL_SCALE_BY_SIZE[size]
    if creature_type == CreatureType.HUMANOID:
        return AppearanceConfig(visual_scale=visual_scale)
    return AppearanceConfig(
        presentation_kind="placeholder",
        visual_scale=visual_scale,
        placeholder_tint=0x36FF62,
    )
