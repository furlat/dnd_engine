"""Public direct Barbarian/Berserker progression proofs."""

from collections.abc import Iterator
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import RechargeType
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.classes import barbarian, fighter, rage
from dnd.content.characters.barbarian_grants import (
    apply_barbarian_level,
    remove_last_barbarian_level,
)
from dnd.content.characters.class_definitions import (
    BARBARIAN_ASI_LEVELS,
    BARBARIAN_ASI_VALUES,
    BARBARIAN_CLASS_SKILLS,
    BARBARIAN_DEFINITION,
    BARBARIAN_STARTING_EQUIPMENT,
    resolve_barbarian_level,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.events import EventQueue
from dnd.core.modifiers import NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.conditions import Charmed, Frightened
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
)


_ROOT = Path(__file__).resolve().parents[2]
_ASI_ABILITIES = {
    4: "strength",
    8: "dexterity",
    12: "constitution",
    16: "wisdom",
    19: "charisma",
}


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _entity(*, strength: int = 10, constitution: int = 10) -> Entity:
    return Entity.create(
        uuid4(),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                constitution=AbilityConfig(ability_score=constitution),
            ),
            health=HealthConfig(),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
        ),
    )


def _barbarian_level(
    level: int,
    *,
    character_level: int | None = None,
    lucky_level: int | None = None,
) -> AppliedClassLevel:
    choices: list[ClassChoiceSelection] = []
    resolved_character_level = character_level or level
    if level == 1 and resolved_character_level == 1:
        choices.extend((
            ClassChoiceSelection(
                choice_id="class.barbarian.first_class.starting_equipment",
                values=("starting_equipment.barbarian.greataxe",),
            ),
            ClassChoiceSelection(
                choice_id="class.barbarian.proficiencies.skills",
                values=("athletics", "perception"),
            ),
        ))
    if level == 3:
        choices.append(ClassChoiceSelection(
            choice_id="class.barbarian.level_3.subclass",
            values=(CharacterSubclass.BERSERKER.value,),
        ))
    if level in BARBARIAN_ASI_LEVELS:
        values = (
            ("feat.lucky",)
            if level == lucky_level
            else (f"ability_score.{_ASI_ABILITIES[level]}.2",)
        )
        choices.append(ClassChoiceSelection(
            choice_id=f"class.barbarian.level_{level}.asi_or_feat",
            values=values,
        ))
    return AppliedClassLevel(
        step_id=f"class.barbarian.level_{level}",
        character_level=resolved_character_level,
        class_id=CharacterClass.BARBARIAN,
        resulting_class_level=level,
        subclass_id=(CharacterSubclass.BERSERKER if level >= 3 else None),
        choices=tuple(choices),
    )


def test_barbarian_definition_is_cold_complete_and_exact() -> None:
    marker = "__DIRECT_BARBARIAN_IMPORTS__="
    script = (
        "import json, sys\n"
        "import dnd.content.characters.class_definitions\n"
        "forbidden = ('dnd.entity', 'dnd.actions', 'dnd.conditions', "
        "'dnd.classes.barbarian', 'dnd.classes.rage', 'dnd.content_system')\n"
        "loaded = sorted(name for name in sys.modules if any("
        "name == prefix or name.startswith(prefix + '.') for prefix in forbidden))\n"
        f"print({marker!r} + json.dumps(loaded))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    line = next(
        row for row in completed.stdout.splitlines() if row.startswith(marker)
    )
    assert json.loads(line[len(marker):]) == []

    assert BARBARIAN_DEFINITION.hit_die == 12
    assert BARBARIAN_DEFINITION.class_skills == BARBARIAN_CLASS_SKILLS
    assert BARBARIAN_DEFINITION.starting_equipment == BARBARIAN_STARTING_EQUIPMENT
    assert tuple(row.class_level for row in BARBARIAN_DEFINITION.levels) == tuple(
        range(1, 21)
    )
    assert tuple(
        row.class_level for row in BARBARIAN_DEFINITION.berserker_levels
    ) == tuple(range(1, 21))
    assert len(BARBARIAN_ASI_VALUES) == 13
    assert {
        row.class_level: row.feature_ids
        for row in BARBARIAN_DEFINITION.berserker_levels
        if row.feature_ids
    } == {
        3: ("class_feature.barbarian.frenzy",),
        6: ("class_feature.barbarian.mindless_rage",),
        10: ("class_feature.barbarian.intimidating_presence",),
        14: ("class_feature.barbarian.retaliation",),
    }


