"""Focused regressions for reversible Barbarian structural feature grants."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.classes import barbarian, rage
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.classes.barbarian_progression_definitions import BARBARIAN_CLASS_REF
from dnd.content_system.barbarian_character_grant_appliers import (
    BARBARIAN_CHARACTER_GRANT_APPLIERS,
    BRUTAL_CRITICAL_REF,
    DANGER_SENSE_REF,
    FAST_MOVEMENT_REF,
    FERAL_INSTINCT_REF,
    FRENZY_REF,
    INDOMITABLE_MIGHT_REF,
    INTIMIDATING_PRESENCE_REF,
    MINDLESS_RAGE_REF,
    PERSISTENT_RAGE_REF,
    PRIMAL_CHAMPION_REF,
    RAGE_REF,
    RECKLESS_ATTACK_REF,
    RELENTLESS_RAGE_REF,
    RETALIATION_REF,
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
from dnd.classes.structural_feature_definitions import (
    UNARMORED_DEFENSE_DECLARATION,
)
from dnd.core.content.identities import ContentRef
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventType
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import AdvantageStatus
from dnd.conditions import Charmed, Frightened
from dnd.creature_transforms import (
    apply_incapacitated_transform,
    remove_modifier_ownership,
)
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
    ordinal: int = 0,
) -> CharacterGrantScheduleEntry:
    return CharacterGrantScheduleEntry(
        kind=CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
        provenance=CharacterGrantProvenance(
            source_kind=CharacterGrantSourceKind.CLASS_LEVEL,
            source_ref=BARBARIAN_CLASS_REF,
            character_level=class_level,
            class_level_id=f"barbarian.level_{class_level}",
            class_level=class_level,
            choice_id=None,
            ordinal_path=(class_level, ordinal),
        ),
        grant_token=(
            f"barbarian:{class_level}:{ordinal}:{content_ref.identity_key}"
        ),
        content_ref=content_ref,
    )


def _context(
    runtime: ContentSystemRuntime,
    *,
    entries: tuple[CharacterGrantScheduleEntry, ...],
    barbarian_level: int,
    additional_refs: tuple[ContentRef, ...] = (),
    entity: Entity | None = None,
) -> BuiltinCharacterGrantContext:
    refs = tuple(
        entry.content_ref
        for entry in entries
        if entry.content_ref is not None
    )
    return BuiltinCharacterGrantContext(
        entity=entity or Entity.create(source_entity_uuid=uuid4()),
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=((BARBARIAN_CLASS_REF, barbarian_level),),
            automatic_grant_refs=(*refs, *additional_refs),
            grant_schedule=entries,
            final_known_spell_refs=(),
            final_known_spells=(),
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
    assert entry.content_ref is not None
    return BARBARIAN_CHARACTER_GRANT_APPLIERS[
        entry.content_ref.identity_key
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
            automatic_grant_refs=(),
        ),
    )


def test_unarmored_defense_is_an_exact_formula_candidate(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(UNARMORED_DEFENSE_DECLARATION.ref, class_level=1)
    entity = Entity.create(source_entity_uuid=uuid4())
    context = _context(
        runtime,
        entries=(entry,),
        barbarian_level=1,
        entity=entity,
    )

    receipt = _apply(context, entry)

    assert receipt.armor_class_formula_ids == (receipt.grant_id,)
    candidate = entity.equipment.armor_class_formula_candidates[receipt.grant_id]
    assert candidate.ability_names == ("dexterity", "constitution")
    assert candidate.allows_shield is True
    assert not entity.active_conditions

    _remove(context, receipt)

    assert not entity.equipment.armor_class_formula_candidates


def test_all_rage_advancements_share_one_action_family_and_max_capacity(
    runtime: ContentSystemRuntime,
) -> None:
    levels = (1, 3, 6, 9, 12, 16, 17, 20)
    capacities = (2, 3, 4, 4, 5, 5, 6, 999)
    entries = tuple(
        _entry(RAGE_REF, class_level=level, ordinal=index)
        for index, level in enumerate(levels)
    )
    context = _context(
        runtime,
        entries=entries,
        barbarian_level=20,
    )
    receipts: list[CharacterGrantReceipt] = []

    for entry, capacity in zip(entries, capacities, strict=True):
        receipts.append(_apply(context, entry))
        assert context.entity.action_economy.resources["rage"].maximum == capacity

    rage_actions = [
        action
        for action in context.entity.registered_actions
        if isinstance(action, rage.Rage)
    ]
    end_actions = [
        action
        for action in context.entity.registered_actions
        if isinstance(action, rage.EndRage)
    ]
    assert len(rage_actions) == len(end_actions) == 1
    assert rage_actions[0].rage_damage == 4
    assert rage_actions[0].behavior_binding is not None
    assert rage_actions[0].behavior_binding.provided_by_ref == RAGE_REF
    assert not context.entity.active_conditions

    _remove(context, *receipts)

    assert "rage" not in context.entity.action_economy.resources
    assert not context.entity.registered_actions


def test_berserker_replaces_rage_with_configured_frenzy_and_cleans_state(
    runtime: ContentSystemRuntime,
) -> None:
    rage_entry = _entry(RAGE_REF, class_level=1)
    frenzy_entry = _entry(FRENZY_REF, class_level=3, ordinal=1)
    entries = (rage_entry, frenzy_entry)
    context = _context(
        runtime,
        entries=entries,
        barbarian_level=15,
        additional_refs=(MINDLESS_RAGE_REF, PERSISTENT_RAGE_REF),
    )

    rage_receipt = _apply(context, rage_entry)
    frenzy_receipt = _apply(context, frenzy_entry)

    assert context.entity.get_action_template("Rage") is None
    assert context.entity.get_action_template("End Rage") is not None
    frenzy = context.entity.get_action_template("Frenzy")
    assert isinstance(frenzy, rage.Frenzy)
    assert frenzy.rage_damage == 3
    assert frenzy.mindless_rage is True
    assert frenzy.persistent_rage is True
    assert frenzy.behavior_binding is not None
    assert frenzy.behavior_binding.provided_by_ref == FRENZY_REF

    raging = rage.Raging(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        rage_damage=frenzy.rage_damage,
        mindless_rage=frenzy.mindless_rage,
        persistent_rage=frenzy.persistent_rage,
    )
    context.entity.add_condition(raging)
    frenzied = rage.Frenzied(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        parent_condition=raging.uuid,
    )
    context.entity.add_condition(frenzied)
    raging.sub_conditions.append(frenzied.uuid)
    assert context.entity.get_action_template("Frenzied Strike") is not None

    _remove(context, rage_receipt, frenzy_receipt)

    assert "Raging" not in context.entity.active_conditions
    assert "Frenzied" not in context.entity.active_conditions
    assert not context.entity.registered_actions


def test_reckless_feature_owns_only_action_and_cleans_transient_state(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(RECKLESS_ATTACK_REF, class_level=2)
    context = _context(runtime, entries=(entry,), barbarian_level=2)

    receipt = _apply(context, entry)
    action = context.entity.get_action_template("Reckless Attack")
    assert isinstance(action, barbarian.RecklessAttack)
    assert action.behavior_binding is not None
    assert action.behavior_binding.provided_by_ref == RECKLESS_ATTACK_REF
    transient = barbarian.RecklessAttacking(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
    )
    context.entity.add_condition(transient)

    _remove(context, receipt)

    assert context.entity.get_action_template("Reckless Attack") is None
    assert "Reckless Attacking" not in context.entity.active_conditions


def test_rage_and_reckless_require_a_strength_melee_attack(
    runtime: ContentSystemRuntime,
) -> None:
    rage_entry = _entry(RAGE_REF, class_level=1)
    reckless_entry = _entry(RECKLESS_ATTACK_REF, class_level=2, ordinal=1)
    context = _context(
        runtime,
        entries=(rage_entry, reckless_entry),
        barbarian_level=2,
    )
    rage_receipt = _apply(context, rage_entry)
    reckless_receipt = _apply(context, reckless_entry)
    entity = context.entity

    entity.add_condition(
        rage.Raging(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            rage_damage=2,
        ),
    )
    entity.add_condition(
        barbarian.RecklessAttacking(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        ),
    )

    dexterity_attack = entity.attack_bonus(
        WeaponSlot.MELEE_MAIN,
        override_ability="dexterity",
    )
    strength_attack = entity.attack_bonus(
        WeaponSlot.MELEE_MAIN,
        override_ability="strength",
    )
    dexterity_damage = entity.get_damages(
        WeaponSlot.MELEE_MAIN,
        override_ability="dexterity",
    )[0]
    strength_damage = entity.get_damages(
        WeaponSlot.MELEE_MAIN,
        override_ability="strength",
    )[0]

    assert dexterity_attack.advantage is AdvantageStatus.NONE
    assert strength_attack.advantage is AdvantageStatus.ADVANTAGE
    assert dexterity_damage.damage_bonus is not None
    assert strength_damage.damage_bonus is not None
    assert dexterity_damage.damage_bonus.normalized_score == 0
    assert strength_damage.damage_bonus.normalized_score == 2

    _remove(context, rage_receipt, reckless_receipt)


def test_danger_sense_uses_authoritative_action_capability_and_is_reversible(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(DANGER_SENSE_REF, class_level=2)
    context = _context(runtime, entries=(entry,), barbarian_level=2)
    receipt = _apply(context, entry)
    dex_save = context.entity.saving_throws.get_saving_throw("dexterity").bonus

    assert dex_save.advantage == AdvantageStatus.ADVANTAGE
    ownership = apply_incapacitated_transform(
        context.entity,
        name="Test Incapacitated",
        effect_source_uuid=uuid4(),
    )
    assert context.entity.can_take_actions() is False
    assert dex_save.advantage == AdvantageStatus.NONE
    remove_modifier_ownership(ownership)
    assert dex_save.advantage == AdvantageStatus.ADVANTAGE

    _remove(context, receipt)

    assert dex_save.advantage == AdvantageStatus.NONE


def test_fast_movement_is_contextual_and_reversible(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(FAST_MOVEMENT_REF, class_level=5)
    context = _context(runtime, entries=(entry,), barbarian_level=5)
    baseline = context.entity.action_economy.movement.normalized_score

    receipt = _apply(context, entry)

    assert context.entity.action_economy.movement.normalized_score == baseline + 10
    _remove(context, receipt)
    assert context.entity.action_economy.movement.normalized_score == baseline


def test_mindless_rage_uses_exact_immunity_sources_and_active_purge(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(MINDLESS_RAGE_REF, class_level=6)
    context = _context(runtime, entries=(entry,), barbarian_level=6)
    charmed = Charmed(
        source_entity_uuid=uuid4(),
        target_entity_uuid=context.entity.uuid,
    )
    context.entity.add_condition(charmed)
    assert "Charmed" in context.entity.active_conditions

    receipt = _apply(context, entry)

    assert len(receipt.condition_immunity_handles) == 2
    assert context.entity.check_condition_immunity("Charmed") is False
    raging = rage.Raging(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        mindless_rage=True,
    )
    context.entity.add_condition(raging)
    assert "Charmed" not in context.entity.active_conditions
    assert context.entity.check_condition_immunity("Charmed") is True
    assert context.entity.check_condition_immunity("Frightened") is True
    frightened = Frightened(
        source_entity_uuid=uuid4(),
        target_entity_uuid=context.entity.uuid,
    )
    context.entity.add_condition(frightened)
    assert "Frightened" not in context.entity.active_conditions

    _remove(context, receipt)

    assert "Raging" not in context.entity.active_conditions
    assert context.entity.check_condition_immunity("Charmed") is False
    assert context.entity.check_condition_immunity("Frightened") is False


def test_feral_instinct_and_three_brutal_critical_ranks_are_reversible(
    runtime: ContentSystemRuntime,
) -> None:
    feral = _entry(FERAL_INSTINCT_REF, class_level=7)
    brutal_entries = tuple(
        _entry(BRUTAL_CRITICAL_REF, class_level=level, ordinal=index + 1)
        for index, level in enumerate((9, 13, 17))
    )
    context = _context(
        runtime,
        entries=(feral, *brutal_entries),
        barbarian_level=17,
    )

    receipts = [_apply(context, feral)]
    receipts.extend(_apply(context, entry) for entry in brutal_entries)

    assert context.entity.initiative.advantage == AdvantageStatus.ADVANTAGE
    assert context.entity.equipment.crit_extra_dice_melee.normalized_score == 3

    _remove(context, *receipts)

    assert context.entity.initiative.advantage == AdvantageStatus.NONE
    assert context.entity.equipment.crit_extra_dice_melee.normalized_score == 0


def test_relentless_persistent_and_indomitable_install_no_feature_conditions(
    runtime: ContentSystemRuntime,
) -> None:
    relentless = _entry(RELENTLESS_RAGE_REF, class_level=11)
    persistent = _entry(PERSISTENT_RAGE_REF, class_level=15, ordinal=1)
    indomitable = _entry(INDOMITABLE_MIGHT_REF, class_level=18, ordinal=2)
    entries = (relentless, persistent, indomitable)
    context = _context(runtime, entries=entries, barbarian_level=18)

    receipts = [_apply(context, entry) for entry in entries]

    resource = context.entity.action_economy.resources["relentless_rage"]
    assert (resource.current, resource.maximum) == (999, 999)
    for name, expected_ref in (
        ("Relentless Rage", RELENTLESS_RAGE_REF),
        ("Indomitable Might", INDOMITABLE_MIGHT_REF),
    ):
        handler = context.entity.get_event_handler_by_name(name)
        assert handler is not None
        assert handler.behavior_binding is not None
        assert handler.behavior_binding.provided_by_ref == expected_ref
    assert not context.entity.active_conditions

    _remove(context, *receipts)

    assert "relentless_rage" not in context.entity.action_economy.resources
    assert not context.entity.event_handlers


def test_primal_champion_boosts_both_scores_and_cleans_exactly(
    runtime: ContentSystemRuntime,
) -> None:
    entry = _entry(PRIMAL_CHAMPION_REF, class_level=20)
    context = _context(runtime, entries=(entry,), barbarian_level=20)
    for existing_hit_die in tuple(context.entity.health.hit_dices):
        context.entity.health.remove_hit_dice_by_uuid(existing_hit_die.uuid)
    context.entity.health.add_hit_dice(
        HitDice.create(
            source_entity_uuid=context.entity.uuid,
            config=HitDiceConfig(
                hit_dice_value=12,
                hit_dice_count=20,
                mode="maximums",
            ),
        ),
    )
    assert context.entity.health.total_hit_dices_number == 20
    strength = context.entity.ability_scores.strength.ability_score
    constitution = context.entity.ability_scores.constitution.ability_score
    initial = (strength.normalized_score, constitution.normalized_score)
    initial_max_hp = context.entity.get_max_hp()
    constitution_hp_delta = (
        context.entity.health.total_hit_dices_number * 2
    )

    receipt = _apply(context, entry)
    assert (
        strength.normalized_score,
        constitution.normalized_score,
    ) == (initial[0] + 4, initial[1] + 4)
    assert context.entity.get_max_hp() == initial_max_hp + constitution_hp_delta

    _remove(context, receipt)
    assert (strength.normalized_score, constitution.normalized_score) == initial
    assert context.entity.get_max_hp() == initial_max_hp


@pytest.mark.parametrize(
    ("content_ref", "names"),
    (
        (
            INTIMIDATING_PRESENCE_REF,
            ("Intimidating Presence", "Extend Intimidating Presence"),
        ),
        (RETALIATION_REF, ("Retaliation",)),
    ),
)
def test_berserker_action_and_reaction_roots_are_exact_and_reversible(
    runtime: ContentSystemRuntime,
    content_ref: ContentRef,
    names: tuple[str, ...],
) -> None:
    entry = _entry(content_ref, class_level=14)
    context = _context(runtime, entries=(entry,), barbarian_level=14)

    receipt = _apply(context, entry)

    for name in names:
        behavior = (
            context.entity.get_action_template(name)
            or context.entity.get_event_handler_by_name(name)
        )
        assert behavior is not None
        assert behavior.behavior_binding is not None
        assert behavior.behavior_binding.provided_by_ref == content_ref
    assert not context.entity.active_conditions

    _remove(context, receipt)

    assert not context.entity.registered_actions
    assert not context.entity.event_handlers


def test_retaliation_does_not_spend_reaction_when_child_attack_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retaliator = Entity.create(source_entity_uuid=uuid4())
    attacker = Entity.create(source_entity_uuid=uuid4())
    reaction_before = retaliator.action_economy.reactions.normalized_score
    assert reaction_before > 0
    monkeypatch.setattr(
        type(retaliator.equipment),
        "_get_weapon_by_slot",
        lambda *_: object(),
    )

    def _cancel_attack(*_, **__) -> Event:
        return Event(
            source_entity_uuid=retaliator.uuid,
            target_entity_uuid=attacker.uuid,
            event_type=EventType.ATTACK,
            phase=EventPhase.DECLARATION,
            use_register=False,
        ).cancel(status_message="test cancellation")

    monkeypatch.setattr("dnd.classes.barbarian.Attack.apply", _cancel_attack)
    applied = DamageAppliedEvent(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=retaliator.uuid,
        applied_damage=1,
        normal_hit_point_damage=1,
        temporary_hit_point_damage=0,
        resulting_normal_hp=1,
        resulting_temporary_hp=0,
        damage_type=DamageType.BLUDGEONING,
        phase=EventPhase.EFFECT,
        use_register=False,
    )

    barbarian.retaliation_processor(applied, retaliator.uuid)

    assert (
        retaliator.action_economy.reactions.normalized_score
        == reaction_before
    )
