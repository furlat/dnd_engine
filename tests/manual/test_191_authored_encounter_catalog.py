"""Preservation checks not duplicated by direct scenario deployment tests."""

import re
from uuid import uuid4

from dnd.content.characters.scenario_character_builds import (
    create_scenario_character,
)
from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_ENCOUNTERS,
    AUTHORED_ROSTERS,
)
from dnd.content.scenarios.scenario_definitions import RosterSpellGrant
from dnd.runtime_reset import reset_engine_runtime


def _spell_id(name: str) -> str:
    return "spell." + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def test_every_authored_spell_matrix_preserves_requested_runtime_spells() -> None:
    """Capacity-overflow spells remain explicit scenario grants."""
    all_rosters = (
        *AUTHORED_ROSTERS,
        *(
            slot.roster
            for encounter in AUTHORED_ENCOUNTERS
            for slot in encounter.roster_slots
        ),
    )
    audited_members = 0
    for roster in all_rosters:
        for member in roster.members:
            requested_names = tuple(member.source.parameters.get("spell_names", ()))
            if not requested_names:
                continue
            audited_members += 1
            reset_engine_runtime()
            entity = create_scenario_character(
                member.source.entity_id,
                uuid4(),
                name=member.display_name,
                faction="spell-matrix-audit",
                parameters=member.source.parameters,
            )
            learned_ids = {
                action.behavior_id for action in entity.registered_actions
            }
            granted_ids = {
                spell_id
                for effect in member.scenario_setup_effects
                if isinstance(effect, RosterSpellGrant)
                for spell_id in effect.spell_ids
            }
            assert len(granted_ids) == sum(
                len(effect.spell_ids)
                for effect in member.scenario_setup_effects
                if isinstance(effect, RosterSpellGrant)
            ), (roster.roster_id, member.member_id)
            assert {
                _spell_id(name) for name in requested_names
            } <= learned_ids | granted_ids, (roster.roster_id, member.member_id)

    reset_engine_runtime()
    assert audited_members == 26


def test_payloads_do_not_export_retired_scenario_ontology() -> None:
    serialized = repr([
        encounter.model_dump(mode="json")
        for encounter in AUTHORED_ENCOUNTERS
    ])
    for retired in (
        "hero_configuration_id",
        "monster_configuration_id",
        "side_kind",
        "hero_slots",
        "monster_slots",
        "source_arena_id",
        "rating_eligible",
        "legacy.",
        "historical_validation",
        "content_digest",
        "recipe_digest",
        "content_ref",
    ):
        assert retired not in serialized