def test_barbarian_berserker_applies_1_to_20_and_removes_exactly() -> None:
    entity = _entity(strength=14, constitution=14)
    sibling_source = uuid4()
    sibling_modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Sibling critical die",
        value=1,
    )
    entity.equipment.crit_extra_dice_melee.self_static.add_value_modifier(
        sibling_modifier,
    )
    entity.skill_set.athletics.add_proficiency_source(
        sibling_source,
        ProficiencyMode.FULL,
    )
    entity.add_feature_source("class_feature.barbarian.rage", sibling_source)
    entity.action_economy.add_resource_contribution(
        "rage",
        sibling_source,
        maximum=1,
        recharge_type="long_rest",
        capacity_policy="maximum",
    )
    baseline_blocks = set(BaseBlock._registry)
    baseline_values = set(BaseValue._registry)
    baseline_objects = set(BaseObject._registry)

    receipts = tuple(
        apply_barbarian_level(
            entity,
            _barbarian_level(level, lucky_level=4),
        )
        for level in range(1, 21)
    )

    assert len(receipts) == 20
    assert entity.health.total_hit_dices_number == 20
    assert entity.health.hit_dices_total_hit_points == 145
    assert entity.action_economy.resources["rage"].maximum == 999
    assert entity.action_economy.resources["relentless_rage"].maximum == 999
    assert entity.action_economy.resolve_attacks_per_attack_action() == 2
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 4
    assert entity.action_economy.movement.normalized_score == 40
    assert entity.initiative.advantage.name == "ADVANTAGE"
    assert entity.ability_scores.strength.ability_score.score == 18
    assert entity.ability_scores.constitution.ability_score.score == 20
    assert entity.equipment.armor_class_formula_candidates
    assert {
        type(action) for action in entity.registered_actions
    } == {
        rage.EndRage,
        rage.Frenzy,
        barbarian.RecklessAttack,
        fighter.ExtraAttack,
        barbarian.IntimidatingPresence,
        barbarian.ExtendIntimidatingPresence,
    }
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    assert (frenzy.rage_damage, frenzy.mindless_rage, frenzy.persistent_rage) == (
        4,
        True,
        True,
    )
    assert all(
        action.behavior_binding is not None
        and action.behavior_binding.origin_root_id == CharacterClass.BARBARIAN.value
        for action in entity.registered_actions
    )
    assert {
        handler.name for handler in entity.event_handlers.values()
    } == {
        "Extra Attack Resource",
        "Indomitable Might",
        "Lucky",
        "Relentless Rage",
        "Retaliation",
    }
    applied_objects = set(BaseObject._registry)
    for _ in range(3):
        assert entity.action_economy.movement.normalized_score == 40
        assert entity.saving_throws.dexterity_saving_throw.bonus.advantage.name == (
            "ADVANTAGE"
        )
    assert set(BaseObject._registry) == applied_objects

    removed = tuple(remove_last_barbarian_level(entity) for _ in range(20))
    assert tuple(row.resulting_class_level for row in removed) == tuple(
        range(20, 0, -1)
    )
    assert entity.applied_class_levels == ()
    assert entity.health.hit_dices == []
    assert entity.registered_actions == []
    assert entity.event_handlers == {}
    assert entity.action_economy.resolve_attacks_per_attack_action() == 1
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 1
    assert entity.skill_set.athletics.proficiency_sources.sources == {
        sibling_source: ProficiencyMode.FULL,
    }
    assert entity.feature_sources == {
        "class_feature.barbarian.rage": {sibling_source},
    }
    assert entity.action_economy.resources["rage"].maximum == 1
    assert set(BaseBlock._registry) == baseline_blocks
    assert set(BaseValue._registry) == baseline_values
    assert set(BaseObject._registry) == baseline_objects


