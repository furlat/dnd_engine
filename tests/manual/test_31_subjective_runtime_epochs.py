"""Decision-epoch coverage for the agent-side subjective runtime."""

from collections import Counter
from uuid import uuid4

import pytest

import dnd.ai.runtime.decision_epoch as subjective_epochs_module
from dnd.ai.runtime.decision_epoch import (
    _action_cost_profile_from_cost_rows,
    _build_action_capabilities,
    _build_affordance_set_and_execution_authority_from_actions,
    _build_affordance_set_from_actions,
)
from dnd.ai.contracts.semantics import ActionTag, MovementKind, OutcomeKind, TopologyOperation, TruthValue, evaluate_fact_expression
from dnd.ai.contracts.control import AffordanceSet
from dnd.actions_functional import execute_by_index, register_spell
from dnd.core.base_object import BaseObject
from dnd.core.base_actions import ActionAvailabilityStatus
from dnd.core.base_actions import ActionCategory
from dnd.core.base_actions import AvailableActionInfo
from dnd.core.base_actions import AvailableActionsResult
from dnd.core.base_actions import AvailableTarget
from dnd.core.base_actions import BaseCost
from dnd.core.base_actions import OutcomeResolution
from dnd.core.base_actions import TargetType
from dnd.core.equipment_types import WeaponSlot
from dnd.classes.fighter import ExtraAttack
from dnd.classes.rage import FrenziedStrike
from dnd.blocks.base_item import BaseItem
from dnd.core.aoe import Cone, Cube, Line, Sphere
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.items.environment_interactables import TrapLever
from tests.manual.authored_encounter_support import (
    assemble_authored_encounter,
    reset_authored_encounter_state,
)
from dnd.spells.abjuration import (
    Aid,
    DeathWard,
    FreedomOfMovement,
    MageArmor,
    ProtectionFromEnergy,
    ProtectionFromPoison,
    Resistance,
    Stoneskin,
)
from dnd.spells.enchantment import Sleep
from dnd.spells.illusion import Blur, GreaterInvisibility, MirrorImage
from dnd.spells.necromancy import BestowCurse, EyebiteStrike
from tests.manual.test_53_srd_monster_traits import _materialize_srd_fixture, reset_srd_trait_state
from tests.content_identity import synthetic_action_identity


@pytest.fixture(autouse=True)
def fresh_engine_runtime() -> None:
    """Each case builds its own world on an empty runtime."""
    reset_authored_encounter_state()


def test_epoch_bindings_preserve_exact_duplicate_named_action_sources() -> None:
    """Private execution authority binds rows by object identity, never display names."""
    arena = assemble_authored_encounter("sorcerer_barbarian_duel")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    discovered = actor.get_available_actions()
    source = next(row for row in discovered.entity_actions if row.valid_targets)
    duplicate = source.model_copy(deep=True, update={"display_name": "Second source"})
    actions = AvailableActionsResult(
        entity_uuid=actor.uuid,
        entity_actions=[source, duplicate],
    )

    affordances, authority = _build_affordance_set_and_execution_authority_from_actions(
        actor,
        actions,
        7,
    )
    rows = affordances.entity_actions

    assert len(rows) == 2
    assert rows[0].row_id != rows[1].row_id
    first_binding = authority.binding_for(rows[0])
    second_binding = authority.binding_for(rows[1])
    assert first_binding is not None
    assert second_binding is not None
    assert first_binding.action_info is source
    assert second_binding.action_info is duplicate
    assert first_binding.target is source.valid_targets[0]
    assert second_binding.target is duplicate.valid_targets[0]


def test_epoch_row_descriptor_cache_reuses_semantic_derivation(monkeypatch) -> None:
    """Repeated row metadata should not rebuild immutable semantic descriptors."""
    subjective_epochs_module.clear_epoch_value_caches()
    row = AvailableActionInfo(
        template_name="Dodge",
        semantic_key="dnd.actions.Dodge",
        **synthetic_action_identity(
            "action.epoch_cache_probe",
        ),
        target_type=TargetType.SELF,
        availability_status=ActionAvailabilityStatus.AVAILABLE,
        valid_targets=[AvailableTarget(index=0)],
        can_afford=True,
        display_name="Dodge",
        cost_type="actions",
        cost_amount=1,
        action_category=ActionCategory.ABILITY,
    )
    calls = 0
    original = subjective_epochs_module.action_semantics_for_available_action

    def counted_semantics(action_row):
        nonlocal calls
        calls += 1
        return original(action_row)

    monkeypatch.setattr(
        subjective_epochs_module,
        "action_semantics_for_available_action",
        counted_semantics,
    )
    first_catalog = {}
    first_references = {}
    second_catalog = {}
    second_references = {}

    first = subjective_epochs_module._describe_action_row(
        row,
        first_catalog,
        first_references,
    )
    second = subjective_epochs_module._describe_action_row(
        row,
        second_catalog,
        second_references,
    )

    assert calls == 1
    assert first == second
    assert first.semantics_ref in first_catalog
    assert second.semantics_ref in second_catalog


def test_epoch_row_id_falls_back_to_semantic_key_not_display_name() -> None:
    """Localized labels should not become command identity when template names are absent."""
    actor = Entity.create(name="Actor", source_entity_uuid=uuid4())
    first = AvailableActionInfo(
        template_name="",
        semantic_key="rules.localized.semantic_action",
        **synthetic_action_identity(
            "action.localized_epoch_probe",
        ),
        target_type=TargetType.POSITION,
        availability_status=ActionAvailabilityStatus.AVAILABLE,
        valid_targets=[AvailableTarget(index=0, position=(1, 2))],
        can_afford=True,
        display_name="Localized first label",
        cost_type="movement",
        cost_amount=5,
        action_category=ActionCategory.MOVEMENT,
    )
    second = first.model_copy(update={"display_name": "Localized second label"})
    actions = AvailableActionsResult(
        entity_uuid=actor.uuid,
        position_actions=[first, second],
    )

    affordances, authority = _build_affordance_set_and_execution_authority_from_actions(
        actor,
        actions,
        11,
    )

    row_ids = [row.row_id for row in affordances.position_actions]
    first_binding = authority.binding_for(affordances.position_actions[0])
    second_binding = authority.binding_for(affordances.position_actions[1])

    assert row_ids[0].startswith("position|rules.localized.semantic_action|pos=1,2")
    assert "Localized" not in " ".join(row_ids)
    assert len(row_ids) == len(set(row_ids))
    assert first_binding is not None
    assert second_binding is not None
    assert first_binding.action_info is first
    assert second_binding.action_info is second


