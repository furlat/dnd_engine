from collections import Counter

from ai.evaluation.config_ladder.schedule import build_connected_schedule
from dnd.core.gridmap import get_map
from dnd.scenarios.evaluation.assembler import reset_composed_scenario_state
from dnd.scenarios.evaluation.battlefield_catalog import (
    BATTLEFIELDS,
    build_battlefield,
    get_battlefield,
)
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
    get_combatant_configuration,
)
from dnd.scenarios.evaluation.compatibility import (
    CompatibilityIssue,
    CompatibilityReport,
    check_built_compatibility,
    check_compatibility,
)
from dnd.scenarios.evaluation.deployment_catalog import (
    DEPLOYMENTS,
    LEGACY_DEPLOYMENTS,
    NEUTRAL_DEPLOYMENTS,
    get_deployment,
)
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec


def test_battlefield_catalog_has_nine_light_aware_mechanical_states() -> None:
    assert len(BATTLEFIELDS) == 9
    assert len({row.battlefield_id for row in BATTLEFIELDS}) == 9
    assert len({row.content_hash for row in BATTLEFIELDS}) == 9
    assert sum(len(row.source_arena_ids) for row in BATTLEFIELDS) == 38
    assert len({arena_id for row in BATTLEFIELDS for arena_id in row.source_arena_ids}) == 38

    bright = get_battlefield("battlefield.open_floor_bright")
    dark = get_battlefield("battlefield.open_floor_dark")
    assert bright.light_level == "bright"
    assert dark.light_level == "darkness"
    assert bright.content_hash != dark.content_hash
    assert all(row.preview is not None for row in BATTLEFIELDS)

    reset_composed_scenario_state()
    build_battlefield(bright.battlefield_id)
    bright_levels = {tile.default_light for tile in get_map().get_all_tiles().values()}
    reset_composed_scenario_state()
    build_battlefield(dark.battlefield_id)
    dark_levels = {tile.default_light for tile in get_map().get_all_tiles().values()}
    assert bright_levels != dark_levels


def test_battlefield_previews_retain_canonical_terrain_barriers_and_objects() -> None:
    """The setup projection uses the same positions and states as map construction."""
    closed = get_battlefield("battlefield.standard_hazards_closed")
    assert closed.preview is not None
    terrain = {(cell.position, cell.terrain) for cell in closed.preview.cells}
    assert ((2, 0), "water") in terrain
    assert ((6, 0), "difficult_terrain") in terrain
    assert ((0, 11), "spikes") in terrain
    door = next(obj for obj in closed.preview.objects if obj.kind == "door")
    assert door.position == (7, 7)
    assert door.blocked_directions == ("west",)
    assert door.is_open is False

    opened = get_battlefield("battlefield.standard_hazards_open")
    assert opened.preview is not None
    open_door = next(obj for obj in opened.preview.objects if obj.kind == "door")
    assert open_door.position == door.position
    assert open_door.blocked_directions == ()
    assert open_door.is_open is True

    labyrinth = get_battlefield("battlefield.reveal_labyrinth_dark")
    assert labyrinth.preview is not None
    assert {
        obj.position
        for obj in labyrinth.preview.objects
        if obj.kind == "door"
    } == {(5, 6), (9, 8)}

    control_room = get_battlefield("battlefield.multi_object_dark")
    assert control_room.preview is not None
    assert {
        (obj.kind, obj.position)
        for obj in control_room.preview.objects
    } >= {
        ("fireball_cannon", (6, 11)),
        ("loot_chest", (5, 10)),
        ("trap_lever", (5, 12)),
    }


def test_deployment_catalog_retains_neutral_and_all_legacy_formations() -> None:
    assert len(NEUTRAL_DEPLOYMENTS) == 9
    assert len(LEGACY_DEPLOYMENTS) == 38
    assert len(DEPLOYMENTS) == 47
    assert len({row.deployment_id for row in DEPLOYMENTS}) == 47
    assert {row.battlefield_id for row in NEUTRAL_DEPLOYMENTS} == {
        row.battlefield_id for row in BATTLEFIELDS
    }
    assert {row.source_arena_id for row in LEGACY_DEPLOYMENTS} == {
        arena_id for battlefield in BATTLEFIELDS for arena_id in battlefield.source_arena_ids
    }
    assert all(row.portable and row.rating_eligible for row in NEUTRAL_DEPLOYMENTS)
    assert all(not row.portable and not row.rating_eligible for row in LEGACY_DEPLOYMENTS)