def test_frenzy_replaces_exact_rage_and_removes_only_its_owned_root() -> None:
    entity = _entity()
    for level in range(1, 3):
        apply_barbarian_level(entity, _barbarian_level(level))
    original_action_rows = tuple(
        (
            action.uuid,
            type(action),
            action.get_semantic_key(),
            action.behavior_binding,
        )
        for action in entity.registered_actions
    )
    apply_barbarian_level(entity, _barbarian_level(3))
    level_one = entity.character_grant_receipt("class.barbarian.level_1")
    original_rage_uuid = level_one.action_uuids[0]
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)

    sibling_action = rage.Frenzy(
        source_entity_uuid=entity.uuid,
        template=True,
        semantic_key="action.class.barbarian.frenzy",
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.barbarian.frenzy",
            provided_by_id="fixture.sibling.frenzy",
            origin_root_id="fixture.sibling",
            runtime_owner_uuid=entity.uuid,
        ),
    )
    entity.register_action(sibling_action)
    sibling_target = _entity()
    sibling_condition = rage.Raging(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=sibling_target.uuid,
        behavior_binding=BehaviorBinding(
            behavior_id="class_feature.barbarian.raging",
            provided_by_id="fixture.sibling.rage",
            origin_root_id="fixture.sibling",
            runtime_owner_uuid=sibling_target.uuid,
        ),
    )
    sibling_target.add_condition(sibling_condition)

    result = frenzy.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = frenzy.active_raging_condition_uuid
    assert root_uuid is not None
    root = entity.active_conditions_by_uuid[root_uuid]
    children = tuple(
        entity.active_conditions_by_uuid[child_uuid]
        for child_uuid in root.sub_conditions
    )
    assert [child.name for child in children] == ["Frenzied"]
    owned_runtime_uuids = {
        modifier_uuid
        for modifier_uuids in root.modifers_uuids.values()
        for modifier_uuid in modifier_uuids
    } | set(root.event_handlers_uuids) | {
        root.duration.uuid,
        children[0].duration.uuid,
    }
    assert owned_runtime_uuids <= set(BaseObject._registry)
    assert "Frenzied Strike" in {
        action.name for action in entity.registered_actions
    }

    remove_last_barbarian_level(entity)
    assert entity.active_conditions == {}
    assert sibling_condition.uuid in sibling_target.active_conditions_by_uuid
    assert sibling_action in entity.registered_actions
    restored = next(
        action
        for action in entity.registered_actions
        if action.uuid == original_rage_uuid
    )
    assert isinstance(restored, rage.Rage)
    assert tuple(
        (
            action.uuid,
            type(action),
            action.get_semantic_key(),
            action.behavior_binding,
        )
        for action in entity.registered_actions
        if action is not sibling_action
    ) == original_action_rows
    assert "Frenzied Strike" not in {
        action.name for action in entity.registered_actions
    }
    assert owned_runtime_uuids.isdisjoint(BaseObject._registry)


