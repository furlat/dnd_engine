"""Exact content identity across spell, content, and presentation catalogs."""

import ast
from pathlib import Path
from uuid import uuid4

import dnd.spells as spells_package
from dnd.content_system.behavior_bindings import BehaviorBinder
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import runtime_behavior_provider
from dnd.core.events import EventPhase
from dnd.entity import Entity, EntityConfig
from dnd.items import spell_items
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells import (
    ALL_SPELLS,
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CATALOG_METADATA_BY_ID,
    SPELL_CATALOG_METADATA_BY_NAME,
    SPELL_CATALOG_METADATA_SPECS,
    SPELL_CONTENT_DECLARATIONS,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
    SPELL_CONTENT_DECLARATIONS_BY_NAME,
    SPELL_CONTENT_IDENTITY_SPECS,
)
from dnd.spells.content_metadata import get_spell_catalog_metadata
from dnd.spells.evocation import FireBolt
from dnd.actions import SpellEvent
from server import spell_catalog
from server.api_models import SpellCatalogEntry, SpellCatalogSavingThrow
from server.content_catalog import build_public_content_catalog
from server.player_replication.journal import SubjectiveFrameProjectionContext
from server.player_replication.mapper import (
    CanonicalSubjectivePresentationMapper,
    CausalEventBatch,
    ProjectedEventSlot,
)
from server.player_replication_contract import (
    BehaviorPresentationRole,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    RootedBehaviorPresentationAttribution,
    SpellPresentationCue,
    SubjectivePerspective,
    UnrootedBehaviorPresentationAttribution,
)

EXPECTED_CATALOG_IDS = (
    "fire_bolt",
    "sacred_flame",
    "poison_spray",
    "ray_of_frost",
    "acid_splash",
    "chill_touch",
    "shocking_grasp",
    "eldritch_blast",
    "true_strike",
    "guidance",
    "light",
    "resistance",
    "aegis_spark",
    "magic_missile",
    "mage_armor",
    "burning_hands",
    "thunderwave",
    "false_life",
    "charm_person",
    "sleep",
    "color_spray",
    "shield",
    "guiding_bolt",
    "grease",
    "fog_cloud",
    "bane",
    "bless",
    "jump",
    "expeditious_retreat",
    "command",
    "cure_wounds",
    "healing_word",
    "inflict_wounds",
    "shield_of_faith",
    "sanctuary",
    "hold_person",
    "shatter",
    "scorching_ray",
    "blur",
    "misty_step",
    "blindness_deafness",
    "spike_growth",
    "web",
    "invisibility",
    "darkness",
    "mirror_image",
    "necrotic_bless",
    "darkvision",
    "see_invisibility",
    "gust_of_wind",
    "enhance_ability",
    "enlarge_reduce",
    "silence",
    "continual_flame",
    "prayer_of_healing",
    "lesser_restoration",
    "protection_from_poison",
    "aid",
    "call_lightning",
    "fireball",
    "lightning_bolt",
    "protection_from_energy",
    "fear",
    "hypnotic_pattern",
    "spirit_guardians",
    "daylight",
    "slow",
    "haste",
    "stinking_cloud",
    "sleet_storm",
    "mass_healing_word",
    "beacon_of_hope",
    "counterspell",
    "remove_curse",
    "bestow_curse",
    "blight",
    "stoneskin",
    "greater_invisibility",
    "ice_storm",
    "dimension_door",
    "banishment",
    "guardian_of_faith",
    "death_ward",
    "freedom_of_movement",
    "hold_monster",
    "cone_of_cold",
    "cloudkill",
    "insect_plague",
    "telekinesis",
    "flame_strike",
    "mass_cure_wounds",
    "greater_restoration",
    "circle_of_death",
    "disintegrate",
    "true_seeing",
    "sunbeam",
    "chain_lightning",
    "eyebite",
    "globe_of_invulnerability",
    "heal",
    "harm",
    "heroes_feast",
    "prismatic_spray",
    "finger_of_death",
    "regenerate",
    "divine_word",
    "sunburst",
    "power_word_stun",
    "incendiary_cloud",
    "antimagic_field",
    "power_word_kill",
    "mass_heal",
)
EXPECTED_NATIVE_CATALOG_IDS = tuple(
    catalog_id
    for catalog_id in EXPECTED_CATALOG_IDS
    if catalog_id not in {
        "aegis_spark",
        "counterspell",
        "shield",
    }
)


