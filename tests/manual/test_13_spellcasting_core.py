"""Manual Chapter 13 checks for spellcasting core."""

from uuid import uuid4

from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
)
from dnd.actions.operations import (
    execute_by_index,
    get_available_actions,
    register_spell,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_actions import (
    ActionCategory,
    AvailableActionInfo,
    OutcomeApplicationScope,
    OutcomeResolution,
    TargetEffectDisposition,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, MultiEntityLogData
from dnd.types.rolls import AttackOutcome
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    EventQueue,
    _enrich_multi_entity_log_from_children,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.types.creatures import CreatureType
from dnd.core.values import BaseValue
from dnd.entities.entity import Entity, EntityConfig
from tests.spell_test_exports import (
    BurningHands,
    ChillTouch,
    EldritchBlast,
    FingerOfDeath,
    Fireball,
    FireBolt,
    GuidingBolt,
    Haste,
    MagicMissile,
    NecroticBless,
    ScorchingRay,
    Thunderwave,
)


def test_eldritch_blast_discloses_level_scaled_attack_outcome() -> None:
    """Eldritch Blast publishes the same typed damage boundary it executes."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Warlock",
        (1, 1),
        "monsters",
        spell_slots={1: 1},
    )
    spell = EldritchBlast(
        source_entity_uuid=caster.uuid,
        caster_level=5,
    )

    profile = spell.get_outcome_profile(caster)

    assert profile is not None
    assert profile.resolution is OutcomeResolution.ATTACK_ROLL
    assert profile.attack_bonus == caster.spell_attack_outcome_baseline().attack_bonus
    assert profile.damage_rolls[0].dice_count == 2
    assert profile.damage_rolls[0].die_size == 10
    assert profile.damage_rolls[0].damage_type == "Force"


def test_immediate_damage_spells_disclose_execution_honest_outcomes() -> None:
    """Attack, save, upcast, bonus, and critical rules match runtime behavior."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Outcome Mage",
        (1, 1),
        "heroes",
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_damage_modifiers=[("Arcane Potency", 3)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        ),
    )

    guiding = GuidingBolt(
        source_entity_uuid=caster.uuid,
        cast_at_level=3,
    ).get_outcome_profile(caster)
    chill = ChillTouch(
        source_entity_uuid=caster.uuid,
        caster_level=11,
    ).get_outcome_profile(caster)
    finger = FingerOfDeath(
        source_entity_uuid=caster.uuid,
        cast_at_level=8,
    ).get_outcome_profile(caster)

    assert guiding is not None
    assert guiding.resolution is OutcomeResolution.ATTACK_ROLL
    assert guiding.damage_rolls[0].dice_count == 6
    assert guiding.damage_rolls[0].die_size == 6
    assert guiding.damage_rolls[0].flat_bonus == 3
    assert guiding.damage_rolls[0].damage_type == "Radiant"
    assert guiding.critical_threshold == 19
    assert guiding.critical_extra_dice == 2

    assert chill is not None
    assert chill.resolution is OutcomeResolution.ATTACK_ROLL
    assert chill.damage_rolls[0].dice_count == 3
    assert chill.damage_rolls[0].die_size == 8
    assert chill.damage_rolls[0].flat_bonus == 3
    assert chill.damage_rolls[0].damage_type == "Necrotic"
    assert chill.critical_threshold == 19
    assert chill.critical_extra_dice == 2

    assert finger is not None
    assert finger.resolution is OutcomeResolution.SAVING_THROW
    assert finger.damage_rolls[0].dice_count == 8
    assert finger.damage_rolls[0].die_size == 8
    assert finger.damage_rolls[0].flat_bonus == 33
    assert finger.damage_rolls[0].damage_type == "Necrotic"
    assert finger.save_dc == caster.spell_save_dc()
    assert finger.save_ability == "constitution"
    assert finger.half_damage_on_save is True


def test_chill_touch_profile_and_execution_share_spell_critical_threshold() -> None:
    """A natural 19 crit is both advertised and executed for Spell Sniper."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Critical Chill Mage",
        (1, 1),
        "heroes",
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
        ),
    )
    target = create_spell_actor(
        "Critical Chill Target",
        (4, 1),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=40)
    spell = ChillTouch(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
    )

    profile = spell.get_outcome_profile(caster)
    with fixed_dice_faces(19, 4, 4, 4, 4):
        result = spell.apply()

    assert profile is not None
    assert profile.critical_threshold == 19
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.attack_outcome is AttackOutcome.CRIT
    damage_rolls = result.damage_rolls
    assert damage_rolls is not None
    assert damage_rolls[0].effective_dice_count == 4


def test_spell_outcome_profiles_declare_target_application_scope() -> None:
    """Area rules apply per affected entity while projectiles use allocation."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Wizard",
        (1, 1),
        "heroes",
        spell_slots={1: 1, 2: 1, 3: 1},
    )

    fireball = Fireball(source_entity_uuid=caster.uuid, cast_at_level=3)
    missile = MagicMissile(source_entity_uuid=caster.uuid, cast_at_level=1)
    rays = ScorchingRay(source_entity_uuid=caster.uuid, cast_at_level=2)

    fireball_profile = fireball.get_outcome_profile(caster)
    missile_profile = missile.get_outcome_profile(caster)
    ray_profile = rays.get_outcome_profile(caster)

    assert fireball_profile is not None
    assert missile_profile is not None
    assert ray_profile is not None
    assert fireball_profile.application_scope is OutcomeApplicationScope.EACH_AFFECTED_ENTITY
    assert missile_profile.application_scope is OutcomeApplicationScope.ALLOCATED_TARGETS
    assert ray_profile.application_scope is OutcomeApplicationScope.ALLOCATED_TARGETS