def test_failed_frenzy_replacement_restores_exact_rage_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = _entity()
    for level in range(1, 3):
        apply_barbarian_level(entity, _barbarian_level(level))
    original_rage = entity.get_action_template("Rage")
    assert isinstance(original_rage, rage.Rage)
    action_rows = tuple(
        (
            action.uuid,
            type(action),
            action.get_semantic_key(),
            action.behavior_binding,
        )
        for action in entity.registered_actions
    )
    rage_configuration = (
        original_rage.rage_damage,
        original_rage.mindless_rage,
        original_rage.persistent_rage,
    )
    feature_sources = {
        feature_id: set(sources)
        for feature_id, sources in entity.feature_sources.items()
    }
    block_registry = set(BaseBlock._registry)
    value_registry = set(BaseValue._registry)
    object_registry = set(BaseObject._registry)
    register_action = Entity.register_action

    def reject_frenzy(owner: Entity, action) -> None:
        if isinstance(action, rage.Frenzy):
            raise RuntimeError("fixture rejects Frenzy admission")
        register_action(owner, action)

    monkeypatch.setattr(Entity, "register_action", reject_frenzy)
    with pytest.raises(RuntimeError, match="rejects Frenzy admission"):
        apply_barbarian_level(entity, _barbarian_level(3))

    assert entity.applied_class_levels == (
        _barbarian_level(1),
        _barbarian_level(2),
    )
    with pytest.raises(KeyError):
        entity.character_grant_receipt("class.barbarian.level_3")
    assert tuple(
        (
            action.uuid,
            type(action),
            action.get_semantic_key(),
            action.behavior_binding,
        )
        for action in entity.registered_actions
    ) == action_rows
    restored_rage = entity.get_action_template("Rage")
    assert isinstance(restored_rage, rage.Rage)
    assert (
        restored_rage.rage_damage,
        restored_rage.mindless_rage,
        restored_rage.persistent_rage,
    ) == rage_configuration
    assert entity.feature_sources == feature_sources
    assert set(BaseBlock._registry) == block_registry
    assert set(BaseValue._registry) == value_registry
    assert set(BaseObject._registry) == object_registry


@pytest.mark.parametrize(
    "failure_mode",
    ("registration_exception", "immunity", "effect_cancel", "effect_exception"),
)
def test_failed_frenzied_child_admission_releases_its_raging_root(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    entity = _entity()
    for level in range(1, 4):
        apply_barbarian_level(entity, _barbarian_level(level))
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    if failure_mode == "immunity":
        entity.add_condition_immunity_source("Frenzied", uuid4())
    elif failure_mode in {"effect_cancel", "effect_exception"}:
        def reject_frenzied_effect(
            event: Event,
            _source_entity_uuid,
        ) -> Event:
            if event.condition.name != "Frenzied":
                return event
            if failure_mode == "effect_exception":
                raise RuntimeError("fixture rejects Frenzied effect")
            return event.cancel(status_message="fixture cancels Frenzied effect")

        entity.add_event_handler(EventHandler(
            name="Reject Frenzied effect",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=entity.uuid,
            )],
            event_processor=reject_frenzied_effect,
        ))
    execution = frenzy.instantiate()
    action_rows = tuple(
        (action.uuid, type(action), action.get_semantic_key())
        for action in entity.registered_actions
    )
    handler_uuids = set(entity.event_handlers)
    block_registry = set(BaseBlock._registry)
    value_registry = set(BaseValue._registry)
    object_registry = set(BaseObject._registry)
    register_action = Entity.register_action

    def reject_frenzied_strike(owner: Entity, action) -> None:
        if isinstance(action, rage.FrenziedStrike):
            raise RuntimeError("fixture rejects Frenzied Strike admission")
        register_action(owner, action)

    if failure_mode == "registration_exception":
        monkeypatch.setattr(Entity, "register_action", reject_frenzied_strike)
        with pytest.raises(RuntimeError, match="rejects Frenzied Strike admission"):
            execution.apply()
    elif failure_mode == "effect_exception":
        with pytest.raises(RuntimeError, match="rejects Frenzied effect"):
            execution.apply()
    else:
        result = execution.apply()
        assert result is not None and result.canceled

    assert entity.active_conditions == {}
    assert entity.active_conditions_by_uuid == {}
    assert frenzy.active_raging_condition_uuid is None
    assert tuple(
        (action.uuid, type(action), action.get_semantic_key())
        for action in entity.registered_actions
    ) == action_rows
    assert set(entity.event_handlers) == handler_uuids
    assert set(BaseBlock._registry) == block_registry
    assert set(BaseValue._registry) == value_registry
    added_objects = set(BaseObject._registry) - object_registry
    assert object_registry - set(BaseObject._registry) == set()
    assert len(added_objects) == 1
    committed_cost = BaseObject._registry[added_objects.pop()]
    assert isinstance(committed_cost, NumericalModifier)
    assert committed_cost.name == "Frenzy_cost"
    assert (
        committed_cost.uuid
        in entity.action_economy.bonus_actions.self_static.value_modifiers
    )