def test_simple_entity_epoch_rows_are_lean_but_multi_entity_rows_keep_options() -> None:
    """Simple entity rows avoid duplicate targets while multi-target spells keep choices."""
    arena = assemble_authored_encounter("line_aoe_corridor")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    actions = mage.get_available_actions()
    direct_affordances = _build_affordance_set_from_actions(mage, actions, 42)

    simple_direct_rows = [
        row for row in direct_affordances.entity_actions
        if row.target_type != "multi_entity" and row.num_projectiles is None and row.allow_same_target is None
    ]
    direct_magic_missile_rows = [
        row for row in direct_affordances.entity_actions
        if row.template_name.startswith("Magic Missile")
    ]

    assert simple_direct_rows
    assert all(not row.target_options for row in simple_direct_rows)
    assert direct_magic_missile_rows
    assert all(row.target_type == "multi_entity" for row in direct_magic_missile_rows)
    assert all(row.target_options for row in direct_magic_missile_rows)


def test_spell_outcome_profiles_reach_epoch_without_registry_growth() -> None:
    """Rule-owned stochastic profiles are pure and reach typed epoch rows."""
    arena = assemble_authored_encounter("line_aoe_corridor")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    fire_template = next(action for action in mage.registered_actions if action.name == "Fire Bolt")
    missile_template = next(action for action in mage.registered_actions if action.name == "Magic Missile")
    root_registry_before = set(BaseObject._registry)
    value_registry_before = set(BaseValue._registry)

    fire_profile = fire_template.get_outcome_profile()
    missile_profile = missile_template.get_outcome_profile()

    assert set(BaseObject._registry) == root_registry_before
    assert set(BaseValue._registry) == value_registry_before
    assert fire_profile is not None
    assert fire_profile.resolution is OutcomeResolution.ATTACK_ROLL
    assert fire_profile.attack_bonus == mage.spell_attack_outcome_baseline().attack_bonus
    assert fire_profile.damage_rolls[0].dice_count == 2
    assert fire_profile.damage_rolls[0].die_size == 10
    assert missile_profile is not None
    assert missile_profile.resolution is OutcomeResolution.AUTOMATIC
    assert missile_profile.applications == 3

    actions = mage.get_available_actions()
    direct = _build_affordance_set_from_actions(mage, actions, 42)
    direct_fire = next(row for row in direct.entity_actions if row.template_name == "Fire Bolt")
    direct_missile = next(
        row for row in direct.entity_actions if row.template_name == "Magic Missile__slot_1"
    )

    assert direct_fire.outcome_profile is not None
    assert direct_missile.outcome_profile is not None
    assert direct_fire.outcome_profile.model_dump(mode="json") == fire_profile.model_dump(mode="json")
    assert direct_missile.outcome_profile.model_dump(mode="json") == missile_profile.model_dump(mode="json")


def test_eldritch_blast_outcome_profile_reaches_actor_capabilities() -> None:
    """A Warlock's ranged fallback remains quantified after legal rows expire."""
    arena = assemble_authored_encounter("skeleton_anti_aoe_split")
    warlock = next(monster for monster in arena.monsters if "Warlock" in monster.name)
    blast_template = next(
        action
        for action in warlock.registered_actions
        if action.name == "Eldritch Blast"
    )
    expected_profile = blast_template.get_outcome_profile()
    before = warlock.get_available_actions()

    blast_row = next(
        row
        for row in before.entity_actions
        if row.template_name == "Eldritch Blast"
    )
    assert blast_row.valid_targets

    result = execute_by_index(warlock, "Eldritch Blast", 0, available=before)

    assert result is not None
    assert result.canceled is False
    assert warlock.action_economy.actions.normalized_score == 0
    after = warlock.get_available_actions()
    affordances = _build_affordance_set_from_actions(warlock, after, 42)

    eldritch_blast = next(
        capability
        for capability in affordances.capabilities
        if capability.semantic_key.endswith("EldritchBlast")
    )
    assert eldritch_blast.normal_range_feet == 120
    assert expected_profile is not None
    assert eldritch_blast.outcome_profile is not None
    assert eldritch_blast.outcome_profile.model_dump(mode="json") == expected_profile.model_dump(mode="json")
    assert eldritch_blast.outcome_profile.resolution.value == "attack_roll"
    assert eldritch_blast.outcome_profile.damage_rolls[0].die_size == 10
    assert eldritch_blast.outcome_profile.damage_rolls[0].damage_type == "Force"


def test_execution_honest_necromancy_profiles_reach_actor_capabilities() -> None:
    """Epoch capabilities expose modeled necromancy damage profiles."""
    arena = assemble_authored_encounter("necrotic_anti_healing_duel")
    necromancer = next(
        monster
        for monster in arena.monsters
        if monster.name == "Validation Necromancer"
    )

    capabilities = {
        capability.semantic_key: capability
        for capability in _build_action_capabilities(necromancer, {})
    }

    chill = capabilities["dnd.spells.necromancy.ChillTouch"].outcome_profile
    finger = capabilities["dnd.spells.necromancy.FingerOfDeath"].outcome_profile
    assert chill is not None
    assert chill.resolution.value == "attack_roll"
    assert finger is not None
    assert finger.resolution.value == "saving_throw"
    blight = capabilities["dnd.spells.necromancy.Blight"].outcome_profile
    harm = capabilities["dnd.spells.necromancy.Harm"].outcome_profile
    assert blight is not None
    assert blight.resolution.value == "saving_throw"
    assert blight.damage_rolls[0].dice_count >= 8
    assert blight.damage_rolls[0].die_size == 8
    assert blight.half_damage_on_save is True
    assert harm is not None
    assert harm.resolution.value == "saving_throw"
    assert harm.damage_rolls[0].dice_count == 14
    assert harm.damage_rolls[0].die_size == 6
    assert harm.half_damage_on_save is True


def test_srd_inflict_wounds_epoch_exposes_melee_spell_attack_profile() -> None:
    """SRD caster melee spell attacks should carry actor-baseline damage."""
    reset_srd_trait_state()
    fanatic = _materialize_srd_fixture("cult_fanatic", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        fanatic,
        fanatic.get_available_actions(),
        42,
    )
    inflict = next(row for row in affordances.entity_actions if row.semantic_key == "dnd.spells.necromancy.InflictWounds")

    assert inflict.outcome_profile is not None
    assert inflict.outcome_profile.resolution.value == "attack_roll"
    assert inflict.outcome_profile.damage_rolls[0].dice_count == 3
    assert inflict.outcome_profile.damage_rolls[0].die_size == 10
    assert inflict.outcome_profile.damage_rolls[0].damage_type == "Necrotic"


def test_srd_command_epoch_exposes_save_control_target_effect() -> None:
    """SRD Command should disclose its save-based control branch."""
    reset_srd_trait_state()
    fanatic = _materialize_srd_fixture("cult_fanatic", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(4, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=60)

    affordances = _build_affordance_set_from_actions(
        fanatic,
        fanatic.get_available_actions(),
        42,
    )
    command = next(row for row in affordances.entity_actions if row.semantic_key == "dnd.spells.enchantment.Command")
    semantics = affordances.semantics_for(command)

    assert semantics.semantic_id == "control.command.grovel"
    assert ActionTag.CONTROL_SOFT in semantics.tags
    assert semantics.target_effects
    assert semantics.target_effects[0].save_ability == "wisdom"
    assert semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.enchantment.CommandGrovelEffect",
        "dnd.conditions.Prone",
    })


