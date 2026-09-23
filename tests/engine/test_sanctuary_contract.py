"""Real Sanctuary attempts preserve costs, targeting intent and causal effects."""

from collections.abc import Iterator
from typing import Literal

import pytest

from dnd.actions import Attack, SpellAction, SpellEvent
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import CreatureType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, SavingThrowD20RollResultEvent
from dnd.entity import Entity
from dnd.spells.abjuration import Sanctuary
from dnd.spells.conjuration import AcidSplash, Entangle, PoisonSpray, Web
from dnd.spells.effect_ids import SANCTUARY_INTERRUPTION_OUTCOME_CODE
from dnd.spells.enchantment import CharmPerson, HoldPerson, PowerWordStun
from dnd.spells.evocation import CureWounds, Fireball, FireBolt, MagicMissile, ScorchingRay
from dnd.spells.necromancy import NecroticBless
from dnd.spells.transmutation import EnlargeReduce
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _arena(*, creature_type: CreatureType = CreatureType.HUMANOID) -> tuple[Entity, Entity]:
    reset_spell_regression_arena(14, 9)
    warded = create_spell_regression_actor(
        "Warded", (4, 3), "protected", spell_slots={1: 4, 2: 2, 3: 2},
        creature_type=creature_type,
    )
    attacker = create_spell_regression_actor(
        "Attacker", (5, 3), "hostile", spell_slots={1: 3, 2: 3, 3: 3, 8: 1},
    )
    Entity.update_all_entities_senses()
    cast = Sanctuary(source_entity_uuid=warded.uuid, target_entity_uuid=warded.uuid).apply()
    assert cast is not None and cast.phase is EventPhase.COMPLETION
    return warded, attacker


def _resources(actor: Entity) -> tuple[int, ...]:
    economy = actor.action_economy
    return (economy.actions.normalized_score, economy.bonus_actions.normalized_score,
            economy.reactions.normalized_score, economy.spell_slot_1.normalized_score,
            economy.spell_slot_2.normalized_score, economy.spell_slot_3.normalized_score,
            economy.spell_slot_8.normalized_score)


def _descendants(event: Event) -> Iterator[Event]:
    for child in event.get_children_events():
        yield child
        yield from _descendants(child)


def _ward_saves(event: Event, attacker: Entity) -> list[SavingThrowD20RollResultEvent]:
    return list({child.lineage_uuid: child for child in _descendants(event)
                 if isinstance(child, SavingThrowD20RollResultEvent)
                 and child.source_entity_uuid == attacker.uuid
                 and child.ability_name == "wisdom"}.values())


@pytest.mark.parametrize("spell_type", [FireBolt, PoisonSpray, HoldPerson, CharmPerson, PowerWordStun])
@pytest.mark.parametrize("saves", [False, True])
def test_selected_harmful_spell_is_gated_before_costs(spell_type: type[SpellAction], saves: bool) -> None:
    warded, attacker = _arena()
    force_save_result(attacker, "wisdom", succeeds=saves)
    force_save_result(warded, "wisdom", succeeds=False)
    set_hp(warded, 100)  # Power Word Stun has its own genuine HP threshold.
    before = _resources(attacker)
    hp_before = warded.get_hp()
    spell = spell_type(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid)
    slot_before = (attacker.action_economy.spell_slot_value(spell.cast_at_level).normalized_score
                   if spell.cast_at_level > 0 else None)
    with fixed_dice_faces(*([4] * 30)):
        result = spell.apply()
    assert result is not None and len(_ward_saves(result, attacker)) == 1
    assert result.action_economy_spent is saves
    if slot_before is not None:
        assert attacker.action_economy.spell_slot_value(spell.cast_at_level).normalized_score == slot_before - int(saves)
    assert "Sanctuary" in warded.active_conditions
    if saves:
        assert result.phase is EventPhase.COMPLETION and not result.canceled
        assert attacker.action_economy.actions.normalized_score == before[0] - 1
        if spell_type in (FireBolt, PoisonSpray):
            assert warded.get_hp() < hp_before
        else:
            assert any(name in warded.active_conditions for name in ("Paralyzed", "Charmed", "Stunned"))
    else:
        assert result.canceled and result.canceled_from_phase is EventPhase.DECLARATION
        assert result.outcome_code == SANCTUARY_INTERRUPTION_OUTCOME_CODE
        assert result.outcome_source_entity_uuid == warded.uuid
        assert _resources(attacker) == before
        assert warded.get_hp() == hp_before
        assert not any(name in warded.active_conditions for name in ("Paralyzed", "Charmed", "Stunned"))


@pytest.mark.parametrize("saves", [False, True])
def test_weapon_attack_preserves_existing_cost_boundary(saves: bool) -> None:
    warded, attacker = _arena()
    attacker.equipment.equip(build_authored_item("weapon.dagger", attacker.uuid), WeaponSlot.MELEE_MAIN)
    force_save_result(attacker, "wisdom", succeeds=saves)
    hp_before, resources = warded.get_hp(), _resources(attacker)
    with fixed_dice_faces(15, 15, 4):
        result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid,
                        weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and len(_ward_saves(result, attacker)) == 1
    assert result.action_economy_spent is saves
    assert result.canceled is not saves
    assert (warded.get_hp() < hp_before) is saves
    assert "Sanctuary" in warded.active_conditions
    if saves:
        assert attacker.action_economy.actions.normalized_score == resources[0] - 1
    else:
        assert _resources(attacker) == resources


