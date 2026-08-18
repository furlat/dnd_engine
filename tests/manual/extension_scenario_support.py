"""Test-only actors and scenes for extension behavior regressions."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_actions import (
    AvailableActionInfo,
)
from dnd.entities.entity import Entity, EntityConfig
from dnd.extensions.aegis_spark import AegisSpark
from dnd.extensions.field_focus import (
    DeployFieldFocus,
    FIELD_KIT_RECIPE,
)
from tests.engine.support import create_test_monster


def create_spell_feature_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=12),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=16),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=3,
                        mode="maximums",
                    ),
                ],
            ),
            proficiency_bonus=2,
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            position=position,
            faction=faction,
        ),
    )


def create_aegis_scene() -> tuple[Entity, Entity, Entity]:
    caster = create_spell_feature_actor("Aegis Warden", (1, 1), "heroes")
    ally = create_spell_feature_actor("Shield Ally", (3, 1), "heroes")
    enemy = create_spell_feature_actor("Training Dummy", (5, 1), "monsters")
    caster.register_action(
        AegisSpark(
            source_entity_uuid=caster.uuid,
            caster_level=5,
            template=True,
        ),
    )
    Entity.update_all_entities_senses(max_distance=30)
    return caster, ally, enemy


def create_field_medic(
    name: str = "Field Medic",
    position: tuple[int, int] = (1, 1),
    faction: str = "heroes",
) -> Entity:
    medic = create_test_monster("monster.goblin", name=name, position=position, faction=faction)
    medic.register_action(
        DeployFieldFocus(source_entity_uuid=medic.uuid, template=True),
    )
    medic.loot_item(
        materialize_item(
            FIELD_KIT_RECIPE,
            medic.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=UsableItem,
        ),
    )
    return medic


def create_field_training_scene() -> tuple[Entity, Entity, UsableItem]:
    medic = create_field_medic()
    ally = create_test_monster("monster.goblin", name="Field Ally", position=(2, 1), faction="heroes")
    floor_kit = materialize_item(
        FIELD_KIT_RECIPE,
        medic.uuid,
        origin=ItemRuntimeOrigin.LOOT,
        expected_type=UsableItem,
    )
    floor_kit.place_on_grid((1, 2))
    Entity.update_all_entities_senses(max_distance=20)
    return medic, ally, floor_kit


def find_action_info(actions, template_name: str) -> AvailableActionInfo:
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def find_item_action(
    actions,
    action_name: str,
    item_uuid,
) -> AvailableActionInfo:
    return find_action_info(actions, f"{action_name}__item_{item_uuid}")


def inventory_item_named(entity: Entity, name: str) -> UsableItem:
    for item in entity.inventory.items.values():
        if item.name == name:
            assert isinstance(item, UsableItem)
            return item
    raise AssertionError(f"{entity.name} does not carry {name}")
