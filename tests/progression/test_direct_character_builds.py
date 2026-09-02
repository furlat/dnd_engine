"""Public substrate and construction proofs for direct character builds."""

from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.actions import Move
from dnd.content.characters.builds import (
    CharacterAppearance,
    CharacterBuild,
    create_character,
    resolve_character_build,
)
from dnd.content.characters.premades import (
    PREMADE_CHARACTER_BUILDS,
    create_premade_character,
)
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.core.base_actions import BaseAction
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    EntityLevelAddedEvent,
    EntityLevelRemovedEvent,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import (
    AppliedClassLevel,
    AppliedOriginState,
    Background,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    FeatureToggleSelection,
    OriginChoiceSelection,
    PreparedSpellSelection,
    Species,
)
from dnd.types.character_receipts import OriginGrantReceipt


def _fighter_level() -> AppliedClassLevel:
    return AppliedClassLevel(
        step_id="class.fighter.level_1",
        character_level=1,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=1,
        choices=(ClassChoiceSelection(
            choice_id="class.fighter.level_1.fighting_style",
            values=("class_feature.fighter.fighting_style.dueling",),
        ),),
    )


def _custom_build() -> CharacterBuild:
    fighter = AppliedClassLevel(
        step_id="class.fighter.level_1",
        character_level=1,
        class_id=CharacterClass.FIGHTER,
        resulting_class_level=1,
        choices=(
            ClassChoiceSelection(
                "class.fighter.first_class.starting_equipment",
                ("starting_equipment.fighter.greatsword",),
            ),
            ClassChoiceSelection(
                "class.fighter.proficiencies.skills",
                ("athletics", "perception"),
            ),
            ClassChoiceSelection(
                "class.fighter.level_1.fighting_style",
                (
                    "class_feature.fighter.fighting_style."
                    "great_weapon_fighting",
                ),
            ),
        ),
    )
    sorcerer = AppliedClassLevel(
        step_id="class.sorcerer.level_1",
        character_level=2,
        class_id=CharacterClass.SORCERER,
        resulting_class_level=1,
        subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
        choices=(
            ClassChoiceSelection(
                "class.sorcerer.level_1.subclass",
                (CharacterSubclass.DRACONIC_BLOODLINE.value,),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.cantrips",
                (
                    "spell.acid_splash",
                    "spell.chill_touch",
                    "spell.fire_bolt",
                    "spell.light",
                ),
            ),
            ClassChoiceSelection(
                "class.sorcerer.level_1.spell_known",
                ("spell.magic_missile", "spell.shield"),
            ),
            ClassChoiceSelection(
                "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                ("class_feature.sorcerer.draconic_ancestry.red",),
            ),
        ),
    )
    return CharacterBuild(
        name="Custom Spellblade",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 15),
            ("dexterity", 13),
            ("constitution", 13),
            ("intelligence", 8),
            ("wisdom", 9),
            ("charisma", 14),
        ),
        flexible_ability_bonuses=(("strength", 2), ("charisma", 1)),
        origin_choices=(OriginChoiceSelection(
            "species.human.additional_language",
            ("language.draconic",),
        ),),
        class_levels=(fighter, sorcerer),
        item_loadout=(ItemLoadoutEntry(
            "weapon.greatsword",
            equipment_slot=WeaponSlot.MELEE_MAIN,
        ),),
        prepared_spells=(PreparedSpellSelection(
            source_id="class.sorcerer.spellcasting",
            spell_ids=("spell.magic_missile",),
        ),),
        feature_toggles=(
            FeatureToggleSelection(
                "class_feature.fighter.fighting_style."
                "great_weapon_fighting",
                True,
            ),
            FeatureToggleSelection("feat.lucky", False),
        ),
        appearance=CharacterAppearance(
            head_category="Head10",
            skin_tint=0xE6BC98,
            hair_tint=0x993F00,
        ),
    )


