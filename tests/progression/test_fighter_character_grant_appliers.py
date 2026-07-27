"""Focused regressions for reversible Fighter structural feature grants."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.classes import fighter
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
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
from dnd.content_system.fighter_character_grant_appliers import (
    ACTION_SURGE_REF,
    FIGHTER_CHARACTER_GRANT_APPLIERS,
    FIGHTING_STYLE_ARCHERY_REF,
    FIGHTING_STYLE_DEFENSE_REF,
    FIGHTING_STYLE_DUELING_REF,
    FIGHTING_STYLE_GREAT_WEAPON_REF,
    FIGHTING_STYLE_PROTECTION_REF,
    FIGHTING_STYLE_TWO_WEAPON_REF,
    IMPROVED_CRITICAL_REF,
    INDOMITABLE_REF,
    LUCKY_FEAT_REF,
    SECOND_WIND_REF,
    SUPERIOR_CRITICAL_REF,
    SURVIVOR_REF,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.identities import ContentRef
from dnd.core.events import EventPhase, SavingThrowEvent
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


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
    character_level: int | None = None,
    ordinal: int = 0,
) -> CharacterGrantScheduleEntry:
    character_level = character_level or class_level
    return CharacterGrantScheduleEntry(
        kind=CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
        provenance=CharacterGrantProvenance(
            source_kind=CharacterGrantSourceKind.CLASS_LEVEL,
            source_ref=FIGHTER_CLASS_REF,
            character_level=character_level,
            class_level_id=f"fighter.level_{class_level}",
            class_level=class_level,
            choice_id=None,
            ordinal_path=(character_level, ordinal),
        ),
        grant_token=(
            f"fighter:{class_level}:{ordinal}:{content_ref.identity_key}"
        ),
        content_ref=content_ref,
    )


def _context(
    runtime: ContentSystemRuntime,
    *,
    entries: tuple[CharacterGrantScheduleEntry, ...],
    fighter_level: int,
    character_id: UUID | None = None,
    entity: Entity | None = None,
) -> BuiltinCharacterGrantContext:
    return BuiltinCharacterGrantContext(
        entity=entity or Entity.create(source_entity_uuid=uuid4()),
        character_id=character_id or uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=((FIGHTER_CLASS_REF, fighter_level),),
            automatic_grant_refs=tuple(
                entry.content_ref
                for entry in entries
                if entry.content_ref is not None
            ),
            grant_schedule=entries,
            final_known_spell_refs=(),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
        ),
        runtime=runtime,
    )


def _apply(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    content_ref = entry.content_ref
    assert content_ref is not None
    return FIGHTER_CHARACTER_GRANT_APPLIERS[
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
            definition_revision=1,
            definition_digest="a" * 64,
            loadout_revision=1,
            loadout_digest="b" * 64,
            grants=receipts,
            automatic_grant_refs=(),
        ),
    )


@pytest.mark.parametrize(
    ("content_ref", "modifier_count", "handler_name"),
    (
        (FIGHTING_STYLE_ARCHERY_REF, 1, None),
        (FIGHTING_STYLE_DEFENSE_REF, 1, None),
        (FIGHTING_STYLE_DUELING_REF, 1, None),
        (FIGHTING_STYLE_TWO_WEAPON_REF, 2, None),
        (FIGHTING_STYLE_GREAT_WEAPON_REF, 0, "Great Weapon Fighting"),
        (FIGHTING_STYLE_PROTECTION_REF, 0, "Protection"),
    ),
)
def test_fighting_styles_install_exact_reversible_structure(
    runtime: ContentSystemRuntime,
    content_ref: ContentRef,
    modifier_count: int,
    handler_name: str | None,
) -> None:
    entry = _entry(content_ref, class_level=1)
    context = _context(runtime, entries=(entry,), fighter_level=1)

    receipt = _apply(context, entry)

    assert len(receipt.modifier_handles) == modifier_count
    assert not context.entity.active_conditions
    if content_ref == FIGHTING_STYLE_ARCHERY_REF:
        assert (
            context.entity.equipment.ranged_attack_bonus.normalized_score
            == 2
        )
    if handler_name is not None:
        handler = context.entity.get_event_handler_by_name(handler_name)
        assert handler is not None
        assert handler.behavior_binding is not None
        assert handler.behavior_binding.provided_by_ref == content_ref

    _remove(context, receipt)

    assert not context.entity.event_handlers
    assert (
        context.entity.equipment.ranged_attack_bonus.normalized_score
        == 0
    )


def test_second_wind_uses_final_fighter_level_and_exact_ownership(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(SECOND_WIND_REF, class_level=1)
    context = _context(runtime, entries=(entry,), fighter_level=12)

    receipt = _apply(context, entry)

    action = context.entity.get_action_template("Second Wind")
    assert isinstance(action, fighter.SecondWind)
    assert action.fighter_level == 12
    assert action.behavior_binding is not None
    assert action.behavior_binding.provided_by_ref == SECOND_WIND_REF
    resource = context.entity.action_economy.resources["second_wind"]
    assert (resource.current, resource.maximum) == (1, 1)
    assert not context.entity.active_conditions

    _remove(context, receipt)

    assert context.entity.get_action_template("Second Wind") is None
    assert "second_wind" not in context.entity.action_economy.resources


def test_action_surge_thresholds_share_one_action_and_sum_uses(
    runtime: ContentSystemRuntime,
) -> None:
    level_two = _entry(ACTION_SURGE_REF, class_level=2, ordinal=0)
    level_seventeen = _entry(
        ACTION_SURGE_REF,
        class_level=17,
        ordinal=1,
    )
    entries = (level_two, level_seventeen)
    context = _context(runtime, entries=entries, fighter_level=17)

    first = _apply(context, level_two)
    second = _apply(context, level_seventeen)

    actions = [
        action
        for action in context.entity.registered_actions
        if isinstance(action, fighter.ActionSurge)
    ]
    assert len(actions) == 1
    assert len(first.action_uuids) == 1
    assert not second.action_uuids
    resource = context.entity.action_economy.resources["action_surge"]
    assert (resource.current, resource.maximum) == (2, 2)

    _remove(context, first, second)

    assert not [
        action
        for action in context.entity.registered_actions
        if isinstance(action, fighter.ActionSurge)
    ]
    assert "action_surge" not in context.entity.action_economy.resources


def test_champion_critical_features_apply_only_to_weapon_attacks(
    runtime: ContentSystemRuntime,
) -> None:
    improved = _entry(IMPROVED_CRITICAL_REF, class_level=3)
    superior = _entry(SUPERIOR_CRITICAL_REF, class_level=15)
    context = _context(
        runtime,
        entries=(improved, superior),
        fighter_level=15,
    )

    improved_receipt = _apply(context, improved)
    assert context.entity.get_crit_threshold() == 19
    superior_receipt = _apply(context, superior)

    assert context.entity.get_crit_threshold() == 18
    assert context.entity.get_crit_threshold(
        weapon_slot=fighter.WeaponSlot.RANGED_MAIN,
    ) == 18
    assert context.entity.get_spell_crit_threshold() == 20
    assert not context.entity.active_conditions

    _remove(context, superior_receipt)
    assert context.entity.get_crit_threshold() == 19
    _remove(context, improved_receipt)
    assert context.entity.get_crit_threshold() == 20


def test_indomitable_thresholds_share_handler_and_no_dc_spends_nothing(
    runtime: ContentSystemRuntime,
) -> None:
    entries = (
        _entry(INDOMITABLE_REF, class_level=9, ordinal=0),
        _entry(INDOMITABLE_REF, class_level=13, ordinal=1),
        _entry(INDOMITABLE_REF, class_level=17, ordinal=2),
    )
    context = _context(runtime, entries=entries, fighter_level=17)
    receipts = tuple(_apply(context, entry) for entry in entries)

    assert len(context.entity.get_event_handlers_by_name("Indomitable")) == 1
    resource = context.entity.action_economy.resources["indomitable"]
    assert (resource.current, resource.maximum) == (3, 3)
    malformed = SavingThrowEvent(
        source_entity_uuid=uuid4(),
        target_entity_uuid=context.entity.uuid,
        ability_name="strength",
        result=False,
        dc=None,
        phase=EventPhase.EFFECT,
        use_register=False,
    )

    assert (
        fighter.indomitable_processor(malformed, context.entity.uuid)
        is None
    )
    assert resource.current == 3

    _remove(context, *receipts)
    assert context.entity.get_event_handler_by_name("Indomitable") is None
    assert "indomitable" not in context.entity.action_economy.resources


def test_survivor_is_one_exact_bound_reversible_handler(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(SURVIVOR_REF, class_level=18)
    context = _context(runtime, entries=(entry,), fighter_level=18)

    receipt = _apply(context, entry)

    handler = context.entity.get_event_handler_by_name("Survivor")
    assert handler is not None
    assert handler.behavior_binding is not None
    assert handler.behavior_binding.provided_by_ref == SURVIVOR_REF
    assert not context.entity.active_conditions

    _remove(context, receipt)
    assert context.entity.get_event_handler_by_name("Survivor") is None


def test_lucky_feat_is_exact_bound_and_reversible_without_condition(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(LUCKY_FEAT_REF, class_level=4)
    context = _context(runtime, entries=(entry,), fighter_level=4)

    receipt = _apply(context, entry)

    resource = context.entity.action_economy.resources["luck_points"]
    assert (resource.current, resource.maximum) == (3, 3)
    handler = context.entity.get_event_handler_by_name("Lucky")
    assert handler is not None
    assert handler.behavior_binding is not None
    assert handler.behavior_binding.provided_by_ref == LUCKY_FEAT_REF
    assert not context.entity.active_conditions

    _remove(context, receipt)
    assert "luck_points" not in context.entity.action_economy.resources
    assert context.entity.get_event_handler_by_name("Lucky") is None
