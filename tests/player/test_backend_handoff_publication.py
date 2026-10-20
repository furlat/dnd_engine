"""Production handoff: actual selected commands remain usable in both seat streams."""

import pytest
from uuid import uuid4

from dnd.actions_functional import register_spell
from dnd.content.characters.premades import PALADIN_PREMADE_ID
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.player.commands import ActionSelection
from dnd.player.facts import ActorChangeFact, SpellFact, AttackFact, DamageResultFact
from dnd.types.actor_facts import ConditionRow, ItemEffectsRow
from dnd.spells.transmutation import DragonsBreath, MagicWeapon
from dnd.spells.enchantment import Hex
from dnd.spells.divination import HuntersMark
from dnd.spells.hit_effects import QuarrySustain
from dnd.spells.conjuration import EnsnaringStrike
from dnd.spells.evocation import BrandingSmite, ChromaticOrb, SearingSmite, SorcerousBurst
from server.protocol import CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PlayerOperation
from server.worker import dispatch, needs_advance
from server.worker_protocol import Advance, Command
from tests.engine.test_bg3_spell_hit_riders import equip
from tests.manual.spell_regression_support import force_save_result
from tests.player.test_compact_choices import request_choices, rows, world
from tests.player.test_handoff_passive_attribution import await_actor, execute, turning_recipe, workers


def submit_spell(world, spell, behavior, target, *, facets=(), hit=True):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    register_spell(actor, spell, caster_level=7)
    choices = request_choices(world).choices
    action = next(row for row in rows(choices)
        if row.behavior_id == behavior and row.can_afford
        and all(any(f.key == key and f.value == value for f in row.variant_facets)
            for key, value in facets)
        and any(choices.subjects[b.subject].uuid == target.uuid
            for b in choices.target_sets[row.target_set] if b.kind == "subject"))
    binding = next(b for b in choices.target_sets[action.target_set]
        if b.kind == "subject" and choices.subjects[b.subject].uuid == target.uuid)
    selection = ActionSelection(action_index=action.discovery_index, target_indices=(binding.index,))
    with fixed_dice_faces(15 if hit else 1, *([2] * 80)):
        reply, records, _ = dispatch(runtime, Command(seat_id=seat,
            request=CommandRequest(command_number=1, actor_uuid=actor.uuid,
                state_revision=publication.state_revision,
                intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
                    selection=selection))))
    assert reply.rejection is None
    # Parse the delivered bytes: assertions cannot pass from native-only fields.
    return tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in records)


@pytest.mark.parametrize("spell,behavior", [
    (BrandingSmite, "spell.branding_smite"),
    (SearingSmite, "spell.searing_smite"),
    (EnsnaringStrike, "spell.ensnaring_strike"),
])
@pytest.mark.parametrize("hit", [False, True])
def test_equipped_smite_completes_capture_for_both_seats(world, spell, behavior, hit):
    runtime, _, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    target.move((caster.position[0] + 1, caster.position[1]))
    equip(caster)
    force_save_result(target, "strength", succeeds=False)
    records = submit_spell(world, spell, behavior, target, hit=hit,
        facets=(("form", "MELEE_MAIN"),))
    assert len(records) == 2
    for record in records:
        facts = [node.fact for group in record.lineages for node in group.events
            if isinstance(node.fact, SpellFact)]
        assert any(fact.attack_outcome is (AttackOutcome.HIT if hit else AttackOutcome.CRIT_MISS)
            for fact in facts), facts


@pytest.mark.parametrize("spell,behavior,element", [
    *((SorcerousBurst, "spell.sorcerous_burst", element) for element in
      ("acid", "cold", "fire", "lightning", "poison", "psychic", "thunder")),
    *((ChromaticOrb, "spell.chromatic_orb", element) for element in
      ("acid", "cold", "fire", "lightning", "poison", "thunder")),
])
def test_selected_projectile_element_survives_a_miss_in_both_streams(world, spell, behavior, element):
    runtime, _, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    facets = (("damage_type", element),) + ((("side", "creature"),) if spell is ChromaticOrb else ())
    records = submit_spell(world, spell, behavior, target, facets=facets, hit=False)
    assert len(records) == 2
    for record in records:
        facts = [node.fact for group in record.lineages for node in group.events
            if isinstance(node.fact, SpellFact)]
        assert any(fact.attack_outcome is AttackOutcome.CRIT_MISS for fact in facts)
        assert any(fact.behavior_id == behavior
            and fact.damage_types == (DamageType(element.title()),) for fact in facts)


def changed_rows(record):
    return [row for group in record.lineages for node in group.events
        if isinstance(node.fact, ActorChangeFact)
        for actor in node.fact.actors for row in actor.rows]


@pytest.mark.parametrize("element", ("acid", "cold", "fire", "lightning", "poison"))
def test_dragons_breath_discloses_exact_grant_and_element(world, element):
    runtime, _, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    target.move((caster.position[0] + 2, caster.position[1]))
    records = submit_spell(world, DragonsBreath, "spell.dragons_breath", caster,
        facets=(("damage_type", element),))
    grant = next(condition for condition in caster.active_conditions_by_uuid.values()
        if condition.get_semantic_key() == "condition.spell.dragons_breath")
    for record in records:
        members = [row.member for row in changed_rows(record)
            if isinstance(row, ConditionRow) and row.member is not None]
        member = next((member for member in members if member.condition_uuid == grant.uuid), None)
        assert member is not None
        assert member.state.energy_type is DamageType(element.title())
    exhaled = execute((runtime, world[1], runtime.publications[world[1]]),
        "action.spell.dragons_breath.exhale", command_number=2, level=2, position=target.position)
    for record in exhaled:
        assert any(isinstance(node.fact, DamageResultFact)
            and node.fact.target_entity_uuid == target.uuid
            and node.fact.damage_type is DamageType(element.title())
            for group in record.lineages for node in group.events)
    end = execute((runtime, world[1], runtime.publications[world[1]]),
        "action.drop_concentration", command_number=3)
    assert grant.uuid not in caster.active_conditions_by_uuid
    for record in end:
        assert any(isinstance(row, ConditionRow) and row.condition_uuid == grant.uuid
            and row.member is None for row in changed_rows(record))