def test_close_area_spells_disclose_save_damage_and_upcast_scaling() -> None:
    """Burning Hands and Thunderwave expose their actor-known damage rules."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Wizard",
        (1, 1),
        "heroes",
        spell_slots={1: 1, 2: 1, 3: 1},
    )

    burning_hands = BurningHands(source_entity_uuid=caster.uuid, cast_at_level=2)
    thunderwave = Thunderwave(source_entity_uuid=caster.uuid, cast_at_level=3)
    burning_profile = burning_hands.get_outcome_profile(caster)
    thunder_profile = thunderwave.get_outcome_profile(caster)

    assert burning_profile is not None
    assert burning_profile.resolution is OutcomeResolution.SAVING_THROW
    assert burning_profile.application_scope is OutcomeApplicationScope.EACH_AFFECTED_ENTITY
    assert burning_profile.save_ability == "dexterity"
    assert burning_profile.half_damage_on_save is True
    assert burning_profile.damage_rolls[0].dice_count == 4
    assert burning_profile.damage_rolls[0].die_size == 6

    assert thunder_profile is not None
    assert thunder_profile.resolution is OutcomeResolution.SAVING_THROW
    assert thunder_profile.application_scope is OutcomeApplicationScope.EACH_AFFECTED_ENTITY
    assert thunder_profile.save_ability == "constitution"
    assert thunder_profile.half_damage_on_save is True
    assert thunder_profile.damage_rolls[0].dice_count == 4
    assert thunder_profile.damage_rolls[0].die_size == 8


def test_necrotic_bless_declares_conditional_target_effects() -> None:
    """Mixed ally/enemy effects are engine-owned rule data, not name policy."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Necromancer",
        (1, 1),
        "monsters",
        spell_slots={2: 1},
    )

    profile = NecroticBless(
        source_entity_uuid=caster.uuid,
        cast_at_level=2,
    ).get_target_effect_profile(caster)

    assert profile is not None
    assert profile.semantic_id == "spell.necrotic_bless"
    assert len(profile.branches) == 2
    blessing = next(
        branch
        for branch in profile.branches
        if branch.disposition is TargetEffectDisposition.BENEFICIAL
    )
    bane = next(
        branch
        for branch in profile.branches
        if branch.disposition is TargetEffectDisposition.HARMFUL
    )
    assert blessing.included_creature_types == frozenset({"undead"})
    assert blessing.excluded_creature_types == frozenset()
    assert blessing.resolution is OutcomeResolution.AUTOMATIC
    assert blessing.condition_fact_ids == ("selected_target.condition.bless",)
    assert bane.included_creature_types == frozenset()
    assert bane.excluded_creature_types == frozenset({"undead"})
    assert bane.resolution is OutcomeResolution.SAVING_THROW
    assert bane.save_ability == "charisma"
    assert bane.save_dc == caster.spell_save_dc()
    assert bane.condition_fact_ids == ("selected_target.condition.bane",)