@pytest.mark.parametrize(
    ("action_name", "last_level"),
    (("Rage", 1), ("Frenzy", 3), ("Frenzy", 6)),
)
@pytest.mark.parametrize(
    "failure_mode",
    ("handler_admission", "effect_cancel", "effect_exception"),
)
def test_failed_raging_root_admission_releases_each_owned_artifact(
    monkeypatch: pytest.MonkeyPatch,
    action_name: str,
    last_level: int,
    failure_mode: str,
) -> None:
    entity = _entity()
    for level in range(1, last_level + 1):
        apply_barbarian_level(entity, _barbarian_level(level))
    action = entity.get_action_template(action_name)
    assert isinstance(action, rage.Rage | rage.Frenzy)
    preexisting_charmed = None
    if last_level == 6:
        preexisting_charmed = Charmed(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
        applied_charmed = entity.add_condition(preexisting_charmed)
        assert applied_charmed is not None and not applied_charmed.canceled

    if failure_mode in {"effect_cancel", "effect_exception"}:
        def reject_raging_effect(
            event: Event,
            _source_entity_uuid,
        ) -> Event:
            if event.condition.name == "Raging":
                if failure_mode == "effect_exception":
                    raise RuntimeError("fixture rejects Raging effect")
                return event.cancel(status_message="fixture cancels Raging effect")
            return event

        entity.add_event_handler(EventHandler(
            name="Reject Raging effect",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=entity.uuid,
            )],
            event_processor=reject_raging_effect,
        ))

    execution = action.instantiate()
    action_rows = tuple(
        (candidate.uuid, type(candidate), candidate.get_semantic_key())
        for candidate in entity.registered_actions
    )
    handler_uuids = set(entity.event_handlers)
    block_registry = set(BaseBlock._registry)
    value_registry = set(BaseValue._registry)
    object_registry = set(BaseObject._registry)

    if failure_mode == "handler_admission":
        add_event_handler = Entity.add_event_handler
        admitted_rage_handlers = 0

        def reject_second_rage_handler(
            owner: Entity,
            handler: EventHandler,
        ) -> None:
            nonlocal admitted_rage_handlers
            if handler.name in {
                "Rage Maintenance",
                "Rage Armor Watch",
                "Rage Death End",
            }:
                admitted_rage_handlers += 1
                if admitted_rage_handlers == 2:
                    raise RuntimeError("fixture rejects second Raging handler")
            add_event_handler(owner, handler)

        monkeypatch.setattr(Entity, "add_event_handler", reject_second_rage_handler)
        expected_error = "rejects second Raging handler"
    else:
        expected_error = "rejects Raging effect"

    if failure_mode == "effect_cancel":
        result = execution.apply()
        assert result is not None and result.canceled
    else:
        with pytest.raises(RuntimeError, match=expected_error):
            execution.apply()

    if preexisting_charmed is None:
        assert entity.active_conditions == {}
        assert entity.active_conditions_by_uuid == {}
    else:
        assert entity.active_conditions == {"Charmed": preexisting_charmed}
        assert entity.active_conditions_by_uuid == {
            preexisting_charmed.uuid: preexisting_charmed,
        }
    assert action.active_raging_condition_uuid is None
    assert tuple(
        (candidate.uuid, type(candidate), candidate.get_semantic_key())
        for candidate in entity.registered_actions
    ) == action_rows
    assert set(entity.event_handlers) == handler_uuids
    assert set(BaseBlock._registry) == block_registry
    assert set(BaseValue._registry) == value_registry
    added_objects = set(BaseObject._registry) - object_registry
    assert object_registry - set(BaseObject._registry) == set()
    assert len(added_objects) == 1
    committed_cost = BaseObject._registry[added_objects.pop()]
    assert isinstance(committed_cost, NumericalModifier)
    assert committed_cost.name == f"{action_name}_cost"
    assert (
        committed_cost.uuid
        in entity.action_economy.bonus_actions.self_static.value_modifiers
    )


