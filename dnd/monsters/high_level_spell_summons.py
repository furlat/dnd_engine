"""The twelve approved spell-summon bodies, composed from native content."""

from dataclasses import dataclass
from uuid import uuid4

from dnd.actions import (
    AllyHelp,
    Attack,
    Dash,
    Disengage,
    Dodge,
    Move,
    Swim,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType
from dnd.blocks.equipment import EquipmentConfig, Weapon
from dnd.blocks.health import HealthConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.attack_types import DamageDieValue
from dnd.core.base_actions import Cost, DamageRollProfile, TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    behavior_content_ref,
    creature_factory,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.equipment_types import WeaponProperty, WeaponSlot, WeaponUsage
from dnd.core.events import Range, RangeType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.monsters.spell_summon_actions import (
    SUMMON_CONDITION_IDENTITIES,
    CinderousSwipe,
    ConcussiveSmash,
    DraconicBreathCadence,
    DragonBreath,
    DrainingKiss,
    ElectrifiedFlail,
    ElementalMultiattackBonus,
    ElementalWarp,
    ExplosiveIcicle,
    GroundedThunder,
    GushingAir,
    HealingVapours,
    HiemalStrike,
    Immolation,
    MuckToMetal,
    MyrmidonBurrow,
    MyrmidonCinderousSwipe,
    MyrmidonStrikeDice,
    MyrmidonTenacity,
    PrimordialGales,
    RagingVortex,
    ScorchingStrike,
    SeismicStrike,
    SludgySling,
    SmoulderingTouch,
    SoilCloggedSlam,
    SweetplumGales,
    WaterSlam,
    WintersBreath,
)
from dnd.monsters.spell_summons import SpellSummonParameters
from dnd.monsters.traits import InnateFlight, MultiattackAction
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.conjuration import MistyStep
from dnd.spells.enchantment import CharmPerson
from dnd.spells.evocation import ScorchingRay, Thunderwave
from dnd.spells.illusion import Invisibility
from dnd.spells.infernal import create_hellish_rebuke_reaction_handler
from dnd.spells.necromancy import Revivify
from dnd.types.senses import SenseMode, SensesType
from dnd.types.world import MovementMode

BPS = frozenset({DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING})
ELEMENTS = (
    DamageType.ACID,
    DamageType.COLD,
    DamageType.FIRE,
    DamageType.LIGHTNING,
    DamageType.POISON,
)
BASE_IMMUNITIES = (
    "Exhaustion",
    "Grappled",
    "Paralyzed",
    "Petrified",
    "Poisoned",
    "Prone",
    "Restrained",
    "Unconscious",
)


@dataclass(frozen=True)
class SpellBody:
    key: str
    name: str
    scores: tuple[int, int, int, int, int, int]
    hp: int
    ac: int
    size: Size
    kind: CreatureType = CreatureType.ELEMENTAL
    fly: int = 0
    swim: bool = False
    nonmagical_bps: bool = True
    resist: tuple[DamageType, ...] = ()
    immune: tuple[DamageType, ...] = ()
    vulnerable: tuple[DamageType, ...] = ()
    conditions: tuple[str, ...] = ("Poisoned",)
    darkvision: int = 60
    initiative_bonus: int = 0
    ethereal: bool = False
    magical_strikes: bool = False


BODIES = (
    SpellBody(
        "air_elemental",
        "Air Elemental",
        (14, 20, 14, 6, 10, 6),
        90,
        15,
        Size.TINY,
        fly=60,
        resist=(DamageType.LIGHTNING, DamageType.THUNDER),
        immune=(DamageType.POISON,),
        conditions=BASE_IMMUNITIES,
        ethereal=True,
    ),
    SpellBody(
        "earth_elemental",
        "Earth Elemental",
        (20, 8, 20, 5, 10, 5),
        126,
        17,
        Size.LARGE,
        immune=(DamageType.POISON,),
        vulnerable=(DamageType.THUNDER,),
        conditions=("Exhaustion", "Paralyzed", "Petrified", "Poisoned", "Unconscious"),
    ),
    SpellBody(
        "fire_elemental",
        "Fire Elemental",
        (11, 17, 16, 6, 10, 7),
        102,
        13,
        Size.TINY,
        nonmagical_bps=False,
        immune=(DamageType.FIRE,),
        conditions=BASE_IMMUNITIES,
        ethereal=True,
    ),
    SpellBody(
        "water_elemental",
        "Water Elemental",
        (18, 14, 18, 5, 10, 8),
        114,
        14,
        Size.MEDIUM,
        swim=True,
        resist=(DamageType.ACID,),
        conditions=BASE_IMMUNITIES,
    ),
    SpellBody(
        "air_myrmidon",
        "Air Myrmidon",
        (18, 14, 14, 9, 10, 10),
        117,
        18,
        Size.SMALL,
        fly=60,
        resist=(DamageType.LIGHTNING, DamageType.THUNDER),
        immune=(DamageType.POISON,),
        initiative_bonus=2,
        ethereal=True,
        magical_strikes=True,
    ),
    SpellBody(
        "earth_myrmidon",
        "Earth Myrmidon",
        (18, 10, 17, 8, 10, 10),
        127,
        18,
        Size.MEDIUM,
        immune=(DamageType.POISON,),
        magical_strikes=True,
    ),
    SpellBody(
        "fire_myrmidon",
        "Fire Myrmidon",
        (13, 18, 15, 9, 10, 10),
        123,
        18,
        Size.SMALL,
        fly=60,
        immune=(DamageType.FIRE, DamageType.POISON),
        initiative_bonus=4,
        ethereal=True,
        magical_strikes=True,
    ),
    SpellBody(
        "water_myrmidon",
        "Water Myrmidon",
        (18, 14, 16, 8, 10, 10),
        127,
        18,
        Size.MEDIUM,
        fly=60,
        swim=True,
        resist=(DamageType.ACID,),
        immune=(DamageType.POISON,),
        initiative_bonus=2,
        ethereal=True,
        magical_strikes=True,
    ),
    SpellBody(
        "deva",
        "Deva",
        (18, 18, 18, 17, 20, 20),
        136,
        21,
        Size.MEDIUM,
        kind=CreatureType.CELESTIAL,
        fly=60,
        resist=(DamageType.RADIANT,),
        conditions=("Charmed", "Exhaustion", "Frightened"),
        darkvision=120,
        initiative_bonus=4,
        magical_strikes=True,
    ),
    SpellBody(
        "djinni",
        "Djinni",
        (21, 15, 22, 15, 16, 20),
        161,
        19,
        Size.MEDIUM,
        nonmagical_bps=False,
        immune=(DamageType.LIGHTNING, DamageType.THUNDER),
        conditions=("Prone", "Hideous Laughter"),
        darkvision=120,
        magical_strikes=True,
    ),
    SpellBody(
        "cambion",
        "Cambion",
        (18, 18, 16, 14, 12, 16),
        82,
        14,
        Size.MEDIUM,
        kind=CreatureType.FIEND,
        fly=60,
        resist=(
            DamageType.FIRE,
            DamageType.LIGHTNING,
            DamageType.COLD,
            DamageType.POISON,
        ),
        conditions=(),
    ),
    SpellBody(
        "draconic_spirit",
        "Draconic Spirit",
        (19, 14, 17, 10, 14, 14),
        50,
        19,
        Size.LARGE,
        kind=CreatureType.DRAGON,
        fly=60,
        swim=True,
        nonmagical_bps=False,
        resist=ELEMENTS,
        conditions=("Charmed", "Frightened", "Poisoned"),
    ),
)


def action_cost(name: str, *, resource: str | None = None):
    return [
        Cost(
            name=name,
            cost_type="actions",
            cost=1,
            resource_name=resource,
            resource_cost=1 if resource else 0,
            evaluator=entity_action_economy_cost_evaluator,
            resource_evaluator=entity_resource_cost_evaluator,
        )
    ]


def bound_weapon(
    entity: Entity,
    name: str,
    die: DamageDieValue,
    count: int,
    flat: int,
    kind: DamageType,
    accuracy: int,
    *,
    extra: tuple[tuple[DamageDieValue, int, DamageType], ...] = (),
    reach: int = 5,
    body: bool = False,
    finesse: bool = False,
    magical: bool = False,
):
    strength = (
        max(
            entity.ability_scores.strength.modifier,
            entity.ability_scores.dexterity.modifier,
        )
        if finesse
        else entity.ability_scores.strength.modifier
    )
    value = lambda number: ModifiableValue.create(
        source_entity_uuid=entity.uuid, base_value=number
    )
    if entity.content_ref is None:
        raise RuntimeError("Summon weapon requires its authored creature identity")
    weapon = Weapon(
        name=name,
        item_id="weapon.spell_summon."
        + entity.content_ref.content_id.removeprefix("creature.spell."),
        source_entity_uuid=entity.uuid,
        intrinsic_owner_uuid=entity.uuid,
        usage=WeaponUsage.BODY if body else WeaponUsage.HELD,
        tags=["natural"] if body else [],
        damage_dice=die,
        dice_numbers=count,
        damage_type=kind,
        damage_bonus=value(flat - strength),
        attack_bonus=value(
            accuracy - strength - entity.proficiency_bonus.normalized_score
        ),
        is_magical=magical,
        properties=[
            WeaponProperty.MARTIAL,
            *([WeaponProperty.FINESSE] if finesse else []),
        ],
        range=Range(type=RangeType.REACH, normal=reach),
        extra_damage_dices=[entry[0] for entry in extra],
        extra_damage_dices_numbers=[entry[1] for entry in extra],
        extra_damage_type=[entry[2] for entry in extra],
        extra_damage_bonus=[value(0) for _ in extra],
    )
    entity.install_initial_items(((weapon, WeaponSlot.MELEE_MAIN),))
    entity.register_action(
        Attack(
            source_entity_uuid=entity.uuid,
            template=True,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
    )
    return weapon


def innate(entity: Entity, kind, *, resource: str | None = None, **values):
    action = kind(
        source_entity_uuid=entity.uuid, template=True, alt_skip_slot=True, **values
    )
    if resource:
        action.costs = action_cost(action.name, resource=resource)
    entity.register_action(action)


def body_dependencies(body: SpellBody):
    actions = {
        "air_elemental": (GushingAir, PrimordialGales),
        "earth_elemental": (SoilCloggedSlam, SeismicStrike),
        "fire_elemental": (SmoulderingTouch, CinderousSwipe),
        "water_elemental": (WaterSlam, WintersBreath),
        "air_myrmidon": (ElectrifiedFlail, RagingVortex),
        "earth_myrmidon": (GroundedThunder, SludgySling, MyrmidonBurrow, MuckToMetal),
        "fire_myrmidon": (ScorchingStrike, MyrmidonCinderousSwipe, Immolation),
        "water_myrmidon": (HiemalStrike, ExplosiveIcicle, HealingVapours),
        "deva": (ConcussiveSmash, AllyHelp),
        "djinni": (SweetplumGales,),
        "cambion": (DrainingKiss,),
        "draconic_spirit": (DragonBreath,),
    }[body.key]
    native = (
        Move,
        Dash,
        Disengage,
        Dodge,
        *((Swim,) if body.swim else ()),
        *((Attack,) if body.key != "cambion" else ()),
        *(
            (MultiattackAction,)
            if body.key.endswith("elemental") or body.key == "draconic_spirit"
            else ()
        ),
        *((ElementalWarp,) if body.key.endswith(("elemental", "myrmidon")) else ()),
    )
    result = [
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=(
                behavior_content_ref(
                    pack_id="content.srd_5_1_cc",
                    content_id="action.monster.multiattack",
                    version=1,
                    definition_kind=ContentDefinitionKind.ACTION,
                    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
                )
                if kind is MultiattackAction
                else get_content_declaration(kind).ref
            ),
        )
        for kind in (*native, *actions)
    ]
    conditions = {
        "air_elemental": (ElementalMultiattackBonus,),
        "earth_elemental": (ElementalMultiattackBonus,),
        "fire_elemental": (ElementalMultiattackBonus,),
        "water_elemental": (ElementalMultiattackBonus,),
        "air_myrmidon": (MyrmidonTenacity, MyrmidonStrikeDice),
        "fire_myrmidon": (MyrmidonStrikeDice,),
        "water_myrmidon": (MyrmidonStrikeDice,),
        "draconic_spirit": (DraconicBreathCadence,),
    }.get(body.key, ())
    condition_ids: dict[type[BaseCondition], str] = dict(SUMMON_CONDITION_IDENTITIES)
    for kind in (*conditions, *((InnateFlight,) if body.fly else ())):
        result.append(
            ContentDependency(
                relation=ContentDependencyRelation.APPLIES_CONDITION,
                target_ref=behavior_content_ref(
                    pack_id="content.srd_5_1_cc",
                    content_id="trait.innate_flight"
                    if kind is InnateFlight
                    else condition_ids[kind],
                    version=1,
                    definition_kind=ContentDefinitionKind.TRAIT
                    if kind is InnateFlight
                    else ContentDefinitionKind.CONDITION,
                    runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
                ),
            )
        )
    spells = {
        "air_myrmidon": ("spell.invisibility",),
        "fire_myrmidon": ("spell.hellish_rebuke",),
        "deva": ("spell.revivify",),
        "djinni": ("spell.thunderwave", "spell.misty_step"),
        "cambion": ("spell.charm_person", "spell.scorching_ray"),
    }.get(body.key, ())
    for identity in spells:
        result.append(
            ContentDependency(
                relation=ContentDependencyRelation.GRANTS_SPELL,
                target_ref=behavior_content_ref(
                    pack_id="content.srd_5_1_cc",
                    content_id=identity,
                    version=1,
                    definition_kind=ContentDefinitionKind.SPELL,
                    runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
                ),
            )
        )
    return tuple(result)


def _declare(body: SpellBody):
    def factory(raw_context: object, parameters: SpellSummonParameters):
        context = CreatureBuildContext.model_validate(raw_context)
        dragon = body.key == "draconic_spirit"
        hp = 50 + 10 * (parameters.slot_level - 5) if dragon else body.hp
        ac = 19 + parameters.slot_level - 5 if dragon else body.ac
        scores = AbilityScoresConfig(
            **{
                name: AbilityConfig(ability_score=score)
                for name, score in zip(
                    (
                        "strength",
                        "dexterity",
                        "constitution",
                        "intelligence",
                        "wisdom",
                        "charisma",
                    ),
                    body.scores,
                )
            }
        )
        saving = SavingThrowSetConfig()
        for name in (
            ("wisdom", "charisma")
            if body.key == "deva"
            else ("strength", "constitution", "intelligence", "charisma")
            if body.key == "cambion"
            else ()
        ):
            saving_value = SavingThrowConfig(proficiency=True)
            setattr(saving, name + "_saving_throw", saving_value)
        entity = Entity.create(
            context.runtime_entity_uuid,
            context.display_name,
            content_ref=context.requested_ref,
            config=EntityConfig(
                faction=context.faction,
                position=context.position,
                creature_type=body.kind,
                size=body.size,
                proficiency_bonus=parameters.proficiency if dragon else 4,
                ability_scores=scores,
                cannot_manipulate_bodies=body.ethereal,
                swimming_speed=30 if body.swim else 0,
                requires_breathing=body.kind is not CreatureType.ELEMENTAL,
                health=HealthConfig(
                    max_hit_points_bonus=hp,
                    nonmagical_attack_resistances=BPS
                    if body.nonmagical_bps
                    else frozenset(),
                    immunities=list(body.immune),
                    resistances=list(body.resist),
                    vulnerabilities=list(body.vulnerable),
                ),
                equipment=EquipmentConfig(unarmored_ac=ac - (body.scores[1] - 10) // 2),
                saving_throws=saving,
                skill_set=SkillSetConfig(
                    perception=SkillConfig(proficiency=body.key == "deva"),
                    insight=SkillConfig(proficiency=body.key == "deva"),
                ),
                spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
                initiative_modifiers=[
                    ("Authored creature initiative", body.initiative_bonus)
                ],
                action_economy=ActionEconomyConfig(movement=30),
            ),
        )
        for name in body.conditions:
            entity.add_condition_immunity(name, immunity_name=body.name)
        entity.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=body.darkvision)
        )
        if body.key == "earth_elemental":
            entity.senses.sense_modes.append(
                SenseMode(sense_type=SensesType.TREMORSENSE, range_feet=60)
            )
        if dragon:
            entity.senses.sense_modes.append(
                SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=30)
            )
        for kind in (Move, Dash, Disengage, Dodge):
            entity.register_action(kind(source_entity_uuid=entity.uuid, template=True))
        if body.swim:
            entity.register_action(Swim(source_entity_uuid=entity.uuid, template=True))
        if body.fly:
            entity.add_condition(
                InnateFlight(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    flying_speed=body.fly,
                )
            )
            entity.register_action(
                Move(
                    source_entity_uuid=entity.uuid,
                    template=True,
                    name="Fly",
                    movement_mode=MovementMode.FLYING,
                )
            )

        def register(kind, **values):
            entity.register_action(
                kind(source_entity_uuid=entity.uuid, template=True, **values)
            )

        if body.key in ("air_myrmidon", "fire_myrmidon", "water_myrmidon"):
            element, identity = {
                "air_myrmidon": (
                    DamageType.LIGHTNING,
                    "action.air_myrmidon.electrified_flail",
                ),
                "fire_myrmidon": (
                    DamageType.FIRE,
                    "action.fire_myrmidon.scorching_strike",
                ),
                "water_myrmidon": (
                    DamageType.COLD,
                    "action.water_myrmidon.hiemal_strike",
                ),
            }[body.key]
            entity.add_condition(
                MyrmidonStrikeDice(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    damage_type=element,
                    action_id=identity,
                )
            )
        if body.key.endswith("elemental") or body.key.endswith("myrmidon"):
            register(ElementalWarp)
        if body.key in (
            "air_elemental",
            "earth_elemental",
            "fire_elemental",
            "water_elemental",
        ):
            config = {
                "air_elemental": (
                    "Air Slam",
                    4,
                    2,
                    2,
                    DamageType.SLASHING,
                    6,
                    ((4, 2, DamageType.LIGHTNING),),
                    "Shocked",
                    (GushingAir, PrimordialGales),
                ),
                "earth_elemental": (
                    "Earth Slam",
                    4,
                    2,
                    5,
                    DamageType.BLUDGEONING,
                    9,
                    (),
                    "Prone",
                    (SoilCloggedSlam, SeismicStrike),
                ),
                "fire_elemental": (
                    "Fire Slam",
                    4,
                    2,
                    0,
                    DamageType.BLUDGEONING,
                    4,
                    ((4, 2, DamageType.FIRE),),
                    "Burning",
                    (SmoulderingTouch, CinderousSwipe),
                ),
                "water_elemental": (
                    "Water Slam",
                    4,
                    2,
                    4,
                    DamageType.BLUDGEONING,
                    8,
                    ((4, 2, DamageType.COLD),),
                    "Chilled",
                    (WaterSlam, WintersBreath),
                ),
            }[body.key]
            bound_weapon(
                entity,
                *config[:6],
                extra=config[6],
                body=True,
                magical=body.magical_strikes,
            )
            entity.action_economy.add_resource(
                "elemental_multiattack", 1, RechargeType.TURN_START
            )
            register(
                MultiattackAction,
                attack_sequence=((WeaponSlot.MELEE_MAIN, 2),),
                costs=action_cost("Multiattack", resource="elemental_multiattack"),
            )
            entity.add_condition(
                ElementalMultiattackBonus(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    prerequisite=config[7],
                    packet_count=1 + len(config[6]),
                )
            )
            for kind in config[8]:
                register(kind)
        elif body.key == "air_myrmidon":
            bound_weapon(
                entity,
                "Bound Flail",
                8,
                1,
                7,
                DamageType.BLUDGEONING,
                11,
                extra=((8, 1, DamageType.LIGHTNING),),
                magical=body.magical_strikes,
            )
            register(ElectrifiedFlail)
            register(RagingVortex)
            entity.action_economy.add_resource(
                "innate_invisibility", 1, RechargeType.SHORT_REST
            )
            innate(
                entity,
                Invisibility,
                resource="innate_invisibility",
                target_type=TargetType.SELF,
                target_entity_uuid=entity.uuid,
            )
            entity.add_condition(
                MyrmidonTenacity(
                    source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
                )
            )
        elif body.key == "earth_myrmidon":
            bound_weapon(
                entity,
                "Grounded Thunder",
                4,
                0,
                9,
                DamageType.BLUDGEONING,
                8,
                extra=((10, 3, DamageType.THUNDER),),
                magical=body.magical_strikes,
            )
            register(GroundedThunder)
            register(SludgySling)
            register(MyrmidonBurrow)
            register(MuckToMetal)
        elif body.key == "fire_myrmidon":
            bound_weapon(
                entity,
                "Bound Scimitar",
                6,
                1,
                7,
                DamageType.SLASHING,
                11,
                extra=((6, 1, DamageType.FIRE),),
                finesse=True,
                magical=body.magical_strikes,
            )
            register(ScorchingStrike)
            register(MyrmidonCinderousSwipe)
            register(Immolation)
            source = uuid4()
            entity.spellcasting.add_innate_source(
                source,
                "charisma",
                provider_id="species.fire_myrmidon",
                provider_level=1,
                maximum_spell_rank=1,
            )
            entity.action_economy.add_resource(
                "innate_rebuke", 1, RechargeType.TURN_START
            )
            handler = create_hellish_rebuke_reaction_handler(entity.uuid)
            entity.spellcasting.add_learned_reaction_spell_source(
                spell_id="spell.hellish_rebuke",
                source_id=source,
                handler_uuid=handler.uuid,
                fixed_cast_rank=1,
                resource_name="innate_rebuke",
            )
            entity.add_event_handler(handler)
        elif body.key == "water_myrmidon":
            bound_weapon(
                entity,
                "Bound Trident",
                6,
                1,
                7,
                DamageType.PIERCING,
                11,
                extra=((6, 1, DamageType.COLD),),
                magical=body.magical_strikes,
            )
            register(HiemalStrike)
            register(ExplosiveIcicle)
            register(HealingVapours)
        elif body.key == "deva":
            bound_weapon(
                entity,
                "Bound Mace",
                6,
                1,
                4,
                DamageType.BLUDGEONING,
                8,
                extra=((8, 4, DamageType.RADIANT),),
                magical=body.magical_strikes,
            )
            entity.action_economy.add_resource(
                "concussive_smash", 1, RechargeType.SHORT_REST
            )
            register(
                ConcussiveSmash,
                costs=action_cost("Concussive Smash", resource="concussive_smash"),
            )
            entity.action_economy.add_resource(
                "innate_revivify", 1, RechargeType.LONG_REST
            )
            innate(entity, Revivify, resource="innate_revivify")
            register(AllyHelp)
        elif body.key == "djinni":
            bound_weapon(
                entity,
                "Bound Scimitar",
                6,
                1,
                6,
                DamageType.SLASHING,
                10,
                extra=((10, 2, DamageType.POISON),),
                magical=body.magical_strikes,
            )
            innate(entity, Thunderwave, cast_at_level=4)
            innate(entity, MistyStep)
            register(SweetplumGales)
        elif body.key == "cambion":
            innate(entity, CharmPerson)
            innate(entity, ScorchingRay)
            register(DrainingKiss)
        elif dragon:
            bound_weapon(
                entity,
                "Rend",
                6,
                1,
                4 + parameters.slot_level,
                DamageType.PIERCING,
                parameters.attack_bonus,
                reach=10,
                body=True,
                magical=body.magical_strikes,
            )
            register(
                MultiattackAction,
                attack_sequence=((WeaponSlot.MELEE_MAIN, parameters.slot_level // 2),),
                description="Make Rends, then gain one free Draconic Breath this turn.",
            )
            register(
                DragonBreath,
                save_dc=parameters.spell_dc,
                packets=(
                    DamageRollProfile(
                        dice_count=2,
                        die_size=6,
                        damage_type=parameters.breath_type.value,
                    ),
                ),
            )
            entity.add_condition(
                DraconicBreathCadence(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    breath_type=parameters.breath_type,
                    save_dc=parameters.spell_dc,
                )
            )
        if body.key != "cambion":
            add_opportunity_attack_handler(entity)
        return entity

    factory.__name__ = "build_" + body.key
    factory.__qualname__ = factory.__name__
    declared = creature_factory(
        pack_id="content.srd_5_2_cc"
        if body.key == "draconic_spirit"
        else "content.srd_5_1_cc",
        content_id="creature.spell." + body.key,
        version=1,
        parameters=SpellSummonParameters,
        dependencies=body_dependencies(body),
        descriptor=ContentDescriptorSpec(
            display_name=body.name,
            description="Approved spell-created combat body and complete native loadout.",
            visibility=ContentVisibility.PUBLIC,
            tags=("creature", "spell_summon"),
            presentation=ContentPresentation(ui_group="creatures.spell_summon"),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=body.name,
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
            adapted_from_source_id="wotc.srd_5_2_cc"
            if body.key == "draconic_spirit"
            else "wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Approved BG3-style bodies/loadouts; bounded engine adaptations recorded in the implementation plan.",
        ),
    )(factory)
    return get_content_declaration(declared)


HIGH_LEVEL_SPELL_SUMMON_DECLARATIONS = tuple(_declare(body) for body in BODIES)
HIGH_LEVEL_SPELL_SUMMON_RECIPES = {
    body.key: ContentRecipe.create(ref=declaration.ref, parameters={})
    for body, declaration in zip(
        BODIES, HIGH_LEVEL_SPELL_SUMMON_DECLARATIONS, strict=True
    )
}