def test_necrotic_bless_combat_log_preserves_each_target_identity() -> None:
    """Mixed target logs identify every living and undead recipient."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Necromancer",
        (1, 1),
        "monsters",
        spell_slots={2: 1},
    )
    living_target = create_spell_actor("Living Target", (2, 1), "heroes")
    undead_ally = create_spell_actor("Undead Ally", (1, 2), "monsters")
    undead_ally.creature_type = CreatureType.UNDEAD
    Entity.materialize_all_navigation(max_distance=30)

    with fixed_dice_faces(1):
        event = NecroticBless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=living_target.uuid,
            extra_target_entity_uuids=[undead_ally.uuid],
            cast_at_level=2,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert event.combat_log is not None
    assert event.combat_log.data["target_names"] == [
        "Living Target",
        "Undead Ally",
    ]
    assert [entry.target_uuid for entry in event.combat_log.sub_entries] == [
        str(living_target.uuid),
        str(undead_ally.uuid),
    ]
    assert [
        target_log["target_uuid"]
        for target_log in event.combat_log.data["per_target_logs"]
    ] == [
        str(living_target.uuid),
        str(undead_ally.uuid),
    ]


def test_multi_target_summary_excludes_auxiliary_cleanup_from_target_data() -> None:
    """Causal cleanup stays nested without becoming a spell target."""
    damage_children = [
        CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_DAMAGE,
            source_name="Sorcerer",
            source_uuid="sorcerer",
            target_name=target_name,
            target_uuid=target_uuid,
            compact=f"Magic Missile hits {target_name}",
            verbose=f"Magic Missile hits {target_name}",
            detailed=f"Magic Missile hits {target_name}",
            data={"final_damage": damage},
            success=True,
        )
        for target_name, target_uuid, damage in (
            ("Warrior", "warrior", 4),
            ("Archer", "archer", 5),
        )
    ]
    cleanup = CombatLogEntry(
        entry_type=CombatLogEntryType.CONDITION_REMOVED,
        source_name="Sorcerer",
        source_uuid="sorcerer",
        target_name="Sorcerer",
        target_uuid="sorcerer",
        compact="Sorcerer is no longer MetamagicActive",
        verbose="Sorcerer is no longer MetamagicActive",
        detailed="Sorcerer is no longer MetamagicActive",
        data={},
        success=True,
    )
    parent = CombatLogEntry(
        entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
        source_name="Sorcerer",
        source_uuid="sorcerer",
        compact="Sorcerer uses Magic Missile",
        verbose="Sorcerer uses Magic Missile",
        detailed="Sorcerer uses Magic Missile",
        data=MultiEntityLogData(
            action_name="Magic Missile",
            caster_name="Sorcerer",
            total_targets=2,
        ).model_dump(),
        success=True,
        sub_entries=[*damage_children, cleanup],
    )

    _enrich_multi_entity_log_from_children(parent, parent.sub_entries)

    assert parent.data["target_names"] == ["Warrior", "Archer"]
    assert parent.data["per_target_damage"] == [4, 5]
    assert len(parent.data["per_target_logs"]) == 2
    assert parent.sub_entries == [*damage_children, cleanup]


def reset_spell_tutorial_state(width: int = 10, height: int = 6) -> None:
    """Clear global state and create a small spell tutorial arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
    intelligence: int = 18,
    proficiency_bonus: int = 3,
    spellcasting: SpellcastingConfig | None = None,
) -> Entity:
    """Create an actor with spellcasting stats, HP, and optional spell slots."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=3,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=proficiency_bonus,
            spellcasting=spellcasting
            or SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def test_spell_discovery_variants_share_the_read_only_definition_graph() -> None:
    """Epoch discovery does not deep-clone a complete spell graph per slot."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Wizard",
        (1, 1),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )
    register_spell(caster, MagicMissile, caster_level=3)
    template = caster.get_action_template("Magic Missile")

    assert isinstance(template, SpellAction)
    variant = template._create_variant(cast_at_level=2)

    assert variant.uuid != template.uuid
    assert variant.costs is not template.costs
    assert variant.spell_range is template.spell_range
    assert variant.is_variant is True
    assert variant.cast_at_level == 2


