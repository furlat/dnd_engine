from ai.evaluation.config_ladder.catalog_snapshot import (
    build_catalog_snapshot,
    load_catalog_snapshot,
    write_catalog_snapshot,
)
from ai.evaluation.config_ladder.schedule import build_connected_schedule, schedule_connectivity
from dnd.scenarios.evaluation.models import (
    BattlefieldSpec,
    BestiaryActorBlueprint,
    DeploymentSpec,
    FighterActorBlueprint,
    SideConfigurationSpec,
)


def test_schedule_crosses_configs_contexts_and_paired_openings_deterministically() -> None:
    heroes = tuple(_hero(index) for index in range(2))
    monsters = tuple(_monsters(index) for index in range(3))
    battlefields = (
        BattlefieldSpec(
            battlefield_id="field.open",
            title="Open Field",
            builder_id="open_floor",
            deployment_ids=("deploy.open",),
        ),
        BattlefieldSpec(
            battlefield_id="field.door",
            title="Door Field",
            builder_id="standard_door",
            deployment_ids=("deploy.door",),
        ),
    )
    deployments = (
        DeploymentSpec(
            deployment_id="deploy.open",
            title="Open Deployment",
            battlefield_id="field.open",
            hero_slots=((2, 2),),
            monster_slots=((10, 4), (10, 6), (10, 8)),
        ),
        DeploymentSpec(
            deployment_id="deploy.door",
            title="Door Deployment",
            battlefield_id="field.door",
            hero_slots=((2, 7),),
            monster_slots=((12, 5), (12, 7), (12, 9)),
        ),
    )

    first = build_connected_schedule(
        heroes=heroes,
        monster_parties=monsters,
        battlefields=battlefields,
        deployments=deployments,
        seeds=(17,),
    )
    second = build_connected_schedule(
        heroes=heroes,
        monster_parties=monsters,
        battlefields=battlefields,
        deployments=deployments,
        seeds=(17,),
    )

    assert len(first.entries) == 2 * 3 * 2 * 1 * 2
    assert first.schedule_hash == second.schedule_hash
    assert {entry.opening_treatment for entry in first.entries} == {"hero_first", "monster_first"}
    assert all(len(rows) == 2 for rows in first.entries_by_pair_block().values())
    assert [entry.schedule_index for entry in first.entries] == list(range(len(first.entries)))


def test_schedule_reports_one_connected_bipartite_participant_graph() -> None:
    schedule = build_connected_schedule(
        heroes=tuple(_hero(index) for index in range(2)),
        monster_parties=tuple(_monsters(index) for index in range(3)),
        battlefields=(BattlefieldSpec(
            battlefield_id="field.open",
            title="Open Field",
            builder_id="open_floor",
            deployment_ids=("deploy.open",),
        ),),
        deployments=(DeploymentSpec(
            deployment_id="deploy.open",
            title="Open Deployment",
            battlefield_id="field.open",
            hero_slots=((2, 2),),
            monster_slots=((10, 4), (10, 6), (10, 8)),
        ),),
        seeds=(11,),
    )

    connectivity = schedule_connectivity(schedule)

    assert connectivity.connected
    assert connectivity.component_count == 1
    assert connectivity.hero_count == 2
    assert connectivity.monster_party_count == 3
    assert connectivity.edge_count == 6


def test_catalog_snapshot_round_trip_authenticates_mechanical_content(tmp_path) -> None:
    heroes = (_hero(0),)
    monsters = (_monsters(0),)
    battlefield = BattlefieldSpec(
        battlefield_id="field.open",
        title="Open Field",
        builder_id="open_floor",
        deployment_ids=("deploy.open",),
    )
    deployment = DeploymentSpec(
        deployment_id="deploy.open",
        title="Open Deployment",
        battlefield_id="field.open",
        hero_slots=((2, 2),),
        monster_slots=((10, 6),),
    )
    snapshot = build_catalog_snapshot(
        heroes=heroes,
        monster_parties=monsters,
        battlefields=(battlefield,),
        deployments=(deployment,),
        policy_version="test-policy",
        policy_source_hash="abc123",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    path = write_catalog_snapshot(snapshot, tmp_path / "catalog.json")

    loaded = load_catalog_snapshot(path)

    assert loaded == snapshot
    assert loaded.hero("hero.0").mechanical_hash == heroes[0].mechanical_hash
    assert loaded.monster_party("monsters.0").mechanical_hash == monsters[0].mechanical_hash


def _hero(index: int) -> SideConfigurationSpec:
    return SideConfigurationSpec(
        configuration_id=f"hero.{index}",
        title=f"Hero {index}",
        side_kind="hero",
        members=(FighterActorBlueprint(
            actor_id="hero",
            level=5,
            fighting_style="archery" if index else "dueling",
            equipment_preset="archery" if index else "sword_shield",
            asi_4=(("dexterity" if index else "strength", 2),),
        ),),
    )


def _monsters(index: int) -> SideConfigurationSpec:
    return SideConfigurationSpec(
        configuration_id=f"monsters.{index}",
        title=f"Monsters {index}",
        side_kind="monster_party",
        members=(BestiaryActorBlueprint(
            actor_id="monster",
            archetype=("skeleton_warrior", "skeleton_archer", "goblin")[index],
            darkvision=True,
        ),),
    )
