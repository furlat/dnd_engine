"""Coverage ledger for displaced stealth and lighting integration scripts.

The archived scripts are historical specifications, not maintained pytest
coverage.  One no longer imports, while several lighting cases accidentally
construct darkvision-capable skeletons and then assert no-darkvision behavior.
This module maps all 58 logical cases to current selectors and restores the
remaining behavior with deterministic state and event-lifecycle assertions.
"""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from unittest.mock import patch
from uuid import UUID, uuid4

from dnd.actions.standard import (
    Attack,
    Disengage,
    Dodge,
    Hide,
    Move,
)
from dnd.actions.operations import execute_use_action
from dnd.blocks.base_item import (
    BaseItem,
    UsableItem,
)
from dnd.blocks.equipment import (
    BodyArmor,
    Weapon,
)
from dnd.conditions import (
    GreaterInvisibilityEffect,
    Hidden,
    Incapacitated,
    Invisible,
    InvisibilityEffect,
)
from dnd.core.base_block import BaseBlock
from dnd.types.world import LightLevel
from dnd.types.senses import SenseMode, SensesType
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.types.equipment import BodyPart, WeaponSlot
from dnd.core.events.resolution_events import (
    DamageRollResultEvent,
)
from dnd.core.events.events_registry import (
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.check_events import (
    SkillCheckEvent,
)
from dnd.core.gridmap import get_map
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus
from dnd.core.values import BaseValue
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from dnd.items.armors import CHAIN_MAIL_RECIPE, LEATHER_ARMOR_RECIPE
from dnd.items.consumables import GREATER_INVISIBILITY_POTION_RECIPE
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.items.weapons import ASSASSIN_DAGGER_RECIPE
from tests.engine.support import create_test_monster
from dnd.spells.evocation import FireBolt
from dnd.spells.illusion import GreaterInvisibility
from tests.engine.support import get_max_hp, reset_combat_state, set_hp


THIS_FILE = "tests/manual/test_135_stealth_lighting_legacy_contract.py"
CONDITIONS_FILE = "tests/engine/test_standard_conditions.py"
SENSES_FILE = "tests/engine/test_senses_light_stealth.py"
PERCEPTION_FILE = "tests/manual/test_12_perception_light_stealth_and_invisibility.py"
ITEMS_FILE = "tests/engine/test_items_inventory_equipment.py"
SPELLS_FILE = "tests/engine/test_manual_17_spell_families.py"
SPELL_FAMILIES_FILE = "tests/engine/test_spell_families.py"


class CoverageStatus(StrEnum):
    """Disposition of one displaced logical case."""

    ACTIVE = "active"
    STRENGTHENED = "strengthened"
    RETIRED = "retired"
    STALE = "stale"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class CoverageRecord:
    """Maintained selector and disposition for one archived logical case."""

    selector: str
    status: CoverageStatus = CoverageStatus.ACTIVE
    reason: str = ""


FOUNDATION_SELECTOR = (
    f"{THIS_FILE}::test_perceivability_boundaries_special_senses_and_objects"
)
ARMOR_SELECTOR = f"{THIS_FILE}::test_armor_stealth_traits_are_item_specific"
ATTACK_REVEAL_SELECTOR = (
    f"{THIS_FILE}::test_real_attack_reveals_hidden_and_spell_invisibility"
)
OTHER_REVEALS_SELECTOR = (
    f"{THIS_FILE}::test_damage_incapacity_and_spell_events_reveal_hidden_state"
)
HIDE_SELECTOR = (
    f"{THIS_FILE}::test_hide_uses_subjective_enemy_visibility_and_emits_stealth_check"
)
HIDE_LIGHT_SELECTOR = (
    f"{THIS_FILE}::test_hide_succeeds_in_darkness_or_without_enemy_observers"
)
NON_REVEAL_SELECTOR = (
    f"{THIS_FILE}::test_non_revealing_actions_and_movement_preserve_hidden"
)
GREATER_SPELL_SELECTOR = (
    f"{THIS_FILE}::test_greater_invisibility_self_cast_owns_lineage_and_concentration"
)
POTION_SELECTOR = (
    f"{THIS_FILE}::test_greater_invisibility_potion_stack_consumes_one_legal_use_at_a_time"
)
DAGGER_SELECTOR = (
    f"{THIS_FILE}::test_assassin_dagger_mutates_only_unseen_damage_and_cleans_handler"
)
MAGICAL_DARKNESS_SELECTOR = (
    f"{THIS_FILE}::test_magical_darkness_controls_attack_discovery_by_sense_mode"
)
TORCH_ZONES_SELECTOR = (
    f"{THIS_FILE}::test_torch_zones_preserve_bright_hidden_and_reveal_very_bright_hidden"
)
LIGHT_ADD_LOG_SELECTOR = (
    f"{THIS_FILE}::test_light_add_spots_only_the_hidden_enemy"
)
LIGHT_MOVE_LOG_SELECTOR = (
    f"{THIS_FILE}::test_anchored_torch_movement_spots_hidden_enemy_reactively"
)
LIGHT_TOGGLE_LOG_SELECTOR = (
    f"{THIS_FILE}::test_light_toggle_spots_hidden_enemy_reactively"
)

REACTIVE_PERCEIVABILITY_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_006_perceivability_events_refilter_visible_entities"
)
PLAIN_VS_SPELL_INVISIBILITY_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_014_plain_invisible_and_spell_invisibility_have_different_reveal_contracts"
)
HIDDEN_ACTION_FILTER_SELECTOR = (
    f"{CONDITIONS_FILE}::test_eb_08_011_hidden_and_invisibility_reveal_handlers_filter_actions"
)
GREATER_EFFECT_SELECTOR = (
    f"{CONDITIONS_FILE}::test_eb_08_013_greater_invisibility_uses_stealth_checks_instead_of_reveal"
)
PERCEPTION_DELTA_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_012_passive_perception_changes_emit_replacement_payloads"
)
LIGHT_REACTIVE_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_004_light_change_reveals_subscribed_dark_cells_reactively"
)
DARKNESS_REACTIVE_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_011_magical_darkness_zone_removal_recomputes_behind_cells"
)
VERY_BRIGHT_SELECTOR = (
    f"{SENSES_FILE}::test_eb_12_010_very_bright_light_reveals_hidden_entities"
)
LIGHT_MODES_SELECTOR = (
    f"{PERCEPTION_FILE}::test_special_senses_change_subjective_light"
)
TORCH_MOVEMENT_SELECTOR = (
    f"{PERCEPTION_FILE}::test_movement_end_preserves_contacts_revealed_by_carried_light"
)
ARMOR_HOOK_SELECTOR = (
    f"{ITEMS_FILE}::test_eb_13_006_equipment_hooks_apply_and_remove_modifiers"
)
INVISIBILITY_SPELL_SELECTOR = (
    f"{SPELLS_FILE}::test_visibility_family_invisibility_links_target_effect_to_concentration"
)
INVISIBILITY_SELF_SELECTOR = (
    f"{SPELL_FAMILIES_FILE}::test_eb_15_008_illusion_and_necromancy_self_effects"
)


