"""Rescued in-process behavior semantics for the CR-0 evidence freeze."""

from __future__ import annotations

from uuid import uuid4

import pytest

import dnd.spells.abjuration as abjuration
from dnd.actions import Attack, AttackEvent, SpellAction, SpellEvent
from dnd.actions_functional import register_spell
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.classes.paladin import create_divine_smite_handler
from dnd.classes.sorcerer import QuickenedSpell, SorceryPointsFeature
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_CLASS,
    SPELL_CATALOG_COMPOSITION_BY_ID,
    SPELL_CATALOG_COMPOSITION_BY_NAME,
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    DamageRollResultEvent,
    EventPhase,
    EventQueue,
    RollModificationOperation,
)
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.traits import ParryFeature
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import (
    CounterspellReactionEvent,
    register_counterspell_reaction,
)
from dnd.spells.effect_ids import COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
from tests.spell_test_exports import (
    ALL_SPELLS,
    Fireball,
    FireBolt,
    MagicMissile,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
)


def _reset_behavior_state(*, grid_size: tuple[int, int] = (40, 8)) -> Game:
    reset_engine_runtime(grid_size=grid_size)
    return Game()


def _deploy_factory_entity(
    game: Game,
    entity: Entity,
    position: tuple[int, int],
) -> Entity:
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def _counterspell_caster(
    game: Game,
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int],
) -> Entity:
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=18),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=12),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=6,
                        mode="maximums",
                    ),
                ],
            ),
            proficiency_bonus=3,
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            position=position,
            faction=faction,
        ),
    )
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def test_spell_catalog_composition_preserves_exact_current_identities() -> None:
    """Every current spell row owns one durable identity and playable surface."""
    rows = SPELL_CATALOG_COMPOSITION_ROWS

    assert tuple(row.catalog_order for row in rows) == tuple(sorted(
        row.catalog_order for row in rows
    ))
    assert tuple(SPELL_CATALOG_COMPOSITION_BY_NAME.values()) == rows
    assert tuple(SPELL_CATALOG_COMPOSITION_BY_ID.values()) == rows
    assert len(SPELL_CATALOG_COMPOSITION_BY_CLASS) == sum(
        row.spell_type is not None for row in rows
    )
    for row in rows:
        assert row.declaration.ref.definition_kind is ContentDefinitionKind.SPELL
        assert row.metadata.catalog_id == row.declaration.ref.content_id.removeprefix(
            "spell.",
        )
        assert (row.spell_type is None) is (
            row.reaction_handler_factory is not None
        )
        if row.spell_type is not None:
            assert SPELL_CATALOG_COMPOSITION_BY_CLASS[row.spell_type] is row
            assert get_content_declaration(row.spell_type).ref == row.declaration.ref

    for display_name, spell_type in ALL_SPELLS.items():
        row = SPELL_CATALOG_COMPOSITION_BY_CLASS[spell_type]
        assert row.display_name == display_name
        assert row.declaration is SPELL_CONTENT_DECLARATIONS_BY_CLASS[spell_type]


def test_monster_parry_activates_exact_reaction_and_spends_one_reaction() -> None:
    """The Parry feature grants its public reaction and applies exactly +2 AC."""
    game = _reset_behavior_state(grid_size=(6, 6))
    defender = _deploy_factory_entity(
        game,
        create_goblin(
            name="Parry Defender",
            position=(2, 2),
            faction="heroes",
        ),
        (2, 2),
    )
    attacker = _deploy_factory_entity(
        game,
        create_goblin(
            name="Parry Attacker",
            position=(2, 3),
            faction="monsters",
        ),
        (2, 3),
    )
    defender.add_condition(
        ParryFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        ),
    )
    handler = defender.get_event_handler_by_name("Parry")
    assert handler is not None
    Entity.update_all_entities_senses(max_distance=20)

    with fixed_dice_faces(10):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(event, AttackEvent)
    assert event.ac is not None
    assert any(
        row["name"] == "Parry" and row["value"] == 2
        for row in event.ac.get_breakdown()
    )
    assert defender.action_economy.reactions.normalized_score == 0