@pytest.mark.parametrize("spell,behavior", [(Hex, "spell.hex"), (HuntersMark, "spell.hunters_mark")])
def test_quarry_cast_publishes_retained_caster_owner(world, spell, behavior):
    runtime, _, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    records = submit_spell(world, spell, behavior, target)
    grant = next(condition for condition in caster.active_conditions_by_uuid.values()
        if isinstance(condition, QuarrySustain))
    for record in records:
        assert any(isinstance(row, ConditionRow) and row.member is not None
            and row.member.condition_uuid == grant.uuid for row in changed_rows(record))
    end = execute((runtime, world[1], runtime.publications[world[1]]),
        "action.drop_concentration", command_number=2)
    assert grant.uuid not in caster.active_conditions_by_uuid
    for record in end:
        assert any(isinstance(row, ConditionRow) and row.condition_uuid == grant.uuid
            and row.member is None for row in changed_rows(record))


def item_effect_rows(record, weapon_uuid):
    effects = [row.effects for row in changed_rows(record)
        if isinstance(row, ItemEffectsRow) and row.item_uuid == weapon_uuid]
    effects.extend(item.effects for group in record.lineages for body in group.bodies
        for item in body.items if item.item_uuid == weapon_uuid)
    effects.extend(item.effects for group in record.lineages for node in group.events
        if isinstance(node.fact, ActorChangeFact) for item in node.fact.items
        if item.item_uuid == weapon_uuid)
    return effects


@pytest.mark.parametrize("behavior", ("spell.magic_weapon", "action.class.paladin.sacred_weapon"))
def test_enchanted_weapon_publishes_membership_on_exact_equipped_weapon(workers, behavior):
    runtime = workers(audience_ids={"cleric": uuid4(), "undead": uuid4()},
        recipe=turning_recipe(caster_premade=PALADIN_PREMADE_ID))
    caster = next(actor for actor in runtime.session.game.entities.values() if actor.faction == "cleric")
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    target.move((caster.position[0] + 1, caster.position[1]))
    add_modifier(target.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
        NumericalModifier(name="Survive enchanted weapon use", value=200, source_entity_uuid=target.uuid))
    register_spell(caster, MagicWeapon, caster_level=5)
    world = await_actor(runtime, caster.uuid)
    weapon = caster.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    records = execute(world, behavior,
        target_uuid=caster.uuid if behavior == "spell.magic_weapon" else None,
        level=2,
        facets=(("form", "MELEE_MAIN"),))
    effect = next(iter(weapon.active_conditions_by_uuid.values()))
    for record in records:
        effects = item_effect_rows(record, weapon.uuid)
        assert any(member.effect_uuid == effect.uuid
            for members in effects for member in members), effects
    publication = runtime.publications[world[1]]
    reply, _, _ = dispatch(runtime, Command(seat_id=world[1], request=CommandRequest(
        command_number=21, actor_uuid=caster.uuid, state_revision=publication.state_revision,
        intent=EndTurnIntent())))
    assert reply.rejection is None
    used_records = execute(await_actor(runtime, caster.uuid), "action.attack",
        target_uuid=target.uuid, command_number=22, first_face=15)
    for record in used_records:
        assert any(isinstance(node.fact, AttackFact)
            and node.fact.source_item_uuid == weapon.uuid
            and any(member.effect_uuid == effect.uuid for member in node.fact.item_effects)
            for group in record.lineages for node in group.events)
    if behavior == "spell.magic_weapon":
        retired = execute((runtime, world[1], runtime.publications[world[1]]),
            "action.drop_concentration", command_number=23)
        assert effect.uuid not in weapon.active_conditions_by_uuid
        for record in retired:
            assert any(all(member.effect_uuid != effect.uuid for member in members)
                for members in item_effect_rows(record, weapon.uuid))
    else:
        retirement_records = []
        for turn in range(40):
            if effect.uuid not in weapon.active_conditions_by_uuid:
                break
            if needs_advance(runtime.session):
                _, delivered, _ = dispatch(runtime, Advance())
            else:
                seat, publication = next((seat, row) for seat, row in runtime.publications.items()
                    if row.boundary.input_actor_uuid is not None)
                reply, delivered, _ = dispatch(runtime, Command(seat_id=seat,
                    request=CommandRequest(command_number=31 + 2 * turn,
                        actor_uuid=publication.boundary.input_actor_uuid,
                        state_revision=publication.state_revision, intent=EndTurnIntent())))
                assert reply.rejection is None
            retirement_records.extend(PlayerOperation.model_validate_json(record.model_dump_json())
                for record in delivered)
        assert effect.uuid not in weapon.active_conditions_by_uuid
        assert any(not members for record in retirement_records
            for members in item_effect_rows(record, weapon.uuid))
