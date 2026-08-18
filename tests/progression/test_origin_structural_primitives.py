"""Source-owned engine primitives required by durable character origins."""

from uuid import uuid4

from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
    ModifierHandleKind,
    ProficiencyHandle,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.core.content.durable_characters import (
    ProficiencySubject,
    ProficiencySubjectKind,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.types.languages import SrdLanguageId
from dnd.types.damage import DamageType
from dnd.core.modifiers import ResistanceModifier
from dnd.types.damage import ResistanceStatus
from dnd.types.senses import SenseMode, SensesType
from dnd.entities.entity import Entity
from server.world_projection import project_entity_summary


def _composition_receipt(
    entity: Entity,
    *grants: CharacterGrantReceipt,
) -> CharacterCompositionReceipt:
    return CharacterCompositionReceipt(
        runtime_entity_uuid=entity.uuid,
        character_id=uuid4(),
        grants=grants,
    )


def _origin_ref(
    kind: ContentDefinitionKind,
    content_id: str,
) -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=kind,
        content_id=content_id,
        content_version=2,
        definition_contract_hash="a" * 64,
    )


def test_creature_training_tracks_language_and_tool_sources_exactly() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    common_source = uuid4()
    infernal_source = uuid4()
    tool_source = uuid4()

    entity.creature_proficiencies.add_language_source(
        common_source,
        SrdLanguageId.COMMON.value,
    )
    entity.creature_proficiencies.add_language_source(
        infernal_source,
        SrdLanguageId.INFERNAL.value,
    )
    entity.creature_proficiencies.add_tool_source(
        tool_source,
        "tool.artisan.masons_tools",
    )

    assert entity.creature_proficiencies.knows_language(
        SrdLanguageId.COMMON.value,
    )
    assert entity.creature_proficiencies.knows_language(
        SrdLanguageId.INFERNAL.value,
    )
    assert entity.creature_proficiencies.is_tool_proficient(
        "tool.artisan.masons_tools",
    )

    assert entity.creature_proficiencies.remove_source(infernal_source)
    assert not entity.creature_proficiencies.knows_language(
        SrdLanguageId.INFERNAL.value,
    )
    assert entity.creature_proficiencies.knows_language(
        SrdLanguageId.COMMON.value,
    )
    assert entity.creature_proficiencies.is_tool_proficient(
        "tool.artisan.masons_tools",
    )


def test_composition_receipt_removes_language_and_tool_proficiencies() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    language_source = uuid4()
    tool_source = uuid4()
    language = ProficiencySubject(
        subject_kind=ProficiencySubjectKind.LANGUAGE,
        subject_id=SrdLanguageId.ELVISH.value,
    )
    tool = ProficiencySubject(
        subject_kind=ProficiencySubjectKind.TOOL,
        subject_id="tool.artisan.brewers_supplies",
    )
    entity.creature_proficiencies.add_language_source(
        language_source,
        SrdLanguageId.ELVISH.value,
    )
    entity.creature_proficiencies.add_tool_source(
        tool_source,
        "tool.artisan.brewers_supplies",
    )

    remove_character_composition(
        entity,
        _composition_receipt(
            entity,
            CharacterGrantReceipt(
                grant_id=uuid4(),
                proficiency_handles=(
                    ProficiencyHandle(
                        subject=language,
                        source_id=language_source,
                    ),
                    ProficiencyHandle(
                        subject=tool,
                        source_id=tool_source,
                    ),
                ),
            ),
        ),
    )

    assert not entity.creature_proficiencies.knows_language(
        SrdLanguageId.ELVISH.value,
    )
    assert not entity.creature_proficiencies.is_tool_proficient(
        "tool.artisan.brewers_supplies",
    )


def test_sense_mode_sources_compose_by_strongest_range_and_reverse() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    entity.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=30),
    ]
    sixty_feet = uuid4()
    unlimited = uuid4()

    entity.senses.add_sense_mode_source(
        sixty_feet,
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
    )
    assert entity.senses.get_sense_range(SensesType.DARKVISION) == 60

    entity.senses.add_sense_mode_source(
        unlimited,
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=0),
    )
    assert entity.senses.get_sense_range(SensesType.DARKVISION) == 0

    remove_character_composition(
        entity,
        _composition_receipt(
            entity,
            CharacterGrantReceipt(
                grant_id=uuid4(),
                sense_mode_source_ids=(unlimited, sixty_feet),
            ),
        ),
    )

    assert entity.senses.get_sense_range(SensesType.DARKVISION) == 30
    assert entity.senses.sense_modes == [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=30),
    ]


def test_composition_receipt_removes_resistance_modifier() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    modifier = ResistanceModifier(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name="Origin fire resistance",
        value=ResistanceStatus.RESISTANCE,
        damage_type=DamageType.FIRE,
    )
    entity.health.damage_reduction.self_static.add_resistance_modifier(
        modifier,
    )
    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.RESISTANCE
    )

    remove_character_composition(
        entity,
        _composition_receipt(
            entity,
            CharacterGrantReceipt(
                grant_id=uuid4(),
                modifier_handles=(
                    ModifierHandle(
                        value_uuid=entity.health.damage_reduction.uuid,
                        modifier_uuid=modifier.uuid,
                        kind=ModifierHandleKind.RESISTANCE,
                    ),
                ),
            ),
        ),
    )

    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.NONE
    )


def test_character_origin_identity_is_exact_and_composition_owned() -> None:
    creature_ref = _origin_ref(
        ContentDefinitionKind.CREATURE,
        "creature.player.fixture",
    ).model_copy(update={"content_version": 1})
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        content_ref=creature_ref,
    )
    species_ref = _origin_ref(
        ContentDefinitionKind.SPECIES,
        "species.elf",
    )
    variant_ref = _origin_ref(
        ContentDefinitionKind.SPECIES_VARIANT,
        "species_variant.elf.high",
    )
    background_ref = _origin_ref(
        ContentDefinitionKind.BACKGROUND,
        "background.acolyte",
    )

    entity.set_character_origin_identity(
        species_ref=species_ref,
        species_variant_ref=variant_ref,
        background_ref=background_ref,
    )

    assert entity.character_species_ref == species_ref
    assert entity.character_species_variant_ref == variant_ref
    assert entity.character_background_ref == background_ref
    projected = project_entity_summary(entity)
    assert projected.species_ref is not None
    assert projected.species_ref.content_id == "species.elf"
    assert projected.species_variant_ref is not None
    assert (
        projected.species_variant_ref.content_id
        == "species_variant.elf.high"
    )
    assert projected.background_ref is not None
    assert projected.background_ref.content_id == "background.acolyte"

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=uuid4(),
            grants=(),
            owns_character_origin_identity=True,
        ),
    )

    assert entity.character_species_ref is None
    assert entity.character_species_variant_ref is None
    assert entity.character_background_ref is None
