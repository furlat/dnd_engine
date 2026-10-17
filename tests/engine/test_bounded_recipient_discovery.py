"""Recipient discovery is bounded by range and perception, never by the size of the world.

Boundary: public discovery (`get_available_actions`) and execution (`execute_available_action`).
Inputs: one caster, recipients in different places, life states and visibility, plus far bystanders.
Outputs: the offered recipients, a row's allocation count, and who receives the effect.
"""

from dataclasses import dataclass

import pytest

from dnd.actions_functional import execute_available_action, register_spell
from dnd.conditions import Invisible
from dnd.core.base_tiles import wall_factory
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.entity import Entity
from dnd.spells.abjuration import HolyAura
from dnd.spells.necromancy import Revivify
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

CASTER_POSITION = (2, 2)


def rows(caster, name):
    Entity.update_all_entities_senses()
    return [row for row in caster.get_available_actions().entity_actions if row.display_name.startswith(name)]


def offered(caster, name):
    return {target.target_uuid for row in rows(caster, name) for target in row.valid_targets}


@dataclass(frozen=True)
class RevivifyCase:
    name: str
    position: tuple[int, int]
    offered: bool
    state: LifeState = LifeState.DEAD
    companion: bool = True
    disintegrated: bool = False
    invisible: bool = False
    walled: bool = False


def check(case: RevivifyCase) -> None:
    reset_spell_regression_arena(16, 10)
    caster = create_spell_regression_actor("Caster", CASTER_POSITION, "heroes", spell_slots={3: 2})
    register_spell(caster, Revivify)
    if case.walled:
        for x in range(16):
            get_map().set_tile(x, 4, tile=wall_factory((x, 4)))
    recipient = create_spell_regression_actor("Recipient", case.position, "heroes")
    recipient.is_player_companion = case.companion
    if case.invisible:
        recipient.add_condition(Invisible(source_entity_uuid=recipient.uuid, target_entity_uuid=recipient.uuid))
    if case.state is LifeState.DYING:
        recipient.uses_death_saves = True
        recipient.receive_damage(recipient.get_hp(), DamageType.FORCE, caster.uuid)
    elif case.state is LifeState.DEAD:
        recipient.receive_damage(1000, DamageType.FORCE, caster.uuid, zero_hp_disposition=(
            RemainsDisposition.DISINTEGRATED if case.disintegrated else RemainsDisposition.INTACT))
    assert recipient.health.life_state is case.state, case.name
    assert (recipient.uuid in offered(caster, "Revivify")) is case.offered, case.name


@pytest.mark.parametrize("case", [
    RevivifyCase("dead companion seen at 25 ft", (7, 2), True),
    RevivifyCase("dead companion at 35 ft", (9, 2), False),
    RevivifyCase("dead companion behind a wall", (2, 6), False, walled=True),
    RevivifyCase("dead non-companion", (4, 2), False, companion=False),
    RevivifyCase("disintegrated companion", (4, 2), False, disintegrated=True),
    RevivifyCase("living companion", (4, 2), False, state=LifeState.ALIVE),
    RevivifyCase("dying companion", (4, 2), True, state=LifeState.DYING),
    RevivifyCase("unperceived invisible dying companion", (4, 2), False, state=LifeState.DYING, invisible=True),
], ids=lambda case: case.name)
def test_revivify_offers_only_reachable_seen_remains_of_companions(case):
    check(case)


def test_holy_aura_allocation_counts_admitted_recipients_not_the_world():
    reset_spell_regression_arena(40, 14)
    caster = create_spell_regression_actor("Caster", CASTER_POSITION, "heroes", spell_slots={8: 2})
    register_spell(caster, HolyAura)
    near = [create_spell_regression_actor("Near ally", position, "heroes") for position in ((4, 2), (2, 6))]
    distant = create_spell_regression_actor("Ally at 40 ft", (10, 2), "heroes")
    hidden = create_spell_regression_actor("Invisible ally", (2, 4), "heroes")
    hidden.add_condition(Invisible(source_entity_uuid=hidden.uuid, target_entity_uuid=hidden.uuid))
    for index in range(10):
        create_spell_regression_actor(f"Far hostile {index}", (20 + index, 8), "monsters")
    [row] = rows(caster, "Holy Aura")
    admitted = {caster.uuid, *(ally.uuid for ally in near)}
    assert {target.target_uuid for target in row.valid_targets} == admitted
    assert row.num_projectiles == 3
    for index in range(20):
        create_spell_regression_actor(f"Far bystander {index}", (20 + index, 12), "monsters")
    [row] = rows(caster, "Holy Aura")
    assert row.num_projectiles == 3
    primary = next(target for target in row.valid_targets if target.target_uuid == caster.uuid)
    with pytest.raises(ValueError, match="exceed the action allocation count"):
        execute_available_action(caster, row, primary,
            extra_target_uuids=[str(ally.uuid) for ally in near] + [str(distant.uuid)])
    assert caster.action_economy.spell_slot_8.normalized_score == 2
    result = execute_available_action(caster, row, primary, extra_target_uuids=[str(ally.uuid) for ally in near])
    assert result is not None and not result.canceled, result
    warded = {entity.uuid for entity in (caster, *near, distant, hidden)
              if any(condition.get_display_name() == "Holy Aura"
                     for condition in entity.active_conditions_by_uuid.values())}
    assert warded == admitted
