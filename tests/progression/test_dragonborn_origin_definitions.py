"""Cold direct rules for the ten SRD Dragonborn ancestries."""

from dataclasses import FrozenInstanceError

import pytest

from dnd.content.characters.dragonborn_definitions import (
    DRAGONBORN_ANCESTRY_DEFINITIONS,
    DragonbornAncestryDefinition,
)
from dnd.content.characters.origin_content import resolve_origin_transforms
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.damage import DamageType
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)
from dnd.types.progression import AppliedOriginState, OriginChoiceSelection


_EXPECTED_ANCESTRIES = {
    DragonbornAncestry.BLACK: (DamageType.ACID, DragonbornBreathGeometry.LINE, AbilityName.DEXTERITY),
    DragonbornAncestry.BLUE: (DamageType.LIGHTNING, DragonbornBreathGeometry.LINE, AbilityName.DEXTERITY),
    DragonbornAncestry.BRASS: (DamageType.FIRE, DragonbornBreathGeometry.LINE, AbilityName.DEXTERITY),
    DragonbornAncestry.BRONZE: (DamageType.LIGHTNING, DragonbornBreathGeometry.LINE, AbilityName.DEXTERITY),
    DragonbornAncestry.COPPER: (DamageType.ACID, DragonbornBreathGeometry.LINE, AbilityName.DEXTERITY),
    DragonbornAncestry.GOLD: (DamageType.FIRE, DragonbornBreathGeometry.CONE, AbilityName.DEXTERITY),
    DragonbornAncestry.GREEN: (DamageType.POISON, DragonbornBreathGeometry.CONE, AbilityName.CONSTITUTION),
    DragonbornAncestry.RED: (DamageType.FIRE, DragonbornBreathGeometry.CONE, AbilityName.DEXTERITY),
    DragonbornAncestry.SILVER: (DamageType.COLD, DragonbornBreathGeometry.CONE, AbilityName.CONSTITUTION),
    DragonbornAncestry.WHITE: (DamageType.COLD, DragonbornBreathGeometry.CONE, AbilityName.CONSTITUTION),
}


def _state(ancestry: str) -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(OriginChoiceSelection(
            "species.dragonborn.draconic_ancestry",
            (ancestry,),
        ),),
    )


def test_dragonborn_ancestry_inventory_is_exact_typed_srd_data() -> None:
    assert set(DRAGONBORN_ANCESTRY_DEFINITIONS) == set(DragonbornAncestry)

    for ancestry, definition in DRAGONBORN_ANCESTRY_DEFINITIONS.items():
        assert isinstance(definition, DragonbornAncestryDefinition)
        assert definition.ancestry is ancestry
        assert (
            definition.damage_type,
            definition.breath_geometry,
            definition.save_ability,
        ) == _EXPECTED_ANCESTRIES[ancestry]
        if definition.breath_geometry is DragonbornBreathGeometry.LINE:
            assert definition.line_length_feet == 30
            assert definition.line_width_feet == 5
            assert definition.cone_length_feet is None
        else:
            assert definition.cone_length_feet == 15
            assert definition.line_length_feet is None
            assert definition.line_width_feet is None


def test_dragonborn_ancestry_definitions_are_cold_and_immutable() -> None:
    definition = DRAGONBORN_ANCESTRY_DEFINITIONS[DragonbornAncestry.BLACK]
    with pytest.raises(FrozenInstanceError):
        definition.damage_type = DamageType.FIRE  # type: ignore[misc]
    with pytest.raises(TypeError):
        DRAGONBORN_ANCESTRY_DEFINITIONS[DragonbornAncestry.BLACK] = definition


def test_invalid_dragonborn_ancestry_choice_fails_before_entity_mutation() -> None:
    with pytest.raises(ValueError, match="contains"):
        resolve_origin_transforms(
            species=Species.DRAGONBORN,
            species_variant=None,
            background=Background.ADVENTURER,
            state=_state("purple"),
        )