def test_mindless_rage_purges_conditions_after_root_completion() -> None:
    entity = _entity()
    for level in range(1, 7):
        apply_barbarian_level(entity, _barbarian_level(level))
    conditions = (
        Charmed(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid),
        Frightened(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid),
    )
    for condition in conditions:
        applied = entity.add_condition(condition)
        assert applied is not None and not applied.canceled

    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    result = frenzy.instantiate().apply()
    assert result is not None and not result.canceled
    assert "Charmed" not in entity.active_conditions
    assert "Frightened" not in entity.active_conditions
    assert all(
        condition.uuid not in BaseObject._registry
        and condition.duration.uuid not in BaseObject._registry
        for condition in conditions
    )

    events = tuple(event for _, event in EventQueue.iter_events_since(0))
    raging_completion = next(
        event
        for event in events
        if event.event_type is EventType.CONDITION_APPLICATION
        and event.phase is EventPhase.COMPLETION
        and event.condition.name == "Raging"
    )
    purge_declarations = tuple(
        event
        for event in events
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.phase is EventPhase.DECLARATION
        and event.condition.name in {"Charmed", "Frightened"}
    )
    assert {event.condition.name for event in purge_declarations} == {
        "Charmed",
        "Frightened",
    }
    assert all(
        event.parent_event == raging_completion.uuid
        for event in purge_declarations
    )


@pytest.mark.parametrize("vetoed_name", ("Charmed", "Frightened"))
def test_mindless_rage_removal_veto_preserves_the_complete_pair(
    vetoed_name: str,
) -> None:
    entity = _entity()
    for level in range(1, 7):
        apply_barbarian_level(entity, _barbarian_level(level))
    conditions = (
        Charmed(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid),
        Frightened(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid),
    )
    for condition in conditions:
        applied = entity.add_condition(condition)
        assert applied is not None and not applied.canceled

    def veto_one_removal(
        event: Event,
        _source_entity_uuid,
    ) -> Event:
        if event.condition.name == vetoed_name:
            return event.cancel(status_message=f"fixture vetoes {vetoed_name}")
        return event

    entity.add_event_handler(EventHandler(
        name=f"Veto {vetoed_name} removal",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION,
            event_target_entity_uuid=entity.uuid,
        )],
        event_processor=veto_one_removal,
    ))
    exact_rows = tuple(
        (condition.name, condition.uuid, condition.duration.uuid)
        for condition in conditions
    )

    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    result = frenzy.instantiate().apply()
    assert result is not None and not result.canceled
    assert "Mindless Rage purge was blocked" in result.status_message
    assert tuple(
        (
            condition.name,
            entity.active_conditions[condition.name].uuid,
            entity.active_conditions[condition.name].duration.uuid,
        )
        for condition in conditions
    ) == exact_rows
    assert all(
        condition.uuid in entity.active_conditions_by_uuid
        and condition.uuid in BaseObject._registry
        and condition.duration.uuid in BaseObject._registry
        for condition in conditions
    )
    completed_removals = tuple(
        event.condition.name
        for _, event in EventQueue.iter_events_since(0)
        if event.event_type is EventType.CONDITION_REMOVAL
        and event.phase is EventPhase.COMPLETION
        and event.condition.name in {"Charmed", "Frightened"}
    )
    assert completed_removals == ()


