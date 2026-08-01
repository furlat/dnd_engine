"""Deterministic Dragonborn Breath Weapon and receipt lifecycle regressions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
    BUILT_IN_RECIPE_PRESET_INVENTORY,
)
from dnd.content_system.character_appearance import FIGHTER_HUMAN_APPEARANCE
from dnd.content_system.character_build_validation import (
    CharacterBuildValidator,
    CharacterGrantScheduleKind,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_origin_definitions import (
    ADVENTURER_BACKGROUND_REF,
)
from dnd.content_system.dragonborn_character_grant_appliers import (
    DRAGONBORN_BREATH_RESOURCE,
    install_dragonborn_ancestry_feature,
)
from dnd.content_system.dragonborn_origin_definitions import (
    DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY,
)
from dnd.content_system.fighter_character_grant_appliers import (
    FIGHTING_STYLE_ARCHERY_REF,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.aoe import Cone, Line
from dnd.core.content.dragonborn import (
    DragonbornAncestry,
    DragonbornAncestryFeatureDefinition,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreName,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    FightingStyleChoice,
    FlexibleAbilityBonusSelection,
    OriginTraitChoice,
    StartingEquipmentPackageChoice,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import AbilityName, EventPhase, EventQueue
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    NumericalModifier,
    ResistanceStatus,
)
from dnd.entity import Entity, EntityConfig
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_WEAPON_DECLARATION,
    DragonbornBreathWeapon,
    DragonbornBreathWeaponEvent,
)
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from server.player_replication.journal import (
    SubjectiveFrameProjectionContext,
)
from server.player_replication.mapper import (
    CanonicalSubjectivePresentationMapper,
    CausalEventBatch,
    ProjectedEventSlot,
)
from server.player_replication_contract import (
    ActionPresentationCue,
    DamagePresentationCue,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    SubjectivePerspective,
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(20, 12))
    yield
    reset_engine_runtime()


@pytest.fixture(scope="module")
def dragonborn_runtime() -> ContentSystemRuntime:
    additions = (
        DRAGONBORN_BREATH_WEAPON_DECLARATION,
        *DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY.values(),
    )
    declarations = {
        declaration.ref.identity_key: declaration
        for declaration in additions
    }
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations=declarations,
                recipe_presets={},
                sources={},
            ),
            packs=(),
            built_in_artifact_digest="a" * 64,
            content_set_digest="b" * 64,
        ),
    )
    return runtime


def _actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    *,
    constitution: int = 10,
    proficiency_bonus: int = 2,
) -> Entity:
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                constitution=AbilityConfig(ability_score=constitution),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=12,
                        hit_dice_count=10,
                        mode="maximums",
                    ),
                ],
            ),
            position=position,
            faction=faction,
            proficiency_bonus=proficiency_bonus,
        ),
    )


def _force_save(
    entity: Entity,
    ability: AbilityName,
    *,
    succeeds: bool,
) -> None:
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name=f"Dragonborn regression {ability} save",
        value=100 if succeeds else -100,
    )
    entity.saving_throws.get_saving_throw(
        ability,
    ).bonus.self_static.add_value_modifier(modifier)


def _install(
    runtime: ContentSystemRuntime,
    entity: Entity,
    ancestry: DragonbornAncestry,
    *,
    character_level: int,
):
    declaration = DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[ancestry]
    definition = declaration.definition_payload
    assert isinstance(definition, DragonbornAncestryFeatureDefinition)
    return install_dragonborn_ancestry_feature(
        entity=entity,
        character_id=uuid4(),
        grant_token=f"species.dragonborn:{ancestry.value}",
        definition_ref=declaration.ref,
        character_level=character_level,
        definition=definition,
        runtime=runtime,
    )


@pytest.mark.parametrize(
    ("character_level", "expected_dice"),
    (
        (1, 2),
        (5, 2),
        (6, 3),
        (10, 3),
        (11, 4),
        (15, 4),
        (16, 5),
        (20, 5),
    ),
)
def test_breath_weapon_damage_scales_at_exact_character_level_thresholds(
    character_level: int,
    expected_dice: int,
) -> None:
    definition = (
        DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[
            DragonbornAncestry.RED
        ].definition_payload
    )
    assert isinstance(definition, DragonbornAncestryFeatureDefinition)
    action = DragonbornBreathWeapon.from_definition(
        source_entity_uuid=uuid4(),
        ancestry_ref=(
            DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[
                DragonbornAncestry.RED
            ].ref
        ),
        definition=definition,
        character_level=character_level,
        template=True,
    )

    assert action.damage_dice_count == expected_dice


@pytest.mark.parametrize(
    ("ancestry", "shape_type", "length_feet", "width_feet"),
    (
        (DragonbornAncestry.BLACK, Line, 30, 5),
        (DragonbornAncestry.GOLD, Cone, 15, None),
    ),
)
def test_breath_weapon_uses_ancestry_authored_geometry(
    ancestry: DragonbornAncestry,
    shape_type: type[Line] | type[Cone],
    length_feet: int,
    width_feet: int | None,
) -> None:
    declaration = DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[ancestry]
    definition = declaration.definition_payload
    assert isinstance(definition, DragonbornAncestryFeatureDefinition)
    action = DragonbornBreathWeapon.from_definition(
        source_entity_uuid=uuid4(),
        ancestry_ref=declaration.ref,
        definition=definition,
        character_level=1,
        template=True,
    )

    assert isinstance(action.aoe_shape, shape_type)
    assert action.aoe_shape.length_feet == length_feet
    if isinstance(action.aoe_shape, Line):
        assert action.aoe_shape.width_feet == width_feet


def test_breath_weapon_uses_constitution_dc_damage_and_one_rest_use(
    dragonborn_runtime: ContentSystemRuntime,
) -> None:
    caster = _actor(
        "Black Dragonborn",
        (2, 5),
        "heroes",
        constitution=16,
        proficiency_bonus=3,
    )
    target = _actor("Line Target", (6, 5), "monsters")
    _force_save(target, "dexterity", succeeds=False)
    receipt = _install(
        dragonborn_runtime,
        caster,
        DragonbornAncestry.BLACK,
        character_level=6,
    )
    template = caster.get_action_template("Breath Weapon")
    assert isinstance(template, DragonbornBreathWeapon)
    action = template.instantiate(end_position=(3, 5))

    hp_before = target.get_hp()
    with fixed_dice_faces(10, 4, 4, 4):
        result = action.apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    assert result.save_dc == 14
    assert result.save_ability == "dexterity"
    assert result.total_damage == 12
    assert hp_before - target.get_hp() == 12
    assert caster.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 0
    assert not template.check_costs()

    caster.on_short_rest()
    assert caster.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 1
    caster.on_turn_start()
    assert template.check_costs()
    assert receipt.action_uuids == (template.uuid,)


def test_successful_constitution_save_halves_cone_damage(
    dragonborn_runtime: ContentSystemRuntime,
) -> None:
    caster = _actor("Green Dragonborn", (3, 5), "heroes")
    target = _actor("Cone Target", (5, 5), "monsters")
    _force_save(target, "constitution", succeeds=True)
    _install(
        dragonborn_runtime,
        caster,
        DragonbornAncestry.GREEN,
        character_level=1,
    )
    template = caster.get_action_template("Breath Weapon")
    assert isinstance(template, DragonbornBreathWeapon)

    hp_before = target.get_hp()
    with fixed_dice_faces(10, 5, 5):
        result = template.instantiate(end_position=(4, 5)).apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    assert result.save_ability == "constitution"
    assert result.total_damage == 5
    assert hp_before - target.get_hp() == 5


def test_real_breath_weapon_projects_one_authored_action_with_damage_child(
    dragonborn_runtime: ContentSystemRuntime,
) -> None:
    """Per-target convolution rows must not become duplicate action roots."""
    caster = _actor("Red Dragonborn", (3, 5), "heroes")
    target = _actor("Breath Target", (5, 5), "monsters")
    _force_save(target, "dexterity", succeeds=False)
    _install(
        dragonborn_runtime,
        caster,
        DragonbornAncestry.RED,
        character_level=1,
    )
    observer_uuid = str(caster.uuid)
    EventQueue.set_identified_entity_observer_computer(
        lambda event: {
            str(entity_uuid): {observer_uuid}
            for entity_uuid in event.get_participant_entity_uuids()
        },
    )
    source_cursor = EventQueue.event_cursor()
    template = caster.get_action_template("Breath Weapon")
    assert isinstance(template, DragonbornBreathWeapon)

    with fixed_dice_faces(10, 4, 4):
        result = template.instantiate(end_position=(4, 5)).apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    slots = tuple(
        ProjectedEventSlot(
            source_event_cursor=cursor + 1,
            event=event,
        )
        for cursor, event in EventQueue.iter_events_since(source_cursor)
    )
    perspective = SubjectivePerspective(
        perspective_epoch_id="dragonborn-presentation",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(observer_uuid,),
        observer_entity_uuids=(observer_uuid,),
        active_observer_uuid=observer_uuid,
    )
    frame = CanonicalSubjectivePresentationMapper().project_frame(
        CausalEventBatch(
            slots=slots,
            through_source_event_cursor=EventQueue.event_cursor(),
        ),
        SubjectiveFrameProjectionContext(
            protocol=PlayerReplicationProtocolIdentity(
                source_stream_id="dragonborn-stream",
                generation_id="dragonborn-generation",
            ),
            perspective=perspective,
            previous_watermarks=PlayerReplicationWatermarks(
                source_event_cursor=source_cursor,
                observation_cursor=0,
                presentation_cursor=0,
                combat_log_cursor=0,
            ),
            next_observation_cursor=1,
        ),
    )

    assert len(frame.presentation) == 2
    action, damage = frame.presentation
    assert isinstance(action, ActionPresentationCue)
    assert isinstance(damage, DamagePresentationCue)
    assert action.actor_uuid == observer_uuid
    assert action.target_uuids == (str(target.uuid),)
    assert action.effect_presentation_ids == (damage.presentation_id,)
    assert damage.parent_presentation_id == action.presentation_id
    assert tuple(
        attribution.definition_ref
        for attribution in action.content_attributions
    ) == (DRAGONBORN_BREATH_WEAPON_DECLARATION.ref,)


def test_ancestry_receipt_removes_resistance_action_resource_and_reapplies_once(
    dragonborn_runtime: ContentSystemRuntime,
) -> None:
    entity = _actor("Silver Dragonborn", (2, 2), "heroes")
    character_id = uuid4()
    declaration = DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[
        DragonbornAncestry.SILVER
    ]
    definition = declaration.definition_payload
    assert isinstance(definition, DragonbornAncestryFeatureDefinition)

    def install():
        return install_dragonborn_ancestry_feature(
            entity=entity,
            character_id=character_id,
            grant_token="species.dragonborn:ancestry",
            definition_ref=declaration.ref,
            character_level=5,
            definition=definition,
            runtime=dragonborn_runtime,
        )

    receipt = install()
    assert (
        entity.health.get_resistance(DamageType(definition.damage_type))
        is ResistanceStatus.RESISTANCE
    )
    assert len([
        action
        for action in entity.registered_actions
        if action.name == "Breath Weapon"
    ]) == 1
    assert entity.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 1

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=character_id,
            grants=(receipt,),
        ),
    )

    assert (
        entity.health.get_resistance(DamageType(definition.damage_type))
        is ResistanceStatus.NONE
    )
    assert not [
        action
        for action in entity.registered_actions
        if action.name == "Breath Weapon"
    ]
    assert not entity.action_economy.has_resource(
        DRAGONBORN_BREATH_RESOURCE,
    )

    install()
    assert len([
        action
        for action in entity.registered_actions
        if action.name == "Breath Weapon"
    ]) == 1
    assert entity.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 1


def test_builtin_dragonborn_choice_validates_materializes_and_removes() -> None:
    """Prove the canonical build ledger reaches the reversible ancestry applier."""
    declarations = {
        declaration.ref.identity_key: declaration
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }
    loaded = LoadedContentSystem(
        registry=FrozenContentRegistry(
            declarations=declarations,
            recipe_presets={
                preset.ref.identity_key: preset
                for preset in BUILT_IN_RECIPE_PRESET_INVENTORY
            },
            sources={},
        ),
        packs=(),
        built_in_artifact_digest="c" * 64,
        content_set_digest="d" * 64,
    )
    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    character_id = uuid4()
    ancestry_declaration = (
        DRAGONBORN_ANCESTRY_DECLARATIONS_BY_ANCESTRY[
            DragonbornAncestry.RED
        ]
    )
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=declarations[
            "content.srd_5_1_cc:species:species.dragonborn@2"
        ].ref,
        background_ref=ADVENTURER_BACKGROUND_REF,
        immutable_origin_choices=(
            OriginTraitChoice(
                choice_id="species.dragonborn.draconic_ancestry",
                selected_ref=ancestry_declaration.ref,
            ),
        ),
        appearance=FIGHTER_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=12,
            constitution=14,
            intelligence=8,
            wisdom=10,
            charisma=13,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=(
            ClassLevelEntry(
                class_level_id=ClassLevelId(value="fighter.level_1"),
                character_level=1,
                class_ref=FIGHTER_CLASS_REF,
                resulting_class_level=1,
                choices=(
                    StartingEquipmentPackageChoice(
                        choice_id=(
                            "class.fighter.first_class.starting_equipment"
                        ),
                        selected_ref=(
                            STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                                ("fighter", "sword_shield")
                            ].ref
                        ),
                    ),
                    FightingStyleChoice(
                        choice_id="class.fighter.level_1.fighting_style",
                        selected_ref=FIGHTING_STYLE_ARCHERY_REF,
                    ),
                    ClassSkillChoice(
                        choice_id="class.fighter.proficiencies.skills",
                        skills=("athletics", "perception"),
                    ),
                ),
            ),
        ),
        earned_character_level=1,
        content_set_digest=loaded.content_set_digest,
        ruleset_digest="e" * 64,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
    )

    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=definition.ruleset_digest,
    ).validate(definition, loadout)
    assert validation.valid, validation.issues
    assert validation.preview is not None
    assert any(
        row.kind is CharacterGrantScheduleKind.SELECTED_CONTENT
        and row.content_ref == ancestry_declaration.ref
        for row in validation.preview.grant_schedule
    )

    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Red Dragonborn Fighter",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.dragonborn.full_materialization",
        ),
        expected_ruleset_digest=definition.ruleset_digest,
        runtime=runtime,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None
    assert entity.health.get_resistance(
        DamageType.FIRE,
    ) is ResistanceStatus.RESISTANCE
    assert isinstance(
        entity.get_action_template("Breath Weapon"),
        DragonbornBreathWeapon,
    )
    assert entity.action_economy.get_resource_current(
        DRAGONBORN_BREATH_RESOURCE,
    ) == 1
    assert any(
        grant.definition_ref == ancestry_declaration.ref
        and grant.action_uuids
        and grant.resource_contribution_ids
        for grant in receipt.grants
    )

    remove_character_composition(entity, receipt)

    assert entity.health.get_resistance(
        DamageType.FIRE,
    ) is ResistanceStatus.NONE
    assert entity.get_action_template("Breath Weapon") is None
    assert not entity.action_economy.has_resource(
        DRAGONBORN_BREATH_RESOURCE,
    )