def test_divine_smite_appends_radiant_packet_and_spends_exact_slot() -> None:
    """A committed melee hit appends one radiant packet and spends slot one."""
    game = _reset_behavior_state(grid_size=(6, 6))
    paladin = _deploy_factory_entity(
        game,
        create_goblin(
            name="Smite Attacker",
            position=(2, 2),
            faction="heroes",
        ),
        (2, 2),
    )
    target = _deploy_factory_entity(
        game,
        create_skeleton(
            name="Smite Target",
            position=(2, 3),
            faction="monsters",
        ),
        (2, 3),
    )
    slot_base = paladin.action_economy.spell_slot_1.get_base_modifier()
    assert slot_base is not None
    slot_base.value = 1
    handler = create_divine_smite_handler(paladin.uuid, 1)
    paladin.add_event_handler(handler)
    Entity.update_all_entities_senses(max_distance=20)
    before = EventQueue.event_cursor()

    with fixed_dice_faces(20, *([4] * 10)):
        attack = Attack(
            source_entity_uuid=paladin.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(attack, AttackEvent)
    assert attack.attack_outcome is AttackOutcome.CRIT
    damage_result = next(
        event
        for _cursor, event in EventQueue.iter_events_since(before)
        if isinstance(event, DamageRollResultEvent)
        and event.phase is EventPhase.COMPLETION
    )
    assert len(damage_result.damage_packets) == 2
    assert damage_result.damage_packets[1].damage.damage_type is DamageType.RADIANT
    modification = damage_result.roll_modifications[-1]
    assert modification.operation is RollModificationOperation.APPEND
    assert modification.handler_name == "Divine Smite"
    assert modification.packet_index == 1
    assert paladin.action_economy.spell_slot_1.normalized_score == 0


def test_counterspell_commits_both_casts_exact_bindings_and_one_cancel() -> None:
    """One exact reaction interrupts one bound spell after both costs commit."""
    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={1: 1},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={3: 1},
    )
    register_spell(caster, MagicMissile, caster_level=3)
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    template = caster.get_action_template("Magic Missile")
    handler = counterspeller.get_event_handler_by_name("Counterspell")
    assert isinstance(template, SpellAction)
    assert template.behavior_binding is not None
    assert handler is not None and handler.behavior_binding is not None
    before = EventQueue.event_cursor()

    event = template.instantiate(
        target_entity_uuid=counterspeller.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled and event.phase is EventPhase.CANCEL
    assert event.canceled_from_phase is EventPhase.EXECUTION
    assert event.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert event.status_message == "The spell was interrupted."
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0

    events = tuple(
        row for _cursor, row in EventQueue.iter_events_since(before)
    )
    incoming_versions = tuple(
        row
        for row in events
        if isinstance(row, SpellEvent)
        and row.lineage_uuid == event.lineage_uuid
    )
    assert incoming_versions
    assert all(
        (
            row.behavior_id,
            row.provided_by_id,
            row.origin_root_id,
        )
        == (
            template.behavior_binding.behavior_id,
            template.behavior_binding.provided_by_id,
            template.behavior_binding.origin_root_id,
        )
        for row in incoming_versions
    )
    assert tuple(
        row.uuid
        for row in incoming_versions
        if row.phase is EventPhase.CANCEL
    ) == (event.uuid,)
    reaction = next(
        row
        for row in events
        if isinstance(row, CounterspellReactionEvent)
        and row.phase is EventPhase.COMPLETION
    )
    assert (
        reaction.behavior_id,
        reaction.provided_by_id,
        reaction.origin_root_id,
    ) == (
        handler.behavior_binding.behavior_id,
        handler.behavior_binding.provided_by_id,
        handler.behavior_binding.origin_root_id,
    )
    assert reaction.combat_log is not None
    assert reaction.combat_log.entry_type is CombatLogEntryType.SPELL_INTERRUPTION
    assert reaction.combat_log.source_uuid == str(counterspeller.uuid)
    assert reaction.combat_log.target_uuid == str(caster.uuid)
    assert reaction.combat_log.data["outcome_code"] == (
        COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    )
    assert reaction.combat_log.data["counterspell_slot_level"] == 3
    assert reaction.combat_log.data["succeeded"] is True


def test_counterspell_ignores_allied_spells_without_spending() -> None:
    """Counterspell observes hostility before committing reaction resources."""
    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={1: 1},
    )
    ally = _counterspell_caster(
        game,
        name="Allied Abjurer",
        position=(6, 2),
        faction="heroes",
        spell_slots={3: 1},
    )
    target = _counterspell_caster(
        game,
        name="Target",
        position=(8, 2),
        faction="monsters",
        spell_slots={},
    )
    register_counterspell_reaction(ally)
    Entity.update_all_entities_senses()

    allied_spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(allied_spell, SpellEvent)
    assert not allied_spell.canceled
    assert allied_spell.phase is EventPhase.COMPLETION
    assert ally.action_economy.reactions.normalized_score == 1
    assert ally.action_economy.spell_slot_3.normalized_score == 1