def test_every_neutral_battlefield_accepts_the_largest_current_party() -> None:
    hero = get_combatant_configuration("hero.sorcerer_l5_standard_torch")
    monsters = get_combatant_configuration("monsters.srd_low_cr_patrol")
    for battlefield in BATTLEFIELDS:
        deployment = get_deployment(f"neutral.{battlefield.battlefield_id}")
        static_report = check_compatibility(hero, monsters, battlefield, deployment)
        assert static_report.admitted, static_report.issues

        reset_composed_scenario_state(battlefield.width, battlefield.height)
        build_battlefield(battlefield.battlefield_id)
        built_report = check_built_compatibility(
            static_report,
            hero,
            monsters,
            deployment,
            get_map(),
        )
        assert built_report.admitted, built_report.issues


def test_static_compatibility_reports_missing_capabilities_without_silent_skip() -> None:
    hero = get_combatant_configuration("hero.sorcerer_l5_standard_torch").model_copy(update={
        "required_battlefield_capabilities": ("nonexistent-object-package",),
    })
    monsters = get_combatant_configuration("monsters.skeleton_trio")
    battlefield = get_battlefield("battlefield.open_floor_bright")
    deployment = get_deployment("neutral.battlefield.open_floor_bright")

    report = check_compatibility(hero, monsters, battlefield, deployment)

    assert not report.admitted
    assert [issue.code for issue in report.issues if issue.severity == "hard"] == ["missing_capability"]


def test_one_seed_neutral_schedule_covers_every_eligible_catalog_cell() -> None:
    eligible_heroes = tuple(row for row in HERO_CONFIGURATIONS if row.rating_eligible)
    eligible_monsters = tuple(
        row for row in MONSTER_PARTY_CONFIGURATIONS if row.rating_eligible
    )
    portable_battlefields = tuple(row for row in BATTLEFIELDS if row.portable)
    deployment_by_id = {row.deployment_id: row for row in DEPLOYMENTS}
    eligible_contexts = {
        (battlefield.battlefield_id, deployment_id)
        for battlefield in portable_battlefields
        for deployment_id in battlefield.deployment_ids
        if deployment_by_id[deployment_id].portable
        and deployment_by_id[deployment_id].rating_eligible
    }
    seed = 20260717
    schedule = build_connected_schedule(
        heroes=eligible_heroes,
        monster_parties=eligible_monsters,
        battlefields=portable_battlefields,
        deployments=DEPLOYMENTS,
        seeds=(seed,),
        experiment_id="one-seed-neutral-baseline",
        created_at="2026-07-17T00:00:00+00:00",
    )

    expected_cells = {
        (
            hero.configuration_id,
            monsters.configuration_id,
            battlefield_id,
            deployment_id,
            seed,
        )
        for hero in eligible_heroes
        for monsters in eligible_monsters
        for battlefield_id, deployment_id in eligible_contexts
    }
    openings_by_cell: dict[tuple[str, str, str, str, int], set[str]] = {}
    for row in schedule.entries:
        cell = (
            row.hero_configuration_id,
            row.monster_configuration_id,
            row.battlefield_id,
            row.deployment_id,
            row.simulation_seed,
        )
        openings_by_cell.setdefault(cell, set()).add(row.opening_treatment)

    assert schedule.exclusions == ()
    assert set(openings_by_cell) == expected_cells
    assert set(map(frozenset, openings_by_cell.values())) == {
        frozenset({"hero_first", "monster_first"})
    }
    assert len(schedule.entries) == len(expected_cells) * 2
    assert Counter(row.hero_configuration_id for row in schedule.entries) == {
        hero.configuration_id: len(eligible_monsters) * len(eligible_contexts) * 2
        for hero in eligible_heroes
    }
    assert Counter(row.monster_configuration_id for row in schedule.entries) == {
        monsters.configuration_id: len(eligible_heroes) * len(eligible_contexts) * 2
        for monsters in eligible_monsters
    }


def test_battlefield_deployment_and_compatibility_contracts_are_described() -> None:
    for model in (BattlefieldSpec, DeploymentSpec, CompatibilityIssue, CompatibilityReport):
        assert all(field.description for field in model.model_fields.values())