def find_action(actions, template_name: str) -> AvailableActionInfo:
    """Return the discovered action row with the requested template name."""
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def test_first_spell_example_prints_visible_discovery_and_cast(capsys) -> None:
    """The opening spellcasting example prints the full discovered-cast readout."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Pyromancer",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_actor("Training Target", (1, 0), "monsters")

    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)
    Entity.materialize_all_navigation(max_distance=30)

    available = get_available_actions(caster)
    fire_bolt = find_action(available, "Fire Bolt")
    missile = find_action(available, "Magic Missile__slot_1")
    fire_target = fire_bolt.valid_targets[0]
    assert fire_target.target_uuid is not None
    fire_target_entity = Entity.get(fire_target.target_uuid)
    assert fire_target_entity is not None

    target_hp_before = target.get_hp()
    actions_before = caster.action_economy.actions.normalized_score
    slot_before = caster.action_economy.spell_slot_1.normalized_score

    with fixed_dice_faces(14, 12, 5, 6):
        event = execute_by_index(
            caster,
            fire_bolt.template_name,
            fire_target.index,
            available=available,
        )

    assert isinstance(event, SpellEvent)
    assert event.dice_roll is not None
    assert event.damage_rolls is not None
    assert event.attack_outcome is not None
    assert event.combat_log is not None
    damage_roll = event.damage_rolls[0]

    readout_lines = [
        f"caster: {caster.name}",
        f"spell attack bonus: {caster.spell_attack_bonus().normalized_score}",
        f"spell save dc: {caster.spell_save_dc()}",
        f"discovered spells: {fire_bolt.display_name}, {missile.display_name}",
        (
            "fire bolt row: "
            f"level={fire_bolt.spell_level}, "
            f"cost={fire_bolt.cost_amount} {fire_bolt.cost_type}, "
            f"targets={len(fire_bolt.valid_targets)}"
        ),
        (
            "magic missile row: "
            f"cast_at={missile.cast_at_level}, "
            f"projectiles={missile.num_projectiles}, "
            f"slot before={slot_before}"
        ),
        (
            f"selected target: {fire_target_entity.name}, "
            f"distance={fire_target.distance}"
        ),
        (
            f"event: {event.spell_id}, "
            f"phase={event.phase.value}, "
            f"outcome={event.attack_outcome.value}"
        ),
        f"attack roll: {event.dice_roll.results} + 7 = {event.dice_roll.total}",
        f"damage roll: {damage_roll.results} = {damage_roll.total}",
        f"target hp: {target_hp_before} -> {target.get_hp()}",
        (
            "actions: "
            f"{actions_before} -> "
            f"{caster.action_economy.actions.normalized_score}"
        ),
        (
            "level 1 slots: "
            f"{slot_before} -> "
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        ),
        f"combat log type: {event.combat_log.entry_type.value}",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "caster: Pyromancer",
        "spell attack bonus: 7",
        "spell save dc: 15",
        "discovered spells: Fire Bolt, Magic Missile (Level 1)",
        "fire bolt row: level=0, cost=1 actions, targets=1",
        "magic missile row: cast_at=1, projectiles=3, slot before=1",
        "selected target: Training Target, distance=5",
        "event: fire_bolt, phase=completion, outcome=Hit",
        "attack roll: [14, 12] + 7 = 19",
        "damage roll: [5, 6] = 11",
        "target hp: 27 -> 16",
        "actions: 1 -> 0",
        "level 1 slots: 1 -> 1",
        "combat log type: attack",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_multi_target_execution_does_not_mutate_cached_discovery_target() -> None:
    """Extra target allocation is bound to an execution copy of the selected row."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Missile Caster",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    first = create_spell_actor("First Target", (1, 0), "monsters")
    second = create_spell_actor("Second Target", (2, 0), "monsters")
    register_spell(caster, MagicMissile, caster_level=5)
    Entity.materialize_all_navigation(max_distance=30)
    available = get_available_actions(caster)
    missile = find_action(available, "Magic Missile__slot_1")
    primary = next(target for target in missile.valid_targets if target.target_uuid == first.uuid)

    event = execute_by_index(
        caster,
        missile.template_name,
        primary.index,
        extra_target_uuids=[str(second.uuid)],
        available=available,
    )

    assert event is not None
    assert primary.extra_target_uuids is None