STEALTH_CASES: dict[str, CoverageRecord] = {
    "test_baseblock_perceivability_defaults": CoverageRecord(
        FOUNDATION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement asserts both raw defaults and observer-relative boundaries.",
    ),
    "test_invisible_flag": CoverageRecord(
        FOUNDATION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "All three archived special-sense bypass modes are deterministic.",
    ),
    "test_stealth_dc_flag": CoverageRecord(
        FOUNDATION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement locks the equal-passive-perception boundary.",
    ),
    "test_senses_filtering_hidden": CoverageRecord(REACTIVE_PERCEIVABILITY_SELECTOR),
    "test_invisible_condition_senses": CoverageRecord(
        PLAIN_VS_SPELL_INVISIBILITY_SELECTOR
    ),
    "test_hidden_condition": CoverageRecord(
        ATTACK_REVEAL_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A real typed Attack lifecycle replaces name/index search with skip paths.",
    ),
    "test_hidden_removal_on_damage": CoverageRecord(
        OTHER_REVEALS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A positive DamageApplied lifecycle and resulting state are asserted.",
    ),
    "test_hidden_removal_on_incapacitated": CoverageRecord(
        OTHER_REVEALS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The full-turn agency-denial condition lifecycle is asserted.",
    ),
    "test_hide_action": CoverageRecord(
        HIDE_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The exact Stealth-check child event and action cost are asserted.",
    ),
    "test_armor_stealth_disadvantage": CoverageRecord(ARMOR_HOOK_SELECTOR),
    "test_armor_no_stealth_disadvantage": CoverageRecord(
        ARMOR_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "Leather and chain mail are compared through the same equipment slot.",
    ),
    "test_object_perceivability": CoverageRecord(
        FOUNDATION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The floor-object senses index now has reactive removal and restoration assertions.",
    ),
    "test_hidden_removal_on_spell_cast": CoverageRecord(
        OTHER_REVEALS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A real Fire Bolt CastSpell lifecycle replaces action-name lookup.",
    ),
    "test_hidden_removal_on_shove": CoverageRecord(HIDDEN_ACTION_FILTER_SELECTOR),
    "test_dash_does_not_remove_hidden": CoverageRecord(HIDDEN_ACTION_FILTER_SELECTOR),
    "test_hide_fails_when_visible_to_enemy": CoverageRecord(
        HIDE_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "Cancellation, zero skill-check children, and unspent action are asserted.",
    ),
    "test_hide_succeeds_when_invisible": CoverageRecord(
        HIDE_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The invisible actor is removed from enemy knowledge before Hide resolves.",
    ),
    "test_invisibility_spell_basic": CoverageRecord(INVISIBILITY_SPELL_SELECTOR),
    "test_invisibility_ends_on_attack": CoverageRecord(
        ATTACK_REVEAL_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A deterministic real Attack lifecycle replaces a random retry loop.",
    ),
    "test_invisibility_ends_on_spell_cast": CoverageRecord(
        OTHER_REVEALS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A deterministic real Fire Bolt lifecycle proves the reveal.",
    ),
    "test_invisibility_concentration_break": CoverageRecord(
        INVISIBILITY_SPELL_SELECTOR
    ),
    "test_greater_invisibility_basic": CoverageRecord(
        GREATER_SPELL_SELECTOR,
        CoverageStatus.STALE,
        "The archived default level-5 caster has no fourth-level spell slot.",
    ),
    "test_greater_invisibility_stealth_check_on_attack": CoverageRecord(
        GREATER_EFFECT_SELECTOR
    ),
    "test_greater_invisibility_escalating_dc": CoverageRecord(
        GREATER_EFFECT_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The maintained test executes successful and failed checks instead of assigning check_count.",
    ),
    "test_greater_invisibility_concentration_break": CoverageRecord(
        GREATER_SPELL_SELECTOR,
        CoverageStatus.STALE,
        "The archived default level-5 caster has no fourth-level spell slot.",
    ),
    "test_greater_invisibility_potion_consumption": CoverageRecord(
        POTION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The item-charge completion event and registry removal are asserted.",
    ),
    "test_greater_invisibility_potion_stacking": CoverageRecord(
        POTION_SELECTOR,
        CoverageStatus.STALE,
        "The archived case attempts a second bonus-action drink without resetting turn economy.",
    ),
    "test_invisibility_spell_self_cast_not_self_trigger": CoverageRecord(
        INVISIBILITY_SELF_SELECTOR
    ),
    "test_greater_invisibility_spell_self_cast_not_self_trigger": CoverageRecord(
        GREATER_SPELL_SELECTOR,
        CoverageStatus.STALE,
        "The archived default level-5 caster cannot legally cast the level-4 spell.",
    ),
    "test_greater_invisibility_potion_not_self_trigger": CoverageRecord(
        POTION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement asserts check_count zero after each real item action.",
    ),
    "test_assassin_dagger_unseen_strike": CoverageRecord(
        DAGGER_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "Fixed dice and typed damage-result evidence replace up to five random retries.",
    ),
    "test_assassin_dagger_no_bonus_when_seen": CoverageRecord(
        DAGGER_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The exact final-roll tuple proves that no bonus die was appended.",
    ),
    "test_assassin_dagger_equip_unequip": CoverageRecord(
        DAGGER_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement checks both entity and global handler registries.",
    ),
}


