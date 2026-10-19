"""Desired native outcomes for new global-audit findings; repairs are pending.

Inputs use real authored builds, registered abilities, item uses and event vetoes.
Outputs are HP, retained grants/conditions, spell slots and world lighting.
Strict xfails identify unrepaired findings; repaired spell cases run normally.
"""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.classes.feats import LuckyFeature
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    SecondWind,
    SecondWindFeature,
)
from dnd.classes.rage import Rage
from dnd.classes.sorcerer import (
    ConvertSlotToSP,
    ConvertSPToSlot,
    DragonWings,
    ElementalAffinityResistanceAction,
    QuickenedSpell,
)
from dnd.content.characters.builds import create_character
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_actions import spell_slot_cost_type
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_skeleton_archer
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import DivineEminenceAction, LeadershipAction, RampageAvailable
from dnd.spells.conjuration import AcidSplash
from dnd.spells.enchantment import Bless
from dnd.spells.evocation import MagicMissile, MassHeal
from dnd.spells.transmutation import EnhanceAbility
from dnd.types.character_progression import CharacterClass
from dnd.types.world import LightLevel
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_high_level_spell_controls import high_actor
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture export
from tests.manual.spell_regression_support import force_save_result
from tests.progression.prepared_class_support import prepared_build
from tests.progression.test_direct_sorcerer_progression import _level as sorcerer_level


def refusal_cases(finding):
    return [
        pytest.param(False, id="admitted"),
        pytest.param(
            True,
            id="refused",
            marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=finding),
        ),
    ]


def refuse_effect(actor, kind, *, recipient=False, target_application_only=False):
    refusals = []

    def refuse(event, _):
        if target_application_only and event.application is None:
            return event
        refusals.append(event.lineage_uuid)
        return event.cancel(status_message="Global audit: effect refused")

    actor.add_event_handler(EventHandler(
        name="Global audit native effect refusal",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=kind,
            event_phase=EventPhase.EFFECT,
            **({"event_target_entity_uuid": actor.uuid} if recipient else
               {"event_source_entity_uuid": actor.uuid}),
        )],
        event_processor=refuse,
    ))
    return refusals


@pytest.mark.parametrize("refused", refusal_cases("GA-01: refused class action commits its benefit"))
@pytest.mark.parametrize("class_id,level,action_type", [
    (CharacterClass.FIGHTER, 2, SecondWind),
    (CharacterClass.FIGHTER, 2, ActionSurge),
    (CharacterClass.BARBARIAN, 1, Rage),
    (CharacterClass.SORCERER, 14, DragonWings),
    (CharacterClass.SORCERER, 6, ElementalAffinityResistanceAction),
    (CharacterClass.SORCERER, 6, QuickenedSpell),
    (CharacterClass.SORCERER, 6, ConvertSlotToSP),
    (CharacterClass.SORCERER, 6, ConvertSPToSlot),
], ids=lambda value: value.__name__ if isinstance(value, type) else str(value))
def test_class_action_benefit_requires_own_effect_admission(game, class_id, level, action_type, refused):
    build = prepared_build(class_id, 1 if class_id is CharacterClass.SORCERER else level)
    if class_id is CharacterClass.SORCERER:
        build = replace(build, class_levels=tuple(sorcerer_level(n) for n in range(1, level + 1)))
    actor = create_character(replace(build, faction="heroes"))
    game.deploy_entity(actor, (2, 2))
    if action_type is SecondWind:
        actor.receive_damage(8, DamageType.FORCE, actor.uuid)
    elif action_type is ConvertSlotToSP:
        actor.action_economy.consume_resource("sorcery_points", 2)
    elif action_type is ConvertSPToSlot:
        actor.action_economy.consume(spell_slot_cost_type(1), 1)

    def benefit():
        if action_type is SecondWind:
            return actor.get_hp()
        if action_type is ConvertSlotToSP:
            return actor.action_economy.resources["sorcery_points"].current
        if action_type is ConvertSPToSlot:
            return actor.action_economy.spell_slot_value(1).normalized_score
        return frozenset(actor.active_conditions)

    before = benefit()
    refusals = refuse_effect(actor, EventType.BASE_ACTION) if refused else []
    template = next(action for action in actor.registered_actions if isinstance(action, action_type))
    with fixed_dice_faces(*([5] * 30)):
        result = template.instantiate().apply()
    after = benefit()
    assert result is not None
    assert result.canceled is refused
    assert bool(refusals) is refused
    # Paid costs are deliberately excluded: interruption does not imply refund.
    assert (after == before) is refused


