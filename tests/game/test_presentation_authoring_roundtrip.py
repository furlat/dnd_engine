"""Production authoring survives the same schemas exported for another client."""

from game.animation_data import load_animation_data
from game.animation_types import DamageContext, DeathContext, AttackRecipe, VoluntaryMovementContext, BodyRig, RigTables
from game.condition_types import ConditionRecipe


def test_admitted_production_authoring_roundtrips_with_timing_fields():
    data = load_animation_data()
    values = ((DamageContext, data.damage_context), (DeathContext, data.death_context),
              (VoluntaryMovementContext, data.movement_context), (RigTables, data.rig),
              *((AttackRecipe, value) for value in data.attack_recipes.values()),
              *((ConditionRecipe, value) for value in data.condition_recipes.values()),
              *((BodyRig, value) for value in data.rigs.values()))
    assert data.attack_recipes and data.condition_recipes and data.rigs
    for model, value in values:
        assert model.model_validate_json(value.model_dump_json()) == value