def test_spell_slots_are_action_economy_values_and_reset_separately(capsys) -> None:
    """Spell slots are spendable action-economy values, not spellcasting fields."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Slot Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    assert caster.action_economy.spell_slot_2.normalized_score == 1
    assert caster.has_spell_slot(1)
    assert caster.has_spell_slot(2)
    assert not caster.has_spell_slot(3)
    assert caster.get_lowest_spell_slot(1) == 1
    assert caster.get_lowest_spell_slot(3) is None
    assert not hasattr(caster.spellcasting, "spell_slot_1")
    initial_state = (
        caster.action_economy.spell_slot_1.normalized_score,
        caster.action_economy.spell_slot_2.normalized_score,
        caster.has_spell_slot(1),
        caster.has_spell_slot(2),
        caster.has_spell_slot(3),
        caster.get_lowest_spell_slot(1),
        caster.get_lowest_spell_slot(3),
        hasattr(caster.spellcasting, "spell_slot_1"),
    )

    caster.action_economy.consume("spell_slot_1", 1)

    assert caster.action_economy.spell_slot_1.normalized_score == 1
    after_consume = caster.action_economy.spell_slot_1.normalized_score

    caster.action_economy.reset_all_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 1
    after_turn_reset = caster.action_economy.spell_slot_1.normalized_score

    caster.action_economy.reset_spell_slot_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    after_slot_reset = caster.action_economy.spell_slot_1.normalized_score

    slot_lines = [
        f"initial slots: level1={initial_state[0]}, level2={initial_state[1]}",
        (
            "has slots: "
            f"l1={initial_state[2]}, "
            f"l2={initial_state[3]}, "
            f"l3={initial_state[4]}"
        ),
        f"lowest slots: from1={initial_state[5]}, from3={initial_state[6]}",
        f"slots live on spellcasting block: {initial_state[7]}",
        f"level1 after consume: {after_consume}",
        f"level1 after turn reset: {after_turn_reset}",
        f"level1 after slot reset: {after_slot_reset}",
    ]

    print("\n".join(slot_lines))

    expected_slot_lines = [
        "initial slots: level1=2, level2=1",
        "has slots: l1=True, l2=True, l3=False",
        "lowest slots: from1=1, from3=None",
        "slots live on spellcasting block: False",
        "level1 after consume: 1",
        "level1 after turn reset: 1",
        "level1 after slot reset: 2",
    ]
    assert slot_lines == expected_slot_lines
    assert capsys.readouterr().out.splitlines() == expected_slot_lines


def test_spell_numbers_compose_from_ability_proficiency_and_modifiers(capsys) -> None:
    """Entity spell helpers combine ability, proficiency, and spell modifiers."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Focused Mage",
        (0, 0),
        "heroes",
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_attack_modifiers=[("Wand", 2)],
            spell_damage_modifiers=[("Elemental Affinity", 3)],
            spell_dc_modifiers=[("Arcane Focus", 1)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        ),
    )

    assert caster.spell_attack_bonus().normalized_score == 9
    assert caster.spell_save_dc() == 16
    assert caster.get_spell_damage_bonus().normalized_score == 3
    assert caster.get_spell_crit_threshold() == 19
    assert caster.get_spell_crit_extra_dice() == 2
    number_lines = [
        f"spell ability: {caster.spellcasting.spellcasting_ability}",
        f"spell attack bonus: {caster.spell_attack_bonus().normalized_score}",
        f"spell save dc: {caster.spell_save_dc()}",
        f"spell damage bonus: {caster.get_spell_damage_bonus().normalized_score}",
        f"spell crit threshold: {caster.get_spell_crit_threshold()}",
        f"spell crit extra dice: {caster.get_spell_crit_extra_dice()}",
    ]

    print("\n".join(number_lines))

    expected_number_lines = [
        "spell ability: intelligence",
        "spell attack bonus: 9",
        "spell save dc: 16",
        "spell damage bonus: 3",
        "spell crit threshold: 19",
        "spell crit extra dice: 2",
    ]
    assert number_lines == expected_number_lines
    assert capsys.readouterr().out.splitlines() == expected_number_lines