def test_direct_character_state_projects_one_complete_birth_fact() -> None:
    reset_engine_runtime()
    entity = Entity.create(uuid4(), name="Direct character")
    feature_source = uuid4()
    level = _fighter_level()
    origin = AppliedOriginState(
        base_ability_scores=(("strength", 15), ("dexterity", 14)),
    )
    prepared = PreparedSpellSelection(
        source_id="class.sorcerer.spellcasting",
        spell_ids=("spell.magic_missile",),
    )
    toggles = (
        FeatureToggleSelection("feat.lucky", False),
        FeatureToggleSelection(
            "class_feature.fighter.fighting_style.protection",
            True,
        ),
    )

    entity.set_character_body_identity("creature.player.humanoid_body")
    entity.set_character_origin_identity(
        species=Species.HUMAN,
        species_variant=None,
        background=Background.ADVENTURER,
    )
    entity.applied_origin_state = origin
    entity.applied_class_levels = (level,)
    entity.prepared_spell_selections = (prepared,)
    entity.feature_toggle_selections = toggles
    entity.add_feature_source("class_feature.fighter.second_wind", feature_source)

    created = entity.compose_entity()

    assert created.event_type is EventType.ENTITY_CREATED
    assert created.phase is EventPhase.COMPLETION
    assert created.entity_kind_id == "creature.player.humanoid_body"
    assert created.creature_content_ref is None
    assert created.character_body_id == "creature.player.humanoid_body"
    assert created.species is Species.HUMAN
    assert created.background is Background.ADVENTURER
    assert created.applied_origin_state == origin
    assert created.applied_class_levels == (level,)
    assert created.feature_ids == ("class_feature.fighter.second_wind",)
    assert created.prepared_spell_selections == (prepared,)
    assert created.feature_toggle_selections == toggles


def test_character_and_creature_birth_identities_are_disjoint() -> None:
    reset_engine_runtime()
    creature_ref = ContentRef(
        pack_id="fixture.direct_character",
        definition_kind=ContentDefinitionKind.CREATURE,
        content_id="creature.fixture",
        content_version=1,
        definition_contract_hash="a" * 64,
    )
    entity = Entity.create(uuid4(), content_ref=creature_ref)

    with pytest.raises(RuntimeError, match="cannot coexist"):
        entity.set_character_body_identity("creature.player.humanoid_body")

    entity.discard_uncommitted()


def test_level_event_types_share_only_progression_facts() -> None:
    level = _fighter_level()
    common = dict(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        use_register=False,
        phase=EventPhase.COMPLETION,
        entity_uuid=uuid4(),
        previous_total_level=0,
        new_total_level=1,
        level=level,
        resulting_class_levels=((CharacterClass.FIGHTER, 1),),
        applied_class_levels=(level,),
        changed_feature_ids=("class_feature.fighter.second_wind",),
    )

    added = EntityLevelAddedEvent(**common)
    removed = EntityLevelRemovedEvent(**{
        **common,
        "previous_total_level": 1,
        "new_total_level": 0,
        "applied_class_levels": (),
    })

    assert added.event_type is EventType.ENTITY_LEVEL_ADDED
    assert removed.event_type is EventType.ENTITY_LEVEL_REMOVED
    assert added.level == removed.level == level
    assert "items" not in EntityLevelAddedEvent.model_fields
    assert "ability_scores" not in EntityLevelAddedEvent.model_fields


def test_entity_receipt_and_feature_sources_preserve_exact_owners() -> None:
    reset_engine_runtime()
    entity = Entity.create(uuid4())
    first = uuid4()
    second = uuid4()
    receipt = OriginGrantReceipt(
        step_id="origin.human.adventurer",
        source_id=first,
        feature_sources=(("trait.origin.species.human.languages", first),),
    )

    entity.add_feature_source("trait.origin.species.human.languages", first)
    entity.add_feature_source("trait.origin.species.human.languages", second)
    entity.store_character_grant_receipt(receipt)

    assert entity.character_grant_receipt(receipt.step_id) == receipt
    assert entity.remove_feature_source(
        "trait.origin.species.human.languages",
        first,
    )
    assert entity.has_feature("trait.origin.species.human.languages")
    assert entity.remove_character_grant_receipt(receipt.step_id) == receipt

    entity.discard_uncommitted()