def test_public_spell_maps_are_projections_of_the_single_authored_inventory() -> None:
    """The package initializer must not author a second literal spell list."""
    source = Path(spells_package.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_map_names = {
        "CANTRIPS",
        *(f"LEVEL_{level}_SPELLS" for level in range(1, 10)),
        "ALL_SPELLS",
    }
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in public_map_names
    }

    assert set(assignments) == public_map_names
    for value in assignments.values():
        assert isinstance(value, ast.Call)
        assert isinstance(value.func, ast.Name)
        assert value.func.id == "_spell_map_for_level"

    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_spell_map_for_level"
    )
    assert any(
        isinstance(node, ast.Name)
        and node.id == "SPELL_CONTENT_IDENTITY_SPECS"
        for node in ast.walk(helper)
    )
    assert not any(
        isinstance(value, ast.Dict)
        for value in assignments.values()
    )


def test_all_public_spells_have_one_explicit_exact_content_identity() -> None:
    """The public spell catalog cannot infer content identity from a label."""
    assert tuple(ALL_SPELLS.items()) == tuple(
        (spec.display_name, spec.spell_type)
        for spec in SPELL_CONTENT_IDENTITY_SPECS
    )
    assert set(SPELL_CONTENT_DECLARATIONS_BY_NAME) == set(ALL_SPELLS)
    assert set(SPELL_CONTENT_DECLARATIONS_BY_CLASS) == set(ALL_SPELLS.values())

    refs = tuple(
        declaration.ref
        for declaration in SPELL_CONTENT_DECLARATIONS
    )
    assert len({ref.identity_key for ref in refs}) == len(refs)
    assert all(
        ref.definition_kind is ContentDefinitionKind.SPELL
        for ref in refs
    )

    for spec, declaration in zip(
        SPELL_CONTENT_IDENTITY_SPECS,
        SPELL_CONTENT_DECLARATIONS,
        strict=True,
    ):
        assert SPELL_CONTENT_DECLARATIONS_BY_NAME[spec.display_name] is declaration
        assert SPELL_CONTENT_DECLARATIONS_BY_CLASS[spec.spell_type] is declaration
        assert get_content_declaration(spec.spell_type).ref == declaration.ref
        assert declaration.ref.pack_id == spec.pack_id
        assert declaration.ref.content_id == spec.content_id
        assert declaration.descriptor.display_name == spec.display_name


def test_spell_icon_keys_use_exact_authored_manifest_identity() -> None:
    """Manifest keys are authored facts, never content-id normalization."""
    assert (
        SPELL_CONTENT_DECLARATIONS_BY_NAME[
            "Burning Hands"
        ].descriptor.presentation.icon_key
        == "spell.burning-hands"
    )
    assert (
        SPELL_CONTENT_DECLARATIONS_BY_NAME[
            "Lightning Bolt"
        ].descriptor.presentation.icon_key
        == "spell.lightning-bolt"
    )


