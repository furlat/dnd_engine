"""Test fixture for a small playable gatehouse encounter."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import Field

from dnd.encounters.controllers import HumanController, PassController, TurnContext
from dnd.core.modifiers import AutoHitModifier
from dnd.types.rolls import AutoHitStatus
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from tests.engine.support import create_test_monster
from dnd.runtime_reset import reset_engine_runtime


class ScenarioHumanController(HumanController):
    """Human controller that records scene lifecycle callbacks."""

    name: str = Field(default="Scenario Human", description="Display name.")
    encounter_start_names: list[str] = Field(
        default_factory=list,
        description="Entity names received when the encounter starts.",
    )
    encounter_end_names: list[str] = Field(
        default_factory=list,
        description="Entity names received when the encounter ends.",
    )
    turn_start_contexts: list[TurnContext] = Field(
        default_factory=list,
        description="Turn contexts received when a controlled turn starts.",
    )

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Record controlled entities when the encounter begins.

        Args:
            entities: Entities assigned to this controller.
        """
        self.encounter_start_names.extend(entity.name for entity in entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Record controlled entities when the encounter ends.

        Args:
            entities: Entities assigned to this controller.
        """
        self.encounter_end_names.extend(entity.name for entity in entities)

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record the playable turn context exposed to a client.

        Args:
            entity: Entity whose turn started.
            context: Turn context passed to the controller.
        """
        self.turn_start_contexts.append(context)


class ScenarioPassController(PassController):
    """Pass controller that records automated scene turns."""

    name: str = Field(default="Scenario Pass", description="Display name.")
    turn_start_names: list[str] = Field(
        default_factory=list,
        description="Entity names whose automated turns started.",
    )
    turn_end_names: list[str] = Field(
        default_factory=list,
        description="Entity names whose automated turns ended.",
    )

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record an automated turn start.

        Args:
            entity: Entity whose turn started.
            context: Turn context passed to the controller.
        """
        self.turn_start_names.append(entity.name)

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Record an automated turn end.

        Args:
            entity: Entity whose turn ended.
            context: Turn context passed to the controller.
        """
        self.turn_end_names.append(entity.name)


@dataclass(frozen=True)
class GatehouseScenario:
    """Playable scenario objects returned by the scene factory."""

    encounter: Encounter
    hero: Entity
    monster: Entity
    hero_controller: ScenarioHumanController
    monster_controller: ScenarioPassController


def reset_playable_scenario_state(width: int = 8, height: int = 6) -> None:
    """Clear global state and create a small gatehouse arena.

    Args:
        width: Arena width in tiles.
        height: Arena height in tiles.
    """
    reset_engine_runtime(grid_size=(width, height))


def create_gatehouse_scenario() -> GatehouseScenario:
    """Create a playable scene with one human hero and one automated monster.

    Returns:
        Gatehouse scenario bundle containing encounter, actors, and controllers.
    """
    reset_playable_scenario_state()
    hero = create_test_monster("monster.goblin", name="Gatehouse Hero", position=(1, 1), faction="heroes")
    monster = create_test_monster("monster.skeleton", name="Gatehouse Skeleton", position=(2, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    hero_controller = ScenarioHumanController(source_entity_uuid=hero.uuid)
    monster_controller = ScenarioPassController(source_entity_uuid=monster.uuid)
    encounter = Encounter(name="Gatehouse Scenario", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()
    encounter.initiative_order = [monster.uuid, hero.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()

    return GatehouseScenario(
        encounter=encounter,
        hero=hero,
        monster=monster,
        hero_controller=hero_controller,
        monster_controller=monster_controller,
    )


def add_melee_auto_hit(entity: Entity) -> UUID:
    """Make the entity's next melee attack hit deterministically.

    Args:
        entity: Attacking entity.

    Returns:
        UUID of the temporary auto-hit modifier.
    """
    modifier = AutoHitModifier(
        name="Scenario Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def remove_melee_auto_hit(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove the deterministic melee attack modifier.

    Args:
        entity: Entity whose attack modifier should be removed.
        modifier_uuid: Modifier UUID returned by `add_melee_auto_hit`.
    """
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)