LIGHTING_CASES: dict[str, CoverageRecord] = {
    "test_hidden_reactively_removes_from_senses": CoverageRecord(
        REACTIVE_PERCEIVABILITY_SELECTOR
    ),
    "test_invisible_reactively_removes_from_senses": CoverageRecord(
        PLAIN_VS_SPELL_INVISIBILITY_SELECTOR
    ),
    "test_hidden_reactive_with_different_perception_observers": CoverageRecord(
        PERCEPTION_DELTA_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The archived fixtures had equal perception; the replacement changes perception and asserts the payload.",
    ),
    "test_darkness_obscurement_hides_entity_reactively": CoverageRecord(
        DARKNESS_REACTIVE_SELECTOR,
        CoverageStatus.STALE,
        "The archived observer has default darkvision while asserting no-darkvision behavior.",
    ),
    "test_light_source_reveals_entity_in_dark": CoverageRecord(
        LIGHT_REACTIVE_SELECTOR
    ),
    "test_gridmap_light_source_add_updates_senses": CoverageRecord(
        LIGHT_REACTIVE_SELECTOR,
        CoverageStatus.STALE,
        "The archived observer has default darkvision and is already able to see the target.",
    ),
    "test_hidden_in_darkness_darkvision_observer": CoverageRecord(
        LIGHT_MODES_SELECTOR
    ),
    "test_hidden_in_darkness_then_torch_lit": CoverageRecord(
        VERY_BRIGHT_SELECTOR
    ),
    "test_hidden_in_dim_light_then_fog_darkens": CoverageRecord(
        DARKNESS_REACTIVE_SELECTOR
    ),
    "test_invisible_entity_in_darkness_truesight_observer": CoverageRecord(
        LIGHT_MODES_SELECTOR
    ),
    "test_hide_in_darkness_succeeds": CoverageRecord(
        HIDE_LIGHT_SELECTOR,
        CoverageStatus.STALE,
        "The archived enemy has default darkvision while the test says it has none.",
    ),
    "test_hide_in_bright_light_no_enemies_succeeds": CoverageRecord(
        HIDE_LIGHT_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement asserts completion, cost, and Hidden state.",
    ),
    "test_non_revealing_actions_comprehensive": CoverageRecord(
        NON_REVEAL_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "Real Dodge and Disengage completion events replace discovery-index booleans.",
    ),
    "test_movement_while_hidden_persists": CoverageRecord(
        NON_REVEAL_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement locks the exact destination and Movement completion.",
    ),
    "test_torch_bearer_sees_enemies_in_dark_cave": CoverageRecord(
        LIGHT_ADD_LOG_SELECTOR,
        CoverageStatus.STALE,
        "The archived carrier has default darkvision and sees the enemy before the torch.",
    ),
    "test_torch_bearer_movement_updates_visibility": CoverageRecord(
        TORCH_MOVEMENT_SELECTOR,
        CoverageStatus.STALE,
        "The archived carrier has default darkvision and sees the far enemy initially.",
    ),
    "test_magical_darkness_blocks_targeting": CoverageRecord(
        MAGICAL_DARKNESS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement asserts both subjective knowledge and typed action discovery.",
    ),
    "test_devils_sight_sees_through_magical_darkness": CoverageRecord(
        MAGICAL_DARKNESS_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The same actor is re-evaluated after receiving Devil's Sight.",
    ),
    "test_torch_three_light_zones": CoverageRecord(
        TORCH_ZONES_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement also couples each zone to Hidden lifecycle behavior.",
    ),
    "test_torch_very_bright_reveals_hidden_enemy": CoverageRecord(
        TORCH_ZONES_SELECTOR
    ),
    "test_torch_bright_zone_does_not_reveal_hidden": CoverageRecord(
        TORCH_ZONES_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "Bright and very-bright Hidden state are asserted in one light source.",
    ),
    "test_light_source_reveals_hidden_generates_spotted_log": CoverageRecord(
        LIGHT_ADD_LOG_SELECTOR,
        CoverageStatus.STALE,
        "Default darkvision makes the hidden enemy visible before illumination.",
    ),
    "test_torch_movement_reveals_hidden_generates_spotted_log": CoverageRecord(
        LIGHT_MOVE_LOG_SELECTOR,
        CoverageStatus.STALE,
        "Default darkvision makes the hidden enemy visible before torch movement.",
    ),
    "test_light_toggle_reveals_hidden_generates_spotted_log": CoverageRecord(
        LIGHT_TOGGLE_LOG_SELECTOR,
        CoverageStatus.STALE,
        "Default darkvision defeats the transition and the archived initial assertion is tautological.",
    ),
    "test_no_spotted_log_for_non_hidden_entity": CoverageRecord(
        LIGHT_ADD_LOG_SELECTOR,
        CoverageStatus.STALE,
        "Default darkvision makes the ordinary target visible before illumination.",
    ),
}