@pytest.mark.parametrize("creature_id,action_type,refused", [
    pytest.param(creature_id, action_type, refused,
        marks=(pytest.mark.xfail(strict=True, raises=AssertionError,
            reason="GA-01: refused monster action commits conditions")
            if refused and creature_id != "knight" else ()))
    for creature_id, action_type in [
    ("priest", DivineEminenceAction),
    ("knight", LeadershipAction),
    ("skeleton_archer", MarkTargetAction),
    ] for refused in (False, True)
])
def test_authored_monster_benefit_requires_own_effect_admission(game, creature_id, action_type, refused):
    if creature_id == "skeleton_archer":
        actor = create_skeleton_archer(name="Archer", position=(2, 2), faction="monsters")
    else:
        actor = materialize_creature(
            SRD_CREATURE_RECIPES_BY_ID[creature_id], runtime_entity_uuid=uuid4(),
            display_name=creature_id, faction="monsters", position=(2, 2),
            deployment_role=CreatureDeploymentRole(role_id=f"audit.{creature_id}"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
    actor.compose_entity()
    game.deploy_entity(actor, (2, 2))
    target = create_skeleton(name="Recipient", position=(4, 2), faction="heroes")
    target.compose_entity()
    game.deploy_entity(target, (4, 2))
    Entity.update_all_entities_senses()
    before = (frozenset(actor.active_conditions), frozenset(target.active_conditions),
              frozenset(condition.uuid for condition in get_map().get_spatial_conditions()))
    refusals = refuse_effect(actor, EventType.BASE_ACTION) if refused else []
    template = next(action for action in actor.registered_actions if isinstance(action, action_type))
    kwargs = {"target_entity_uuid": target.uuid} if action_type is MarkTargetAction else {}
    result = template.instantiate(**kwargs).apply()
    after = (frozenset(actor.active_conditions), frozenset(target.active_conditions),
             frozenset(condition.uuid for condition in get_map().get_spatial_conditions()))
    assert result is not None
    assert result.canceled is refused
    assert bool(refusals) is refused
    assert (after == before) is refused


@pytest.mark.parametrize("item_id,refused", [
    pytest.param(item_id, refused,
        marks=(pytest.mark.xfail(strict=True, raises=AssertionError,
            reason="GA-02: refused item use commits healing or coating")
            if refused and item_id in {
                "consumable.healing_potion", "consumable.potion_haste",
                "consumable.potion_greater_invisibility", "consumable.potion_true_seeing",
                "gear.ember_quiver",
            } else ()))
    for item_id in [
    "consumable.healing_potion",
    "consumable.potion_haste",
    "consumable.potion_greater_invisibility",
    "consumable.potion_true_seeing",
    "consumable.weapon_coat.fire",
    "consumable.weapon_coat.lightning",
    "consumable.weapon_coat.basic_poison",
    "consumable.weapon_coat.assassin_poison",
    "consumable.weapon_coat.concentration_fire",
    "consumable.weapon_coat.timed_fire",
    "gear.ember_quiver",
    ] for refused in (False, True)
])
def test_authored_item_benefit_requires_own_effect_admission(game, item_id, refused):
    actor = combatant(game)
    actor.receive_damage(30, DamageType.FORCE, actor.uuid)
    quiver = item_id == "gear.ember_quiver"
    weapon = build_authored_item("weapon.longbow" if quiver else "weapon.longsword", actor.uuid)
    assert actor.loot_item(weapon)
    assert actor.equip_item(weapon.uuid, WeaponSlot.RANGED_MAIN if quiver else WeaponSlot.MELEE_MAIN)
    item = build_authored_item(item_id, actor.uuid)
    assert actor.loot_item(item)
    if quiver:
        assert actor.equip_item(item.uuid, BodyPart.BACKPACK)
    before = (actor.get_hp(), frozenset(actor.active_conditions), frozenset(weapon.active_conditions))
    refusals = refuse_effect(actor, EventType.CAST_SPELL if quiver else EventType.BASE_ACTION) if refused else []
    use_name = item.get_use_actions(actor.uuid)[0].get_discovery_template_name()
    with fixed_dice_faces(*([4] * 20)):
        result = execute_use_action(actor, item.uuid, use_name)
    after = (actor.get_hp(), frozenset(actor.active_conditions), frozenset(weapon.active_conditions))
    assert result is not None
    assert result.canceled is refused
    assert bool(refusals) is refused
    assert (after == before) is refused


@pytest.mark.parametrize("refused", [False, True], ids=["admitted", "refused"])
@pytest.mark.parametrize("start_lit", [False, True], ids=["ignite", "extinguish"])
@pytest.mark.parametrize("item_id", ["equipment.portable_torch", "environment.wall_torch"])
def test_torch_use_requires_own_effect_admission(game, start_lit, refused, item_id):
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 5, default_light=LightLevel.DARKNESS)
    actor = combatant(game)
    torch = build_authored_item(item_id, actor.uuid)
    if item_id == "equipment.portable_torch":
        assert actor.loot_item(torch)
    else:
        torch.place_on_grid((3, 2))
        actor.update_entity_senses(max_distance=10)
    if start_lit:
        use_name = torch.get_use_actions(actor.uuid)[0].get_discovery_template_name()
        initial = execute_use_action(actor, torch.uuid, use_name)
        assert initial is not None
        assert not initial.canceled
    assert torch.is_lit is start_lit
    light_before = grid.get_tile(3, 2).resolved_light_level
    refusals = refuse_effect(actor, EventType.BASE_ACTION) if refused else []
    use_name = torch.get_use_actions(actor.uuid)[0].get_discovery_template_name()
    result = execute_use_action(actor, torch.uuid, use_name)
    lit_after = torch.is_lit
    assert result is not None
    assert result.canceled is refused
    assert bool(refusals) is refused
    assert lit_after is (start_lit if refused else not start_lit)
    assert (grid.get_tile(3, 2).resolved_light_level == light_before) is refused


@pytest.mark.parametrize("refused", refusal_cases("GA-03: refused feature condition leaves grants"))
@pytest.mark.parametrize("condition_type", [SecondWindFeature, ActionSurgeFeature, LuckyFeature, RampageAvailable])
def test_rejected_feature_membership_has_no_action_or_resource_grant(game, condition_type, refused):
    actor = create_character(prepared_build(CharacterClass.WIZARD, 1))
    game.deploy_entity(actor, (2, 2))
    before = (frozenset(actor.action_economy.resources), frozenset(a.uuid for a in actor.registered_actions))
    refusals = refuse_effect(actor, EventType.CONDITION_APPLICATION, recipient=True) if refused else []
    condition = condition_type(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    result = actor.add_condition(condition)
    after = (frozenset(actor.action_economy.resources), frozenset(a.uuid for a in actor.registered_actions))
    assert result is not None
    assert result.canceled is refused
    assert (condition.uuid in actor.active_conditions_by_uuid) is (not refused)
    assert bool(refusals) is refused
    assert (after == before) is refused


@pytest.mark.parametrize("refused", [False, True], ids=["admitted", "refused"])
def test_enhance_ability_temp_hp_requires_condition_admission(game, refused):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3, 2))
    refusals = refuse_effect(target, EventType.CONDITION_APPLICATION, recipient=True) if refused else []
    with fixed_dice_faces(*([4] * 20)):
        result = EnhanceAbility(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            enhance_ability_type="constitution", alt_skip_slot=True,
        ).apply()
    temporary_hp = target.health.temporary_hit_points.normalized_score
    assert result is not None
    assert result.canceled is refused
    assert ("Enhance Ability" in target.active_conditions) is (not refused)
    assert bool(refusals) is refused
    assert temporary_hp == (0 if refused else 8)