def test_all_public_spells_have_one_exact_authored_catalog_row() -> None:
    """The reviewed literal inventory prevents silent omissions or aliases."""
    assert len(set(EXPECTED_CATALOG_IDS)) == len(EXPECTED_CATALOG_IDS)
    assert tuple(
        metadata.catalog_id
        for _, metadata in SPELL_CATALOG_METADATA_SPECS
    ) == EXPECTED_NATIVE_CATALOG_IDS
    assert tuple(SPELL_CATALOG_METADATA_BY_ID) == EXPECTED_NATIVE_CATALOG_IDS
    assert tuple(SPELL_CATALOG_METADATA_BY_NAME) == tuple(ALL_SPELLS)
    assert tuple(SPELL_CATALOG_METADATA_BY_CLASS) == tuple(
        ALL_SPELLS.values(),
    )

    for spec in SPELL_CONTENT_IDENTITY_SPECS:
        metadata = SPELL_CATALOG_METADATA_BY_CLASS[spec.spell_type]
        assert metadata is SPELL_CATALOG_METADATA_BY_NAME[spec.display_name]
        assert metadata is SPELL_CATALOG_METADATA_BY_ID[metadata.catalog_id]
        assert get_spell_catalog_metadata(spec.spell_type) is metadata
        assert metadata.catalog_id == spec.content_id.removeprefix("spell.")


def test_spell_refs_resolve_in_frozen_registry_and_public_content_catalog() -> None:
    """Every spell-catalog join target is installed and publicly discoverable."""
    loaded = bootstrap_content_system()
    public = build_public_content_catalog(loaded)
    public_by_key = {
        entry.ref.identity_key: entry
        for entry in public.entries
    }

    for declaration in SPELL_CONTENT_DECLARATIONS:
        resolved = loaded.registry.resolve_definition(declaration.ref)
        assert resolved.ref == declaration.ref
        catalog_entry = public_by_key[declaration.ref.identity_key]
        assert catalog_entry.ref == declaration.ref
        assert catalog_entry.display_name == declaration.descriptor.display_name


def test_public_registered_spell_definitions_are_exactly_the_spell_catalog() -> None:
    """A public independent spell cannot exist outside the authored catalog."""
    loaded = bootstrap_content_system(pack_roots=())
    registered_public_spell_refs = {
        declaration.ref.model_dump_json()
        for declaration in loaded.registry.declarations.values()
        if (
            declaration.ref.definition_kind is ContentDefinitionKind.SPELL
            and declaration.descriptor.visibility is ContentVisibility.PUBLIC
        )
    }
    catalog_refs = {
        row.content_ref.model_dump_json()
        for row in spell_catalog.build_spell_catalog().spells
    }

    assert catalog_refs == registered_public_spell_refs


def test_spell_catalog_id_and_content_ref_are_independently_authored() -> None:
    """Catalog lookup projects its explicit ID and exact durable identity."""
    expected = SPELL_CONTENT_DECLARATIONS_BY_CLASS[FireBolt].ref
    composition = next(
        row
        for row in SPELL_CATALOG_COMPOSITION_ROWS
        if row.spell_type is FireBolt
    )
    entry = spell_catalog.build_spell_catalog_entry(composition)

    assert entry.id == SPELL_CATALOG_METADATA_BY_CLASS[FireBolt].catalog_id
    assert entry.id == "fire_bolt"
    assert entry.content_ref == expected
    assert entry.model_dump()["content_ref"] == expected.model_dump()
    assert "aliases" not in entry.model_dump()

def test_spell_catalog_projection_has_no_runtime_inference_paths() -> None:
    """The backend projection cannot recover facts from names or source code."""
    source = Path(spell_catalog.__file__).read_text(encoding="utf-8")
    forbidden_fragments = (
        "import inspect",
        "inspect.getsource",
        "import re",
        "re.search",
        "normalize_spell_id",
        "SPELL_CATALOG_OVERRIDES",
        "HEALING_SPELL_IDS",
        "_instantiate_spell",
        "uuid4",
        "ALL_SPELLS",
    )
    assert all(fragment not in source for fragment in forbidden_fragments)


def test_spell_catalog_wire_schema_is_hard_cut_and_exact() -> None:
    """The plural save list and height dimension have no legacy aliases."""
    entry_schema = SpellCatalogEntry.model_json_schema()
    save_schema = SpellCatalogSavingThrow.model_json_schema()

    assert {
        "id",
        "content_ref",
        "name",
        "level",
        "school",
        "description",
        "target_type",
        "range_type",
        "range_ft",
        "saving_throws",
        "source",
        "vfx",
    } <= set(entry_schema["required"])
    assert "saving_throw" not in entry_schema["properties"]
    assert "aliases" not in entry_schema["properties"]
    assert "aoe_height_ft" in entry_schema["properties"]
    assert save_schema["properties"]["ability"]["enum"] == [
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    ]
    assert save_schema["required"] == ["ability", "dc_source"]