def test_condition_lock_control_spells_expose_target_effects() -> None:
    """Disabling arena spells should reach epochs as typed target effects."""
    arena = assemble_authored_encounter("condition_lock_sanctum")
    controller = next(monster for monster in arena.monsters if "Controller" in monster.name)
    controller.update_entity_senses(max_distance=60)

    affordances = _build_affordance_set_from_actions(
        controller,
        controller.get_available_actions(),
        42,
    )
    hold_person = next(
        row
        for row in affordances.entity_actions
        if row.semantic_key == "dnd.spells.enchantment.HoldPerson"
    )
    fear = next(
        row
        for row in affordances.position_actions
        if row.semantic_key == "dnd.spells.illusion.Fear"
    )
    hypnotic_pattern = next(
        row
        for row in affordances.position_actions
        if row.semantic_key == "dnd.spells.illusion.HypnoticPattern"
    )

    hold_semantics = affordances.semantics_for(hold_person)
    fear_semantics = affordances.semantics_for(fear)
    hypnotic_semantics = affordances.semantics_for(hypnotic_pattern)

    assert hold_semantics.semantic_id == "control.hold_person"
    assert ActionTag.CONTROL_HARD in hold_semantics.tags
    assert hold_semantics.target_effects
    assert hold_semantics.target_effects[0].save_ability == "wisdom"
    assert hold_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.enchantment.HoldPersonEffect",
        "dnd.conditions.Paralyzed",
    })

    assert fear_semantics.semantic_id == "control.fear"
    assert ActionTag.CONTROL_SOFT in fear_semantics.tags
    assert fear_semantics.target_effects
    assert fear_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.illusion.FearEffect",
        "dnd.conditions.Frightened",
    })

    assert hypnotic_semantics.semantic_id == "control.hypnotic_pattern"
    assert ActionTag.CONTROL_HARD in hypnotic_semantics.tags
    assert hypnotic_semantics.target_effects
    assert hypnotic_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.illusion.HypnoticPatternEffect",
        "dnd.conditions.Charmed",
    })


def test_sleep_epoch_exposes_hp_pool_agency_denial() -> None:
    """Sleep should disclose automatic unconsciousness and undead exclusion."""
    arena = assemble_authored_encounter("condition_lock_sanctum")
    support = next(monster for monster in arena.monsters if "Support" in monster.name)
    register_spell(support, Sleep, caster_level=5)
    support.update_entity_senses(max_distance=60)

    affordances = _build_affordance_set_from_actions(
        support,
        support.get_available_actions(),
        42,
    )
    sleep = next(
        row
        for row in affordances.position_actions
        if row.semantic_key == "dnd.spells.enchantment.Sleep"
    )
    semantics = affordances.semantics_for(sleep)

    assert semantics.semantic_id == "control.sleep"
    assert ActionTag.CONTROL_HARD in semantics.tags
    assert semantics.target_effects
    sleep_effect = semantics.target_effects[0]
    assert sleep_effect.outcome_kind is OutcomeKind.GUARANTEED
    assert sleep_effect.condition_semantic_keys == frozenset({
        "dnd.spells.enchantment.SleepEffect",
    })
    assert evaluate_fact_expression(
        sleep_effect.applicability,
        {"selected_target.creature_type": "undead"},
    ) is TruthValue.FALSE


def test_condition_lock_support_spells_expose_target_buffs() -> None:
    """Support rows should disclose the concrete buff/debuff they apply."""
    arena = assemble_authored_encounter("condition_lock_sanctum")
    support = next(monster for monster in arena.monsters if "Support" in monster.name)
    support.update_entity_senses(max_distance=60)

    affordances = _build_affordance_set_from_actions(
        support,
        support.get_available_actions(),
        42,
    )
    bless = next(
        row
        for row in affordances.entity_actions
        if row.semantic_key == "dnd.spells.enchantment.Bless"
    )
    bane = next(
        row
        for row in affordances.entity_actions
        if row.semantic_key == "dnd.spells.enchantment.Bane"
    )
    shield = next(
        row
        for row in affordances.entity_actions
        if row.semantic_key == "dnd.spells.abjuration.ShieldOfFaith"
    )
    sanctuary = next(
        row
        for row in affordances.entity_actions
        if row.semantic_key == "dnd.spells.abjuration.Sanctuary"
    )

    bless_semantics = affordances.semantics_for(bless)
    bane_semantics = affordances.semantics_for(bane)
    shield_semantics = affordances.semantics_for(shield)
    sanctuary_semantics = affordances.semantics_for(sanctuary)

    assert bless_semantics.semantic_id == "support.bless"
    assert ActionTag.SUPPORT_BUFF in bless_semantics.tags
    assert bless_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.enchantment.BlessEffect",
    })

    assert bane_semantics.semantic_id == "control.bane"
    assert ActionTag.CONTROL_SOFT in bane_semantics.tags
    assert bane_semantics.target_effects[0].save_ability == "charisma"
    assert bane_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.enchantment.BaneEffect",
    })

    assert shield_semantics.semantic_id == "support.shield_of_faith"
    assert shield_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.abjuration.ShieldOfFaithEffect",
    })
    assert sanctuary_semantics.semantic_id == "support.sanctuary"
    assert sanctuary_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.abjuration.SanctuaryEffect",
    })