def reset_stealth_world(
    *,
    width: int = 12,
    height: int = 3,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Reset global engine state and build one deterministic rectangular map."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    Encounter.clear_registry()
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    for tile in grid._tiles.values():
        tile.default_light = default_light


def captured_combat_logs() -> list[CombatLogEntry]:
    """Install a standalone-log callback and return its mutable capture list."""
    captured: list[CombatLogEntry] = []

    def capture(event) -> None:
        if event.combat_log is not None:
            captured.append(event.combat_log)

    EventQueue.set_combat_log_callback(capture)
    return captured


def target_is_discoverable(actor: Entity, target_uuid: UUID) -> bool:
    """Return whether any discovered entity action exposes one target UUID."""
    actions = actor.get_available_actions(target_filter="enemies")
    return any(
        target.target_uuid == target_uuid
        for action in actions.entity_actions
        for target in action.valid_targets
    )


def latest_damage_roll_result() -> DamageRollResultEvent:
    """Return the latest completed typed damage-roll result."""
    events = [
        event
        for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        if isinstance(event, DamageRollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ]
    assert events
    return events[-1]


def add_hidden(entity: Entity, stealth_result: int = 30) -> Hidden:
    """Apply and return a Hidden condition owned by one entity."""
    hidden = Hidden(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        stealth_result=stealth_result,
    )
    result = entity.add_condition(hidden)
    assert result is not None and result.phase == EventPhase.COMPLETION
    assert entity.active_conditions["Hidden"] is hidden
    return hidden


def spotted_logs(entries: list[CombatLogEntry]) -> list[CombatLogEntry]:
    """Filter captured entries to observer-scoped entity-spotted facts."""
    return [
        entry
        for entry in entries
        if entry.entry_type == CombatLogEntryType.ENTITY_SPOTTED
    ]


def test_legacy_stealth_and_lighting_ledger_is_complete_and_resolved() -> None:
    """Every displaced selector has an explicit, non-unresolved disposition."""
    assert len(STEALTH_CASES) == 33
    assert len(LIGHTING_CASES) == 25
    all_cases = {**STEALTH_CASES, **LIGHTING_CASES}
    assert len(all_cases) == 58
    assert all(record.selector.startswith("tests/") for record in all_cases.values())
    assert all(
        record.reason
        for record in all_cases.values()
        if record.status is not CoverageStatus.ACTIVE
    )
    counts = Counter(record.status for record in all_cases.values())
    assert counts == {
        CoverageStatus.ACTIVE: 17,
        CoverageStatus.STRENGTHENED: 28,
        CoverageStatus.STALE: 13,
    }
    assert counts[CoverageStatus.RETIRED] == 0
    assert counts[CoverageStatus.UNRESOLVED] == 0


def test_perceivability_boundaries_special_senses_and_objects() -> None:
    """Perceivability defaults, ties, bypass senses, and objects stay reactive."""
    reset_stealth_world(width=8)
    observer = create_test_monster("monster.skeleton", 
        name="Observer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    target = create_test_monster("monster.skeleton", 
        name="Target",
        position=(3, 1),
        faction="monsters",
        darkvision=False,
    )
    truesight = create_test_monster("monster.skeleton", 
        name="Truesight",
        position=(5, 1),
        faction="heroes",
        darkvision=False,
    )
    blindsight = create_test_monster("monster.skeleton", 
        name="Blindsight",
        position=(6, 1),
        faction="heroes",
        darkvision=False,
    )
    tremorsense = create_test_monster("monster.skeleton", 
        name="Tremorsense",
        position=(7, 1),
        faction="heroes",
        darkvision=False,
    )
    truesight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    blindsight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=60)
    ]
    tremorsense.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TREMORSENSE, range_feet=60)
    ]
    item = BaseItem(source_entity_uuid=uuid4(), name="Hidden Cache")
    item.place_on_grid((2, 1))
    Entity.update_all_entities_senses(max_distance=8)

    assert target.stealth_dc is None
    assert target.is_invisible is False
    assert target.is_perceivable_by(None)
    assert target.is_perceivable_by(uuid4())
    assert item.uuid in observer.senses.objects

    passive = observer.get_passive_perception()
    target.set_stealth_dc(passive)
    assert not target.is_perceivable_by(observer.uuid)
    assert target.uuid not in observer.senses.entities
    target.set_stealth_dc(passive - 1)
    assert target.is_perceivable_by(observer.uuid)
    assert target.uuid in observer.senses.entities
    target.set_stealth_dc(None)

    target.set_invisible(True)
    assert not target.is_perceivable_by(observer.uuid)
    assert target.is_perceivable_by(truesight.uuid)
    assert target.is_perceivable_by(blindsight.uuid)
    assert target.is_perceivable_by(tremorsense.uuid)
    target.set_invisible(False)
    assert target.uuid in observer.senses.entities

    item.set_stealth_dc(passive)
    observer.update_entity_senses(max_distance=8)
    assert item.uuid not in observer.senses.objects
    item.set_stealth_dc(None)
    observer.update_entity_senses(max_distance=8)
    assert item.uuid in observer.senses.objects