def test_action_execution_keeps_its_exact_entity_owned_template() -> None:
    template = BaseAction(
        source_entity_uuid=uuid4(),
        name="Template",
        template=True,
    )

    execution = template.instantiate(registered_template_uuid=uuid4())

    assert execution.registered_template_uuid == template.uuid
    assert execution.uuid != template.uuid
    assert not execution.template
    with pytest.raises(ValidationError):
        execution.registered_template_uuid = uuid4()

    move_template = Move(
        source_entity_uuid=uuid4(),
        name="Move",
        template=True,
    )
    move_execution = move_template.instantiate(
        registered_template_uuid=uuid4(),
    )
    assert move_execution.registered_template_uuid == move_template.uuid

    move_execution.remove_from_register()
    move_template.remove_from_register()
    execution.remove_from_register()
    template.remove_from_register()


def test_custom_build_resolves_purely_and_composes_one_complete_birth() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    build = _custom_build()
    before_blocks = frozenset(BaseBlock._registry)
    before_objects = frozenset(BaseObject._registry)

    resolved = resolve_character_build(build)

    assert resolved.known_spell_ids == (
        "spell.acid_splash",
        "spell.chill_touch",
        "spell.fire_bolt",
        "spell.light",
        "spell.magic_missile",
        "spell.shield",
    )
    assert frozenset(BaseBlock._registry) == before_blocks
    assert frozenset(BaseObject._registry) == before_objects
    assert EventQueue._all_events == []

    entity = create_character(build)
    created = tuple(
        event
        for event in EventQueue._all_events
        if event.event_type is EventType.ENTITY_CREATED
    )
    level_events = tuple(
        event
        for event in EventQueue._all_events
        if event.event_type in {
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_REMOVED,
        }
    )

    assert len(created) == 1
    assert level_events == ()
    assert entity.applied_class_levels == build.class_levels
    assert entity.prepared_spell_selections == build.prepared_spells
    assert entity.feature_toggle_selections == build.feature_toggles
    assert entity.ability_scores.strength.ability_score.score == 17
    assert entity.ability_scores.charisma.ability_score.score == 15
    assert created[0].applied_class_levels == build.class_levels
    assert created[0].prepared_spell_selections == build.prepared_spells
    assert created[0].feature_toggle_selections == build.feature_toggles


@pytest.mark.parametrize(
    ("base_scores", "message"),
    (
        (
            (
                ("strength", 14),
                ("dexterity", 13),
                ("constitution", 13),
                ("intelligence", 8),
                ("wisdom", 9),
                ("charisma", 14),
            ),
            "exactly 27 points",
        ),
        (
            tuple((ability, 15) for ability in (
                "strength",
                "dexterity",
                "constitution",
                "intelligence",
                "wisdom",
                "charisma",
            )),
            "exactly 27 points",
        ),
        (
            (
                ("strength", 16),
                ("dexterity", 13),
                ("constitution", 13),
                ("intelligence", 8),
                ("wisdom", 9),
                ("charisma", 13),
            ),
            "between 8 and 15",
        ),
    ),
)
def test_build_resolution_enforces_standard_twenty_seven_point_buy(
    base_scores: tuple[tuple[str, int], ...],
    message: str,
) -> None:
    reset_engine_runtime(grid_size=(8, 8))
    before_blocks = frozenset(BaseBlock._registry)
    before_objects = frozenset(BaseObject._registry)

    with pytest.raises(ValueError, match=message):
        resolve_character_build(replace(
            _custom_build(),
            base_ability_scores=base_scores,
        ))

    assert frozenset(BaseBlock._registry) == before_blocks
    assert frozenset(BaseObject._registry) == before_objects
    assert EventQueue._all_events == []


