"""An area spell's offered hit set is exactly the set its execution applies to.

Boundary: native discovery (``get_available_actions`` area rows) and native
execution (``execute_available_action``) in one small lit room. Glass cells
block propagation but not sight, so every creature is perceived and only the
area's line of effect decides who is hit. Globe of Invulnerability is out of
scope; no fixture contains one.
"""

from dataclasses import dataclass

import pytest

from dnd.actions import ActionEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.core.base_actions import TargetType
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, SavingThrowEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.catalog_content import SPELL_CATALOG_METADATA_BY_NAME, SPELL_CONTENT_IDENTITY_SPECS
from dnd.spells.evocation import ConeOfCold, FlameStrike, IceStorm, LightningBolt
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, reset_spell_regression_arena,
)

CASTER = (2, 5)
CREATURES = (("Front", (5, 5), "monsters"), ("Ally", (3, 6), "heroes"), ("Side", (6, 3), "monsters"),
             ("Glassed", (8, 5), "monsters"), ("Far", (11, 6), "monsters"), ("Rear", (12, 2), "monsters"))
GLASS = frozenset({(7, 4), (7, 5), (7, 6), (10, 5), (10, 6), (10, 7)})
AIMS_PER_SPELL = 6
AREA_SPELLS = {spec.spell_type: spec for spec in SPELL_CONTENT_IDENTITY_SPECS
    if SPELL_CATALOG_METADATA_BY_NAME[spec.display_name].target_type == "position_aoe"}
# These choose recipients from an HP pool; at 1 HP every creature in the
# area fits the smallest pool, so the area alone decides who is chosen.
HP_POOL_SPELLS = frozenset({"spell.sleep", "spell.color_spray"})


@dataclass(frozen=True)
class Outcome:
    canceled: bool
    discovered: frozenset[str]
    applied: frozenset[str]


def room(spell_type) -> Entity:
    reset_spell_regression_arena(15, 10)
    grid = get_map()
    for x, y in GLASS:
        grid.set_tile(x, y, blocks_optics=False, blocks_propagation=True, name="Glass")
    caster = create_spell_regression_actor("Caster", CASTER, "heroes",
        spell_slots={level: 2 for level in range(1, 10)})
    for name, position, faction in CREATURES:
        create_spell_regression_actor(name, position, faction, hit_die_count=1)
    if AREA_SPELLS[spell_type].content_id in HP_POOL_SPELLS:
        for entity in Entity.get_all_entities():
            entity.receive_damage(entity.get_normal_hp() - 1, DamageType.FORCE, entity.uuid)
    register_spell(caster, spell_type)
    Entity.update_all_entities_senses(max_distance=120)
    return caster


def area_row(caster: Entity, spell_type):
    template = next(action for action in caster.registered_actions if isinstance(action, spell_type))
    return next(row for row in get_available_actions(caster).position_actions
        if row.target_type is TargetType.POSITION_AOE
        and row.template_name.split("__", 1)[0] == template.name)


def names(uuids) -> frozenset[str]:
    return frozenset(entity.name for uid in uuids if (entity := Entity.get(uid)) is not None)


def offered_aims(spell_type) -> list[tuple[int, int]]:
    """A few offered aims, each with a different offered hit set."""
    row = area_row(room(spell_type), spell_type)
    aims, seen = [], set()
    by_position = {target.position: target for target in row.valid_targets if target.position is not None}
    for position in sorted(by_position):
        hit = names(by_position[position].affected_entity_uuids or ())
        if hit not in seen and len(aims) < AIMS_PER_SPELL:
            seen.add(hit)
            aims.append(position)
    return aims


def cast_at(spell_type, aim) -> Outcome:
    """Discover the aim, execute it in the same room and read its applications."""
    caster = room(spell_type)
    row = area_row(caster, spell_type)
    target = next(target for target in row.valid_targets if target.position == aim)
    discovered = names(target.affected_entity_uuids or ())
    cause = AREA_SPELLS[spell_type].content_id
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 800)):
        result = execute_available_action(caster, row, target)
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    applied = names(event.target_entity_uuid for event in events
        if isinstance(event, ActionEvent) and event.application is not None
        or isinstance(event, SavingThrowEvent) and event.saving_throw_context is not None
        and event.saving_throw_context.cause_id == cause)
    return Outcome(canceled=result is None or result.canceled, discovered=discovered, applied=applied)


@pytest.fixture(autouse=True)
def clean_runtime():
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("spell_type", AREA_SPELLS, ids=lambda spell_type: AREA_SPELLS[spell_type].display_name)
def test_discovery_hit_set_equals_execution_applications(spell_type):
    aims = offered_aims(spell_type)
    assert aims, "no offered aim"
    for aim in aims:
        outcome = cast_at(spell_type, aim)
        assert not outcome.canceled, aim
        assert outcome.discovered == outcome.applied, (aim,
            "discovery only", sorted(outcome.discovered - outcome.applied),
            "execution only", sorted(outcome.applied - outcome.discovered))


@pytest.mark.parametrize("spell_type,aim,hit,missed", [
    # U1: caster-origin shapes stop at glass, in discovery as in execution.
    (ConeOfCold, (12, 2), {"Front", "Side"}, {"Glassed", "Far"}),
    (LightningBolt, (11, 6), {"Front"}, {"Far"}),
    # U2: cylinders fall from above, so glass does not shelter anyone.
    (IceStorm, (8, 5), {"Glassed", "Front", "Side", "Far"}, set()),
    (FlameStrike, (9, 6), {"Glassed", "Far"}, set()),
], ids=["U1-cone", "U1-line", "U2-ice-storm", "U2-flame-strike"])
def test_area_line_of_effect_is_the_same_in_discovery_and_execution(spell_type, aim, hit, missed):
    outcome = cast_at(spell_type, aim)
    assert not outcome.canceled
    assert hit <= outcome.discovered and not missed & outcome.discovered, sorted(outcome.discovered)
    assert outcome.discovered == outcome.applied