@pytest.mark.parametrize("transfer", [
    pytest.param(False, id="original-carrier-control"),
    pytest.param(True, id="transferred"),
])
def test_torch_transfer_releases_old_carrier_light(game, transfer):
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 5, default_light=LightLevel.DARKNESS)
    first = combatant(game)
    second = combatant(game, "New holder", (15, 2))
    torch = build_authored_item("equipment.portable_torch", first.uuid)
    first.loot_item(torch)
    use_name = torch.get_use_actions(first.uuid)[0].get_discovery_template_name()
    result = execute_use_action(first, torch.uuid, use_name)
    assert result is not None
    assert not result.canceled
    assert torch.is_lit
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.VERY_BRIGHT
    assert grid.get_tile(15, 2).resolved_light_level is LightLevel.DARKNESS
    if transfer:
        assert first.inventory.transfer_to(torch.uuid, second.inventory)
        assert torch.owner_uuid == second.uuid
    # Either native reanchoring or extinguishing can satisfy this invariant.
    old_carrier_light = grid.get_tile(2, 2).resolved_light_level
    assert old_carrier_light is (
        LightLevel.DARKNESS if transfer else LightLevel.VERY_BRIGHT
    )


@pytest.mark.parametrize("refused", [False, True], ids=["admitted", "refused"])
@pytest.mark.parametrize("spell_type", [MagicMissile, AcidSplash, Bless, MassHeal])
def test_each_spell_target_application_requires_its_own_admission(game, spell_type, refused):
    caster = high_actor(game)
    target = high_actor(game, "Recipient", (3, 2), "heroes" if spell_type in (Bless, MassHeal) else "foes")
    if spell_type is MassHeal:
        target.receive_damage(25, DamageType.FORCE, caster.uuid)
    force_save_result(target, "dexterity", succeeds=False)
    before = (target.get_hp(), frozenset(target.active_conditions))
    refusals = refuse_effect(caster, EventType.CAST_SPELL, target_application_only=True) if refused else []
    with fixed_dice_faces(*([4] * 30)):
        result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None
    # The admitted cast root may succeed even when a target child is refused.
    if not refused:
        assert not result.canceled
    assert bool(refusals) is refused
    after = (target.get_hp(), frozenset(target.active_conditions))
    assert (after == before) is refused