def test_zone_and_removal_control_spells_expose_profiles() -> None:
    """Zone/removal spell rows should not collapse to generic spell damage."""
    arena = assemble_authored_encounter("condition_lock_sanctum")
    controller = next(monster for monster in arena.monsters if "Controller" in monster.name)
    controller.update_entity_senses(max_distance=80)
    controller_affordances = _build_affordance_set_from_actions(
        controller,
        controller.get_available_actions(),
        42,
    )
    banishment = next(
        row
        for row in controller_affordances.entity_actions
        if row.semantic_key == "dnd.spells.abjuration.Banishment"
    )
    slow = next(
        row
        for row in controller_affordances.position_actions
        if row.semantic_key == "dnd.spells.transmutation.Slow"
    )

    banishment_semantics = controller_affordances.semantics_for(banishment)
    slow_semantics = controller_affordances.semantics_for(slow)

    assert banishment_semantics.semantic_id == "control.banishment"
    assert ActionTag.CONTROL_HARD in banishment_semantics.tags
    assert banishment_semantics.target_effects[0].save_ability == "charisma"
    assert banishment_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.abjuration.BanishedCondition",
    })

    assert slow_semantics.semantic_id == "control.slow"
    assert ActionTag.CONTROL_SOFT in slow_semantics.tags
    assert slow_semantics.target_effects[0].save_ability == "wisdom"
    assert slow_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.transmutation.SlowedEffect",
    })

    zone_arena = assemble_authored_encounter("zone_control_web_gauntlet")
    mage = next(monster for monster in zone_arena.monsters if "Web Mage" in monster.name)
    mage.update_entity_senses(max_distance=80)
    zone_affordances = _build_affordance_set_from_actions(
        mage,
        mage.get_available_actions(),
        42,
    )
    grease = next(
        row
        for row in zone_affordances.position_actions
        if row.semantic_key == "dnd.spells.conjuration.Grease"
    )
    web = next(
        row
        for row in zone_affordances.position_actions
        if row.semantic_key == "dnd.spells.conjuration.Web"
    )
    spike_growth = next(
        row
        for row in zone_affordances.position_actions
        if row.semantic_key == "dnd.spells.transmutation.SpikeGrowth"
    )
    invisibility = next(
        row
        for row in zone_affordances.entity_actions
        if row.semantic_key == "dnd.spells.illusion.Invisibility"
    )

    grease_semantics = zone_affordances.semantics_for(grease)
    web_semantics = zone_affordances.semantics_for(web)
    spike_semantics = zone_affordances.semantics_for(spike_growth)
    invisibility_semantics = zone_affordances.semantics_for(invisibility)

    assert grease_semantics.semantic_id == "control.grease"
    assert grease_semantics.target_effects[0].condition_semantic_keys == frozenset({"dnd.conditions.Prone"})
    assert web_semantics.semantic_id == "control.web"
    assert web_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.conjuration.WebRestrained",
        "dnd.conditions.Restrained",
    })

    assert spike_semantics.semantic_id == "control.spike_growth"
    assert ActionTag.DAMAGE_AREA in spike_semantics.tags
    assert ActionTag.ZONE_PERSISTENT in spike_semantics.tags
    assert spike_semantics.topology_effects[0].operation is TopologyOperation.CREATE_HAZARD

    assert invisibility_semantics.semantic_id == "defense.invisibility"
    assert invisibility_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.conditions.InvisibilityEffect",
    })


def test_defensive_spell_profile_hooks_are_valid_contracts() -> None:
    """Defensive spells outside the starting arenas should still declare facts."""
    reset_srd_trait_state()
    caster = _materialize_srd_fixture("priest", position=(1, 1), faction="monsters")
    expected = (
        (Aid, "support.aid", "dnd.spells.abjuration.AidEffect"),
        (DeathWard, "support.death_ward", "dnd.spells.abjuration.DeathWardEffect"),
        (FreedomOfMovement, "support.freedom_of_movement", "dnd.spells.abjuration.FreedomOfMovementEffect"),
        (MageArmor, "support.mage_armor", "dnd.spells.abjuration.MageArmorCondition"),
        (ProtectionFromEnergy, "support.protection_from_energy.fire", "dnd.spells.abjuration.ProtectionFromEnergyEffect"),
        (ProtectionFromPoison, "support.protection_from_poison", "dnd.spells.abjuration.ProtectionFromPoisonEffect"),
        (Resistance, "support.resistance", "dnd.spells.abjuration.ResistanceEffect"),
        (Stoneskin, "support.stoneskin", "dnd.spells.abjuration.StoneskinEffect"),
        (Blur, "defense.blur", "dnd.spells.illusion.BlurEffect"),
        (GreaterInvisibility, "defense.greater_invisibility", "dnd.conditions.GreaterInvisibilityEffect"),
        (MirrorImage, "defense.mirror_image", "dnd.spells.illusion.MirrorImageEffect"),
    )

    for spell_cls, semantic_id, condition_key in expected:
        spell = spell_cls(source_entity_uuid=caster.uuid, template=True)
        profile = spell.get_target_effect_profile()

        assert profile is not None
        assert profile.semantic_id == semantic_id
        assert condition_key in profile.branches[0].condition_semantic_keys
        assert profile.branches[0].disposition.value == "beneficial"


def test_blindness_deafness_epoch_exposes_save_control_target_effect() -> None:
    """Blindness/Deafness should disclose its save-based condition branch."""
    arena = assemble_authored_encounter("necrotic_anti_healing_duel")
    necromancer = next(
        monster
        for monster in arena.monsters
        if monster.name == "Validation Necromancer"
    )
    necromancer.update_entity_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        necromancer,
        necromancer.get_available_actions(),
        42,
    )
    blindness = next(row for row in affordances.entity_actions if row.semantic_key == "dnd.spells.necromancy.BlindnessDeafness")
    semantics = affordances.semantics_for(blindness)

    assert semantics.semantic_id == "control.blindness_deafness.blinded"
    assert ActionTag.CONTROL_SOFT in semantics.tags
    assert semantics.target_effects
    assert semantics.target_effects[0].save_ability == "constitution"
    assert semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.necromancy.BlindnessDeafnessEffect",
        "dnd.conditions.Blinded",
    })


def test_bestow_curse_and_eyebite_strike_expose_selected_condition_branches() -> None:
    """Complex necromancy control actions should disclose the selected branch."""
    reset_srd_trait_state()
    caster = _materialize_srd_fixture("priest", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    caster.register_action(BestowCurse(
        source_entity_uuid=caster.uuid,
        template=True,
        curse_option=3,
    ))
    caster.register_action(EyebiteStrike(
        source_entity_uuid=caster.uuid,
        template=True,
        spell_dc=15,
        effect_choice="asleep",
    ))
    Entity.update_all_entities_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        caster,
        caster.get_available_actions(),
        42,
    )
    bestow = next(row for row in affordances.entity_actions if row.semantic_key == "dnd.spells.necromancy.BestowCurse")
    bestow_semantics = affordances.semantics_for(bestow)
    eyebite_profile = EyebiteStrike(
        source_entity_uuid=caster.uuid,
        template=True,
        spell_dc=15,
        effect_choice="asleep",
    ).get_target_effect_profile()

    assert bestow_semantics.semantic_id == "control.bestow_curse.option_3"
    assert bestow_semantics.target_effects
    assert bestow_semantics.target_effects[0].save_ability == "wisdom"
    assert bestow_semantics.target_effects[0].condition_semantic_keys == frozenset({
        "dnd.spells.necromancy.InactionCurseEffect",
    })

    assert eyebite_profile is not None
    assert eyebite_profile.semantic_id == "control.eyebite.asleep"
    assert eyebite_profile.branches[0].save_dc == 15
    assert eyebite_profile.branches[0].condition_semantic_keys == frozenset({
        "dnd.spells.necromancy.EyebiteAsleepEffect",
    })


