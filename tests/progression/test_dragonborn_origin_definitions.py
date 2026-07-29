"""Exact authored contracts for the ten SRD Dragonborn ancestries."""

from pydantic import TypeAdapter, ValidationError
import pytest

from dnd.content_system.dragonborn_origin_definitions import (
    DRAGONBORN_ANCESTRY_DECLARATIONS,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.dragonborn import (
    DragonbornAncestry,
    DragonbornAncestryFeatureDefinition,
    DragonbornBreathGeometry,
)
from dnd.core.content.durable_characters import (
    BuildChoiceSelection,
    ChoiceRequirementKind,
    OriginTraitChoice,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.creature_types import DamageType
from dnd.origins.dragonborn import DRAGONBORN_BREATH_WEAPON_REF


_EXPECTED_ANCESTRIES = {
    DragonbornAncestry.BLACK: (
        DamageType.ACID.value,
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    DragonbornAncestry.BLUE: (
        DamageType.LIGHTNING.value,
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    DragonbornAncestry.BRASS: (
        DamageType.FIRE.value,
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    DragonbornAncestry.BRONZE: (
        DamageType.LIGHTNING.value,
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    DragonbornAncestry.COPPER: (
        DamageType.ACID.value,
        DragonbornBreathGeometry.LINE,
        "dexterity",
    ),
    DragonbornAncestry.GOLD: (
        DamageType.FIRE.value,
        DragonbornBreathGeometry.CONE,
        "dexterity",
    ),
    DragonbornAncestry.GREEN: (
        DamageType.POISON.value,
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
    DragonbornAncestry.RED: (
        DamageType.FIRE.value,
        DragonbornBreathGeometry.CONE,
        "dexterity",
    ),
    DragonbornAncestry.SILVER: (
        DamageType.COLD.value,
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
    DragonbornAncestry.WHITE: (
        DamageType.COLD.value,
        DragonbornBreathGeometry.CONE,
        "constitution",
    ),
}


def test_dragonborn_ancestry_inventory_is_exact_typed_srd_data() -> None:
    declarations = DRAGONBORN_ANCESTRY_DECLARATIONS

    assert len(declarations) == 10
    assert {
        row.definition_payload.ancestry
        for row in declarations
        if isinstance(
            row.definition_payload,
            DragonbornAncestryFeatureDefinition,
        )
    } == set(DragonbornAncestry)
    assert tuple(row.ref.identity_key for row in declarations) == tuple(
        sorted(row.ref.identity_key for row in declarations),
    )

    for declaration in declarations:
        assert declaration.ref.pack_id == "content.srd_5_1_cc"
        assert declaration.ref.definition_kind is ContentDefinitionKind.TRAIT
        assert declaration.ref.content_version == 1
        assert declaration.descriptor.visibility.value == "public"
        assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
        definition = declaration.definition_payload
        assert isinstance(definition, DragonbornAncestryFeatureDefinition)
        expected = _EXPECTED_ANCESTRIES[definition.ancestry]
        assert (
            definition.damage_type,
            definition.breath_geometry,
            definition.save_ability,
        ) == expected
        assert definition.line_length_feet == (
            30 if definition.breath_geometry is DragonbornBreathGeometry.LINE
            else None
        )
        assert definition.line_width_feet == (
            5 if definition.breath_geometry is DragonbornBreathGeometry.LINE
            else None
        )
        assert definition.cone_length_feet == (
            15 if definition.breath_geometry is DragonbornBreathGeometry.CONE
            else None
        )
        assert len(declaration.dependencies) == 1
        dependency = declaration.dependencies[0]
        assert dependency.relation is ContentDependencyRelation.GRANTS_ACTION
        assert dependency.target_ref == DRAGONBORN_BREATH_WEAPON_REF


def test_general_origin_trait_choice_is_not_the_sorcerer_choice() -> None:
    selected_ref = DRAGONBORN_ANCESTRY_DECLARATIONS[0].ref
    choice = OriginTraitChoice(
        choice_id="species.dragonborn.draconic_ancestry",
        selected_ref=selected_ref,
    )

    assert choice.choice_type == "origin_trait"
    assert ChoiceRequirementKind(choice.choice_type) is (
        ChoiceRequirementKind.ORIGIN_TRAIT
    )
    restored = TypeAdapter(BuildChoiceSelection).validate_python(
        choice.model_dump(mode="json"),
    )
    assert restored == choice

    with pytest.raises(
        ValidationError,
        match="origin trait choice must reference a trait",
    ):
        OriginTraitChoice(
            choice_id="species.dragonborn.draconic_ancestry",
            selected_ref=DRAGONBORN_BREATH_WEAPON_REF,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "ancestry": "black",
                "damage_type": "Acid",
                "breath_geometry": "line",
                "save_ability": "dexterity",
                "cone_length_feet": 15,
            },
            "line breath",
        ),
        (
            {
                "ancestry": "gold",
                "damage_type": "Fire",
                "breath_geometry": "cone",
                "save_ability": "dexterity",
                "line_length_feet": 30,
                "line_width_feet": 5,
            },
            "cone breath",
        ),
    ),
)
def test_dragonborn_geometry_contract_fails_closed(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        DragonbornAncestryFeatureDefinition.model_validate(payload)