def test_complete_spell_catalog_uses_the_exact_class_declarations() -> None:
    """Every wire row is an exact projection of the reviewed inventory."""
    spell_catalog.build_spell_catalog.cache_clear()
    response = spell_catalog.build_spell_catalog()

    assert response.version == "2026-07-26.2"
    assert tuple(row.id for row in response.spells) == EXPECTED_CATALOG_IDS
    for composition, row in zip(
        SPELL_CATALOG_COMPOSITION_ROWS,
        response.spells,
        strict=True,
    ):
        declaration = composition.declaration
        metadata = composition.metadata
        assert row.name == composition.display_name
        assert row.id == metadata.catalog_id
        assert row.content_ref == declaration.ref
        assert row.level == composition.level
        assert row.school == composition.school
        assert row.description == metadata.description
        assert row.target_type == metadata.target_type
        assert row.range_type == metadata.range_type
        assert row.range_ft == metadata.range_ft
        assert row.projectile_type == metadata.projectile_type
        assert row.damage_types == [
            damage_type.value
            for damage_type in metadata.damage_types
        ]
        assert tuple(
            save.ability
            for save in row.saving_throws
        ) == tuple(
            save.ability
            for save in metadata.saving_throws
        )
        assert row.source == declaration.provenance.primary_source_id
        assert "aliases" not in row.model_dump()

        if metadata.aoe is None:
            assert row.aoe_shape_type is None
            assert row.aoe_radius_ft is None
            assert row.aoe_length_ft is None
            assert row.aoe_width_ft is None
            assert row.aoe_height_ft is None
        else:
            assert row.aoe_shape_type == metadata.aoe.shape
            assert row.aoe_radius_ft == metadata.aoe.radius_ft
            assert row.aoe_length_ft == metadata.aoe.length_ft
            assert row.aoe_width_ft == metadata.aoe.width_ft
            assert row.aoe_height_ft == metadata.aoe.height_ft


def test_deferred_and_multi_save_spells_keep_exact_ordered_metadata() -> None:
    """Zone, object, and granted-action saves remain visible in the catalog."""
    response = spell_catalog.build_spell_catalog()
    rows = {row.id: row for row in response.spells}

    assert tuple(
        save.ability
        for save in rows["sleet_storm"].saving_throws
    ) == ("dexterity", "constitution")
    assert tuple(
        save.ability
        for save in rows["prismatic_spray"].saving_throws
    ) == ("dexterity", "constitution", "wisdom")
    assert tuple(
        save.ability
        for save in rows["guardian_of_faith"].saving_throws
    ) == ("dexterity",)
    assert tuple(
        save.ability
        for save in rows["sunbeam"].saving_throws
    ) == ("constitution",)

    assert rows["sleet_storm"].aoe_shape_type == "cylinder"
    assert rows["sleet_storm"].aoe_radius_ft == 40
    assert rows["sleet_storm"].aoe_height_ft == 20
    assert rows["sunbeam"].aoe_shape_type == "line"
    assert rows["sunbeam"].aoe_length_ft == 60
    assert rows["sunbeam"].aoe_width_ft == 5
    assert rows["ice_storm"].aoe_height_ft == 40
    assert rows["flame_strike"].aoe_height_ft == 40


