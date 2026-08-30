"""A real level-20 Berserker composes and reverses through schema 2."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.classes import barbarian, fighter, rage
from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_CLASS_REF,
    BERSERKER_SUBCLASS_REF,
)
from dnd.content_system.barbarian_character_grant_appliers import (
    BRUTAL_CRITICAL_REF,
    FRENZY_REF,
    MINDLESS_RAGE_REF,
    PRIMAL_CHAMPION_REF,
    RAGE_REF,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import (
    materialize_character,
    remove_character_composition,
)
from dnd.content_system.character_appearance import BARBARIAN_HUMAN_APPEARANCE
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.durable_characters import (
    AbilityScoreAllocation,
    AbilityScoreImprovementChoice,
    AbilityScoreName,
    BackgroundDefinition,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
    ClassLevelEntry,
    ClassLevelId,
    ClassSkillChoice,
    FlexibleAbilityBonusSelection,
    SpeciesDefinition,
    StartingEquipmentPackageChoice,
    SubclassChoice,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_support import OriginRuntimeSupport
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    ContentDeclarationMode,
    compute_definition_contract_hash,
)
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import ArmorType, WeaponProperty, WeaponSlot
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageStatus,
    NumericalModifier,
)
from dnd.actions import AttackEvent
from dnd.blocks.equipment import Weapon
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.weapons import GREATSWORD_RECIPE
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from dnd.runtime_reset import reset_engine_runtime


_RULESET_DIGEST = "c" * 64
_NEUTRAL_ORIGIN_PROVENANCE = ContentProvenance(
    primary_source_id="fixture.barbarian_materialization.source",
    source_anchor="complete no-op origin fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
    notes="Complete by definition: this fixture origin grants no mechanics.",
)


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _origin_declaration(
    *,
    kind: ContentDefinitionKind,
    content_id: str,
    payload: SpeciesDefinition | BackgroundDefinition,
    provenance,
) -> ContentDeclaration:
    ref = ContentRef(
        pack_id="fixture.barbarian_materialization",
        definition_kind=kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.TYPED_DEFINITION,
            definition_kind=kind,
            definition_model=type(payload),
        ),
    )
    return ContentDeclaration(
        ref=ref,
        mode=ContentDeclarationMode.TYPED_DEFINITION,
        descriptor=ContentDescriptor.from_spec(
            ref,
            ContentDescriptorSpec(
                display_name=content_id,
                description="Complete no-op origin fixture.",
                tags=("character_creation", "player_capable", "fixture_noop_origin"),
                visibility=ContentVisibility.DEVELOPER,
            ),
        ),
        provenance=provenance,
        definition_payload=payload,
    )


def _runtime_with_neutral_origins() -> tuple[
    ContentSystemRuntime,
    str,
    ContentRef,
    ContentRef,
]:
    loaded = bootstrap_content_system()
    species = _origin_declaration(
        kind=ContentDefinitionKind.SPECIES,
        content_id="species.neutral_barbarian_origin",
        payload=SpeciesDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
        provenance=_NEUTRAL_ORIGIN_PROVENANCE,
    )
    background = _origin_declaration(
        kind=ContentDefinitionKind.BACKGROUND,
        content_id="background.neutral_barbarian_origin",
        payload=BackgroundDefinition(
            runtime_support=OriginRuntimeSupport.available(),
        ),
        provenance=_NEUTRAL_ORIGIN_PROVENANCE,
    )
    declarations = dict(loaded.registry.declarations)
    declarations[species.ref.identity_key] = species
    declarations[background.ref.identity_key] = background
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations=declarations,
                recipe_presets=loaded.registry.recipe_presets,
                sources=loaded.registry.sources,
            ),
            packs=loaded.packs,
            built_in_artifact_digest=loaded.built_in_artifact_digest,
            content_set_digest=loaded.content_set_digest,
        ),
    )
    return runtime, loaded.content_set_digest, species.ref, background.ref


def _barbarian_levels() -> tuple[ClassLevelEntry, ...]:
    levels: list[ClassLevelEntry] = []
    for level in range(1, 21):
        choices = []
        if level == 1:
            choices.extend((
                StartingEquipmentPackageChoice(
                    choice_id=(
                        "class.barbarian.first_class.starting_equipment"
                    ),
                    selected_ref=(
                        STARTING_EQUIPMENT_PACKAGE_DECLARATIONS_BY_PRESET[
                            ("barbarian", "greataxe")
                        ].ref
                    ),
                ),
                ClassSkillChoice(
                    choice_id="class.barbarian.proficiencies.skills",
                    skills=("athletics", "perception"),
                ),
            ))
        if level == 3:
            choices.append(
                SubclassChoice(
                    choice_id="class.barbarian.level_3.subclass",
                    selected_ref=BERSERKER_SUBCLASS_REF,
                ),
            )
        ability_increases = {
            4: ((AbilityScoreName.STRENGTH, 2),),
            8: (
                (AbilityScoreName.STRENGTH, 1),
                (AbilityScoreName.CONSTITUTION, 1),
            ),
            12: ((AbilityScoreName.CONSTITUTION, 2),),
            16: ((AbilityScoreName.CONSTITUTION, 2),),
            19: ((AbilityScoreName.WISDOM, 2),),
        }.get(level)
        if ability_increases is not None:
            choices.append(
                AbilityScoreImprovementChoice(
                    choice_id=f"class.barbarian.level_{level}.asi_or_feat",
                    increases=ability_increases,
                ),
            )
        levels.append(
            ClassLevelEntry(
                class_level_id=ClassLevelId(
                    value=f"barbarian.level_{level}",
                ),
                character_level=level,
                class_ref=BARBARIAN_CLASS_REF,
                resulting_class_level=level,
                subclass_ref=(
                    BERSERKER_SUBCLASS_REF if level >= 3 else None
                ),
                choices=tuple(sorted(
                    choices,
                    key=lambda choice: choice.choice_id,
                )),
            ),
        )
    return tuple(levels)


def test_level_twenty_berserker_materializes_and_reverses_exactly() -> None:
    runtime, content_set_digest, species_ref, background_ref = (
        _runtime_with_neutral_origins()
    )
    character_id = uuid4()
    definition = CharacterDefinitionRevisionV2.create(
        character_id=character_id,
        definition_revision=1,
        body_recipe=PLAYER_CHARACTER_BODY_RECIPE,
        species_ref=species_ref,
        background_ref=background_ref,
            appearance=BARBARIAN_HUMAN_APPEARANCE,
        base_ability_scores=AbilityScoreAllocation(
            strength=15,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=8,
        ),
        flexible_ability_bonuses=FlexibleAbilityBonusSelection(
            plus_two=AbilityScoreName.STRENGTH,
            plus_one=AbilityScoreName.CONSTITUTION,
        ),
        class_levels=_barbarian_levels(),
        earned_character_level=20,
        content_set_digest=content_set_digest,
        ruleset_digest=_RULESET_DIGEST,
    )
    loadout = CharacterLoadoutRevisionV1.create(
        character_id=character_id,
        loadout_revision=1,
        based_on_definition_revision=1,
    )

    result = materialize_character(
        definition=definition,
        holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=1,
        ),
        loadout=loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Level Twenty Berserker",
        faction="heroes",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="test.barbarian_berserker",
        ),
        expected_ruleset_digest=_RULESET_DIGEST,
        runtime=runtime,
    )
    entity = result.entity
    receipt = result.composition_receipt
    assert receipt is not None

    assert not entity.active_conditions
    assert entity.health.total_hit_dices_number == 20
    assert len(entity.health.hit_dices) == 20
    assert {
        hit_die.hit_dice_value.normalized_score
        for hit_die in entity.health.hit_dices
    } == {12}
    assert entity.health.hit_dices_total_hit_points == 145

    assert entity.ability_scores.strength.ability_score.score == 24
    assert entity.ability_scores.constitution.ability_score.score == 24
    assert entity.get_max_hp() == 145 + (7 * 20)
    assert entity.get_max_hp() - (145 + (5 * 20)) == 40
    assert entity.proficiency_bonus.normalized_score == 6

    feature_refs = tuple(
        grant.definition_ref for grant in receipt.grants
    )
    assert feature_refs.count(RAGE_REF) == 8
    assert feature_refs.count(BRUTAL_CRITICAL_REF) == 3
    assert feature_refs.count(FRENZY_REF) == 1
    assert feature_refs.count(MINDLESS_RAGE_REF) == 1
    assert feature_refs.count(PRIMAL_CHAMPION_REF) == 1

    assert entity.get_action_template("Rage") is None
    assert isinstance(entity.get_action_template("Frenzy"), rage.Frenzy)
    assert isinstance(entity.get_action_template("End Rage"), rage.EndRage)
    assert isinstance(
        entity.get_action_template("Reckless Attack"),
        barbarian.RecklessAttack,
    )
    assert isinstance(
        entity.get_action_template("Extra Attack"),
        fighter.ExtraAttack,
    )
    assert isinstance(
        entity.get_action_template("Intimidating Presence"),
        barbarian.IntimidatingPresence,
    )
    assert isinstance(
        entity.get_action_template("Extend Intimidating Presence"),
        barbarian.ExtendIntimidatingPresence,
    )
    frenzy = entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    assert frenzy.rage_damage == 4
    assert frenzy.mindless_rage is True
    assert frenzy.persistent_rage is True

    assert (
        entity.action_economy.resources["rage"].current,
        entity.action_economy.resources["rage"].maximum,
    ) == (999, 999)
    assert (
        entity.action_economy.resources["relentless_rage"].current,
        entity.action_economy.resources["relentless_rage"].maximum,
    ) == (999, 999)
    assert (
        entity.action_economy.resources["extra_attacks"].current,
        entity.action_economy.resources["extra_attacks"].maximum,
    ) == (1, 1)
    assert entity.action_economy.resolve_attacks_per_attack_action() == 2
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 3
    assert entity.initiative.advantage == AdvantageStatus.ADVANTAGE
    assert len(entity.equipment.armor_class_formula_candidates) == 1
    assert all(
        entity.get_event_handler_by_name(name) is not None
        for name in (
            "Extra Attack Resource",
            "Relentless Rage",
            "Indomitable Might",
            "Retaliation",
        )
    )

    assert (
        entity.skill_set.athletics.proficiency_sources.sources
        and entity.skill_set.perception.proficiency_sources.sources
    )
    assert (
        entity.saving_throws.strength_saving_throw
        .proficiency_sources.sources
    )
    assert (
        entity.saving_throws.constitution_saving_throw
        .proficiency_sources.sources
    )
    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
    )
    assert entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert all(
        entity.creature_proficiencies.is_armor_proficient(armor_type)
        for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM)
    )
    assert entity.creature_proficiencies.is_shield_proficient()

    feature_action_uuids = {
        action_uuid
        for grant in receipt.grants
        for action_uuid in grant.action_uuids
    }
    feature_handler_uuids = {
        handler_uuid
        for grant in receipt.grants
        for handler_uuid in grant.handler_uuids
    }
    body_action_uuids = {
        action.uuid
        for action in entity.registered_actions
        if action.uuid not in feature_action_uuids
    }
    body_handler_uuids = (
        set(entity.event_handlers) - feature_handler_uuids
    )

    entity.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Presentation Metadata Target",
        config=EntityConfig(
            position=(3, 2),
            faction="monsters",
        ),
    )
    target.equipment.ac_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Forced Frenzied Strike miss",
            value=100,
        ),
    )
    entity.compose_entity()
    target.compose_entity()
    game = Game()
    game.deploy_entity(entity, (2, 2))
    game.deploy_entity(target, (3, 2))
    Entity.update_all_entities_senses(max_distance=30)
    raging = rage.Raging(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_damage=4,
        mindless_rage=True,
        persistent_rage=True,
    )
    entity.add_condition(raging)
    frenzied = rage.Frenzied(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        parent_condition=raging.uuid,
    )
    entity.add_condition(frenzied)
    raging.sub_conditions.append(frenzied.uuid)
    with fixed_dice_faces(10):
        missed_strike = rage.FrenziedStrike(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        ).apply()
    assert isinstance(missed_strike, AttackEvent)
    assert missed_strike.attack_outcome is AttackOutcome.MISS
    assert missed_strike.weapon_name == "Greatsword"
    assert missed_strike.damage_types == [DamageType.SLASHING]
    entity.remove_condition("HasAttacked")

    remove_character_composition(entity, receipt)

    remaining_action_uuids = {
        action.uuid for action in entity.registered_actions
    }
    remaining_handler_uuids = set(entity.event_handlers)
    assert body_action_uuids <= remaining_action_uuids
    assert feature_action_uuids.isdisjoint(remaining_action_uuids)
    assert body_handler_uuids <= remaining_handler_uuids
    assert feature_handler_uuids.isdisjoint(remaining_handler_uuids)
    assert not entity.active_conditions
    assert entity.get_action_template("Frenzied Strike") is None
    assert entity.health.hit_dices == []
    assert entity.ability_scores.strength.ability_score.score == 0
    assert entity.ability_scores.constitution.ability_score.score == 0
    assert entity.proficiency_bonus.normalized_score == 0
    assert entity.action_economy.resolve_attacks_per_attack_action() == 1
    assert not {
        "rage",
        "relentless_rage",
        "extra_attacks",
    } & entity.action_economy.resources.keys()
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 0
    assert entity.initiative.advantage == AdvantageStatus.NONE
    assert not entity.equipment.armor_class_formula_candidates
    assert (
        entity.skill_set.athletics.proficiency_sources.sources == {}
        and entity.skill_set.perception.proficiency_sources.sources == {}
    )
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.SIMPLE,),
    )
    assert not entity.creature_proficiencies.is_weapon_proficient(
        (WeaponProperty.MARTIAL,),
    )
    assert not any(
        entity.creature_proficiencies.is_armor_proficient(armor_type)
        for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM)
    )
    assert not entity.creature_proficiencies.is_shield_proficient()