def test_extra_attack_resource_is_normalized_as_attack_economy() -> None:
    """Granted extra attacks are typed economy, not generic limited resources."""
    profile = _action_cost_profile_from_cost_rows(
        [
            BaseCost(
                name="Extra Attack",
                cost_type="actions",
                cost=0,
                resource_name="extra_attacks",
                resource_cost=1,
            )
        ],
        can_afford=True,
    )

    assert profile.consumes_attack_slot is True
    assert profile.resource_costs == {}


def test_weapon_attack_wrappers_share_one_stochastic_profile() -> None:
    """Normal, granted, and frenzy attacks publish the same weapon outcome."""
    arena = assemble_authored_encounter("caster_crossfire")
    barbarian = arena.hero
    normal = next(
        action
        for action in barbarian.registered_actions
        if action.name == "Attack_MELEE_MAIN"
    )
    extra = ExtraAttack(
        source_entity_uuid=barbarian.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=True,
    )
    frenzy = FrenziedStrike(
        source_entity_uuid=barbarian.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=True,
    )
    root_registry_before = set(BaseObject._registry)
    value_registry_before = set(BaseValue._registry)

    normal_profile = normal.get_outcome_profile()
    extra_profile = extra.get_outcome_profile()
    frenzy_profile = frenzy.get_outcome_profile()

    assert set(BaseObject._registry) == root_registry_before
    assert set(BaseValue._registry) == value_registry_before
    assert normal_profile is not None
    assert extra_profile == normal_profile
    assert frenzy_profile == normal_profile


def test_visible_environment_interaction_is_a_capability_before_it_is_legal() -> None:
    """A known lever remains plannable at range without becoming an executable row."""
    arena = assemble_authored_encounter("trap_lever_killzone")
    assert arena.environment is not None
    lever = arena.environment.trap_lever
    assert isinstance(lever, TrapLever)
    hero = arena.hero
    hero.update_entity_senses(max_distance=20)

    distant = _build_affordance_set_from_actions(
        hero,
        hero.get_available_actions(),
        42,
    )
    capability = next(
        row
        for row in distant.capabilities
        if row.source_item_uuid == str(lever.uuid)
    )
    capability_semantics = distant.semantic_catalog[capability.semantics_ref]

    assert all(row.source_item_uuid != str(lever.uuid) for row in distant.all_rows)
    assert capability.semantic_id == "interaction.trap.deactivate"
    assert capability_semantics.semantic_id == "interaction.trap.deactivate"

    lever_guard = next(
        monster
        for monster in arena.monsters
        if monster.name == "Validation Lever Guard"
    )
    lever_guard.update_entity_senses(max_distance=20)
    adjacent = _build_affordance_set_from_actions(
        lever_guard,
        lever_guard.get_available_actions(),
        43,
    )
    legal_row = next(
        row
        for row in adjacent.all_rows
        if row.source_item_uuid == str(lever.uuid)
    )

    assert legal_row.semantic_id == capability.semantic_id
    assert adjacent.semantic_catalog[legal_row.semantics_ref] == capability_semantics


def test_sorcerer_epoch_carries_metamagic_transforms_and_base_spell_levels() -> None:
    """Real discovery exposes transform contracts plus intrinsic spell-level inputs."""
    arena = assemble_authored_encounter("standard_skeleton_doors")
    sorcerer = arena.hero
    sorcerer.update_entity_senses(max_distance=20)

    affordances = _build_affordance_set_from_actions(
        sorcerer,
        sorcerer.get_available_actions(),
        42,
    )

    quickened = next(
        row for row in affordances.self_actions
        if row.semantic_key == "dnd.classes.sorcerer.QuickenedSpell"
    )
    twinned = next(
        row for row in affordances.self_actions
        if row.semantic_key == "dnd.classes.sorcerer.TwinnedSpell"
    )
    assert affordances.semantics_for(quickened).capability_transformations
    assert affordances.semantics_for(twinned).capability_transformations
    spell_levels = {
        capability.semantic_key: capability.base_spell_level
        for capability in affordances.capabilities
        if capability.action_category == "spell"
    }
    assert spell_levels["dnd.spells.evocation.FireBolt"] == 0
    assert spell_levels["dnd.spells.evocation.MagicMissile"] == 1
    unknown_capabilities = {
        capability.semantic_key
        for capability in affordances.capabilities
        if affordances.semantic_catalog[capability.semantics_ref].semantic_id
        == "action.unknown"
    }
    assert unknown_capabilities == set()