def test_armor_stealth_traits_are_item_specific() -> None:
    """Leather remains neutral while chain mail owns reversible disadvantage."""
    reset_stealth_world()
    actor = create_test_monster("monster.skeleton", name="Scout", position=(1, 1), darkvision=False)
    leather = materialize_item(
        LEATHER_ARMOR_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    chain_mail = materialize_item(
        CHAIN_MAIL_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    assert actor.loot_item(leather)
    assert actor.loot_item(chain_mail)

    assert actor.equip_item(leather.uuid, BodyPart.BODY)
    assert (
        actor.skill_bonus(None, "stealth").advantage
        == AdvantageStatus.NONE
    )

    assert actor.equip_item(chain_mail.uuid, BodyPart.BODY)
    assert (
        actor.skill_bonus(None, "stealth").advantage
        == AdvantageStatus.DISADVANTAGE
    )

    assert actor.unequip_item(BodyPart.BODY) is chain_mail
    assert (
        actor.skill_bonus(None, "stealth").advantage
        == AdvantageStatus.NONE
    )


def test_real_attack_reveals_hidden_and_spell_invisibility() -> None:
    """One real Attack lifecycle removes both revealable stealth conditions."""
    reset_stealth_world()
    attacker = create_test_monster("monster.skeleton", 
        name="Ambusher",
        position=(1, 1),
        faction="heroes",
        darkvision=False,
    )
    target = create_test_monster("monster.skeleton", 
        name="Target",
        position=(2, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)
    add_hidden(attacker)
    invisibility = InvisibilityEffect(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
    )
    attacker.add_condition(invisibility)

    with fixed_dice_faces(10, 10, 4):
        result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert result is not None and result.phase == EventPhase.COMPLETION
    assert result.event_type == EventType.ATTACK
    assert "Hidden" not in attacker.active_conditions
    assert "Invisible" not in attacker.active_conditions
    assert attacker.stealth_dc is None
    assert attacker.is_invisible is False
    assert sum(
        event.lineage_uuid == result.lineage_uuid
        and event.event_type == EventType.ATTACK
        and event.phase == EventPhase.COMPLETION
        for event in EventQueue._all_events
    ) == 1


def test_damage_incapacity_and_spell_events_reveal_hidden_state() -> None:
    """Damage, full-turn denial, and spell casting use their typed reveal edges."""
    reset_stealth_world()
    source = create_test_monster("monster.skeleton", name="Source", position=(1, 1), faction="heroes")
    hidden_target = create_test_monster("monster.skeleton", 
        name="Hidden Target",
        position=(2, 1),
        faction="monsters",
    )
    add_hidden(hidden_target)
    cursor = EventQueue.event_cursor()

    assert hidden_target.receive_damage(
        1,
        DamageType.SLASHING,
        source.uuid,
    ) == 1

    assert "Hidden" not in hidden_target.active_conditions
    assert hidden_target.stealth_dc is None
    damage_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type == EventType.DAMAGE_APPLIED
    ]
    assert [event.phase for event in damage_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]

    add_hidden(hidden_target)
    incapacity = Incapacitated(
        source_entity_uuid=source.uuid,
        target_entity_uuid=hidden_target.uuid,
    )
    condition_result = hidden_target.add_condition(incapacity)

    assert condition_result is not None
    assert condition_result.phase == EventPhase.COMPLETION
    assert "Hidden" not in hidden_target.active_conditions
    assert "Incapacitated" in hidden_target.active_conditions
    assert hidden_target.stealth_dc is None

    reset_stealth_world()
    caster = create_test_monster("monster.generic_caster", 
        name="Hidden Caster",
        position=(1, 1),
        faction="heroes",
        level=5,
    )
    spell_target = create_test_monster("monster.skeleton", 
        name="Spell Target",
        position=(4, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)
    add_hidden(caster)
    caster.add_condition(
        InvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
    )

    with fixed_dice_faces(10, 10, 4):
        spell_result = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=spell_target.uuid,
        ).apply()

    assert spell_result is not None
    assert spell_result.phase == EventPhase.COMPLETION
    assert spell_result.event_type == EventType.CAST_SPELL
    assert "Hidden" not in caster.active_conditions
    assert "Invisible" not in caster.active_conditions
    assert caster.stealth_dc is None
    assert caster.is_invisible is False


def test_hide_uses_subjective_enemy_visibility_and_emits_stealth_check() -> None:
    """Hide cancels while observed, then succeeds once the actor is unseen."""
    reset_stealth_world(width=8)
    hider = create_test_monster("monster.skeleton", 
        name="Hider",
        position=(3, 1),
        faction="heroes",
        darkvision=False,
    )
    enemy = create_test_monster("monster.skeleton", 
        name="Enemy",
        position=(0, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=8)
    assert hider.uuid in enemy.senses.entities
    skill_checks_before = len(EventQueue.get_events_by_type(EventType.SKILL_CHECK))

    canceled = Hide(source_entity_uuid=hider.uuid).apply()

    assert canceled is not None and canceled.canceled
    assert canceled.phase == EventPhase.CANCEL
    assert "Hidden" not in hider.active_conditions
    assert hider.action_economy.actions.normalized_score == 1
    assert len(EventQueue.get_events_by_type(EventType.SKILL_CHECK)) == skill_checks_before

    hider.set_invisible(True)
    assert hider.uuid not in enemy.senses.entities
    with fixed_dice_faces(12):
        completed = Hide(source_entity_uuid=hider.uuid).apply()

    assert completed is not None and not completed.canceled
    assert completed.phase == EventPhase.COMPLETION
    assert hider.action_economy.actions.normalized_score == 0
    hidden = hider.active_conditions.get("Hidden")
    assert isinstance(hidden, Hidden)
    checks = [
        event
        for event in EventQueue.get_events_by_type(EventType.SKILL_CHECK)
        if isinstance(event, SkillCheckEvent)
        and event.phase == EventPhase.COMPLETION
        and event.source_entity_uuid == hider.uuid
    ]
    assert len(checks) == 1
    assert checks[0].dice_roll.results == [12]
    assert hidden.stealth_result == checks[0].dice_roll.total
    assert hider.stealth_dc == checks[0].dice_roll.total


def test_hide_succeeds_in_darkness_or_without_enemy_observers() -> None:
    """Darkness and absence of enemy observers are both legal Hide contexts."""
    reset_stealth_world(default_light=LightLevel.DARKNESS)
    dark_hider = create_test_monster("monster.skeleton", 
        name="Dark Hider",
        position=(4, 1),
        faction="heroes",
        darkvision=False,
    )
    dark_enemy = create_test_monster("monster.skeleton", 
        name="Dark Enemy",
        position=(0, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)
    assert dark_hider.uuid not in dark_enemy.senses.entities

    with fixed_dice_faces(11):
        dark_result = Hide(source_entity_uuid=dark_hider.uuid).apply()

    assert dark_result is not None and dark_result.phase == EventPhase.COMPLETION
    assert isinstance(dark_hider.active_conditions.get("Hidden"), Hidden)
    assert dark_hider.action_economy.actions.normalized_score == 0

    reset_stealth_world()
    lone_hider = create_test_monster("monster.skeleton", 
        name="Lone Hider",
        position=(4, 1),
        faction="heroes",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)

    with fixed_dice_faces(11):
        bright_result = Hide(source_entity_uuid=lone_hider.uuid).apply()

    assert bright_result is not None
    assert bright_result.phase == EventPhase.COMPLETION
    assert isinstance(lone_hider.active_conditions.get("Hidden"), Hidden)
    assert lone_hider.action_economy.actions.normalized_score == 0


def test_non_revealing_actions_and_movement_preserve_hidden() -> None:
    """Dodge, Disengage, and a completed step leave Hidden intact."""
    reset_stealth_world()
    actor = create_test_monster("monster.skeleton", 
        name="Hidden Mover",
        position=(1, 1),
        faction="heroes",
        darkvision=False,
    )
    actor.update_entity_senses(max_distance=10)
    add_hidden(actor)

    dodge = Dodge(source_entity_uuid=actor.uuid).apply()
    assert dodge is not None and dodge.phase == EventPhase.COMPLETION
    assert "Hidden" in actor.active_conditions

    actor.action_economy.reset_all_costs()
    disengage = Disengage(source_entity_uuid=actor.uuid).apply()
    assert disengage is not None and disengage.phase == EventPhase.COMPLETION
    assert "Hidden" in actor.active_conditions

    actor.action_economy.reset_all_costs()
    movement_cursor = EventQueue.event_cursor()
    movement = Move(
        source_entity_uuid=actor.uuid,
        end_position=(2, 1),
        use_movement_cost=False,
    ).apply()

    assert movement is not None and movement.phase == EventPhase.COMPLETION
    assert actor.position == (2, 1)
    assert "Hidden" in actor.active_conditions
    movement_events = [
        event
        for _, event in EventQueue.iter_events_since(movement_cursor)
        if event.event_type == EventType.MOVEMENT
    ]
    assert movement_events
    assert movement_events[-1].phase == EventPhase.COMPLETION


def test_greater_invisibility_self_cast_owns_lineage_and_concentration() -> None:
    """A legal level-7 self-cast survives its own lineage and follows concentration."""
    reset_stealth_world()
    caster = create_test_monster("monster.generic_caster", 
        name="Illusionist",
        position=(1, 1),
        faction="heroes",
        level=7,
    )
    observer = create_test_monster("monster.skeleton", 
        name="Observer",
        position=(5, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)
    assert caster.action_economy.spell_slot_4.normalized_score == 1

    result = GreaterInvisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=4,
    ).apply()

    assert result is not None and result.phase == EventPhase.COMPLETION
    assert caster.action_economy.spell_slot_4.normalized_score == 0
    condition = caster.active_conditions.get("Invisible")
    assert isinstance(condition, GreaterInvisibilityEffect)
    assert condition.check_count == 0
    assert condition.creation_lineage_uuid == result.lineage_uuid
    assert caster.is_invisible is True
    assert caster.uuid not in observer.senses.entities
    concentration = caster.active_conditions.get("Concentrating")
    assert isinstance(concentration, BaseCondition)
    assert concentration.linked_conditions == [(caster.uuid, condition.uuid)]

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Invisible" not in caster.active_conditions
    assert caster.is_invisible is False
    assert caster.uuid in observer.senses.entities


def test_greater_invisibility_potion_stack_consumes_one_legal_use_at_a_time() -> None:
    """A stacked potion spends one item and one bonus action per legal use."""
    reset_stealth_world()
    actor = create_test_monster("monster.skeleton", name="Drinker", position=(1, 1), darkvision=False)
    first = materialize_item(
        GREATER_INVISIBILITY_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    second = materialize_item(
        GREATER_INVISIBILITY_POTION_RECIPE,
        actor.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert actor.loot_item(first)
    assert actor.loot_item(second)
    assert actor.inventory.item_count == 1
    stacked = next(iter(actor.inventory.items.values()))
    assert isinstance(stacked, UsableItem)
    assert stacked.stack_count == 2
    assert stacked.charges == 1
    assert stacked.max_charges == 1

    first_result = execute_use_action(
        actor,
        stacked.uuid,
        "Drink Greater Invisibility Potion",
    )

    assert first_result is not None
    assert first_result.phase == EventPhase.COMPLETION
    first_condition = actor.active_conditions.get("Invisible")
    assert isinstance(first_condition, GreaterInvisibilityEffect)
    assert first_condition.check_count == 0
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert actor.inventory.item_count == 1
    assert stacked.stack_count == 1
    assert stacked.charges == 1

    actor.remove_condition("Invisible")
    actor.action_economy.reset_all_costs()
    second_result = execute_use_action(
        actor,
        stacked.uuid,
        "Drink Greater Invisibility Potion",
    )

    assert second_result is not None
    assert second_result.phase == EventPhase.COMPLETION
    second_condition = actor.active_conditions.get("Invisible")
    assert isinstance(second_condition, GreaterInvisibilityEffect)
    assert second_condition.check_count == 0
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert actor.inventory.item_count == 0
    assert BaseBlock.get(stacked.uuid) is None
    charge_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(charge_completions) == 2
    assert charge_completions[0].item_destroyed is False
    assert charge_completions[1].item_destroyed is True


def test_assassin_dagger_mutates_only_unseen_damage_and_cleans_handler() -> None:
    """Unseen Strike appends one die only when unseen and leaves no handler."""
    reset_stealth_world()
    attacker = create_test_monster("monster.skeleton", 
        name="Assassin",
        position=(1, 1),
        faction="heroes",
        darkvision=False,
    )
    target = create_test_monster("monster.skeleton", 
        name="Target",
        position=(2, 1),
        faction="monsters",
        darkvision=False,
    )
    dagger = materialize_item(
        ASSASSIN_DAGGER_RECIPE,
        attacker.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert attacker.loot_item(dagger)
    assert attacker.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    handler_uuid = getattr(dagger, "_handler_uuid")
    assert handler_uuid is not None
    assert attacker.get_event_handler_by_name("Unseen Strike") is not None
    assert EventHandler.get(handler_uuid) is not None
    Entity.update_all_entities_senses(max_distance=10)
    assert attacker.uuid in target.senses.entities

    target_hp = get_max_hp(target)
    with fixed_dice_faces(10, 4):
        seen_result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert seen_result is not None and seen_result.phase == EventPhase.COMPLETION
    seen_damage = latest_damage_roll_result()
    assert [
        packet.final_roll.results
        for packet in seen_damage.damage_packets
    ] == [[4]]
    assert seen_damage.roll_modifications == []
    assert target_hp - target.get_hp() == 6

    set_hp(target, target_hp)
    attacker.action_economy.reset_all_costs()
    attacker.set_invisible(True)
    assert attacker.uuid not in target.senses.entities
    with fixed_dice_faces(10, 4, 3):
        unseen_result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert unseen_result is not None and unseen_result.phase == EventPhase.COMPLETION
    unseen_damage = latest_damage_roll_result()
    assert len(unseen_damage.damage_packets) == 2
    assert [
        packet.final_roll.results
        for packet in unseen_damage.damage_packets
    ] == [[4], [3]]
    assert len(unseen_damage.roll_modifications) == 1
    modification = unseen_damage.roll_modifications[0]
    assert modification.handler_name == "Unseen Strike"
    assert modification.packet_index == 1
    assert modification.previous_total is None
    assert modification.final_total == 3
    assert modification.reason == "1d6 piercing (unseen attacker)"
    assert target_hp - target.get_hp() == 9

    assert attacker.unequip_item(WeaponSlot.MELEE_MAIN) is dagger
    assert getattr(dagger, "_handler_uuid") is None
    assert attacker.get_event_handler_by_name("Unseen Strike") is None
    assert handler_uuid not in EventQueue._event_handlers


def test_magical_darkness_controls_attack_discovery_by_sense_mode() -> None:
    """Darkvision cannot target through magical darkness; Devil's Sight can."""
    reset_stealth_world(width=8)
    attacker = create_test_monster("monster.skeleton", 
        name="Attacker",
        position=(1, 1),
        faction="heroes",
        darkvision=True,
    )
    target = create_test_monster("monster.skeleton", 
        name="Target",
        position=(2, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=8)
    assert target.uuid in attacker.senses.entities
    assert target_is_discoverable(attacker, target.uuid)

    target_tile = get_map().get_tile(2, 1)
    assert target_tile is not None
    target_tile.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS)

    assert target.uuid not in attacker.senses.entities
    assert not target_is_discoverable(attacker, target.uuid)
    attacker.senses.sense_modes.append(
        SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120)
    )
    attacker.update_entity_senses(max_distance=8)

    assert target.uuid in attacker.senses.entities
    assert target_is_discoverable(attacker, target.uuid)
    assert (
        target_tile.get_effective_light_for(attacker.uuid, attacker.position)
        == LightLevel.BRIGHT_LIGHT
    )


def test_torch_zones_preserve_bright_hidden_and_reveal_very_bright_hidden() -> None:
    """One torch locks all three zones and their distinct Hidden semantics."""
    reset_stealth_world(width=12, default_light=LightLevel.DARKNESS)
    carrier = create_test_monster("monster.skeleton", 
        name="Torchbearer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    near_hidden = create_test_monster("monster.skeleton", 
        name="Near Hidden",
        position=(1, 1),
        faction="monsters",
        darkvision=False,
    )
    bright_hidden = create_test_monster("monster.skeleton", 
        name="Bright Hidden",
        position=(3, 1),
        faction="monsters",
        darkvision=False,
    )
    add_hidden(near_hidden, 99)
    add_hidden(bright_hidden, 99)
    torch = materialize_item(
        TORCH_RECIPE,
        carrier.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    assert carrier.loot_item(torch)

    torch.ignite(carrier.uuid)

    levels = {
        position: get_map().get_tile(*position).resolved_light_level
        for position in [(0, 1), (1, 1), (3, 1), (5, 1), (9, 1)]
        if get_map().get_tile(*position) is not None
    }
    assert levels == {
        (0, 1): LightLevel.VERY_BRIGHT,
        (1, 1): LightLevel.VERY_BRIGHT,
        (3, 1): LightLevel.BRIGHT_LIGHT,
        (5, 1): LightLevel.DIM_LIGHT,
        (9, 1): LightLevel.DARKNESS,
    }
    assert "Hidden" not in near_hidden.active_conditions
    assert near_hidden.stealth_dc is None
    assert "Hidden" in bright_hidden.active_conditions
    assert bright_hidden.stealth_dc == 99


def test_light_add_spots_only_the_hidden_enemy() -> None:
    """Lighting a subscribed dark cell logs the hidden enemy, not plain darkness."""
    reset_stealth_world(width=8, default_light=LightLevel.DARKNESS)
    observer = create_test_monster("monster.skeleton", 
        name="Observer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    hidden_enemy = create_test_monster("monster.skeleton", 
        name="Lurker",
        position=(3, 1),
        faction="monsters",
        darkvision=False,
    )
    plain_enemy = create_test_monster("monster.skeleton", 
        name="Plain Enemy",
        position=(4, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=8)
    add_hidden(hidden_enemy, observer.get_passive_perception() - 1)
    assert hidden_enemy.uuid not in observer.senses.entities
    assert plain_enemy.uuid not in observer.senses.entities
    logs = captured_combat_logs()

    get_map().add_light_source(
        (2, 1),
        bright_radius_feet=20,
        dim_radius_feet=0,
    )

    assert hidden_enemy.uuid in observer.senses.entities
    assert plain_enemy.uuid in observer.senses.entities
    spotted = spotted_logs(logs)
    assert len(spotted) == 1
    assert spotted[0].target_uuid == str(hidden_enemy.uuid)
    assert spotted[0].perceiver_uuids == {str(observer.uuid)}
    assert spotted[0].data["observer_uuid"] == str(observer.uuid)
    assert spotted[0].data["target_uuid"] == str(hidden_enemy.uuid)
    assert spotted[0].data["target_position"] == hidden_enemy.position


def test_torch_light_change_refreshes_move_targets() -> None:
    """Authoritative illumination invalidates cached movement affordances."""
    reset_stealth_world(width=16, default_light=LightLevel.DARKNESS)
    carrier = create_test_monster("monster.skeleton", 
        name="Torchbearer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=16)

    before = carrier.get_available_actions()
    before_move = next(
        action
        for action in before.position_actions
        if action.template_name == "Move"
    )
    before_positions = {
        target.position
        for target in before_move.valid_targets
    }
    before_revision = carrier.senses.path_revision
    assert (3, 1) not in before_positions
    assert not carrier.senses._paths_dirty

    torch = materialize_item(
        TORCH_RECIPE,
        carrier.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    assert carrier.loot_item(torch)
    torch.ignite(carrier.uuid)

    assert carrier.senses._paths_dirty
    after = carrier.get_available_actions()
    after_move = next(
        action
        for action in after.position_actions
        if action.template_name == "Move"
    )
    after_positions = {
        target.position
        for target in after_move.valid_targets
    }
    assert carrier.senses.path_revision > before_revision
    assert not carrier.senses._paths_dirty
    assert (3, 1) in after_positions


def test_anchored_torch_movement_spots_hidden_enemy_reactively() -> None:
    """Moving an anchored torch produces one observation and one spotted fact."""
    reset_stealth_world(width=16, default_light=LightLevel.DARKNESS)
    carrier = create_test_monster("monster.skeleton", 
        name="Torchbearer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    hidden_enemy = create_test_monster("monster.skeleton", 
        name="Skulker",
        position=(10, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=16)
    add_hidden(hidden_enemy, carrier.get_passive_perception() - 1)
    torch = materialize_item(
        TORCH_RECIPE,
        carrier.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    assert carrier.loot_item(torch)
    torch.ignite(carrier.uuid)
    assert hidden_enemy.uuid not in carrier.senses.entities
    logs = captured_combat_logs()
    cursor = EventQueue.event_cursor()

    Entity.update_entity_position(carrier, (6, 1))

    enemy_tile = get_map().get_tile(10, 1)
    assert enemy_tile is not None
    assert enemy_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Hidden" in hidden_enemy.active_conditions
    assert hidden_enemy.uuid in carrier.senses.entities
    assert [entry.target_uuid for entry in spotted_logs(logs)] == [
        str(hidden_enemy.uuid)
    ]
    light_completions = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type == EventType.SPATIAL_LIGHT_CHANGED
        and event.phase == EventPhase.COMPLETION
    ]
    assert len(light_completions) == 1


def test_light_toggle_spots_hidden_enemy_reactively() -> None:
    """Turning an existing light back on logs exactly the new hidden contact."""
    reset_stealth_world(width=8, default_light=LightLevel.DARKNESS)
    observer = create_test_monster("monster.skeleton", 
        name="Watcher",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    hidden_enemy = create_test_monster("monster.skeleton", 
        name="Sneaker",
        position=(3, 1),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=8)
    add_hidden(hidden_enemy, observer.get_passive_perception() - 1)
    light_uuid = get_map().add_light_source(
        (1, 1),
        bright_radius_feet=20,
        dim_radius_feet=0,
    )
    assert hidden_enemy.uuid in observer.senses.entities
    get_map().toggle_light_source(light_uuid, False)
    assert hidden_enemy.uuid not in observer.senses.entities
    logs = captured_combat_logs()

    get_map().toggle_light_source(light_uuid, True)

    assert hidden_enemy.uuid in observer.senses.entities
    assert [entry.target_uuid for entry in spotted_logs(logs)] == [
        str(hidden_enemy.uuid)
    ]