def test_registered_spells_surface_cantrips_and_slot_variants(capsys) -> None:
    """Registered spell templates generate the rows a controller can select."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Menu Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1, 2: 1, 3: 1},
    )
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    ally = create_spell_actor("Haste Ally", (0, 1), "heroes")
    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)
    register_spell(caster, Haste, caster_level=5)
    Entity.materialize_all_navigation(max_distance=30)

    available = get_available_actions(caster)
    fire_bolt = find_action(available, "Fire Bolt")
    missile_1 = find_action(available, "Magic Missile__slot_1")
    missile_2 = find_action(available, "Magic Missile__slot_2")
    missile_3 = find_action(available, "Magic Missile__slot_3")
    haste = find_action(available, "Haste__slot_3")

    assert fire_bolt.action_category == ActionCategory.SPELL
    assert fire_bolt.spell_level == 0
    assert fire_bolt.cast_at_level == 0
    assert not fire_bolt.is_spell_variant
    assert [target.target_uuid for target in fire_bolt.valid_targets] == [
        enemy.uuid
    ]

    assert missile_1.base_template_name == "Magic Missile"
    assert missile_1.display_name == "Magic Missile (Level 1)"
    assert missile_1.cast_at_level == 1
    assert missile_1.num_projectiles == 3
    assert missile_1.allow_same_target is True
    assert missile_2.cast_at_level == 2
    assert missile_2.num_projectiles == 4
    assert missile_3.cast_at_level == 3
    assert missile_3.num_projectiles == 5

    assert haste.base_template_name == "Haste"
    assert haste.cast_at_level == 3
    assert {target.target_uuid for target in haste.valid_targets} == {
        enemy.uuid,
        ally.uuid,
    }
    fire_target_names: list[str] = []
    for target_row in fire_bolt.valid_targets:
        assert target_row.target_uuid is not None
        target_entity = Entity.get(target_row.target_uuid)
        assert target_entity is not None
        fire_target_names.append(target_entity.name)
    haste_target_names: list[str] = []
    for target_row in haste.valid_targets:
        assert target_row.target_uuid is not None
        target_entity = Entity.get(target_row.target_uuid)
        assert target_entity is not None
        haste_target_names.append(target_entity.name)
    haste_target_names.sort()
    discovery_lines = [
        (
            "fire bolt row: "
            f"category={fire_bolt.action_category.value}, "
            f"level={fire_bolt.spell_level}, "
            f"cast_at={fire_bolt.cast_at_level}, "
            f"variant={fire_bolt.is_spell_variant}, "
            f"targets={fire_target_names}"
        ),
        (
            "magic missile level 1: "
            f"base={missile_1.base_template_name}, "
            f"display={missile_1.display_name}, "
            f"cast_at={missile_1.cast_at_level}, "
            f"projectiles={missile_1.num_projectiles}, "
            f"same_target={missile_1.allow_same_target}"
        ),
        (
            "magic missile scaling: "
            f"level2={missile_2.num_projectiles}, "
            f"level3={missile_3.num_projectiles}"
        ),
        (
            "haste row: "
            f"base={haste.base_template_name}, "
            f"cast_at={haste.cast_at_level}, "
            f"targets={haste_target_names}"
        ),
    ]

    print("\n".join(discovery_lines))

    expected_discovery_lines = [
        "fire bolt row: category=spell, level=0, cast_at=0, variant=False, targets=['Training Target']",
        "magic missile level 1: base=Magic Missile, display=Magic Missile (Level 1), cast_at=1, projectiles=3, same_target=True",
        "magic missile scaling: level2=4, level3=5",
        "haste row: base=Haste, cast_at=3, targets=['Haste Ally', 'Training Target']",
    ]
    assert discovery_lines == expected_discovery_lines
    assert capsys.readouterr().out.splitlines() == expected_discovery_lines


def test_fire_bolt_uses_spell_attack_bonus_scaling_and_damage(capsys) -> None:
    """A threatened cantrip rolls disadvantage, scales damage, and costs an action."""
    reset_spell_tutorial_state()
    caster = create_spell_actor("Pyromancer", (0, 0), "heroes")
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    Entity.materialize_all_navigation(max_distance=30)
    hp_before = enemy.get_hp()

    with fixed_dice_faces(14, 12, 5, 6):
        event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
            caster_level=5,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.attack_outcome == AttackOutcome.HIT
    assert event.dice_roll is not None
    assert event.dice_roll.results == [14, 12]
    assert event.dice_roll.total == 19
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [5, 6]
    assert event.damage_rolls[0].total == 11
    assert enemy.get_hp() == hp_before - 11
    assert caster.action_economy.actions.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.ATTACK
    assert event.combat_log.data["outcome"] == "hit"
    fire_lines = [
        (
            "event phase: "
            f"{event.phase.value}, canceled={event.canceled}, "
            f"outcome={event.attack_outcome.value}"
        ),
        f"attack roll: {event.dice_roll.results} -> {event.dice_roll.total}",
        f"damage roll: {event.damage_rolls[0].results} -> {event.damage_rolls[0].total}",
        f"target hp: {hp_before}->{enemy.get_hp()}",
        f"actions after cast: {caster.action_economy.actions.normalized_score}",
        (
            "combat log: "
            f"{event.combat_log.entry_type.value}, "
            f"outcome={event.combat_log.data['outcome']}"
        ),
    ]

    print("\n".join(fire_lines))

    expected_fire_lines = [
        "event phase: completion, canceled=False, outcome=Hit",
        "attack roll: [14, 12] -> 19",
        "damage roll: [5, 6] -> 11",
        "target hp: 27->16",
        "actions after cast: 0",
        "combat log: attack, outcome=hit",
    ]
    assert fire_lines == expected_fire_lines
    assert capsys.readouterr().out.splitlines() == expected_fire_lines


def test_magic_missile_auto_hits_multiple_darts_and_spends_slot(capsys) -> None:
    """A leveled multi-target spell creates dart children and consumes its slot."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Missile Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    Entity.materialize_all_navigation(max_distance=30)
    hp_before = enemy.get_hp()

    with fixed_dice_faces(2, 3, 4):
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.total_targets == 3
    assert event.total_damage == 12
    assert enemy.get_hp() == hp_before - 12
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.MULTI_ENTITY_ACTION
    assert len(event.combat_log.sub_entries) == 3
    assert event.combat_log.data["target_names"] == ["Training Target"]
    assert event.combat_log.data["per_target_damage"] == [3, 4, 5]
    assert event.combat_log.data["total_damage"] == 12
    missile_lines = [
        f"event phase: {event.phase.value}, canceled={event.canceled}",
        f"targets/projectiles: {event.total_targets}, damage={event.total_damage}",
        f"target hp: {hp_before}->{enemy.get_hp()}",
        f"actions after cast: {caster.action_economy.actions.normalized_score}",
        (
            "level 1 slots after cast: "
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        ),
        (
            "combat log: "
            f"{event.combat_log.entry_type.value}, "
            f"sub_entries={len(event.combat_log.sub_entries)}"
        ),
    ]

    print("\n".join(missile_lines))

    expected_missile_lines = [
        "event phase: completion, canceled=False",
        "targets/projectiles: 3, damage=12",
        "target hp: 27->15",
        "actions after cast: 0",
        "level 1 slots after cast: 0",
        "combat log: multi_entity_action, sub_entries=3",
    ]
    assert missile_lines == expected_missile_lines
    assert capsys.readouterr().out.splitlines() == expected_missile_lines