def test_frenzied_cleanup_rejects_a_missing_owned_strike() -> None:
    entity = _entity()
    for level in range(1, 4):
        apply_barbarian_level(entity, _barbarian_level(level))
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    applied = frenzy.instantiate().apply()
    assert applied is not None and not applied.canceled
    root_uuid = frenzy.active_raging_condition_uuid
    assert root_uuid is not None
    root = entity.active_conditions_by_uuid[root_uuid]
    child = entity.active_conditions_by_uuid[root.sub_conditions[0]]
    strike_uuid = child.frenzied_strike_action_uuid
    assert strike_uuid is not None
    assert entity.unregister_action_by_uuid(strike_uuid)

    with pytest.raises(RuntimeError, match="Frenzied-owned strike action is missing"):
        entity.remove_condition_by_uuid(root_uuid)

    assert root_uuid in entity.active_conditions_by_uuid
    assert child.uuid in entity.active_conditions_by_uuid


def test_reckless_root_and_mindless_immunities_use_exact_owners() -> None:
    entity = _entity()
    for level in range(1, 7):
        apply_barbarian_level(entity, _barbarian_level(level))
    reckless = entity.get_action_template("Reckless Attack")
    assert isinstance(reckless, barbarian.RecklessAttack)
    result = reckless.instantiate().apply()
    assert result is not None and not result.canceled
    assert reckless.active_reckless_condition_uuid is not None
    assert "Reckless Attacking" in entity.active_conditions
    assert entity.check_condition_immunity("Charmed") is False
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    frenzy_result = frenzy.instantiate().apply()
    assert frenzy_result is not None and not frenzy_result.canceled
    assert entity.check_condition_immunity("Charmed") is True

    remove_last_barbarian_level(entity)
    assert "Reckless Attacking" in entity.active_conditions
    assert entity.check_condition_immunity("Charmed") is False
    remove_last_barbarian_level(entity)
    remove_last_barbarian_level(entity)
    remove_last_barbarian_level(entity)
    remove_last_barbarian_level(entity)
    assert "Reckless Attacking" not in entity.active_conditions


def test_first_class_and_multiclass_barbarian_packages_are_distinct() -> None:
    first = _entity()
    apply_barbarian_level(first, _barbarian_level(1))
    assert first.creature_proficiencies.is_armor_proficient(ArmorType.LIGHT)
    assert first.creature_proficiencies.is_armor_proficient(ArmorType.MEDIUM)
    assert first.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert first.saving_throws.strength_saving_throw.proficiency
    assert first.saving_throws.constitution_saving_throw.proficiency

    multiclass = _entity()
    multiclass.applied_class_levels = (AppliedClassLevel(
        step_id="class.sorcerer.level_1",
        character_level=1,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=1,
    ),)
    apply_barbarian_level(
        multiclass,
        _barbarian_level(1, character_level=2),
    )
    assert not multiclass.creature_proficiencies.is_armor_proficient(
        ArmorType.LIGHT,
    )
    assert multiclass.creature_proficiencies.is_shield_proficient()
    assert not multiclass.saving_throws.strength_saving_throw.proficiency
    assert not multiclass.skill_set.athletics.proficiency


def test_barbarian_resolution_rejects_invalid_choices_before_mutation() -> None:
    entity = _entity()
    invalid = _barbarian_level(1)
    invalid = AppliedClassLevel(
        step_id=invalid.step_id,
        character_level=invalid.character_level,
        class_id=invalid.class_id,
        resulting_class_level=invalid.resulting_class_level,
        choices=invalid.choices[:-1],
    )
    with pytest.raises(ValueError, match="exact authored order"):
        apply_barbarian_level(entity, invalid)
    assert entity.applied_class_levels == ()
    assert entity.health.hit_dices == []
    assert not entity.feature_sources

    resolved = resolve_barbarian_level(_barbarian_level(1), ())
    assert resolved.starting_equipment_id == "starting_equipment.barbarian.greataxe"