@pytest.mark.parametrize("spell_type", [AcidSplash, MagicMissile, ScorchingRay])
def test_extra_selected_warded_target_blocks_entire_unpaid_allocation(spell_type: type[SpellAction]) -> None:
    warded, attacker = _arena()
    other = create_spell_regression_actor("Other recipient", (4, 4), "protected")
    Entity.update_all_entities_senses()
    force_save_result(attacker, "wisdom", succeeds=False)
    before = _resources(attacker)
    hp_before = (warded.get_hp(), other.get_hp())
    with fixed_dice_faces(*([15] * 15)):
        result = spell_type(source_entity_uuid=attacker.uuid, target_entity_uuid=other.uuid,
                            extra_target_entity_uuids=[warded.uuid]).apply()
    assert result is not None and result.canceled
    assert not result.action_economy_spent
    assert len(_ward_saves(result, attacker)) == 1
    assert _resources(attacker) == before
    assert (warded.get_hp(), other.get_hp()) == hp_before


def test_repeated_rays_do_not_repeat_the_sanctuary_gate() -> None:
    warded, attacker = _arena()
    force_save_result(attacker, "wisdom", succeeds=True)
    before = warded.get_hp()
    with fixed_dice_faces(*([4] * 30)):
        result = ScorchingRay(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert len(_ward_saves(result, attacker)) == 1
    assert result.action_economy_spent
    assert attacker.action_economy.actions.normalized_score == 0
    assert attacker.action_economy.spell_slot_2.normalized_score == 2
    assert warded.get_hp() < before


def test_beneficial_spell_to_warded_enemy_has_no_gate() -> None:
    warded, attacker = _arena()
    force_save_result(attacker, "wisdom", succeeds=False)
    set_hp(warded, 100)
    with fixed_dice_faces(4):
        result = CureWounds(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert not _ward_saves(result, attacker)
    assert warded.get_hp() > 100 and "Sanctuary" in warded.active_conditions


def test_area_damage_bypasses_targeting_ward() -> None:
    warded, attacker = _arena()
    force_save_result(attacker, "wisdom", succeeds=False)
    hp_before = warded.get_hp()
    with fixed_dice_faces(*([3] * 80)):
        result = Fireball(source_entity_uuid=attacker.uuid, end_position=warded.position).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert not _ward_saves(result, attacker)
    assert warded.get_hp() < hp_before and "Sanctuary" in warded.active_conditions
    assert attacker.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("spell_type,breaks", [(CureWounds, False), (Fireball, True), (Entangle, True), (Web, True)])
def test_self_break_depends_on_harmful_enemy_effect(spell_type: type[SpellAction], breaks: bool) -> None:
    caster, enemy = _arena()
    force_save_result(enemy, "strength", succeeds=False)
    force_save_result(enemy, "dexterity", succeeds=False)
    spell = (spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=enemy.uuid)
             if spell_type is CureWounds else spell_type(source_entity_uuid=caster.uuid, end_position=enemy.position))
    with fixed_dice_faces(*([3] * 80)):
        result = spell.apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert ("Sanctuary" not in caster.active_conditions) is breaks
    if spell_type is Entangle:
        assert "Restrained" in enemy.active_conditions


def test_empty_harmful_zone_does_not_break_sanctuary() -> None:
    caster, _enemy = _arena()
    result = Entangle(source_entity_uuid=caster.uuid, end_position=(11, 7)).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert "Sanctuary" in caster.active_conditions


@pytest.mark.parametrize("creature_type,blocked", [(CreatureType.UNDEAD, False), (CreatureType.HUMANOID, True)])
def test_mixed_necrotic_bless_uses_recipient_branch(creature_type: CreatureType, blocked: bool) -> None:
    warded, attacker = _arena(creature_type=creature_type)
    force_save_result(attacker, "wisdom", succeeds=False)
    before = _resources(attacker)
    with fixed_dice_faces(*([10] * 10)):
        result = NecroticBless(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid).apply()
    assert result is not None and result.canceled is blocked
    if blocked:
        assert _resources(attacker) == before and len(_ward_saves(result, attacker)) == 1
    else:
        assert not _ward_saves(result, attacker)
        assert "Bless" in warded.active_conditions
        assert attacker.action_economy.actions.normalized_score == 0


def test_blessing_enemy_undead_does_not_break_own_ward() -> None:
    caster, _enemy = _arena()
    undead = create_spell_regression_actor("Enemy undead", (4, 4), "hostile", creature_type=CreatureType.UNDEAD)
    Entity.update_all_entities_senses()
    result = NecroticBless(source_entity_uuid=caster.uuid, target_entity_uuid=undead.uuid).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert "Bless" in undead.active_conditions and "Sanctuary" in caster.active_conditions


@pytest.mark.parametrize("mode", ["enlarge", "reduce"])
def test_transformation_gate_matches_existing_unwilling_recipient_rule(mode: Literal["enlarge", "reduce"]) -> None:
    warded, attacker = _arena()
    force_save_result(attacker, "wisdom", succeeds=False)
    with fixed_dice_faces(10):
        blocked = EnlargeReduce(source_entity_uuid=attacker.uuid, target_entity_uuid=warded.uuid,
                                enlarge_mode=mode).apply()
    assert blocked is not None and blocked.canceled
    assert attacker.action_economy.actions.normalized_score == 1
    willing = EnlargeReduce(source_entity_uuid=warded.uuid, target_entity_uuid=warded.uuid,
                            enlarge_mode=mode).apply()
    assert willing is not None and willing.phase is EventPhase.COMPLETION
    assert "Sanctuary" in warded.active_conditions