def test_srd_natural_attack_epoch_uses_natural_damage_profile() -> None:
    """Natural weapon rows should carry natural damage, not equipped proxy damage."""
    reset_srd_trait_state()
    gnoll = _materialize_srd_fixture("gnoll", position=(1, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        gnoll,
        gnoll.get_available_actions(),
        42,
    )
    bite = next(row for row in affordances.entity_actions if row.template_name == "Bite")

    assert str(target.uuid) in bite.row_id
    assert bite.outcome_profile is not None
    assert bite.outcome_profile.effect_id == "natural_attack.bite"
    assert bite.outcome_profile.damage_rolls[0].die_size == 4
    assert bite.outcome_profile.damage_rolls[0].damage_type == "Piercing"
    semantics = affordances.semantics_for(bite)
    assert ActionTag.ATTACK_WEAPON in semantics.tags
    assert ActionTag.DAMAGE_SINGLE_TARGET in semantics.tags


def test_srd_attack_riders_compose_damage_and_control_semantics() -> None:
    """Hit riders should add target effects without replacing attack damage."""
    reset_srd_trait_state()
    wolf = _materialize_srd_fixture("wolf", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        wolf,
        wolf.get_available_actions(),
        42,
    )
    bite = next(row for row in affordances.entity_actions if row.weapon_name == "Bite")
    semantics = affordances.semantics_for(bite)

    assert semantics.semantic_id == "attack.hit_rider.prone"
    assert ActionTag.ATTACK_WEAPON in semantics.tags
    assert ActionTag.DAMAGE_SINGLE_TARGET in semantics.tags
    assert ActionTag.CONTROL_SOFT in semantics.tags
    assert semantics.target_effects
    assert semantics.target_effects[0].save_dc == 11
    assert semantics.target_effects[0].save_ability == "strength"
    assert semantics.target_effects[0].condition_semantic_keys == frozenset({"dnd.conditions.Prone"})


def test_srd_uniform_multiattack_epoch_exposes_repeated_profile() -> None:
    """Uniform Multiattack rows should reach epochs as repeated applications."""
    reset_srd_trait_state()
    scout = _materialize_srd_fixture("scout", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(6, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=60)

    affordances = _build_affordance_set_from_actions(
        scout,
        scout.get_available_actions(),
        42,
    )
    longbow = next(row for row in affordances.entity_actions if row.template_name == "Scout Multiattack: Longbow")
    semantics = affordances.semantics_for(longbow)

    assert longbow.outcome_profile is not None
    assert longbow.outcome_profile.effect_id == "multiattack.scout_multiattack_longbow"
    assert longbow.outcome_profile.applications == 2
    assert longbow.outcome_profile.damage_rolls[0].die_size == 8
    assert ActionTag.ATTACK_WEAPON in semantics.tags
    assert ActionTag.DAMAGE_SINGLE_TARGET in semantics.tags


def test_srd_actor_known_bonus_damage_reaches_epoch_profiles() -> None:
    """Actor-baseline bonus damage should be present in controller epochs."""
    reset_srd_trait_state()
    bugbear = _materialize_srd_fixture("bugbear", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    affordances = _build_affordance_set_from_actions(
        bugbear,
        bugbear.get_available_actions(),
        42,
    )
    morningstar = next(row for row in affordances.entity_actions if row.weapon_name == "Morningstar")

    assert morningstar.outcome_profile is not None
    assert len(morningstar.outcome_profile.damage_rolls) == 2
    assert morningstar.outcome_profile.damage_rolls[1].die_size == 8
    assert morningstar.outcome_profile.damage_rolls[1].flat_bonus == 0
    assert morningstar.outcome_profile.damage_rolls[1].damage_type == "Piercing"


def test_srd_active_monster_actions_reach_setup_semantics() -> None:
    """Active SRD monster traits should be typed setup rows in epochs."""
    reset_srd_trait_state()
    priest = _materialize_srd_fixture("priest", position=(1, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=30)
    priest_affordances = _build_affordance_set_from_actions(
        priest,
        priest.get_available_actions(),
        42,
    )
    divine_eminence = next(row for row in priest_affordances.self_actions if row.template_name == "Divine Eminence")
    divine_semantics = priest_affordances.semantics_for(divine_eminence)

    assert divine_semantics.semantic_id == "setup.divine_eminence"
    assert ActionTag.SETUP_SELF in divine_semantics.tags
    assert ActionTag.SUPPORT_BUFF in divine_semantics.tags
    assert divine_semantics.self_setup is not None
    assert divine_semantics.self_setup.increases_weapon_damage is True

    reset_srd_trait_state()
    knight = _materialize_srd_fixture("knight", position=(1, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=30)
    knight_affordances = _build_affordance_set_from_actions(
        knight,
        knight.get_available_actions(),
        42,
    )
    leadership = next(row for row in knight_affordances.self_actions if row.template_name == "Leadership")
    leadership_semantics = knight_affordances.semantics_for(leadership)

    assert leadership_semantics.semantic_id == "support.leadership"
    assert ActionTag.SETUP_SELF in leadership_semantics.tags
    assert ActionTag.SUPPORT_BUFF in leadership_semantics.tags
    assert leadership_semantics.self_setup is not None
    assert leadership_semantics.self_setup.maximum_duration_rounds == 10


def test_aoe_discovery_reuses_preview_rows_for_upcast_variants(monkeypatch) -> None:
    """Upcast AoE variants do not recompute identical shape previews per slot."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    compute_calls: Counter[str] = Counter()
    original = Entity._compute_aoe_at_position

    def wrapped_compute(
        self,
        shape,
        shape_definition_key,
        position,
        template,
        *args,
        **kwargs,
    ):
        compute_calls[template.get_discovery_template_name()] += 1
        return original(
            self,
            shape,
            shape_definition_key,
            position,
            template,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(Entity, "_compute_aoe_at_position", wrapped_compute)
    actions = archmage.get_available_actions()
    fireball_actions = [
        action
        for action in actions.position_actions
        if action.template_name.startswith("Fireball__slot_")
    ]

    assert [action.template_name for action in fireball_actions] == [
        "Fireball__slot_3",
        "Fireball__slot_4",
        "Fireball__slot_5",
    ]
    assert len({len(action.valid_targets) for action in fireball_actions}) == 1
    assert fireball_actions[0].valid_targets
    assert compute_calls["Fireball__slot_3"] > 0
    assert compute_calls["Fireball__slot_4"] == 0
    assert compute_calls["Fireball__slot_5"] == 0


def test_epoch_reuses_immutable_targets_shared_by_spell_variants() -> None:
    """Flattened upcast rows retain one typed target value per engine preview."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    affordances = _build_affordance_set_from_actions(
        archmage,
        archmage.get_available_actions(),
        42,
    )
    fireball_rows = [
        row
        for row in affordances.position_actions
        if row.template_name.startswith("Fireball__slot_")
    ]
    rows_by_variant: dict[str, dict[tuple[int, int], object]] = {}
    for row in fireball_rows:
        target = row.targets[0]
        assert target.position is not None
        rows_by_variant.setdefault(row.template_name, {})[target.position] = target

    shared_position = next(iter(rows_by_variant["Fireball__slot_3"]))
    assert rows_by_variant["Fireball__slot_3"][shared_position] is (
        rows_by_variant["Fireball__slot_4"][shared_position]
    )
    assert rows_by_variant["Fireball__slot_4"][shared_position] is (
        rows_by_variant["Fireball__slot_5"][shared_position]
    )


def test_multi_target_wire_round_trip_reuses_canonical_target_pool() -> None:
    """Parsed selected rows and source options share one immutable target value."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    affordances = _build_affordance_set_from_actions(
        archmage,
        archmage.get_available_actions(),
        42,
    )

    restored = AffordanceSet.model_validate_json(affordances.model_dump_json())
    missile_rows = [
        row
        for row in restored.entity_actions
        if row.template_name.startswith("Magic Missile__slot_")
    ]

    assert missile_rows
    for row in missile_rows:
        selected = row.targets[0]
        matching_option = next(
            option
            for option in row.target_options
            if option.target_uuid == selected.target_uuid
        )
        assert selected is matching_option


def test_aoe_discovery_reads_visible_field_once_per_query_context() -> None:
    """AoE candidates share one immutable snapshot of caster-visible cells."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)

    class CountingVisibleMap(dict[tuple[int, int], bool]):
        """Track full visibility scans while preserving normal mapping behavior."""

        items_calls: int = 0

        def items(self):
            self.items_calls += 1
            return super().items()

    visible = CountingVisibleMap(archmage.senses.visible)
    archmage.senses.visible = visible
    discovery_variants = {
        template.uuid: template.get_discovery_variants(archmage)
        for template in archmage.registered_actions
    }

    actions = archmage._collect_aoe_actions(
        include_dead=False,
        fov_cache={},
        barrier_positions=get_map().get_barrier_positions(),
        discovery_variants=discovery_variants,
    )

    assert actions
    assert sum(len(action.valid_targets) for action in actions) > 10
    assert visible.items_calls <= 3


def test_aoe_discovery_caches_empty_previews_for_upcast_variants(monkeypatch) -> None:
    """Empty AoE previews are shared across slots and unchanged epochs."""
    arena = assemble_authored_encounter("skeleton_anti_aoe_split")
    warlock = next(monster for monster in arena.monsters if "Warlock" in monster.name)
    warlock.update_entity_senses(max_distance=20)
    compute_calls: Counter[str] = Counter()
    original = Entity._compute_aoe_at_position

    def wrapped_compute(
        self,
        shape,
        shape_definition_key,
        position,
        template,
        *args,
        **kwargs,
    ):
        compute_calls[template.get_discovery_template_name()] += 1
        return original(
            self,
            shape,
            shape_definition_key,
            position,
            template,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(Entity, "_compute_aoe_at_position", wrapped_compute)
    first_actions = warlock.get_available_actions()
    first_counts = compute_calls.copy()
    second_actions = warlock.get_available_actions()

    first_empty_aoes = [
        action
        for action in first_actions.position_actions
        if action.template_name.startswith(("Burning Hands__slot_", "Thunderwave__slot_"))
    ]
    second_empty_aoes = [
        action
        for action in second_actions.position_actions
        if action.template_name.startswith(("Burning Hands__slot_", "Thunderwave__slot_"))
    ]
    assert first_empty_aoes
    assert second_empty_aoes
    assert all(
        action.availability_status is ActionAvailabilityStatus.NO_VALID_TARGETS
        and not action.valid_targets
        for action in (*first_empty_aoes, *second_empty_aoes)
    )
    assert not [
        action
        for action in warlock.get_available_actions(legal_only=True).position_actions
        if action.template_name.startswith(("Burning Hands__slot_", "Thunderwave__slot_"))
    ]
    assert first_counts["Burning Hands__slot_1"] > 0
    assert first_counts["Burning Hands__slot_2"] == 0
    assert first_counts["Thunderwave__slot_1"] > 0
    assert first_counts["Thunderwave__slot_2"] == 0
    assert compute_calls == first_counts


def test_aoe_discovery_cache_key_covers_complete_shape_definition() -> None:
    """AoE previews with different cone angles cannot share cached targets."""
    arena = assemble_authored_encounter("condition_lock_sanctum")
    support = next(monster for monster in arena.monsters if "Support" in monster.name)
    burning_hands = next(
        action
        for action in support.position_actions
        if action.name == "Burning Hands"
    )
    assert isinstance(burning_hands.aoe_shape, Cone)
    narrow = burning_hands.model_copy(
        update={"aoe_shape": burning_hands.aoe_shape.model_copy(update={"angle_degrees": 30})}
    )
    wide = burning_hands.model_copy(
        update={"aoe_shape": burning_hands.aoe_shape.model_copy(update={"angle_degrees": 90})}
    )
    valid_positions = [(10, 5), (10, 6)]
    narrow_key = support._aoe_discovery_cache_key(
        narrow,
        valid_positions,
        include_dead=False,
        shape_definition_key=support._aoe_shape_definition_key(narrow.aoe_shape),
    )
    wide_key = support._aoe_discovery_cache_key(
        wide,
        valid_positions,
        include_dead=False,
        shape_definition_key=support._aoe_shape_definition_key(wide.aoe_shape),
    )

    assert narrow_key != wide_key


def test_directional_aoe_footprint_keys_match_geometry_equivalence() -> None:
    """Directional footprints share rays while centered shapes keep centers."""
    source_uuid = uuid4()
    caster_position = (5, 5)
    cone = Cone(source_entity_uuid=source_uuid, target=(6, 6), length_feet=30)
    line = Line(source_entity_uuid=source_uuid, target=(6, 6), length_feet=30)
    directional_cube = Cube(
        source_entity_uuid=source_uuid,
        target=(6, 6),
        size_feet=15,
        centered=False,
    )
    sphere = Sphere(source_entity_uuid=source_uuid, target=(6, 6), radius_feet=20)
    centered_cube = Cube(
        source_entity_uuid=source_uuid,
        target=(6, 6),
        size_feet=15,
        centered=True,
    )

    assert cone.footprint_target_key(caster_position) == cone.model_copy(
        update={"target": (9, 9)}
    ).footprint_target_key(caster_position)
    assert line.footprint_target_key(caster_position) == line.model_copy(
        update={"target": (8, 8)}
    ).footprint_target_key(caster_position)
    assert directional_cube.footprint_target_key(caster_position) == (
        directional_cube.model_copy(update={"target": (12, 6)}).footprint_target_key(
            caster_position
        )
    )
    assert sphere.footprint_target_key(caster_position) != sphere.model_copy(
        update={"target": (9, 9)}
    ).footprint_target_key(caster_position)
    assert centered_cube.footprint_target_key(caster_position) != (
        centered_cube.model_copy(update={"target": (9, 9)}).footprint_target_key(
            caster_position
        )
    )


def test_aoe_occupancy_resolution_uses_only_subjective_entity_positions(
    monkeypatch,
) -> None:
    """Preview occupancy never consults objective grid entity placement."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    visible_uuid, visible_position = next(iter(archmage.senses.entities.items()))
    shape = Sphere(
        source_entity_uuid=archmage.uuid,
        target=visible_position,
        radius_feet=20,
    )
    shape.computed_origin = visible_position
    shape.affected_positions = {visible_position, archmage.position}

    def reject_objective_lookup(_position):
        raise AssertionError("subjective preview consulted objective occupancy")

    monkeypatch.setattr(get_map(), "get_entities_at", reject_objective_lookup)
    shape._resolve_subjective_entities(
        archmage.position,
        archmage.senses,
        archmage.uuid,
    )

    assert shape.affected_entity_uuids == {visible_uuid, archmage.uuid}


def test_aoe_discovery_reuses_footprints_until_subjective_topology_changes(
    monkeypatch,
) -> None:
    """Repeated discovery reuses pure footprints and invalidates on blockers."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    compute_calls = 0
    original_compute = Entity._compute_aoe_propagation_footprint

    def track_compute(self, *args, **kwargs):
        nonlocal compute_calls
        compute_calls += 1
        return original_compute(self, *args, **kwargs)

    monkeypatch.setattr(Entity, "_compute_aoe_propagation_footprint", track_compute)
    archmage.get_available_actions()
    first_compute_calls = compute_calls
    archmage.get_available_actions()

    assert first_compute_calls > 0
    assert compute_calls == first_compute_calls

    wall = BaseItem(
        source_entity_uuid=archmage.uuid,
        name="AoE Preview Cache Wall",
        is_pickable=False,
        blocks_vision_field=True,
    )
    get_map().place_object(wall.uuid, (7, 7))
    archmage.get_available_actions()

    assert compute_calls > first_compute_calls


def test_aoe_discovery_reuses_previews_until_subjective_contacts_change(
    monkeypatch,
) -> None:
    """Repeated discovery caches previews against subjective contact facts."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    compute_calls = 0
    original_compute = Entity._compute_aoe_at_position

    def track_compute(self, *args, **kwargs):
        nonlocal compute_calls
        compute_calls += 1
        return original_compute(self, *args, **kwargs)

    monkeypatch.setattr(Entity, "_compute_aoe_at_position", track_compute)
    archmage.get_available_actions()
    first_compute_calls = compute_calls
    archmage.get_available_actions()

    assert first_compute_calls > 0
    assert compute_calls == first_compute_calls

    contact_uuid, old_position = next(iter(archmage.senses.entities.items()))
    visible_positions = [
        position
        for position, is_visible in archmage.senses.visible.items()
        if is_visible and position != old_position
    ]
    archmage.senses.entities[contact_uuid] = visible_positions[0]
    archmage.get_available_actions()

    assert compute_calls > first_compute_calls


def test_move_discovery_reuses_subjective_path_projection(monkeypatch) -> None:
    """Movement rows reuse projected paths and costs without rescanning paths."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    path_cost_calls = 0
    original_cost = Entity.movement_path_cost_feet

    def track_cost(self, *args, **kwargs):
        nonlocal path_cost_calls
        path_cost_calls += 1
        return original_cost(self, *args, **kwargs)

    monkeypatch.setattr(Entity, "movement_path_cost_feet", track_cost)
    first_actions = archmage.get_available_actions()
    first_path_cost_calls = path_cost_calls
    second_actions = archmage.get_available_actions()

    assert first_path_cost_calls == 0
    assert path_cost_calls == 0
    first_move = next(
        action for action in first_actions.position_actions
        if action.template_name == "Move"
    )
    second_move = next(
        action for action in second_actions.position_actions
        if action.template_name == "Move"
    )
    assert first_move.valid_targets == second_move.valid_targets
    assert archmage.senses.path_costs

    remaining_movement = archmage.action_economy.movement_remaining()
    archmage._collect_path_actions(remaining_movement - 5)

    assert path_cost_calls == 0


def test_position_spell_rows_preserve_variants_costs_and_semantics() -> None:
    """Plain position spells retain spell metadata through discovery."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)

    actions = archmage.get_available_actions()
    cloudkill_rows = [
        row
        for row in actions.position_actions
        if row.template_name.startswith("Cloudkill")
    ]
    dimension_door_rows = [
        row
        for row in actions.position_actions
        if row.template_name.startswith("Dimension Door")
    ]

    assert [row.template_name for row in cloudkill_rows] == ["Cloudkill__slot_5"]
    assert [row.template_name for row in dimension_door_rows] == [
        "Dimension Door__slot_4",
        "Dimension Door__slot_5",
    ]
    assert all(row.action_category.value == "spell" for row in cloudkill_rows)
    assert all(row.action_category.value == "spell" for row in dimension_door_rows)
    assert any(cost.cost_type == "spell_slot_5" for cost in cloudkill_rows[0].costs)
    assert any(cost.cost_type == "spell_slot_4" for cost in dimension_door_rows[0].costs)

    affordances = _build_affordance_set_from_actions(archmage, actions, 42)
    dimension_door = next(
        row
        for row in affordances.position_actions
        if row.template_name == "Dimension Door__slot_4"
    )
    dimension_semantics = affordances.semantics_for(dimension_door)
    assert dimension_semantics.semantic_id == "movement.teleport.dimension_door"
    assert ActionTag.MOVEMENT_TELEPORT in dimension_semantics.tags
    assert dimension_semantics.spatial is not None
    assert dimension_semantics.spatial.movement_kind is MovementKind.TELEPORT
    assert dimension_semantics.spatial.ignores_intermediate_cells is True


def test_teleport_escape_rows_expose_mobility_semantics() -> None:
    """Short-range teleport rows should be visible as escape/reposition tools."""
    arena = assemble_authored_encounter("teleport_escape_skirmish")
    mage = next(monster for monster in arena.monsters if "Escape Mage" in monster.name)
    mage.update_entity_senses(max_distance=80)

    affordances = _build_affordance_set_from_actions(
        mage,
        mage.get_available_actions(),
        42,
    )
    misty_step = next(
        row
        for row in affordances.position_actions
        if row.semantic_key == "dnd.spells.conjuration.MistyStep"
    )
    semantics = affordances.semantics_for(misty_step)

    assert semantics.semantic_id == "movement.teleport.misty_step"
    assert ActionTag.MOVEMENT_TELEPORT in semantics.tags
    assert semantics.spatial is not None
    assert semantics.spatial.movement_kind is MovementKind.TELEPORT
    assert semantics.spatial.ignores_intermediate_cells is True


def test_position_spell_discovery_does_not_leak_unseen_occupancy() -> None:
    """A hidden occupant cannot remove a subjectively valid destination row."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    hidden_entity = arena.hero
    hidden_position = hidden_entity.position

    assert hidden_entity.uuid in archmage.senses.entities
    archmage.senses.entities.pop(hidden_entity.uuid)
    actions = archmage.get_available_actions()
    dimension_door = next(
        row
        for row in actions.position_actions
        if row.template_name == "Dimension Door__slot_4"
    )

    assert any(target.position == hidden_position for target in dimension_door.valid_targets)


def test_visible_position_spell_targets_are_not_limited_to_walkable_paths() -> None:
    """Ground-zone spells can target visible occupied cells with no move path."""
    arena = assemble_authored_encounter("zone_control_web_gauntlet")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    occupied_positions = {contact.position for contact in mage.senses.entities.values()}

    assert occupied_positions
    assert all(position not in mage.senses.paths for position in occupied_positions)
    actions = mage.get_available_actions()
    web = next(
        row
        for row in actions.position_actions
        if row.template_name == "Web__slot_2"
    )

    assert occupied_positions <= {
        target.position
        for target in web.valid_targets
        if target.position is not None
    }


def test_position_spell_variants_reuse_subjective_target_projection(
    monkeypatch,
) -> None:
    """Equivalent position variants share one subjective destination scan."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    walkability_checks = 0
    original_check = Entity._is_subjectively_walkable_position

    def track_check(self, *args, **kwargs):
        nonlocal walkability_checks
        walkability_checks += 1
        return original_check(self, *args, **kwargs)

    monkeypatch.setattr(Entity, "_is_subjectively_walkable_position", track_check)
    archmage.get_available_actions()
    first_checks = walkability_checks
    archmage.get_available_actions()

    assert first_checks > 0
    assert walkability_checks == first_checks


def test_jump_discovery_exposes_subjective_distance_and_movement_cost() -> None:
    """Jump candidates carry the same distance bound used by action economy."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)

    actions = archmage.get_available_actions()
    jump = next(row for row in actions.position_actions if row.template_name == "Jump")
    remaining_movement = archmage.action_economy.movement_remaining()

    assert jump.valid_targets
    assert all(
        target.distance is not None and target.distance <= remaining_movement
        for target in jump.valid_targets
    )
    assert all(target.path_cost == target.distance for target in jump.valid_targets)