@pytest.mark.parametrize("premade_id", tuple(PREMADE_CHARACTER_BUILDS))
def test_all_premades_are_ordinary_builds_using_the_same_creator(
    premade_id: str,
) -> None:
    reset_engine_runtime(grid_size=(8, 8))
    build = PREMADE_CHARACTER_BUILDS[premade_id]

    entity = create_premade_character(premade_id)

    assert entity.name == build.name
    assert entity.applied_class_levels == build.class_levels
    assert entity.character_species is build.species
    assert entity.character_background is build.background
    assert sum(
        event.event_type is EventType.ENTITY_CREATED
        for event in EventQueue._all_events
    ) == 1
    assert all(
        event.event_type not in {
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_REMOVED,
        }
        for event in EventQueue._all_events
    )
    created = next(
        event
        for event in EventQueue._all_events
        if event.event_type is EventType.ENTITY_CREATED
    )
    runtime_torches = tuple(
        item
        for item in entity.inventory.items.values()
        if item.item_id == "equipment.portable_torch"
    )
    birth_torches = tuple(
        item
        for item in created.items
        if item.item_id == "equipment.portable_torch"
    )
    assert len(runtime_torches) == len(birth_torches)
    assert all(item.is_lit for item in runtime_torches)
    assert all(item.is_lit for item in birth_torches)


def test_sorcerer_premade_preserves_accepted_first_class_skills() -> None:
    build = PREMADE_CHARACTER_BUILDS["hero.sorcerer_l5_standard_torch"]
    skills = next(
        choice.values
        for choice in build.class_levels[0].choices
        if choice.choice_id == "class.sorcerer.proficiencies.skills"
    )

    assert skills == ("arcana", "deception")


def test_build_validation_rejects_unsupported_toggle_before_runtime_mutation() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    build = replace(
        _custom_build(),
        feature_toggles=(FeatureToggleSelection(
            "class_feature.fighter.second_wind",
            True,
        ),),
    )
    before_blocks = frozenset(BaseBlock._registry)
    before_objects = frozenset(BaseObject._registry)

    with pytest.raises(ValueError, match="unsupported feature toggle"):
        create_character(build)

    assert Entity.get_all_entities() == []
    assert frozenset(BaseBlock._registry) == before_blocks
    assert frozenset(BaseObject._registry) == before_objects
    assert EventQueue._all_events == []


def test_initial_item_collision_discards_the_entire_provisional_character() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    entity_uuid = uuid4()
    build = replace(
        _custom_build(),
        item_loadout=(
            ItemLoadoutEntry(
                "weapon.greatsword",
                equipment_slot=WeaponSlot.MELEE_MAIN,
            ),
            ItemLoadoutEntry(
                "shield.shield",
                equipment_slot=WeaponSlot.MELEE_OFF,
            ),
        ),
    )

    with pytest.raises(ValueError, match="collision"):
        create_character(build, runtime_entity_uuid=entity_uuid)

    assert Entity.get(entity_uuid) is None
    assert all(
        block.source_entity_uuid != entity_uuid
        for block in BaseBlock._registry.values()
    )
    assert all(
        obj.source_entity_uuid != entity_uuid
        for obj in BaseObject._registry.values()
    )
    assert EventQueue._all_events == []


def test_birth_publication_failure_discards_the_unpublished_aggregate() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    entity_uuid = uuid4()

    def reject_birth(event):
        if event.event_type is EventType.ENTITY_CREATED:
            raise RuntimeError("observer rejected character birth")

    EventQueue.add_pre_completion_callback(reject_birth)

    with pytest.raises(RuntimeError, match="observer rejected character birth"):
        create_character(_custom_build(), runtime_entity_uuid=entity_uuid)

    assert Entity.get(entity_uuid) is None
    assert all(
        event.event_type is not EventType.ENTITY_CREATED
        for event in EventQueue._all_events
    )
    assert all(
        event.event_type not in {
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_REMOVED,
        }
        for event in EventQueue._all_events
    )


def test_torch_premade_birth_failure_leaves_no_light_or_event_residue() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    entity_uuid = uuid4()

    def reject_birth(event):
        if event.event_type is EventType.ENTITY_CREATED:
            raise RuntimeError("observer rejected torch character birth")

    EventQueue.add_pre_completion_callback(reject_birth)
    build = PREMADE_CHARACTER_BUILDS["hero.fighter_l5_shield_torch"]

    with pytest.raises(RuntimeError, match="rejected torch character birth"):
        create_character(build, runtime_entity_uuid=entity_uuid)

    assert Entity.get(entity_uuid) is None
    assert EventQueue._all_events == []
    assert get_map()._light_sources == {}