def test_haste_links_spell_effect_to_concentration_and_cleans_up(capsys) -> None:
    """A concentration spell links target effects to the caster's condition."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Time Mage",
        (0, 0),
        "heroes",
        spell_slots={3: 1},
    )
    ally = create_spell_actor("Haste Ally", (1, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=30)
    movement_before = ally.action_economy.movement.normalized_score
    actions_before = ally.action_economy.actions.normalized_score
    ac_before = ally.ac_bonus().normalized_score

    event = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Haste" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == movement_before * 2
    assert ally.action_economy.actions.normalized_score == actions_before
    assert ally.action_economy.resources["haste_action"].current == 1
    assert ally.ac_bonus().normalized_score == ac_before + 2
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    concentrating = caster.active_conditions["Concentrating"]
    assert concentrating.linked_conditions == [
        (ally.uuid, ally.active_conditions["Haste"].uuid)
    ]
    after_apply = (
        event.phase.value,
        event.canceled,
        "Concentrating" in caster.active_conditions,
        "Haste" in ally.active_conditions,
        ally.action_economy.movement.normalized_score,
        ally.action_economy.actions.normalized_score,
        ally.action_economy.resources["haste_action"].current,
        ally.ac_bonus().normalized_score,
        caster.action_economy.spell_slot_3.normalized_score,
        concentrating.linked_conditions
        == [(ally.uuid, ally.active_conditions["Haste"].uuid)],
    )

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Haste" not in ally.active_conditions
    assert "haste_action" not in ally.action_economy.resources
    assert "Haste Lethargy" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0
    assert ally.ac_bonus().normalized_score == ac_before
    after_cleanup = (
        "Concentrating" in caster.active_conditions,
        "Haste" in ally.active_conditions,
        "Haste Lethargy" in ally.active_conditions,
        ally.ac_bonus().normalized_score,
    )

    haste_lines = [
        f"event phase: {after_apply[0]}, canceled={after_apply[1]}",
        (
            "conditions after cast: "
            f"caster_concentrating={after_apply[2]}, "
            f"ally_haste={after_apply[3]}"
        ),
        (
            "ally movement/actions/haste/ac: "
            f"{movement_before}->{after_apply[4]}, "
            f"{actions_before}->{after_apply[5]}, "
            f"haste={after_apply[6]}, "
            f"{ac_before}->{after_apply[7]}"
        ),
        f"level 3 slots after cast: {after_apply[8]}",
        f"concentration linked to haste: {after_apply[9]}",
        (
            "after concentration cleanup: "
            f"caster_concentrating={after_cleanup[0]}, "
            f"ally_haste={after_cleanup[1]}, "
            f"ally_haste_lethargy={after_cleanup[2]}, "
            f"ally_ac={after_cleanup[3]}"
        ),
    ]

    print("\n".join(haste_lines))

    expected_haste_lines = [
        "event phase: completion, canceled=False",
        "conditions after cast: caster_concentrating=True, ally_haste=True",
        "ally movement/actions/haste/ac: 30->60, 1->1, haste=1, 10->12",
        "level 3 slots after cast: 0",
        "concentration linked to haste: True",
        "after concentration cleanup: caster_concentrating=False, ally_haste=False, ally_haste_lethargy=True, ally_ac=10",
    ]
    assert haste_lines == expected_haste_lines
    assert capsys.readouterr().out.splitlines() == expected_haste_lines