def test_bound_spell_event_projects_the_same_content_ref() -> None:
    """Runtime cue attribution closes the catalog-to-presentation join."""
    loaded = bootstrap_content_system()
    binder = BehaviorBinder(loaded.registry)
    caster_uuid = uuid4()
    spell = FireBolt(
        source_entity_uuid=caster_uuid,
        use_register=False,
    )
    binding = binder.bind_independent(
        spell,
        runtime_owner_uuid=caster_uuid,
    )
    declaration = SPELL_CONTENT_DECLARATIONS_BY_CLASS[FireBolt]
    assert binding.definition_ref == declaration.ref

    with runtime_behavior_provider(spell):
        event = SpellEvent(
            name="Fire Bolt",
            spell_id="fire_bolt",
            source_entity_uuid=caster_uuid,
            spell_school="evocation",
            spell_level=0,
            cast_at_level=0,
            range_type="ranged",
            projectile_type="bolt",
            phase=EventPhase.COMPLETION,
            use_register=False,
        )

    perspective = SubjectivePerspective(
        perspective_epoch_id="spell-content-test",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(str(caster_uuid),),
        observer_entity_uuids=(str(caster_uuid),),
        active_observer_uuid=str(caster_uuid),
    )
    frame = CanonicalSubjectivePresentationMapper().project_frame(
        CausalEventBatch(
            slots=(
                ProjectedEventSlot(
                    source_event_cursor=1,
                    event=event,
                ),
            ),
            through_source_event_cursor=1,
        ),
        SubjectiveFrameProjectionContext(
            protocol=PlayerReplicationProtocolIdentity(
                source_stream_id="spell-content-stream",
                generation_id="spell-content-generation",
            ),
            perspective=perspective,
            previous_watermarks=PlayerReplicationWatermarks(
                source_event_cursor=0,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            next_observation_cursor=1,
        ),
    )

    assert len(frame.presentation) == 1
    cue = frame.presentation[0]
    assert isinstance(cue, SpellPresentationCue)
    assert cue.content_attributions == (
        UnrootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=declaration.ref,
            provided_by_ref=declaration.ref,
        ),
    )


def test_executed_acid_flask_projects_exact_item_rooted_spell_attribution() -> None:
    """Real item execution carries its spell/item chain into presentation."""
    reset_engine_runtime(grid_size=(8, 8))
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Alchemist",
        config=EntityConfig(position=(1, 1), faction="heroes"),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Target",
        config=EntityConfig(position=(3, 3), faction="monsters"),
    )
    Entity.update_all_entities_senses(max_distance=100)
    flask = materialize_item(
        spell_items.ACID_FLASK_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=spell_items.SpellGrantingItem,
    )
    action = flask.get_use_actions(caster.uuid)[0].instantiate(
        end_position=target.position,
    )

    result = action.apply()

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    observer = str(caster.uuid)
    projected = result.model_copy(
        update={
            "identified_entity_observer_uuids": {
                str(caster.uuid): {observer},
                str(target.uuid): {observer},
            },
            "located_entity_observer_uuids": {
                str(caster.uuid): {observer},
                str(target.uuid): {observer},
            },
        },
    )
    perspective = SubjectivePerspective(
        perspective_epoch_id="acid-flask-content-test",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(observer,),
        observer_entity_uuids=(observer,),
        active_observer_uuid=observer,
    )
    frame = CanonicalSubjectivePresentationMapper().project_frame(
        CausalEventBatch(
            slots=(
                ProjectedEventSlot(
                    source_event_cursor=1,
                    event=projected,
                ),
            ),
            through_source_event_cursor=1,
        ),
        SubjectiveFrameProjectionContext(
            protocol=PlayerReplicationProtocolIdentity(
                source_stream_id="acid-flask-content-stream",
                generation_id="acid-flask-content-generation",
            ),
            perspective=perspective,
            previous_watermarks=PlayerReplicationWatermarks(
                source_event_cursor=0,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            next_observation_cursor=1,
        ),
    )

    cue = next(
        row
        for row in frame.presentation
        if isinstance(row, SpellPresentationCue)
    )
    assert cue.content_attributions == (
        RootedBehaviorPresentationAttribution(
            role=BehaviorPresentationRole.BEHAVIOR,
            definition_ref=spell_items.ACID_FLASK_SPELL_REF,
            provided_by_ref=spell_items.ACID_FLASK_REF,
            origin_root_ref=spell_items.ACID_FLASK_REF,
        ),
    )
