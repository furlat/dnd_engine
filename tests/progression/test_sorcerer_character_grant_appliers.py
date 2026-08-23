"""Focused regressions for reversible Sorcerer structural feature grants."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.classes import sorcerer
from dnd.classes.sorcerer_progression_definitions import (
    SORCERER_CLASS_DEFINITION,
    SORCERER_CLASS_REF,
)
from dnd.classes.sorcerer_structural_feature_definitions import (
    CAREFUL_SPELL_DECLARATION,
    DISTANT_SPELL_DECLARATION,
    DRACONIC_PRESENCE_DECLARATION,
    DRAGON_WINGS_DECLARATION,
    EMPOWERED_SPELL_DECLARATION,
    EXTENDED_SPELL_DECLARATION,
    HEIGHTENED_SPELL_DECLARATION,
    QUICKENED_SPELL_DECLARATION,
    RED_DRAGON_ANCESTRY_DECLARATION,
    SORCEROUS_RESTORATION_DECLARATION,
    SUBTLE_SPELL_DECLARATION,
    TWINNED_SPELL_DECLARATION,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_build_validation import (
    CharacterBuildPreview,
    CharacterGrantProvenance,
    CharacterGrantScheduleEntry,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import CharacterGrantReceipt
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.content_system.sorcerer_character_grant_appliers import (
    DRACONIC_RESILIENCE_REF,
    ELEMENTAL_AFFINITY_REF,
    ELEMENTAL_AFFINITY_RESISTANCE_REF,
    METAMAGIC_ACTIVE_REF,
    SORCERER_CHARACTER_GRANT_APPLIERS,
    SORCERY_POINTS_REF,
)
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.core.content.identities import ContentRef
from dnd.core.dice import fixed_dice_faces
from dnd.types.damage import DamageType
from dnd.types.damage import ResistanceStatus
from dnd.entities.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition
from dnd.core.base_conditions import BaseCondition
from dnd.core.gridmap import get_map


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


@pytest.fixture(scope="module")
def runtime() -> ContentSystemRuntime:
    installed = ContentSystemRuntime()
    installed.install(bootstrap_content_system())
    return installed


def _entry(
    content_ref: ContentRef,
    *,
    class_level: int,
    ordinal: int = 0,
    selected: bool = False,
) -> CharacterGrantScheduleEntry:
    return CharacterGrantScheduleEntry(
        kind=(
            CharacterGrantScheduleKind.SELECTED_CONTENT
            if selected
            else CharacterGrantScheduleKind.AUTOMATIC_CONTENT
        ),
        provenance=CharacterGrantProvenance(
            source_kind=CharacterGrantSourceKind.CLASS_LEVEL,
            source_ref=SORCERER_CLASS_REF,
            character_level=class_level,
            class_level_id=f"sorcerer.level_{class_level}",
            class_level=class_level,
            choice_id=(
                f"sorcerer.choice.{ordinal}" if selected else None
            ),
            ordinal_path=(class_level, ordinal),
        ),
        grant_token=(
            f"sorcerer:{class_level}:{ordinal}:{content_ref.identity_key}"
        ),
        content_ref=content_ref,
    )


def _draconic_presence_field(
    caster_uuid: UUID,
) -> sorcerer.DraconicPresenceAura:
    """Resolve the one exact independently owned aura for a caster."""
    matches = [
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, sorcerer.DraconicPresenceAura)
        and condition.anchor_uuid == caster_uuid
    ]
    assert len(matches) == 1
    return matches[0]


def _context(
    runtime: ContentSystemRuntime,
    *,
    entries: tuple[CharacterGrantScheduleEntry, ...],
    sorcerer_level: int,
    normal_spell_slots: tuple[tuple[int, int], ...] = (),
    entity: Entity | None = None,
) -> BuiltinCharacterGrantContext:
    return BuiltinCharacterGrantContext(
        entity=entity or Entity.create(source_entity_uuid=uuid4()),
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=((SORCERER_CLASS_REF, sorcerer_level),),
            automatic_grant_refs=tuple(
                entry.content_ref
                for entry in entries
                if (
                    entry.content_ref is not None
                    and entry.kind
                    is CharacterGrantScheduleKind.AUTOMATIC_CONTENT
                )
            ),
            grant_schedule=entries,
            final_known_spell_refs=(),
            final_known_spells=(),
            caster_contributions=(),
            effective_spellcaster_level=sorcerer_level,
            normal_spell_slots=normal_spell_slots,
        ),
        runtime=runtime,
    )


def _apply(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    content_ref = entry.content_ref
    assert content_ref is not None
    return SORCERER_CHARACTER_GRANT_APPLIERS[
        content_ref.identity_key
    ](context, entry)


def _remove(
    context: BuiltinCharacterGrantContext,
    *receipts: CharacterGrantReceipt,
) -> None:
    remove_character_composition(
        context.entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=context.entity.uuid,
            character_id=context.character_id,
            grants=receipts,
        ),
    )


def test_sorcery_point_levels_share_one_font_family_and_max_capacity(
    runtime: ContentSystemRuntime,
) -> None:
    entries = tuple(
        _entry(SORCERY_POINTS_REF, class_level=level, ordinal=level)
        for level in (2, 3, 4)
    )
    context = _context(
        runtime,
        entries=entries,
        sorcerer_level=4,
        normal_spell_slots=((1, 4), (2, 3)),
    )
    receipts = tuple(_apply(context, entry) for entry in entries)

    resource = context.entity.action_economy.resources["sorcery_points"]
    assert (resource.current, resource.maximum) == (4, 4)
    assert len(receipts[0].action_uuids) == 4
    assert not receipts[1].action_uuids
    assert not receipts[2].action_uuids
    assert {
        action.name for action in context.entity.registered_actions
    } == {
        "Slot→SP L1",
        "2SP→Slot L1",
        "Slot→SP L2",
        "3SP→Slot L2",
    }
    assert all(
        action.behavior_binding is not None
        and action.behavior_binding.provided_by_ref == SORCERY_POINTS_REF
        for action in context.entity.registered_actions
    )
    assert not context.entity.active_conditions

    _remove(context, *receipts)

    assert "sorcery_points" not in context.entity.action_economy.resources
    assert not context.entity.registered_actions


@pytest.mark.parametrize(
    ("declaration", "action_type"),
    (
        (DISTANT_SPELL_DECLARATION, sorcerer.DistantSpell),
        (QUICKENED_SPELL_DECLARATION, sorcerer.QuickenedSpell),
        (TWINNED_SPELL_DECLARATION, sorcerer.TwinnedSpell),
    ),
)
def test_implemented_metamagic_choices_own_one_reversible_action(
    runtime: ContentSystemRuntime,
    declaration,
    action_type: type[BaseAction],
) -> None:
    entry = _entry(
        declaration.ref,
        class_level=3,
        selected=True,
    )
    context = _context(
        runtime,
        entries=(entry,),
        sorcerer_level=3,
    )

    receipt = _apply(context, entry)

    assert len(receipt.action_uuids) == 1
    action = context.entity.registered_actions[0]
    assert isinstance(action, action_type)
    assert action.behavior_binding is not None
    assert action.behavior_binding.provided_by_ref == declaration.ref
    assert receipt.transient_condition_refs_to_remove == (
        METAMAGIC_ACTIVE_REF,
    )

    transient = sorcerer.MetamagicActive(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
    )
    context.runtime.bind_granted_behavior(
        transient,
        provider_ref=METAMAGIC_ACTIVE_REF,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.add_condition(transient)

    _remove(context, receipt)

    assert not context.entity.registered_actions
    assert "MetamagicActive" not in context.entity.active_conditions


def test_draconic_resilience_owns_hp_and_unarmored_ac_formula(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(DRACONIC_RESILIENCE_REF, class_level=1)
    context = _context(
        runtime,
        entries=(entry,),
        sorcerer_level=7,
    )

    receipt = _apply(context, entry)

    assert context.entity.health.max_hit_points_bonus.normalized_score == 7
    assert receipt.armor_class_formula_ids == (receipt.grant_id,)
    candidate = context.entity.equipment.armor_class_formula_candidates[
        receipt.grant_id
    ]
    assert candidate.base_ac == 13
    assert candidate.ability_names == ("dexterity",)
    assert candidate.requires_unarmored is True
    assert candidate.allows_shield is True
    assert not context.entity.active_conditions

    _remove(context, receipt)

    assert context.entity.health.max_hit_points_bonus.normalized_score == 0
    assert not context.entity.equipment.armor_class_formula_candidates


def test_ancestry_drives_exact_reversible_elemental_affinity(
    runtime: ContentSystemRuntime,
) -> None:
    ancestry = _entry(
        RED_DRAGON_ANCESTRY_DECLARATION.ref,
        class_level=1,
        selected=True,
    )
    affinity = _entry(
        ELEMENTAL_AFFINITY_REF,
        class_level=6,
        ordinal=1,
    )
    points = _entry(
        SORCERY_POINTS_REF,
        class_level=6,
        ordinal=2,
    )
    context = _context(
        runtime,
        entries=(ancestry, affinity, points),
        sorcerer_level=6,
    )

    ancestry_receipt = _apply(context, ancestry)
    points_receipt = _apply(context, points)
    affinity_receipt = _apply(context, affinity)

    assert ancestry_receipt.modifier_handles == ()
    assert affinity_receipt.spell_damage_affinity_contribution_ids == (
        affinity_receipt.grant_id,
    )
    contribution = (
        context.entity.spellcasting.spell_damage_affinity_contributions[
            affinity_receipt.grant_id
        ]
    )
    assert contribution.damage_type is DamageType.FIRE
    assert contribution.ability_name == "charisma"
    assert len(affinity_receipt.action_uuids) == 1
    action = next(
        action
        for action in context.entity.registered_actions
        if action.uuid == affinity_receipt.action_uuids[0]
    )
    assert isinstance(
        action,
        sorcerer.ElementalAffinityResistanceAction,
    )
    assert action.behavior_binding is not None
    assert action.behavior_binding.provided_by_ref == ELEMENTAL_AFFINITY_REF
    assert not context.entity.active_conditions

    resource = context.entity.action_economy.resources["sorcery_points"]
    assert resource.current == 6
    result = action.instantiate().apply()
    assert result is not None
    assert resource.current == 5
    active = tuple(context.entity.active_conditions.values())
    assert len(active) == 1
    resistance = active[0]
    assert isinstance(resistance, sorcerer.ElementalAffinityResistance)
    assert resistance.duration.duration == 600
    assert resistance.behavior_binding is not None
    assert (
        resistance.behavior_binding.definition_ref
        == ELEMENTAL_AFFINITY_RESISTANCE_REF
    )
    assert (
        context.entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.RESISTANCE
    )

    _remove(
        context,
        ancestry_receipt,
        points_receipt,
        affinity_receipt,
    )

    assert (
        not context.entity.spellcasting.spell_damage_affinity_contributions
    )
    assert not context.entity.registered_actions
    assert not context.entity.active_conditions
    assert (
        context.entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.NONE
    )


def test_sorcerous_restoration_recovers_four_on_short_rest_and_cleans(
    runtime: ContentSystemRuntime,
) -> None:
    points = _entry(SORCERY_POINTS_REF, class_level=20)
    restoration = _entry(
        SORCEROUS_RESTORATION_DECLARATION.ref,
        class_level=20,
        ordinal=1,
    )
    context = _context(
        runtime,
        entries=(points, restoration),
        sorcerer_level=20,
    )
    points_receipt = _apply(context, points)
    restoration_receipt = _apply(context, restoration)
    resource = context.entity.action_economy.resources["sorcery_points"]

    assert resource.consume(9)
    context.entity.on_short_rest()
    assert resource.current == 15
    context.entity.on_short_rest()
    assert resource.current == 19
    context.entity.on_short_rest()
    assert resource.current == 20

    _remove(context, restoration_receipt)
    assert resource.consume(4)
    context.entity.on_short_rest()
    assert resource.current == 16

    _remove(context, points_receipt)
    assert "sorcery_points" not in context.entity.action_economy.resources


@pytest.mark.parametrize(
    "declaration",
    (
        CAREFUL_SPELL_DECLARATION,
        EMPOWERED_SPELL_DECLARATION,
        EXTENDED_SPELL_DECLARATION,
        HEIGHTENED_SPELL_DECLARATION,
        SUBTLE_SPELL_DECLARATION,
    ),
)
def test_future_metamagic_rows_are_public_but_not_selectable(
    runtime: ContentSystemRuntime,
    declaration,
) -> None:
    entry = _entry(
        declaration.ref,
        class_level=3,
        selected=True,
    )
    context = _context(
        runtime,
        entries=(entry,),
        sorcerer_level=3,
    )

    selectable_refs = {
        content_ref.identity_key
        for level in SORCERER_CLASS_DEFINITION.level_definitions
        for requirement in level.choice_requirements
        for content_ref in requirement.allowed_refs
    }
    assert declaration.ref.identity_key not in selectable_refs
    with pytest.raises(
        RuntimeError,
        match="No lawful runtime mechanic is installed",
    ):
        _apply(context, entry)


def test_dragon_wings_materializes_a_reversible_flying_action(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(DRAGON_WINGS_DECLARATION.ref, class_level=14)
    context = _context(
        runtime,
        entries=(entry,),
        sorcerer_level=14,
    )

    receipt = _apply(context, entry)

    assert len(receipt.action_uuids) == 2
    toggle = context.entity.get_action_template("Dragon Wings")
    fly = context.entity.get_action_template("Fly")
    assert isinstance(toggle, sorcerer.DragonWings)
    assert isinstance(fly, sorcerer.Fly)
    assert fly.movement_mode.value == "flying"
    start_x, start_y = context.entity.position
    destination = (start_x + 1, start_y)
    Entity.materialize_all_navigation(max_distance=20)
    assert (
        fly.instantiate(
            end_position=destination,
        ).validate_requirements_for_discovery()
        is False
    )

    result = toggle.instantiate().apply()

    assert result is not None and not result.canceled
    assert "Dragon Wings" in context.entity.active_conditions
    assert (
        fly.instantiate(
            end_position=destination,
        ).validate_requirements_for_discovery()
        is True
    )
    flight_result = fly.instantiate(end_position=destination).apply()
    assert flight_result is not None and not flight_result.canceled
    assert context.entity.position == destination

    context.entity.action_economy.reset_all_costs()
    result = toggle.instantiate().apply()

    assert result is not None and not result.canceled
    assert "Dragon Wings" not in context.entity.active_conditions

    _remove(context, receipt)

    assert context.entity.get_action_template("Dragon Wings") is None
    assert context.entity.get_action_template("Fly") is None


@pytest.mark.parametrize(
    ("mode", "effect_name"),
    (
        ("awe", "Charmed"),
        ("fear", "Frightened"),
    ),
)
def test_draconic_presence_materializes_a_reversible_aura_action(
    runtime: ContentSystemRuntime,
    mode: str,
    effect_name: str,
) -> None:
    points = _entry(SORCERY_POINTS_REF, class_level=18)
    entry = _entry(
        DRACONIC_PRESENCE_DECLARATION.ref,
        class_level=18,
        ordinal=1,
    )
    context = _context(
        runtime,
        entries=(points, entry),
        sorcerer_level=18,
    )
    context.entity.faction = "heroes"
    points_receipt = _apply(context, points)

    receipt = _apply(context, entry)

    assert len(receipt.action_uuids) == 2
    action = context.entity.get_action_template(
        f"Draconic Presence ({mode.title()})",
    )
    assert isinstance(action, sorcerer.DraconicPresence)
    result = action.instantiate().apply()

    assert result is not None and not result.canceled
    assert (
        context.entity.action_economy.resources["sorcery_points"].current
        == 13
    )
    aura = _draconic_presence_field(context.entity.uuid)
    field = aura
    assert field.anchor_uuid == context.entity.uuid
    assert aura.mode == mode
    assert aura.duration.duration == 10
    assert "Concentrating" in context.entity.active_conditions

    failed_target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Failed Target",
    )
    failed_target.faction = "monsters"
    Entity.update_entity_position(failed_target, (1, 0))
    successful_target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Successful Target",
    )
    successful_target.faction = "monsters"
    Entity.update_entity_position(successful_target, (2, 0))
    ally = Entity.create(
        source_entity_uuid=uuid4(),
        name="Ally",
    )
    ally.faction = "heroes"
    Entity.update_entity_position(ally, (3, 0))
    with fixed_dice_faces(1):
        failed_target.on_turn_start()
    with fixed_dice_faces(20):
        successful_target.on_turn_start()
    ally.on_turn_start()

    assert effect_name in failed_target.active_conditions
    assert (
        failed_target.active_conditions[effect_name].source_entity_uuid
        == context.entity.uuid
    )
    immunity_name = (
        f"Draconic Presence Immunity:{context.entity.uuid}"
    )
    immunity = successful_target.active_conditions.get(immunity_name)
    assert isinstance(immunity, sorcerer.DraconicPresenceImmunity)
    assert immunity.duration.duration == 14_400
    assert effect_name not in successful_target.active_conditions
    assert effect_name not in ally.active_conditions
    with fixed_dice_faces():
        successful_target.on_turn_start()
    assert immunity.duration.duration == 14_399

    context.entity.remove_condition("Concentrating")

    assert BaseCondition.get(field.uuid) is None
    assert effect_name not in failed_target.active_conditions
    assert immunity_name in successful_target.active_conditions

    _remove(context, receipt)

    assert (
        context.entity.get_action_template("Draconic Presence (Awe)")
        is None
    )
    assert (
        context.entity.get_action_template("Draconic Presence (Fear)")
        is None
    )
    assert immunity_name not in successful_target.active_conditions

    _remove(context, points_receipt)


def test_draconic_presence_expires_with_its_concentration_after_ten_rounds(
    runtime: ContentSystemRuntime,
) -> None:
    points = _entry(SORCERY_POINTS_REF, class_level=18)
    presence = _entry(
        DRACONIC_PRESENCE_DECLARATION.ref,
        class_level=18,
        ordinal=1,
    )
    context = _context(
        runtime,
        entries=(points, presence),
        sorcerer_level=18,
    )
    points_receipt = _apply(context, points)
    presence_receipt = _apply(context, presence)
    action = context.entity.get_action_template(
        "Draconic Presence (Awe)",
    )
    assert isinstance(action, sorcerer.DraconicPresence)
    assert action.instantiate().apply() is not None
    field = _draconic_presence_field(context.entity.uuid)

    for _ in range(9):
        assert not field.progress_spatial_duration()
        assert BaseCondition.get(field.uuid) is field
        assert "Concentrating" in context.entity.active_conditions
    assert field.progress_spatial_duration()

    assert BaseCondition.get(field.uuid) is None
    assert "Concentrating" not in context.entity.active_conditions

    _remove(context, presence_receipt, points_receipt)
