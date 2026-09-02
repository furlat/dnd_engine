"""Public direct Sorcerer/Draconic Bloodline progression proofs."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.content.characters.class_definitions import (
    SORCERER_DEFINITION,
    SORCERER_SPELL_RANKS,
    resolve_sorcerer_level,
)
from dnd.content.characters.sorcerer_grants import (
    apply_sorcerer_level,
    remove_last_sorcerer_level,
)
from dnd.classes import sorcerer
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.progression import FULL_CASTER_SPELL_SLOTS
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Darkness
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    FeatureToggleSelection,
    PreparedSpellSelection,
)


_CANTRIPS = {
    1: ("spell.acid_splash", "spell.chill_touch", "spell.fire_bolt", "spell.light"),
    4: ("spell.poison_spray",),
    10: ("spell.ray_of_frost",),
}
_SPELLS = {
    1: ("spell.burning_hands", "spell.charm_person"),
    2: ("spell.color_spray",),
    3: ("spell.blindness_deafness",),
    4: ("spell.blur",),
    5: ("spell.counterspell",),
    6: ("spell.daylight",),
    7: ("spell.banishment",),
    8: ("spell.blight",),
    9: ("spell.cloudkill",),
    10: ("spell.cone_of_cold",),
    11: ("spell.chain_lightning",),
    13: ("spell.finger_of_death",),
    15: ("spell.incendiary_cloud",),
    17: ("spell.power_word_kill",),
}


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _entity() -> Entity:
    return Entity.create(
        uuid4(),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                charisma=AbilityConfig(ability_score=10),
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


def _level(level: int, *, replace_at_two: bool = True) -> AppliedClassLevel:
    choices: list[ClassChoiceSelection] = []
    if level == 1:
        choices.extend((
            ClassChoiceSelection(
                "class.sorcerer.first_class.starting_equipment",
                ("starting_equipment.sorcerer.dagger",),
            ),
            ClassChoiceSelection(
                "class.sorcerer.proficiencies.skills",
                ("arcana", "persuasion"),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.subclass",
                (CharacterSubclass.DRACONIC_BLOODLINE.value,),
            ),
        ))
    if level in _CANTRIPS:
        choices.append(ClassChoiceSelection(
            f"class.sorcerer.level_{level}.cantrips",
            _CANTRIPS[level],
        ))
    if level in _SPELLS:
        choices.append(ClassChoiceSelection(
            f"class.sorcerer.level_{level}.spell_known",
            _SPELLS[level],
        ))
    if level == 2 and replace_at_two:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_2.spell_replacement",
            ("spell.burning_hands", "spell.magic_missile"),
        ))
    if level == 3:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_3.metamagic",
            (
                "class_feature.sorcerer.metamagic.quickened_spell",
                "class_feature.sorcerer.metamagic.twinned_spell",
            ),
        ))
    if level == 10:
        choices.append(ClassChoiceSelection(
            "class.sorcerer.level_10.metamagic",
            ("class_feature.sorcerer.metamagic.distant_spell",),
        ))
    if level in {4, 8, 12, 16, 19}:
        choices.append(ClassChoiceSelection(
            f"class.sorcerer.level_{level}.asi_or_feat",
            ("ability_score.charisma.2",),
        ))
    if level == 1:
        choices.append(ClassChoiceSelection(
            "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
            ("class_feature.sorcerer.draconic_ancestry.red",),
        ))
    return AppliedClassLevel(
        step_id=f"class.sorcerer.level_{level}",
        character_level=level,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=level,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=tuple(choices),
    )


def _registry_ids() -> tuple[frozenset[object], ...]:
    return (
        frozenset(BaseObject._registry),
        frozenset(BaseBlock._registry),
        frozenset(BaseValue._registry),
        frozenset(ModifiableValue._registry),
    )


def test_direct_sorcerer_definition_and_resolver_cover_exact_twenty_rows() -> None:
    assert len(SORCERER_DEFINITION.levels) == 20
    assert len(SORCERER_DEFINITION.draconic_levels) == 20
    assert SORCERER_DEFINITION.hit_die == 6
    assert SORCERER_DEFINITION.spell_ranks == SORCERER_SPELL_RANKS
    applied: tuple[AppliedClassLevel, ...] = ()
    for class_level in range(1, 21):
        row = _level(class_level)
        resolved = resolve_sorcerer_level(row, applied)
        assert resolved.maximum_spell_rank == max(
            FULL_CASTER_SPELL_SLOTS[class_level],
        )
        assert dict(resolved.normal_spell_slots) == FULL_CASTER_SPELL_SLOTS[
            class_level
        ]
        applied = (*applied, row)


def test_direct_sorcerer_applies_one_to_twenty_and_reverses_to_exact_baseline() -> None:
    entity = _entity()
    entity.prepared_spell_selections = (
        PreparedSpellSelection(
            source_id="class.sorcerer.spellcasting",
            spell_ids=("spell.magic_missile",),
        ),
    )
    entity.feature_toggle_selections = (
        FeatureToggleSelection(
            feature_id="class_feature.sorcerer.metamagic.quickened_spell",
            enabled=True,
        ),
    )
    baseline = _registry_ids()
    prepared = entity.prepared_spell_selections
    toggles = entity.feature_toggle_selections

    for class_level in range(1, 21):
        apply_sorcerer_level(entity, _level(class_level))

    assert len(entity.applied_class_levels) == 20
    assert len(entity.health.hit_dices) == 20
    assert entity.health.max_hit_points_bonus.score == 20
    assert entity.ability_scores.charisma.ability_score.score == 20
    assert entity.action_economy.resources["sorcery_points"].maximum == 20
    assert entity.action_economy.get_normal_spell_slot_capacities() == (
        FULL_CASTER_SPELL_SLOTS[20]
    )
    assert len(entity.spellcasting.sources) == 1
    source = next(iter(entity.spellcasting.sources.values()))
    assert source.provider_level == 20
    assert source.maximum_spell_rank == 9
    known_action_ids = {
        action.semantic_key
        for action in entity.registered_actions
        if action.semantic_key in SORCERER_SPELL_RANKS
    }
    assert "spell.burning_hands" not in known_action_ids
    assert "spell.magic_missile" in known_action_ids
    assert len(known_action_ids) == 20
    assert entity.spellcasting.learned_reaction_spell_handler_uuid(
        "spell.counterspell",
    ) is not None
    assert entity.prepared_spell_selections == prepared
    assert entity.feature_toggle_selections == toggles

    for _ in range(20):
        remove_last_sorcerer_level(entity)

    assert entity.applied_class_levels == ()
    assert entity.health.hit_dices == []
    assert entity.health.max_hit_points_bonus.score == 0
    assert entity.ability_scores.charisma.ability_score.score == 10
    assert entity.spellcasting.sources == {}
    assert entity.spellcasting.learned_reaction_spell_handlers == {}
    assert entity.action_economy.get_normal_spell_slot_capacities() == {}
    assert entity.prepared_spell_selections == prepared
    assert entity.feature_toggle_selections == toggles
    assert _registry_ids() == baseline


def test_direct_sorcerer_replacement_restores_exact_action_identity_and_order() -> None:
    entity = _entity()
    apply_sorcerer_level(entity, _level(1))
    original = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == "spell.burning_hands"
    )
    original_uuid = original.uuid
    original_index = entity.registered_actions.index(original)

    apply_sorcerer_level(entity, _level(2))
    assert all(
        action.uuid != original_uuid for action in entity.registered_actions
    )
    remove_last_sorcerer_level(entity)

    restored = entity.registered_actions[original_index]
    assert restored.uuid == original_uuid
    assert restored.semantic_key == "spell.burning_hands"
    assert restored.caster_level == 1


def test_direct_sorcerer_rejects_invalid_choice_before_mutation() -> None:
    entity = _entity()
    baseline = _registry_ids()
    invalid = AppliedClassLevel(
        step_id="class.sorcerer.level_1",
        character_level=1,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=1,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=(),
    )
    with pytest.raises(ValueError, match="exact authored order"):
        apply_sorcerer_level(entity, invalid)
    assert entity.applied_class_levels == ()
    assert _registry_ids() == baseline


def test_direct_sorcerer_owner_failure_restores_exact_prior_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = _entity()
    apply_sorcerer_level(entity, _level(1))
    apply_sorcerer_level(entity, _level(2))
    prior_levels = entity.applied_class_levels
    prior_actions = tuple(
        (action.uuid, action.semantic_key)
        for action in entity.registered_actions
    )
    prior_handlers = tuple(entity.event_handlers)
    prior_features = {
        feature_id: frozenset(source_ids)
        for feature_id, source_ids in entity.feature_sources.items()
    }
    prior_source = next(iter(entity.spellcasting.sources.items()))
    prior_slots = entity.action_economy.get_normal_spell_slot_capacities()
    prior_registries = _registry_ids()
    original_register_action = Entity.register_action

    def reject_quickened(entity_: Entity, action) -> None:
        if action.semantic_key == "action.class.sorcerer.quickened_spell":
            raise RuntimeError("forced public owner failure")
        original_register_action(entity_, action)

    monkeypatch.setattr(Entity, "register_action", reject_quickened)

    with pytest.raises(RuntimeError, match="forced public owner failure"):
        apply_sorcerer_level(entity, _level(3))

    assert entity.applied_class_levels == prior_levels
    assert tuple(
        (action.uuid, action.semantic_key)
        for action in entity.registered_actions
    ) == prior_actions
    assert tuple(entity.event_handlers) == prior_handlers
    assert {
        feature_id: frozenset(source_ids)
        for feature_id, source_ids in entity.feature_sources.items()
    } == prior_features
    assert next(iter(entity.spellcasting.sources.items())) == prior_source
    assert entity.action_economy.get_normal_spell_slot_capacities() == prior_slots
    assert _registry_ids() == prior_registries


@pytest.mark.parametrize(
    ("class_level", "action_id", "condition_name"),
    (
        (
            3,
            "action.class.sorcerer.quickened_spell",
            "MetamagicActive",
        ),
        (
            6,
            "action.class.sorcerer.elemental_affinity.resistance",
            "Elemental Affinity Resistance (Fire)",
        ),
        (14, "action.class.sorcerer.dragon_wings.toggle", "Dragon Wings"),
        (
            18,
            "action.class.sorcerer.draconic_presence",
            "Concentrating",
        ),
    ),
)
def test_direct_sorcerer_level_removal_releases_its_exact_active_root(
    class_level: int,
    action_id: str,
    condition_name: str,
) -> None:
    entity = _entity()
    for current_level in range(1, class_level + 1):
        apply_sorcerer_level(entity, _level(current_level))
    action = next(
        candidate
        for candidate in entity.registered_actions
        if candidate.semantic_key == action_id
    )

    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    root = entity.active_conditions[condition_name]
    owned_ids = {root.uuid, root.duration.uuid, *root.event_handlers_uuids}
    assert owned_ids <= set(BaseObject._registry)

    remove_last_sorcerer_level(entity)

    assert condition_name not in entity.active_conditions
    assert owned_ids.isdisjoint(BaseObject._registry)


def test_direct_sorcerer_reaction_replacement_restores_exact_shared_owner() -> None:
    entity = _entity()
    first = _level(1, replace_at_two=False)
    first_choices = tuple(
        ClassChoiceSelection(choice.choice_id, (
            "spell.shield",
            "spell.charm_person",
        ))
        if choice.choice_id == "class.sorcerer.level_1.spell_known"
        else choice
        for choice in first.choices
    )
    first = AppliedClassLevel(
        step_id=first.step_id,
        character_level=first.character_level,
        class_id=first.class_id,
        resulting_class_level=first.resulting_class_level,
        subclass_id=first.subclass_id,
        choices=first_choices,
    )
    apply_sorcerer_level(entity, first)
    original_handler = entity.spellcasting.learned_reaction_spell_handler_uuid(
        "spell.shield",
    )
    assert original_handler is not None

    second = _level(2, replace_at_two=False)
    second_choices = (*second.choices, ClassChoiceSelection(
        "class.sorcerer.level_2.spell_replacement",
        ("spell.shield", "spell.magic_missile"),
    ))
    second = AppliedClassLevel(
        step_id=second.step_id,
        character_level=second.character_level,
        class_id=second.class_id,
        resulting_class_level=second.resulting_class_level,
        subclass_id=second.subclass_id,
        choices=second_choices,
    )
    apply_sorcerer_level(entity, second)
    assert entity.spellcasting.learned_reaction_spell_handler_uuid(
        "spell.shield",
    ) is None

    remove_last_sorcerer_level(entity)

    assert entity.spellcasting.learned_reaction_spell_handler_uuid(
        "spell.shield",
    ) == original_handler
    assert original_handler in entity.event_handlers


def test_sorcerer_spell_updates_preserve_same_named_foreign_source() -> None:
    entity = _entity()
    foreign_source = uuid4()
    entity.spellcasting.add_innate_source(
        foreign_source,
        "charisma",
        provider_id="species.tiefling",
        provider_level=5,
        maximum_spell_rank=2,
    )
    foreign_darkness = Darkness(
        source_entity_uuid=entity.uuid,
        caster_level=5,
        spellcasting_source_id=foreign_source,
        template=True,
        semantic_key="spell.darkness",
    )
    entity.register_action(foreign_darkness)

    for class_level in range(1, 4):
        row = _level(class_level, replace_at_two=False)
        if class_level == 3:
            row = AppliedClassLevel(
                step_id=row.step_id,
                character_level=row.character_level,
                class_id=row.class_id,
                resulting_class_level=row.resulting_class_level,
                subclass_id=row.subclass_id,
                choices=tuple(
                    ClassChoiceSelection(
                        choice.choice_id,
                        ("spell.darkness",),
                    )
                    if choice.choice_id.endswith(".spell_known")
                    else choice
                    for choice in row.choices
                ),
            )
        apply_sorcerer_level(entity, row)

    sorcerer_darkness = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == "spell.darkness"
        and action.spellcasting_source_id != foreign_source
    )
    assert foreign_darkness.caster_level == 5
    assert sorcerer_darkness.caster_level == 3

    fourth = _level(4, replace_at_two=False)
    fourth = AppliedClassLevel(
        step_id=fourth.step_id,
        character_level=fourth.character_level,
        class_id=fourth.class_id,
        resulting_class_level=fourth.resulting_class_level,
        subclass_id=fourth.subclass_id,
        choices=(
            *fourth.choices[:2],
            ClassChoiceSelection(
                "class.sorcerer.level_4.spell_replacement",
                ("spell.darkness", "spell.magic_missile"),
            ),
            *fourth.choices[2:],
        ),
    )
    apply_sorcerer_level(entity, fourth)
    assert foreign_darkness in entity.registered_actions
    assert sorcerer_darkness not in entity.registered_actions

    remove_last_sorcerer_level(entity)
    restored = tuple(
        action
        for action in entity.registered_actions
        if action.semantic_key == "spell.darkness"
    )
    assert restored[0] is foreign_darkness
    assert restored[1].uuid == sorcerer_darkness.uuid
    assert restored[1].spellcasting_source_id == sorcerer_darkness.spellcasting_source_id
    assert foreign_darkness.caster_level == 5
    assert restored[1].caster_level == 3


def test_reaction_replacement_preserves_handler_identity_state_and_order() -> None:
    entity = _entity()
    first = _level(1, replace_at_two=False)
    first = AppliedClassLevel(
        step_id=first.step_id,
        character_level=first.character_level,
        class_id=first.class_id,
        resulting_class_level=first.resulting_class_level,
        subclass_id=first.subclass_id,
        choices=tuple(
            ClassChoiceSelection(
                choice.choice_id,
                ("spell.shield", "spell.charm_person"),
            )
            if choice.choice_id.endswith(".spell_known")
            else choice
            for choice in first.choices
        ),
    )
    apply_sorcerer_level(entity, first)
    shield_uuid = entity.spellcasting.learned_reaction_spell_handler_uuid(
        "spell.shield",
    )
    assert shield_uuid is not None

    sibling = EventHandler(
        name="Later sibling",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.TURN_START,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=lambda event, _source: event,
    )
    entity.add_event_handler(sibling)
    entity_order = tuple(entity.event_handlers)
    queue_order = tuple(EventQueue._event_handlers)

    second = _level(2, replace_at_two=False)
    second = AppliedClassLevel(
        step_id=second.step_id,
        character_level=second.character_level,
        class_id=second.class_id,
        resulting_class_level=second.resulting_class_level,
        subclass_id=second.subclass_id,
        choices=(*second.choices, ClassChoiceSelection(
            "class.sorcerer.level_2.spell_replacement",
            ("spell.shield", "spell.magic_missile"),
        )),
    )
    apply_sorcerer_level(entity, second)
    assert tuple(entity.event_handlers) == entity_order
    assert tuple(EventQueue._event_handlers) == queue_order
    assert not entity.event_handlers[shield_uuid].enabled

    remove_last_sorcerer_level(entity)
    assert tuple(entity.event_handlers) == entity_order
    assert tuple(EventQueue._event_handlers) == queue_order
    assert entity.event_handlers[shield_uuid].enabled


def test_sorcerer_active_root_veto_preserves_level_slots_and_root() -> None:
    entity = _entity()
    for class_level in range(1, 4):
        apply_sorcerer_level(entity, _level(class_level))
    quickened = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == "action.class.sorcerer.quickened_spell"
    )
    result = quickened.instantiate().apply()
    assert result is not None and not result.canceled
    root = entity.active_conditions["MetamagicActive"]
    levels = entity.applied_class_levels
    slots = entity.action_economy.get_normal_spell_slot_capacities()

    def veto(event: Event, _source) -> Event:
        if event.condition.uuid == root.uuid:
            return event.cancel(status_message="fixture veto")
        return event

    entity.add_event_handler(EventHandler(
        name="Veto metamagic removal",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION,
            event_target_entity_uuid=entity.uuid,
        )],
        event_processor=veto,
    ))

    with pytest.raises(RuntimeError, match="active-root removal was canceled"):
        remove_last_sorcerer_level(entity)

    assert entity.applied_class_levels == levels
    assert entity.action_economy.get_normal_spell_slot_capacities() == slots
    assert entity.active_conditions_by_uuid[root.uuid] is root


@pytest.mark.parametrize(
    ("level", "action_id", "binding_id"),
    (
        (3, "action.class.sorcerer.quickened_spell", "class_feature.sorcerer.metamagic_active"),
        (6, "action.class.sorcerer.elemental_affinity.resistance", "class_feature.sorcerer.elemental_affinity.resistance"),
        (14, "action.class.sorcerer.dragon_wings.toggle", "class_feature.sorcerer.dragon_wings.active"),
        (18, "action.class.sorcerer.draconic_presence", "class_feature.sorcerer.draconic_presence"),
    ),
)
def test_sorcerer_runtime_roots_keep_canonical_child_bindings(
    level: int,
    action_id: str,
    binding_id: str,
) -> None:
    entity = _entity()
    for class_level in range(1, level + 1):
        apply_sorcerer_level(entity, _level(class_level))
    action = next(
        action
        for action in entity.registered_actions
        if action.semantic_key == action_id
    )
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = (
        action.active_metamagic_condition_uuid
        if level == 3
        else action.active_resistance_condition_uuid
        if level == 6
        else action.active_wings_condition_uuid
        if level == 14
        else action.active_concentrating_condition_uuid
    )
    assert root_uuid is not None
    root = BaseObject.get(root_uuid)
    assert root.behavior_binding.behavior_id == binding_id
    if level == 3:
        handler = entity.event_handlers[root.event_handlers_uuids[0]]
        assert handler.behavior_binding.behavior_id == binding_id
    if level == 18:
        aura_uuid = root.linked_conditions[0][1]
        aura = sorcerer.DraconicPresenceAura.get(aura_uuid)
        assert aura.behavior_binding.behavior_id == (
            "class_feature.sorcerer.draconic_presence.aura"
        )


def test_draconic_presence_level_removal_releases_persistent_immunity_child() -> None:
    caster = _entity()
    target = Entity.create(
        uuid4(),
        config=EntityConfig(position=(1, 0), faction="targets"),
    )
    caster.faction = "casters"
    for class_level in range(1, 19):
        apply_sorcerer_level(caster, _level(class_level))
    action = next(
        action
        for action in caster.registered_actions
        if action.semantic_key == "action.class.sorcerer.draconic_presence"
    )
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    concentration = caster.active_conditions["Concentrating"]
    aura = sorcerer.DraconicPresenceAura.get(
        concentration.linked_conditions[0][1],
    )
    turn_start = Event(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        event_type=EventType.TURN_START,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    with fixed_dice_faces(20):
        aura._on_hostile_turn_start(turn_start, caster.uuid)

    immunity = next(
        condition
        for condition in target.active_conditions_by_uuid.values()
        if condition.name.startswith("Draconic Presence Immunity")
    )
    assert immunity.behavior_binding.behavior_id == (
        "class_feature.sorcerer.draconic_presence.immunity"
    )
    assert action.immunity_condition_uuids[target.uuid] == immunity.uuid

    remove_last_sorcerer_level(caster)

    assert immunity.uuid not in target.active_conditions_by_uuid
    assert immunity.uuid not in BaseObject._registry


def test_sorcerer_removal_rejects_a_modifier_moved_to_a_foreign_channel() -> None:
    entity = _entity()
    level = _level(1)
    receipt = apply_sorcerer_level(entity, level)
    modifier_uuid = receipt.maximum_hit_point_modifier_ids[0]
    modifier = entity.health.max_hit_points_bonus.self_static.value_modifiers.pop(
        modifier_uuid,
    )
    entity.ability_scores.charisma.ability_score.self_static.value_modifiers[
        modifier_uuid
    ] = modifier
    action_order = tuple(action.uuid for action in entity.registered_actions)

    with pytest.raises(RuntimeError, match="modifier ownership changed"):
        remove_last_sorcerer_level(entity)

    assert entity.applied_class_levels == (level,)
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert tuple(action.uuid for action in entity.registered_actions) == action_order


def test_sorcerer_root_cleanup_rejects_a_same_uuid_foreign_binding() -> None:
    entity = _entity()
    for class_level in range(1, 4):
        apply_sorcerer_level(entity, _level(class_level))
    level = _level(3)
    receipt = entity.character_grant_receipt(level.step_id)
    quickened_uuid = receipt.metamagic_root_owner_action_uuids[0]
    original = next(
        action for action in entity.registered_actions
        if action.uuid == quickened_uuid
    )
    result = original.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = original.active_metamagic_condition_uuid
    assert root_uuid is not None
    assert entity.unregister_action_by_uuid(quickened_uuid)
    entity.register_action(sorcerer.QuickenedSpell(
        uuid=quickened_uuid,
        source_entity_uuid=entity.uuid,
        template=True,
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.sorcerer.quickened_spell",
            provided_by_id="fixture.foreign.quickened_spell",
            origin_root_id="fixture.foreign",
            runtime_owner_uuid=entity.uuid,
        ),
    ))

    with pytest.raises(RuntimeError, match="metamagic root ownership changed"):
        remove_last_sorcerer_level(entity)

    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert entity.applied_class_levels[-1] == level


def test_sorcerer_root_cleanup_rejects_canonical_twinned_in_quickened_row() -> None:
    entity = _entity()
    for class_level in range(1, 4):
        apply_sorcerer_level(entity, _level(class_level))
    level = _level(3)
    receipt = entity.character_grant_receipt(level.step_id)
    quickened_uuid = receipt.metamagic_root_owner_action_uuids[0]
    original = next(
        action for action in entity.registered_actions
        if action.uuid == quickened_uuid
    )
    result = original.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = original.active_metamagic_condition_uuid
    assert root_uuid is not None
    assert entity.unregister_action_by_uuid(quickened_uuid)
    entity.register_action(sorcerer.TwinnedSpell(
        uuid=quickened_uuid,
        source_entity_uuid=entity.uuid,
        template=True,
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.sorcerer.twinned_spell",
            provided_by_id="class_feature.sorcerer.metamagic.twinned_spell",
            origin_root_id="class.sorcerer",
            runtime_owner_uuid=entity.uuid,
        ),
    ))

    with pytest.raises(RuntimeError, match="metamagic root ownership changed"):
        remove_last_sorcerer_level(entity)

    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert entity.applied_class_levels[-1] == level


def test_sorcerer_root_cleanup_rejects_fear_in_an_awe_presence_row() -> None:
    entity = _entity()
    for class_level in range(1, 19):
        apply_sorcerer_level(entity, _level(class_level))
    level = _level(18)
    receipt = entity.character_grant_receipt(level.step_id)
    original = next(
        action for action in entity.registered_actions
        if action.uuid in receipt.draconic_presence_root_owner_action_uuids
        and action.mode == "awe"
    )
    result = original.instantiate().apply()
    assert result is not None and not result.canceled
    root_uuid = original.active_concentrating_condition_uuid
    assert root_uuid is not None
    assert entity.unregister_action_by_uuid(original.uuid)
    entity.register_action(sorcerer.DraconicPresence(
        uuid=original.uuid,
        source_entity_uuid=entity.uuid,
        mode="fear",
        template=True,
        behavior_binding=BehaviorBinding(
            behavior_id="action.class.sorcerer.draconic_presence",
            provided_by_id="class_feature.sorcerer.draconic_presence",
            origin_root_id="class.sorcerer",
            runtime_owner_uuid=entity.uuid,
        ),
    ))

    with pytest.raises(RuntimeError, match="Draconic Presence root ownership changed"):
        remove_last_sorcerer_level(entity)

    assert entity.active_conditions_by_uuid[root_uuid].uuid == root_uuid
    assert entity.character_grant_receipt(level.step_id) is receipt
    assert entity.applied_class_levels[-1] == level