def test_counterspell_committed_quickened_cast_consumes_override() -> None:
    """Only the interrupted committed cast consumes Quickened Spell state."""
    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Quickened Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={3: 2},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={3: 1},
    )
    register_spell(caster, Fireball, caster_level=5)
    caster.add_condition(
        SorceryPointsFeature(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            sorcery_points=2,
            metamagic_choices=["quickened"],
        ),
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    template = caster.get_action_template("Fireball")
    assert isinstance(template, SpellAction)

    quickened = QuickenedSpell(source_entity_uuid=caster.uuid).apply()
    assert quickened is not None and not quickened.canceled
    assert "MetamagicActive" in caster.active_conditions
    assert template.effective_costs[0].cost_type == "bonus_actions"

    invalid = template.instantiate(end_position=(39, 7)).apply()
    assert isinstance(invalid, SpellEvent)
    assert invalid.canceled_from_phase is EventPhase.DECLARATION
    assert "MetamagicActive" in caster.active_conditions
    assert template.effective_costs[0].cost_type == "bonus_actions"

    interrupted = template.instantiate(
        end_position=counterspeller.position,
    ).apply()
    assert isinstance(interrupted, SpellEvent)
    assert interrupted.canceled_from_phase is EventPhase.EXECUTION
    assert interrupted.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert "MetamagicActive" not in caster.active_conditions
    assert template.alt_cost_type is None
    assert template.effective_costs[0].cost_type == "actions"
    assert template.instantiate(
        end_position=counterspeller.position,
    ).pre_validate()


def test_counterspell_uses_third_rank_floor_for_low_spells_and_cantrips() -> None:
    """Counterspell never spends rank one or two, even against rank zero."""
    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={1: 1},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={1: 1, 2: 1, 3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(spell, SpellEvent) and spell.canceled
    assert counterspeller.action_economy.spell_slot_1.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_2.normalized_score == 1
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0

    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()

    cantrip = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(cantrip, SpellEvent) and cantrip.canceled
    assert cantrip.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0


def test_counterspell_check_outcomes_spend_exact_committed_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed and successful checks spend both casts but cancel only on success."""
    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={5: 1},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(abjuration.random, "randint", lambda _low, _high: 1)

    failed = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        cast_at_level=5,
        template=False,
    ).apply()

    assert isinstance(failed, SpellEvent)
    assert not failed.canceled and failed.phase is EventPhase.COMPLETION
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_5.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0

    game = _reset_behavior_state()
    caster = _counterspell_caster(
        game,
        name="Caster",
        position=(2, 2),
        faction="heroes",
        spell_slots={1: 1, 5: 1},
    )
    counterspeller = _counterspell_caster(
        game,
        name="Abjurer",
        position=(6, 2),
        faction="monsters",
        spell_slots={3: 1},
    )
    register_counterspell_reaction(counterspeller)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(abjuration.random, "randint", lambda _low, _high: 20)

    succeeded = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        cast_at_level=5,
        template=False,
    ).apply()

    assert isinstance(succeeded, SpellEvent) and succeeded.canceled
    assert succeeded.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 0
    assert counterspeller.action_economy.reactions.normalized_score == 0
    assert counterspeller.action_economy.spell_slot_3.normalized_score == 0