def test_barbarian_owner_failure_rolls_back_only_the_partial_level() -> None:
    entity = _entity()
    entity.action_economy.add_resource(
        "rage",
        maximum=7,
        recharge_type=RechargeType.SHORT_REST,
    )
    existing = entity.action_economy.resources["rage"]
    block_registry_before = set(BaseBlock._registry)
    object_registry_before = set(BaseObject._registry)
    value_registry_before = set(BaseValue._registry)

    with pytest.raises(ValueError, match="already uses short_rest recharge"):
        apply_barbarian_level(entity, _barbarian_level(1))

    assert entity.applied_class_levels == ()
    with pytest.raises(KeyError):
        entity.character_grant_receipt("class.barbarian.level_1")
    assert entity.health.hit_dices == []
    assert not entity.registered_actions
    assert not entity.event_handlers
    assert not entity.feature_sources
    assert not entity.equipment.armor_class_formula_candidates
    assert entity.action_economy.resources["rage"] is existing
    assert (existing.current, existing.maximum) == (7, 7)
    assert set(BaseBlock._registry) == block_registry_before
    assert set(BaseObject._registry) == object_registry_before
    assert set(BaseValue._registry) == value_registry_before


def test_barbarian_root_cleanup_uses_receipt_identity_not_semantic_key() -> None:
    entity = _entity()
    level = _barbarian_level(1)
    receipt = apply_barbarian_level(entity, level)
    rage_uuid = receipt.raging_root_owner_action_uuids[0]
    rage_action = next(
        action for action in entity.registered_actions if action.uuid == rage_uuid
    )
    rage_action.semantic_key = "fixture.mutated.display_key"
    result = rage_action.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = rage_action.active_raging_condition_uuid
    assert root_uuid is not None

    remove_last_barbarian_level(entity)

    assert root_uuid not in entity.active_conditions_by_uuid
    assert entity.applied_class_levels == ()


def test_barbarian_root_cleanup_rejects_a_same_uuid_foreign_binding() -> None:
    entity = _entity()
    level = _barbarian_level(1)
    receipt = apply_barbarian_level(entity, level)
    rage_uuid = receipt.raging_root_owner_action_uuids[0]
    original = next(
        action for action in entity.registered_actions if action.uuid == rage_uuid
    )
    result = original.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = original.active_raging_condition_uuid
    assert root_uuid is not None
    assert entity.unregister_action_by_uuid(rage_uuid)
    entity.register_action(rage.Rage(
        uuid=rage_uuid,
        source_entity_uuid=entity.uuid,
        rage_damage=original.rage_damage,
        mindless_rage=original.mindless_rage,
        persistent_rage=original.persistent_rage,
        template=True,
        semantic_key="action.class.barbarian.rage",
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.barbarian.rage",
            provided_by_id="fixture.foreign.rage",
            origin_root_id="fixture.foreign",
            runtime_owner_uuid=entity.uuid,
        ),
    ))

    with pytest.raises(RuntimeError, match="Rage root ownership changed"):
        remove_last_barbarian_level(entity)

    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert entity.applied_class_levels == (level,)


def test_barbarian_root_cleanup_rejects_canonical_frenzy_in_a_rage_row() -> None:
    entity = _entity()
    level = _barbarian_level(1)
    receipt = apply_barbarian_level(entity, level)
    rage_uuid = receipt.raging_root_owner_action_uuids[0]
    original = next(
        action for action in entity.registered_actions if action.uuid == rage_uuid
    )
    result = original.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = original.active_raging_condition_uuid
    assert root_uuid is not None
    assert entity.unregister_action_by_uuid(rage_uuid)
    entity.register_action(rage.Frenzy(
        uuid=rage_uuid,
        source_entity_uuid=entity.uuid,
        rage_damage=original.rage_damage,
        mindless_rage=original.mindless_rage,
        persistent_rage=original.persistent_rage,
        template=True,
        semantic_key="action.class.barbarian.frenzy",
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.barbarian.frenzy",
            provided_by_id="class_feature.barbarian.frenzy",
            origin_root_id="class.barbarian",
            runtime_owner_uuid=entity.uuid,
        ),
    ))

    with pytest.raises(RuntimeError, match="Rage root ownership changed"):
        remove_last_barbarian_level(entity)

    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert entity.applied_class_levels == (level,)
