"""Validation arenas for pressure-testing AI controller behavior."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Literal, Optional
from uuid import UUID, uuid4

from dnd.actions_functional import register_spells_by_name
from dnd.classes.barbarian_factory import BarbarianConfig, PrimalPathChoice, create_barbarian as _create_barbarian
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.controller import Controller, PassController
from dnd.conditions import Blinded, Poisoned
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.maps.arena_layout import (
    ARENA_HEIGHT,
    ARENA_WIDTH,
    DIFFICULT_TERRAIN_POSITIONS,
    DOOR_POSITION,
    STANDARD_BLOCKING_CHANNELS,
    SPIKE_ZONE_POSITIONS,
    TRAP_LEVER_POSITION,
    WATER_POSITIONS,
    StandardBarrierObjects,
    StandardArenaObjects,
    build_standard_arena_environment,
    create_standard_arena_floor,
    darken_arena,
)
from dnd.monsters.bestiary import (
    create_caster as _create_caster,
    create_goblin as _create_goblin,
    create_goblin_archer as _create_goblin_archer,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
    register_goblin_nimble_escape,
)
from dnd.monsters.srd_roster import create_srd_monster as _create_srd_monster
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.test_items import (
    create_fireball_cannon,
    create_healing_potion,
    create_lightning_weapon_coat,
    create_potion_of_haste,
    create_potion_of_greater_invisibility,
    create_acid_flask,
    create_scroll_of_fireball,
    create_scroll_of_hold_person,
    create_scroll_of_magic_missile,
    create_scroll_of_spike_growth,
    create_torch,
    create_wand_of_fire,
    create_wand_of_magic_missiles,
    create_wall_torch,
    create_weapon_coat,
    LootAllAction,
    StorageChest,
)
from dnd.items.weapons import create_club, create_longbow, create_shortsword
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.abjuration import register_counterspell_reaction, register_shield_reaction
from dnd.scenarios.evaluation.wardrobes import (
    BERSERKER_WARDROBE,
    BESTIARY_WARDROBES,
    CASTER_WARDROBES,
    SRD_WARDROBES,
    equip_wardrobe,
)


def create_barbarian(config: BarbarianConfig, source_id: Optional[UUID] = None) -> Entity:
    """Build a legacy-setting Barbarian with its annotated arena wardrobe."""
    return equip_wardrobe(_create_barbarian(config, source_id), BERSERKER_WARDROBE)


def create_caster(
    source_id: Optional[UUID] = None,
    name: str = "Caster",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    level: int = 5,
    wardrobe: Literal["arcane", "dark", "divine", "necromancer"] = "arcane",
) -> Entity:
    """Build a legacy-setting caster with a role-specific annotated wardrobe."""
    entity = _create_caster(source_id, name, position, faction, level)
    return equip_wardrobe(entity, CASTER_WARDROBES[wardrobe])


def create_goblin(
    source_id: Optional[UUID] = None,
    name: str = "Goblin",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 40,
) -> Entity:
    """Build a legacy-setting Goblin with practical footwear."""
    entity = _create_goblin(source_id, name, position, faction, weight)
    return equip_wardrobe(entity, BESTIARY_WARDROBES["goblin"])


def create_goblin_archer(
    source_id: Optional[UUID] = None,
    name: str = "Goblin Archer",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 40,
) -> Entity:
    """Build a legacy-setting Goblin Archer with practical footwear."""
    entity = _create_goblin_archer(source_id, name, position, faction, weight)
    return equip_wardrobe(entity, BESTIARY_WARDROBES["goblin_archer"])


def create_srd_monster(
    monster_id: str,
    source_id: Optional[UUID] = None,
    name: Optional[str] = None,
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Build a legacy-setting SRD creature with its catalog wardrobe, when any."""
    entity = _create_srd_monster(monster_id, source_id, name, position, faction)
    return equip_wardrobe(entity, SRD_WARDROBES.get(monster_id, ()))


@dataclass(frozen=True)
class ValidationArenaSpec:
    """Stable metadata for one AI validation arena.

    Attributes:
        arena_id: Stable identifier used by harnesses and dashboards.
        title: Human-readable arena name.
        hero_role: Main player-side role under test.
        tags: Machine-readable mechanics sampled by the arena.
        expected_pressure: Behaviors the arena should pressure in AI playtests.
        map_notes: Notable terrain and object facts.
    """

    arena_id: str
    title: str
    hero_role: str
    tags: tuple[str, ...]
    expected_pressure: tuple[str, ...]
    map_notes: tuple[str, ...]


@dataclass(frozen=True)
class ValidationArena:
    """Constructed validation arena bundle.

    Attributes:
        spec: Stable arena metadata.
        encounter: Encounter containing the arena combatants.
        hero: Hero-side actor.
        monsters: Monster-side actors.
        controllers: Controller map keyed by controlled entity UUID.
        notable_positions: Important map coordinates for assertions and dashboards.
        environment: Standard arena object bundle when the standard environment is used.
        side_a: Complete neutral side-A roster. Defaults to the legacy hero tuple.
        side_b: Complete neutral side-B roster. Defaults to the legacy monster tuple.
    """

    spec: ValidationArenaSpec
    encounter: Encounter
    hero: Entity
    monsters: tuple[Entity, ...]
    controllers: dict[UUID, Controller]
    notable_positions: dict[str, tuple[int, int]]
    environment: Optional[StandardArenaObjects] = None
    side_a: tuple[Entity, ...] = ()
    side_b: tuple[Entity, ...] = ()

    def __post_init__(self) -> None:
        """Populate neutral side views for historical hero-versus-monster arenas."""
        if not self.side_a:
            object.__setattr__(self, "side_a", (self.hero,))
        if not self.side_b:
            object.__setattr__(self, "side_b", self.monsters)


ArenaFactory = Callable[[], ValidationArena]


_OPENING_FACTION: ContextVar[Optional[str]] = ContextVar(
    "ai_validation_opening_faction",
    default=None,
)


STANDARD_SKELETON_DOORS = ValidationArenaSpec(
    arena_id="standard_skeleton_doors",
    title="Standard Skeleton Door Baseline",
    hero_role="level 5 sorcerer",
    tags=("baseline", "skeletons", "door", "chokepoint", "darkness", "hazards"),
    expected_pressure=(
        "open or navigate the closed door",
        "avoid bunching after ranged or spell pressure",
        "preserve support and ranged roles behind a frontline monster",
    ),
    map_notes=(
        f"closed directional door at {DOOR_POSITION}",
        "dark standard arena with torches, water, difficult terrain, spike zone, and trap lever",
    ),
)

GOBLIN_WATER_SKIRMISH = ValidationArenaSpec(
    arena_id="goblin_water_skirmish",
    title="Goblin Water Skirmish",
    hero_role="level 5 archer fighter",
    tags=("goblins", "water", "difficult-terrain", "ranged", "nimble-escape", "caster"),
    expected_pressure=(
        "route around water instead of using raw Manhattan movement",
        "use ranged pressure without collapsing into melee",
        "surface bonus-action skirmisher options distinctly from attacks",
    ),
    map_notes=(
        f"water cells at {WATER_POSITIONS}",
        f"difficult terrain bands at {DIFFICULT_TERRAIN_POSITIONS}",
    ),
)

SKELETON_ANTI_AOE_SPLIT = ValidationArenaSpec(
    arena_id="skeleton_anti_aoe_split",
    title="Skeleton Anti-AoE Split",
    hero_role="level 5 sorcerer",
    tags=("skeletons", "open-field", "anti-aoe", "spacing", "ranged", "support"),
    expected_pressure=(
        "punish policies that cluster monsters into Fireball geometry",
        "keep archer and warlock pressure available without marching into melee",
        "make spread/hold-spacing decisions visible in telemetry",
    ),
    map_notes=("open 15x15 floor with monsters intentionally split around the hero",),
)

CASTER_CROSSFIRE = ValidationArenaSpec(
    arena_id="caster_crossfire",
    title="Caster Crossfire",
    hero_role="level 5 barbarian",
    tags=("caster", "skeletons", "open-door", "crossfire", "aoe", "reaction-shield"),
    expected_pressure=(
        "combine spell and ranged pressure against a melee hero",
        "avoid friendly-fire area rows when a frontline ally is engaged",
        "handle Shield reactions and spell-slot resources in telemetry",
    ),
    map_notes=(
        f"standard barrier with the door opened at {DOOR_POSITION}",
        f"trap lever remains at {TRAP_LEVER_POSITION} and spike zone remains at arena edge",
    ),
)

ITEM_RESOURCE_GAUNTLET = ValidationArenaSpec(
    arena_id="item_resource_gauntlet",
    title="Item Resource Gauntlet",
    hero_role="level 5 archer fighter",
    tags=("items", "scrolls", "wands", "potions", "mixed-monsters", "aoe", "resource-economy"),
    expected_pressure=(
        "surface consumables and charged items as first-class affordances",
        "avoid treating spell access as only class-native spellcasting",
        "compare weapon attacks against scroll, wand, potion, and weapon-coat options",
    ),
    map_notes=(
        "open floor with mixed monster roles and a hero carrying scrolls, wands, potions, and a weapon coat",
    ),
)

DOUBLE_DOOR_DARK_HUNT = ValidationArenaSpec(
    arena_id="double_door_dark_hunt",
    title="Double Door Dark Hunt",
    hero_role="level 5 barbarian",
    tags=("doors", "darkness", "navigation", "object-interaction", "multi-room", "skeletons"),
    expected_pressure=(
        "navigate more than one closed door without assuming a single baseline door",
        "separate exploration movement from enemy-chase movement when enemies are not yet visible",
        "preserve light and darkvision differences in subjective observations",
    ),
    map_notes=(
        "two closed directional door barriers split the arena into three dark rooms",
    ),
)

ARCANE_DEVICE_CONTROL = ValidationArenaSpec(
    arena_id="arcane_device_control",
    title="Arcane Device Control",
    hero_role="level 5 sorcerer",
    tags=("environment-object", "fireball-cannon", "healing-potion", "positioning", "friendly-fire", "mixed-monsters"),
    expected_pressure=(
        "reason about usable battlefield objects rather than only entity-owned actions",
        "avoid or exploit area effects from an environmental Fireball cannon",
        "value positioning around central objects and side pickups",
    ),
    map_notes=(
        "central Fireball cannon with nearby floor potions and monsters on multiple approach vectors",
    ),
)

SKELETON_MARK_FOCUS_FIRE = ValidationArenaSpec(
    arena_id="skeleton_mark_focus_fire",
    title="Skeleton Mark Focus Fire",
    hero_role="level 5 shield fighter",
    tags=("skeletons", "support", "mark-target", "focus-fire", "ranged", "frontline", "high-ac"),
    expected_pressure=(
        "treat Mark Target as a real support affordance rather than dead UI noise",
        "coordinate archer, frontline, and caster actions against one durable target",
        "make focus-fire choices and target-marker follow-up visible in telemetry",
    ),
    map_notes=(
        "open floor with a high-AC shield fighter between skeleton frontline, archer, and warlock roles",
    ),
)

BUFF_CONSUMABLE_AMBUSH = ValidationArenaSpec(
    arena_id="buff_consumable_ambush",
    title="Buff Consumable Ambush",
    hero_role="level 5 barbarian",
    tags=("buffs", "consumables", "invisibility", "haste", "caster", "goblins", "skeletons", "darkness"),
    expected_pressure=(
        "surface self-buff and consumable rows alongside direct damage rows",
        "avoid collapsing all caster play into walking forward when buff actions are legal",
        "track invisibility, haste, and scroll resources in the local agent state",
    ),
    map_notes=(
        "dark open-door standard arena where monsters begin with potions, a hold-person scroll, and mixed ranged pressure",
    ),
)

FORCED_MOVEMENT_HAZARD_BRIDGE = ValidationArenaSpec(
    arena_id="forced_movement_hazard_bridge",
    title="Forced Movement Hazard Bridge",
    hero_role="level 5 barbarian",
    tags=("forced-movement", "hazards", "water", "spike-zone", "thunderwave", "positioning", "caster", "skeletons"),
    expected_pressure=(
        "distinguish ordinary movement, forced movement, and hazardous destination quality",
        "notice Thunderwave and similar displacement rows as tactical options",
        "avoid path shortcuts through water while still valuing forced movement near spike zones",
    ),
    map_notes=(
        "standard hazard arena with the door open and one warlock placed near the spike-zone edge",
    ),
)

LINE_AOE_CORRIDOR = ValidationArenaSpec(
    arena_id="line_aoe_corridor",
    title="Line AoE Corridor",
    hero_role="level 5 sorcerer",
    tags=("line-aoe", "corridor", "friendly-fire", "formation", "multi-target", "caster", "skeletons"),
    expected_pressure=(
        "value Lightning Bolt and other line effects when enemies are aligned",
        "avoid friendly-fire and wasted area rows when allies occupy the same lane",
        "show multi-target target sets directly in affordance and brief output",
    ),
    map_notes=(
        "open corridor-like formation with several actors sharing one horizontal lane",
    ),
)

ZONE_CONTROL_WEB_GAUNTLET = ValidationArenaSpec(
    arena_id="zone_control_web_gauntlet",
    title="Zone Control Web Gauntlet",
    hero_role="level 5 barbarian",
    tags=("zone-control", "web", "grease", "spike-growth", "concentration", "pathing", "caster", "goblins"),
    expected_pressure=(
        "treat Web, Grease, and Spike Growth as battlefield-shaping choices rather than decorative spells",
        "route actors around controlled cells instead of only chasing Manhattan distance",
        "show concentration and hazardous-zone facts in local agent summaries",
    ),
    map_notes=(
        "open-door standard arena with water, difficult terrain, and a control caster behind a skirmisher line",
    ),
)

SUPPORT_ATTRITION_CACHE = ValidationArenaSpec(
    arena_id="support_attrition_cache",
    title="Support Attrition Cache",
    hero_role="level 5 shield fighter",
    tags=("support", "healing", "bless", "bane", "aid", "potions", "resource-economy", "skeletons"),
    expected_pressure=(
        "surface support, healing, and defensive concentration actions beside attacks",
        "notice wounded allies and consumable healing options",
        "avoid reducing the enemy side to pure damage when a support turn is stronger",
    ),
    map_notes=(
        "open floor with a wounded frontline monster, a support caster, and healing consumables",
    ),
)

HIGH_LEVEL_SPELL_RESOURCE_DUEL = ValidationArenaSpec(
    arena_id="high_level_spell_resource_duel",
    title="High-Level Spell Resource Duel",
    hero_role="level 9 sorcerer",
    tags=("high-level-spells", "resource-economy", "control", "aoe", "reaction-shield", "caster", "mixed-monsters", "skeletons"),
    expected_pressure=(
        "compare expensive level 4 and 5 spell rows against lower-cost pressure",
        "keep control, burst, and defensive reactions visible in telemetry",
        "avoid overfitting policy choices to level 5 skeleton-only spell lists",
    ),
    map_notes=(
        "open floor with a level 9 sorcerer facing a high-slot enemy caster and mixed escorts",
    ),
)

SORCERER_BARBARIAN_DUEL = ValidationArenaSpec(
    arena_id="sorcerer_barbarian_duel",
    title="Sorcerer Barbarian Duel",
    hero_role="level 5 sorcerer",
    tags=("duel", "sorcerer", "barbarian", "control", "incapacitated", "melee", "resource-economy"),
    expected_pressure=(
        "compare Hold Person and ranged spell pressure against a melee class threat",
        "ensure Incapacitated blocks zero-cost martial setup actions",
        "resume Barbarian Rage, Frenzy, Reckless Attack, movement, and attacks after control ends",
    ),
    map_notes=(
        "open floor duel with a level 5 Sorcerer starting forty feet from a level 5 Berserker Barbarian",
    ),
)

CLASS_PARTY_MIRROR_SCRAMBLE = ValidationArenaSpec(
    arena_id="class_party_mirror_scramble",
    title="Class Party Mirror Scramble",
    hero_role="level 5 shield fighter",
    tags=("class-party", "fighter", "barbarian", "sorcerer", "gear-loadout", "resource-economy", "ranged", "melee"),
    expected_pressure=(
        "avoid overfitting monster policy to skeleton and goblin factories",
        "compare class-feature rows such as Rage, Action Surge, Second Wind, metamagic, and spell slots",
        "treat enemy class gear as real tactical loadout data rather than cosmetic fixture noise",
    ),
    map_notes=(
        "open floor mirror-party setup with a monster Barbarian, archer Fighter, and Sorcerer",
    ),
)

RANGED_LOADOUT_KITING_RING = ValidationArenaSpec(
    arena_id="ranged_loadout_kiting_ring",
    title="Ranged Loadout Kiting Ring",
    hero_role="level 5 barbarian",
    tags=("ranged", "gear-loadout", "water", "difficult-terrain", "fighter", "goblins", "skirmish", "resource-economy"),
    expected_pressure=(
        "prefer legal ranged pressure before wasting turns walking a full ranged loadout into melee",
        "route around water and difficult terrain while preserving distance from a melee hero",
        "surface fallback melee weapons without confusing them with the primary ranged plan",
    ),
    map_notes=(
        "open standard terrain with water and difficult terrain between a Barbarian and ranged enemies",
    ),
)

CONCENTRATION_CONTROL_CROSSROADS = ValidationArenaSpec(
    arena_id="concentration_control_crossroads",
    title="Concentration Control Crossroads",
    hero_role="level 5 sorcerer",
    tags=("concentration", "control", "friendly-fire", "hypnotic-pattern", "slow", "web", "support", "mixed-monsters"),
    expected_pressure=(
        "rank concentration control against direct damage when allies are near the target area",
        "keep friendly-fire and affected-entity metadata visible in affordance briefs",
        "exercise support/control spell mixes without relying on the generic Caster factory alone",
    ),
    map_notes=(
        "open crossroads with a frontline ally near the hero and backline control/support casters",
    ),
)

TELEPORT_ESCAPE_SKIRMISH = ValidationArenaSpec(
    arena_id="teleport_escape_skirmish",
    title="Teleport Escape Skirmish",
    hero_role="level 5 barbarian",
    tags=("teleport", "misty-step", "dimension-door", "ranged", "goblins", "escape", "gear-loadout"),
    expected_pressure=(
        "treat teleport and disengage-style repositioning as real survival options",
        "avoid walking fragile casters into melee when escape rows and ranged pressure exist",
        "keep ranged attackers productive while a melee hero crosses terrain",
    ),
    map_notes=(
        "open standard terrain with water and difficult terrain between a Barbarian and mobile ranged enemies",
    ),
)

DARKNESS_REVEAL_LABYRINTH = ValidationArenaSpec(
    arena_id="darkness_reveal_labyrinth",
    title="Darkness Reveal Labyrinth",
    hero_role="level 5 sorcerer",
    tags=("darkness", "fog-cloud", "invisibility", "see-invisibility", "daylight", "vision", "navigation"),
    expected_pressure=(
        "preserve subjective vision facts through darkness, fog, invisibility, and reveal tools",
        "separate unknown enemies from remembered enemies instead of chasing objective state",
        "value light and vision spells as information-changing actions",
    ),
    map_notes=(
        "dark multi-room arena with two doors, a darkness caster, and a reveal caster using existing spell implementations",
    ),
)

GUARDIAN_ZONE_SHRINE = ValidationArenaSpec(
    arena_id="guardian_zone_shrine",
    title="Guardian Zone Shrine",
    hero_role="level 5 shield fighter",
    tags=("guardian-of-faith", "spirit-guardians", "zone-control", "healing", "beacon-of-hope", "support", "summon-object"),
    expected_pressure=(
        "treat persistent guardian and aura-style spell zones as tactical map facts",
        "compare healing/support concentration against direct damage and movement",
        "avoid walking allies and enemies through dangerous controlled cells without reason",
    ),
    map_notes=(
        "open shrine-like center with a support caster, wounded guard, ranged escort, and persistent-zone spell access",
    ),
)

TRAP_LEVER_KILLZONE = ValidationArenaSpec(
    arena_id="trap_lever_killzone",
    title="Trap Lever Killzone",
    hero_role="level 5 barbarian",
    tags=("trap-lever", "environment-object", "hazards", "forced-movement", "object-interaction", "skeletons"),
    expected_pressure=(
        "treat trap levers as real nearby action affordances instead of map decoration",
        "compare hazard control against direct movement and attacks",
        "avoid moving through spike cells when an object interaction can change the battlefield",
    ),
    map_notes=(
        f"standard trap lever at {TRAP_LEVER_POSITION} beside active spike-zone cells",
        "open door with monsters already close enough to use or ignore the lever deliberately",
    ),
)

CONDITION_LOCK_SANCTUM = ValidationArenaSpec(
    arena_id="condition_lock_sanctum",
    title="Condition Lock Sanctum",
    hero_role="level 5 barbarian",
    tags=("conditions", "command", "hold-person", "fear", "hypnotic-pattern", "support", "concentration", "saves"),
    expected_pressure=(
        "rank disabling and debuff spells against direct damage when a melee hero is closing",
        "surface save-based condition outcomes and concentration risks in telemetry",
        "keep support/control casters from behaving like simple melee units",
    ),
    map_notes=(
        "open floor with a frontline guard screening condition and support casters",
    ),
)

NECROTIC_ANTI_HEALING_DUEL = ValidationArenaSpec(
    arena_id="necrotic_anti_healing_duel",
    title="Necrotic Anti-Healing Duel",
    hero_role="level 5 shield fighter",
    tags=("anti-healing", "necromancy", "high-level-spells", "conditions", "healing", "resource-economy"),
    expected_pressure=(
        "notice Chill Touch and other anti-healing/status choices beside raw burst spells",
        "compare Harm, Blight, Bestow Curse, and Finger of Death against ordinary attacks",
        "keep wounded-target and healing-resource facts visible to downstream policy",
    ),
    map_notes=(
        "open duel with a wounded shield fighter carrying healing while a necromancer has anti-heal and execution spells",
    ),
)

DAMAGE_AFFINITY_WEAPON_LAB = ValidationArenaSpec(
    arena_id="damage_affinity_weapon_lab",
    title="Damage Affinity Weapon Lab",
    hero_role="hero-side skeleton warrior",
    tags=("damage-affinity", "vulnerability", "weapon-choice", "skeletons", "fighter", "gear-loadout"),
    expected_pressure=(
        "surface target vulnerabilities in subjective entity facts",
        "surface weapon damage types in decision-epoch affordances",
        "prefer bludgeoning weapon pressure against a visible bludgeoning-vulnerable target",
    ),
    map_notes=(
        "open floor with a hero-side skeleton warrior and a monster fighter carrying both shortsword and club attacks",
    ),
)

RESISTANCE_WEAPON_COUNTERPLAY = ValidationArenaSpec(
    arena_id="resistance_weapon_counterplay",
    title="Resistance Weapon Counterplay",
    hero_role="level 5 resistant shield fighter",
    tags=("damage-affinity", "resistance", "vulnerability", "weapon-choice", "fighter", "gear-loadout"),
    expected_pressure=(
        "surface target resistances and vulnerabilities on a non-skeleton target",
        "compare weapon damage types against both positive and negative damage multipliers",
        "avoid hardcoding skeleton-specific bludgeoning logic into enemy weapon choice",
    ),
    map_notes=(
        "open duel with a shield fighter resistant to piercing but vulnerable to bludgeoning",
    ),
)

FIELD_CACHE_LOOT_RACE = ValidationArenaSpec(
    arena_id="field_cache_loot_race",
    title="Field Cache Loot Race",
    hero_role="level 5 archer fighter",
    tags=("items", "chest", "loot", "object-interaction", "resource-economy", "mixed-monsters", "ranged"),
    expected_pressure=(
        "notice usable map caches as nearby resource affordances, not only carried inventory",
        "compare looting a chest against immediate ranged pressure",
        "make post-loot consumable and item-spell rows visible in follow-up epochs",
    ),
    map_notes=(
        "open floor with an adjacent loot chest containing scrolls, an acid flask, a potion, and a weapon coat",
    ),
)

CLEANSE_SUPPORT_TRIAGE = ValidationArenaSpec(
    arena_id="cleanse_support_triage",
    title="Cleanse Support Triage",
    hero_role="level 5 shield fighter",
    tags=("support", "restoration", "conditions", "poisoned", "blinded", "healing", "resource-economy"),
    expected_pressure=(
        "surface restoration and healing spells when allies begin impaired",
        "separate support-target evaluation from enemy-target attack selection",
        "keep active conditions and wounded allies present in subjective summaries",
    ),
    map_notes=(
        "open floor with a support caster, a poisoned frontline ally, and a blinded ranged ally",
    ),
)

MULTI_TARGET_MISSILE_ALLOCATION = ValidationArenaSpec(
    arena_id="multi_target_missile_allocation",
    title="Multi-Target Missile Allocation",
    hero_role="level 5 sorcerer",
    tags=("multi-target", "magic-missile", "scorching-ray", "target-allocation", "wounded-targets", "caster"),
    expected_pressure=(
        "show multiple legal targets and projectile counts for multi-entity spells",
        "pressure policies that collapse every dart or ray into the first visible target",
        "compare guaranteed force damage against ordinary attack and area rows",
    ),
    map_notes=(
        "open floor with a Sorcerer facing several wounded, visible enemies at different hit point totals",
    ),
)

MULTI_PROJECTILE_NO_AOE_LAB = ValidationArenaSpec(
    arena_id="multi_projectile_no_aoe_lab",
    title="Multi-Projectile No-AoE Lab",
    hero_role="level 5 narrow-spell sorcerer",
    tags=("multi-target", "magic-missile", "scorching-ray", "target-allocation", "no-aoe", "wounded-targets", "caster"),
    expected_pressure=(
        "force projectile allocation without Fireball or Lightning Bolt dominating the choice",
        "show multiple wounded visible targets for Magic Missile and Scorching Ray rows",
        "separate projectile-count reasoning from area-template reasoning",
    ),
    map_notes=(
        "open floor with spread wounded enemies and a Sorcerer whose spell list excludes area damage",
    ),
)

REACTION_COUNTERSPELL_LAB = ValidationArenaSpec(
    arena_id="reaction_counterspell_lab",
    title="Reaction Counterspell Lab",
    hero_role="level 5 sorcerer",
    tags=("reaction", "counterspell", "shield", "spell-interrupt", "caster", "resource-economy"),
    expected_pressure=(
        "surface reaction handlers as part of enemy capability rather than only active-turn rows",
        "exercise Counterspell and Shield resource spend when high-value spells or attacks are attempted",
        "make interrupted command outcomes and reaction telemetry visible to controller review",
    ),
    map_notes=(
        "open caster duel with an abjurer carrying Counterspell and a shield mage with Shield reaction support",
    ),
)

GUARDIAN_CHOKE_BODY_BLOCK = ValidationArenaSpec(
    arena_id="guardian_choke_body_block",
    title="Guardian Choke Body Block",
    hero_role="level 5 barbarian",
    tags=("guardian-of-faith", "summon-object", "body-block", "chokepoint", "zone-control", "caster", "frontline"),
    expected_pressure=(
        "treat conjured persistent objects and allied bodies as map-shaping tactical facts",
        "compare Guardian of Faith, Spirit Guardians, and ordinary attacks in a narrow approach lane",
        "avoid evaluating movement only by distance when bodies and zones define the useful route",
    ),
    map_notes=(
        "open-door standard barrier with a frontline guard in the choke and a guardian caster behind it",
    ),
)

MULTI_OBJECT_CONTROL_ROOM = ValidationArenaSpec(
    arena_id="multi_object_control_room",
    title="Multi-Object Control Room",
    hero_role="level 5 archer fighter",
    tags=("multi-object", "environment-object", "object-interaction", "trap-lever", "chest", "torch", "fireball-cannon", "vision"),
    expected_pressure=(
        "show several nearby object actions in the same decision epoch without collapsing them into attacks",
        "compare lever, cache, cannon, and light-control actions against immediate combat pressure",
        "exercise local object-state tracking after one object interaction changes the room",
    ),
    map_notes=(
        "standard dark arena with adjacent lever, loot cache, wall torch, and Fireball cannon around the actor",
    ),
)

SRD_LOW_CR_PATROL = ValidationArenaSpec(
    arena_id="srd_low_cr_patrol",
    title="SRD Low-CR Patrol",
    hero_role="level 5 archer fighter",
    tags=("srd-roster", "low-cr", "mixed-monsters", "ranged", "beast", "support"),
    expected_pressure=(
        "compare many weak SRD bodies without overfitting to skeleton names",
        "keep ranged, melee, beast, and support roles distinct in one small encounter",
        "track low-CR bodies as real actors rather than dashboard noise",
    ),
    map_notes=(
        "open patrol spread with a bandit, guard, kobold, wolf, and acolyte sampling the SRD roster",
    ),
)

SRD_UNDEAD_CRYPT = ValidationArenaSpec(
    arena_id="srd_undead_crypt",
    title="SRD Undead Crypt",
    hero_role="level 5 shield fighter",
    tags=(
        "srd-roster",
        "undead",
        "skeletons",
        "darkvision",
        "condition-immunity",
        "bruiser",
    ),
    expected_pressure=(
        "exercise undead poison immunity and low-speed pursuit facts",
        "compare ghoul pressure against slow zombie bodies",
        "avoid assuming every undead encounter is the custom skeleton trio",
    ),
    map_notes=(
        "dark open crypt with zombie, ghoul, skeleton, and ogre-zombie pressure from different approach lanes",
    ),
)

SRD_GOBLINOID_WARBAND = ValidationArenaSpec(
    arena_id="srd_goblinoid_warband",
    title="SRD Goblinoid Warband",
    hero_role="level 5 barbarian",
    tags=("srd-roster", "goblinoid", "darkvision", "shield", "ranged", "bruiser"),
    expected_pressure=(
        "stress darkvision goblinoid roles without relying on the bespoke goblin factory",
        "compare shielded hobgoblin discipline against bugbear bruiser pressure",
        "avoid collapsing mixed melee-ranged warbands into a single chase policy",
    ),
    map_notes=(
        "open-door standard arena with kobold, hobgoblin, bugbear, and gnoll roles around terrain",
    ),
)

SRD_DIVINE_CULT_CELL = ValidationArenaSpec(
    arena_id="srd_divine_cult_cell",
    title="SRD Divine Cult Cell",
    hero_role="level 5 sorcerer",
    tags=("srd-roster", "cult", "support", "control", "healing", "items"),
    expected_pressure=(
        "rank cult control and priest support against direct attacks",
        "surface healing, sanctuary, hold person, and inflict wounds in one enemy side",
        "check concentration awareness across several support and control casters",
    ),
    map_notes=(
        "shrine-like open floor with a cult fanatic, priest, cultist, and guard around consumables",
    ),
)

SRD_ELITE_MERCENARY_CONTRACT = ValidationArenaSpec(
    arena_id="srd_elite_mercenary_contract",
    title="SRD Elite Mercenary Contract",
    hero_role="level 9 sorcerer",
    tags=("srd-roster", "elite", "heavy-armor", "counterspell", "mage", "leader"),
    expected_pressure=(
        "pit high-level spell resources against SRD elite martial and caster roles",
        "compare counterspell-capable mage pressure with knight and veteran durability",
        "avoid overfitting policy evaluation to level 5 baseline combat only",
    ),
    map_notes=(
        "open elite contract with knight, veteran, mage, and bandit captain using SRD-derived loadouts",
    ),
)

ARENA_SPECS: tuple[ValidationArenaSpec, ...] = (
    STANDARD_SKELETON_DOORS,
    GOBLIN_WATER_SKIRMISH,
    SKELETON_ANTI_AOE_SPLIT,
    CASTER_CROSSFIRE,
    ITEM_RESOURCE_GAUNTLET,
    DOUBLE_DOOR_DARK_HUNT,
    ARCANE_DEVICE_CONTROL,
    SKELETON_MARK_FOCUS_FIRE,
    BUFF_CONSUMABLE_AMBUSH,
    FORCED_MOVEMENT_HAZARD_BRIDGE,
    LINE_AOE_CORRIDOR,
    ZONE_CONTROL_WEB_GAUNTLET,
    SUPPORT_ATTRITION_CACHE,
    HIGH_LEVEL_SPELL_RESOURCE_DUEL,
    SORCERER_BARBARIAN_DUEL,
    CLASS_PARTY_MIRROR_SCRAMBLE,
    RANGED_LOADOUT_KITING_RING,
    CONCENTRATION_CONTROL_CROSSROADS,
    TELEPORT_ESCAPE_SKIRMISH,
    DARKNESS_REVEAL_LABYRINTH,
    GUARDIAN_ZONE_SHRINE,
    TRAP_LEVER_KILLZONE,
    CONDITION_LOCK_SANCTUM,
    NECROTIC_ANTI_HEALING_DUEL,
    DAMAGE_AFFINITY_WEAPON_LAB,
    RESISTANCE_WEAPON_COUNTERPLAY,
    FIELD_CACHE_LOOT_RACE,
    CLEANSE_SUPPORT_TRIAGE,
    MULTI_TARGET_MISSILE_ALLOCATION,
    MULTI_PROJECTILE_NO_AOE_LAB,
    REACTION_COUNTERSPELL_LAB,
    GUARDIAN_CHOKE_BODY_BLOCK,
    MULTI_OBJECT_CONTROL_ROOM,
    SRD_LOW_CR_PATROL,
    SRD_UNDEAD_CRYPT,
    SRD_GOBLINOID_WARBAND,
    SRD_DIVINE_CULT_CELL,
    SRD_ELITE_MERCENARY_CONTRACT,
)


def list_ai_validation_arena_specs() -> tuple[ValidationArenaSpec, ...]:
    """Return the ordered AI validation arena catalog.

    Returns:
        Stable arena specs in dashboard display order.
    """
    return ARENA_SPECS


def create_ai_validation_arena(
    arena_id: str,
    *,
    opening_faction: Optional[str] = None,
) -> ValidationArena:
    """Create an AI validation arena by stable id.

    Args:
        arena_id: Identifier from `list_ai_validation_arena_specs()`.
        opening_faction: Optional faction whose highest-initiative combatant
            opens the encounter while all initiative rolls remain unchanged.

    Returns:
        Constructed arena bundle.

    Raises:
        ValueError: If the arena id is unknown.
    """
    factories: dict[str, ArenaFactory] = {
        STANDARD_SKELETON_DOORS.arena_id: create_standard_skeleton_door_arena,
        GOBLIN_WATER_SKIRMISH.arena_id: create_goblin_water_skirmish_arena,
        SKELETON_ANTI_AOE_SPLIT.arena_id: create_skeleton_anti_aoe_split_arena,
        CASTER_CROSSFIRE.arena_id: create_caster_crossfire_arena,
        ITEM_RESOURCE_GAUNTLET.arena_id: create_item_resource_gauntlet_arena,
        DOUBLE_DOOR_DARK_HUNT.arena_id: create_double_door_dark_hunt_arena,
        ARCANE_DEVICE_CONTROL.arena_id: create_arcane_device_control_arena,
        SKELETON_MARK_FOCUS_FIRE.arena_id: create_skeleton_mark_focus_fire_arena,
        BUFF_CONSUMABLE_AMBUSH.arena_id: create_buff_consumable_ambush_arena,
        FORCED_MOVEMENT_HAZARD_BRIDGE.arena_id: create_forced_movement_hazard_bridge_arena,
        LINE_AOE_CORRIDOR.arena_id: create_line_aoe_corridor_arena,
        ZONE_CONTROL_WEB_GAUNTLET.arena_id: create_zone_control_web_gauntlet_arena,
        SUPPORT_ATTRITION_CACHE.arena_id: create_support_attrition_cache_arena,
        HIGH_LEVEL_SPELL_RESOURCE_DUEL.arena_id: create_high_level_spell_resource_duel_arena,
        SORCERER_BARBARIAN_DUEL.arena_id: create_sorcerer_barbarian_duel_arena,
        CLASS_PARTY_MIRROR_SCRAMBLE.arena_id: create_class_party_mirror_scramble_arena,
        RANGED_LOADOUT_KITING_RING.arena_id: create_ranged_loadout_kiting_ring_arena,
        CONCENTRATION_CONTROL_CROSSROADS.arena_id: create_concentration_control_crossroads_arena,
        TELEPORT_ESCAPE_SKIRMISH.arena_id: create_teleport_escape_skirmish_arena,
        DARKNESS_REVEAL_LABYRINTH.arena_id: create_darkness_reveal_labyrinth_arena,
        GUARDIAN_ZONE_SHRINE.arena_id: create_guardian_zone_shrine_arena,
        TRAP_LEVER_KILLZONE.arena_id: create_trap_lever_killzone_arena,
        CONDITION_LOCK_SANCTUM.arena_id: create_condition_lock_sanctum_arena,
        NECROTIC_ANTI_HEALING_DUEL.arena_id: create_necrotic_anti_healing_duel_arena,
        DAMAGE_AFFINITY_WEAPON_LAB.arena_id: create_damage_affinity_weapon_lab_arena,
        RESISTANCE_WEAPON_COUNTERPLAY.arena_id: create_resistance_weapon_counterplay_arena,
        FIELD_CACHE_LOOT_RACE.arena_id: create_field_cache_loot_race_arena,
        CLEANSE_SUPPORT_TRIAGE.arena_id: create_cleanse_support_triage_arena,
        MULTI_TARGET_MISSILE_ALLOCATION.arena_id: create_multi_target_missile_allocation_arena,
        MULTI_PROJECTILE_NO_AOE_LAB.arena_id: create_multi_projectile_no_aoe_lab_arena,
        REACTION_COUNTERSPELL_LAB.arena_id: create_reaction_counterspell_lab_arena,
        GUARDIAN_CHOKE_BODY_BLOCK.arena_id: create_guardian_choke_body_block_arena,
        MULTI_OBJECT_CONTROL_ROOM.arena_id: create_multi_object_control_room_arena,
        SRD_LOW_CR_PATROL.arena_id: create_srd_low_cr_patrol_arena,
        SRD_UNDEAD_CRYPT.arena_id: create_srd_undead_crypt_arena,
        SRD_GOBLINOID_WARBAND.arena_id: create_srd_goblinoid_warband_arena,
        SRD_DIVINE_CULT_CELL.arena_id: create_srd_divine_cult_cell_arena,
        SRD_ELITE_MERCENARY_CONTRACT.arena_id: create_srd_elite_mercenary_contract_arena,
    }
    factory = factories.get(arena_id)
    if factory is None:
        raise ValueError(f"Unknown AI validation arena: {arena_id}")
    token = _OPENING_FACTION.set(opening_faction)
    try:
        return factory()
    finally:
        _OPENING_FACTION.reset(token)


def reset_ai_validation_arena_state(width: int = ARENA_WIDTH, height: int = ARENA_HEIGHT) -> None:
    """Clear global engine state for a fresh validation arena.

    Args:
        width: Arena width in grid cells.
        height: Arena height in grid cells.
    """
    reset_engine_runtime(grid_size=(width, height))


def create_standard_skeleton_door_arena() -> ValidationArena:
    """Create the standard skeleton door baseline arena.

    Returns:
        Validation arena with the current skeleton trio behind the closed door.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    hero = _create_level_5_sorcerer("Validation Sorcerer", (2, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Skeleton Warrior", position=(12, 5), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Skeleton Archer", position=(12, 7), faction="monsters", darkvision=True),
        create_skeleton_warlock(name="Validation Skeleton Warlock", position=(12, 9), faction="monsters", darkvision=True),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Standard Skeleton Door",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=STANDARD_SKELETON_DOORS,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={"door": DOOR_POSITION, "hero_start": hero.position},
        environment=environment,
    )


def create_goblin_water_skirmish_arena() -> ValidationArena:
    """Create a mixed goblin skirmish around water and rough terrain.

    Returns:
        Validation arena with water blocking direct lanes between sides.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    hero = _create_level_5_archer_fighter("Validation Archer Fighter", (4, 1))
    goblin_archer = create_goblin_archer(name="Validation Goblin Archer", position=(1, 2), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    monsters = (
        create_goblin(name="Validation Goblin Skirmisher", position=(0, 1), faction="monsters"),
        goblin_archer,
        create_caster(name="Validation Goblin Caster", position=(0, 4), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Goblin Water Skirmish",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=GOBLIN_WATER_SKIRMISH,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "water_choke": WATER_POSITIONS[1],
            "difficult_band": DIFFICULT_TERRAIN_POSITIONS[0],
        },
        environment=environment,
    )


def create_skeleton_anti_aoe_split_arena() -> ValidationArena:
    """Create an open arena where skeletons begin deliberately split.

    Returns:
        Validation arena that should expose clustering regressions quickly.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Blast Sorcerer", (7, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Split Warrior", position=(2, 2), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Split Archer", position=(12, 2), faction="monsters", darkvision=True),
        create_skeleton_warlock(name="Validation Split Warlock", position=(12, 12), faction="monsters", darkvision=True),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Skeleton Anti-AoE Split",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SKELETON_ANTI_AOE_SPLIT,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "warrior_start": monsters[0].position,
            "archer_start": monsters[1].position,
            "warlock_start": monsters[2].position,
        },
    )


def create_caster_crossfire_arena() -> ValidationArena:
    """Create an open-door crossfire against a melee hero.

    Returns:
        Validation arena with a caster, archer, and frontline skeleton.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()
    hero = _create_level_5_barbarian("Validation Barbarian", (2, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Crossfire Guard", position=(8, 7), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Crossfire Archer", position=(12, 6), faction="monsters", darkvision=True),
        create_caster(name="Validation Crossfire Mage", position=(12, 8), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Caster Crossfire",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=CASTER_CROSSFIRE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "spike_zone_sample": next(iter(SPIKE_ZONE_POSITIONS)),
        },
        environment=environment,
    )


def create_item_resource_gauntlet_arena() -> ValidationArena:
    """Create an open mixed-role arena with heavy inventory pressure.

    Returns:
        Validation arena that exposes scroll, wand, potion, and weapon-coat
        affordances alongside ordinary weapon attacks.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_archer_fighter("Validation Item Fighter", (2, 7))
    _give_item_gauntlet_loadout(hero)
    goblin_archer = create_goblin_archer(name="Validation Cache Goblin Archer", position=(11, 4), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    monsters = (
        create_skeleton_warrior(name="Validation Cache Guard", position=(10, 7), faction="monsters", darkvision=True),
        goblin_archer,
        create_caster(name="Validation Cache Mage", position=(12, 10), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Item Resource Gauntlet",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=ITEM_RESOURCE_GAUNTLET,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={"hero_start": hero.position, "frontline_start": monsters[0].position},
    )


def create_double_door_dark_hunt_arena() -> ValidationArena:
    """Create a dark three-room arena with two independent closed doors.

    Returns:
        Validation arena that pressures object navigation without visible enemies.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    create_standard_arena_floor(grid)
    first_barrier = _place_validation_directional_barrier(grid, column=5, door_y=7, label="First")
    second_barrier = _place_validation_directional_barrier(grid, column=9, door_y=7, label="Second")
    darken_arena(grid)

    hero = _create_level_5_barbarian("Validation Door Barbarian", (2, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Door Guard", position=(12, 6), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Door Archer", position=(12, 8), faction="monsters", darkvision=True),
        create_skeleton_warlock(name="Validation Door Warlock", position=(11, 7), faction="monsters", darkvision=True),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Double Door Dark Hunt",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=DOUBLE_DOOR_DARK_HUNT,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "first_door": grid.get_object_position(first_barrier.door.uuid) or (5, 7),
            "second_door": grid.get_object_position(second_barrier.door.uuid) or (9, 7),
        },
    )


def create_arcane_device_control_arena() -> ValidationArena:
    """Create an arena centered on a usable environmental spell device.

    Returns:
        Validation arena with a central Fireball cannon and mixed monsters.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    create_standard_arena_floor(grid)
    cannon = create_fireball_cannon(uuid4(), position=(7, 7), charges=2)
    potion = create_healing_potion(uuid4(), heal_amount=12)
    potion.place_on_grid((6, 7))

    hero = _create_level_5_sorcerer("Validation Device Sorcerer", (3, 7))
    monsters = (
        create_goblin(name="Validation Device Skirmisher", position=(10, 6), faction="monsters"),
        create_skeleton_archer(name="Validation Device Archer", position=(11, 8), faction="monsters", darkvision=True),
        create_caster(name="Validation Device Mage", position=(12, 7), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Arcane Device Control",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=ARCANE_DEVICE_CONTROL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "fireball_cannon": grid.get_object_position(cannon.uuid) or (7, 7),
            "floor_potion": grid.get_object_position(potion.uuid) or (6, 7),
        },
    )


def create_skeleton_mark_focus_fire_arena() -> ValidationArena:
    """Create an arena around skeleton support and focus-fire pressure.

    Returns:
        Validation arena with a high-AC Fighter facing a marked-target skeleton
        package.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Shield Fighter", (6, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Focus Guard", position=(9, 7), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Focus Archer", position=(11, 6), faction="monsters", darkvision=True),
        create_skeleton_warlock(name="Validation Focus Warlock", position=(11, 8), faction="monsters", darkvision=True),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Skeleton Mark Focus Fire",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SKELETON_MARK_FOCUS_FIRE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "guard_start": monsters[0].position,
            "archer_start": monsters[1].position,
            "warlock_start": monsters[2].position,
        },
    )


def create_buff_consumable_ambush_arena() -> ValidationArena:
    """Create an arena that puts monster-side buffs and consumables in play.

    Returns:
        Validation arena with mixed monsters carrying self-buff and scroll
        resources.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Ambush Barbarian", (2, 7))
    ambush_mage = create_caster(name="Validation Ambush Mage", position=(12, 7), faction="monsters", level=5)
    ambush_mage.loot_item(create_scroll_of_hold_person(ambush_mage.uuid))
    goblin_archer = create_goblin_archer(name="Validation Ambush Goblin Archer", position=(10, 5), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    goblin_archer.loot_item(create_potion_of_haste(goblin_archer.uuid))
    guard = create_skeleton_warrior(name="Validation Ambush Guard", position=(10, 9), faction="monsters", darkvision=True)
    guard.loot_item(create_potion_of_greater_invisibility(guard.uuid))
    monsters = (guard, goblin_archer, ambush_mage)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Buff Consumable Ambush",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=BUFF_CONSUMABLE_AMBUSH,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "mage_start": ambush_mage.position,
        },
        environment=environment,
    )


def create_forced_movement_hazard_bridge_arena() -> ValidationArena:
    """Create an arena that places forced movement next to hazard terrain.

    Returns:
        Validation arena with Thunderwave-capable monsters near water and spikes.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Hazard Barbarian", (4, 10))
    monsters = (
        create_skeleton_warlock(name="Validation Hazard Warlock", position=(6, 10), faction="monsters", darkvision=True),
        create_caster(name="Validation Hazard Mage", position=(10, 7), faction="monsters", level=5),
        create_skeleton_archer(name="Validation Hazard Archer", position=(11, 9), faction="monsters", darkvision=True),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Forced Movement Hazard Bridge",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=FORCED_MOVEMENT_HAZARD_BRIDGE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "warlock_start": monsters[0].position,
            "spike_zone_sample": next(iter(SPIKE_ZONE_POSITIONS)),
            "water_choke": WATER_POSITIONS[1],
        },
        environment=environment,
    )


def create_line_aoe_corridor_arena() -> ValidationArena:
    """Create an arena that makes line and multi-target spell geometry obvious.

    Returns:
        Validation arena with multiple actors aligned on a corridor-like lane.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Line Sorcerer", (2, 7))
    monsters = (
        create_skeleton_warrior(name="Validation Line Guard", position=(8, 7), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Line Archer", position=(10, 7), faction="monsters", darkvision=True),
        create_caster(name="Validation Line Mage", position=(12, 7), faction="monsters", level=5),
        create_goblin(name="Validation Off-Line Goblin", position=(10, 9), faction="monsters"),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Line AoE Corridor",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=LINE_AOE_CORRIDOR,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "line_lane_y": (hero.position[0], hero.position[1]),
            "off_line_monster": monsters[3].position,
        },
    )


def create_zone_control_web_gauntlet_arena() -> ValidationArena:
    """Create an arena that pressures pathing through control spell options.

    Returns:
        Validation arena with a control caster, skirmisher, and frontline guard.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Web Barbarian", (3, 7))
    control_mage = create_caster(name="Validation Web Mage", position=(11, 7), faction="monsters", level=5)
    register_spells_by_name(control_mage, ["Web", "Grease", "Spike Growth", "Fog Cloud"], caster_level=5)
    goblin_archer = create_goblin_archer(name="Validation Web Goblin Archer", position=(10, 5), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    monsters = (
        create_skeleton_warrior(name="Validation Web Guard", position=(8, 7), faction="monsters", darkvision=True),
        goblin_archer,
        control_mage,
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Zone Control Web Gauntlet",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=ZONE_CONTROL_WEB_GAUNTLET,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "control_mage_start": control_mage.position,
            "water_choke": WATER_POSITIONS[1],
        },
        environment=environment,
    )


def create_support_attrition_cache_arena() -> ValidationArena:
    """Create an arena where support and healing rows are intentionally useful.

    Returns:
        Validation arena with a wounded guard and a support caster carrying
        healing and weapon-buff items.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Attrition Fighter", (5, 7))
    wounded_guard = create_skeleton_warrior(name="Validation Wounded Guard", position=(8, 7), faction="monsters", darkvision=True)
    wounded_guard.health.take_damage(10, DamageType.SLASHING, hero.uuid)
    support_caster = create_caster(
        name="Validation Support Acolyte",
        position=(11, 7),
        faction="monsters",
        level=5,
        wardrobe="divine",
    )
    register_spells_by_name(
        support_caster,
        ["Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"],
        caster_level=5,
    )
    support_caster.loot_item(create_healing_potion(support_caster.uuid, heal_amount=14))
    support_caster.loot_item(create_lightning_weapon_coat(support_caster.uuid))
    archer = create_skeleton_archer(name="Validation Attrition Archer", position=(10, 5), faction="monsters", darkvision=True)
    monsters = (wounded_guard, archer, support_caster)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Support Attrition Cache",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SUPPORT_ATTRITION_CACHE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "wounded_guard_start": wounded_guard.position,
            "support_start": support_caster.position,
        },
    )


def create_high_level_spell_resource_duel_arena() -> ValidationArena:
    """Create an arena that samples higher-slot spell and reaction pressure.

    Returns:
        Validation arena with level 9 spell lists on both sides.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_9_sorcerer("Validation Duel Sorcerer", (3, 7))
    archmage = create_caster(name="Validation Duel Archmage", position=(11, 7), faction="monsters", level=9)
    register_spells_by_name(
        archmage,
        ["Cone of Cold", "Cloudkill", "Hypnotic Pattern", "Slow", "Banishment", "Dimension Door"],
        caster_level=9,
    )
    monsters = (
        create_skeleton_warrior(name="Validation Duel Guard", position=(8, 7), faction="monsters", darkvision=True),
        create_goblin_archer(name="Validation Duel Skirmisher", position=(10, 5), faction="monsters"),
        archmage,
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: High-Level Spell Resource Duel",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=HIGH_LEVEL_SPELL_RESOURCE_DUEL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "archmage_start": archmage.position,
            "frontline_start": monsters[0].position,
        },
    )


def create_sorcerer_barbarian_duel_arena() -> ValidationArena:
    """Create a compact class duel between control magic and melee pressure.

    Returns:
        Validation arena with a level 5 Sorcerer and one level 5 Berserker
        Barbarian built from the real class factories.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Duel Sorcerer", (3, 7))
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Validation Duel Barbarian",
            position=(11, 7),
            faction="monsters",
            primal_path=PrimalPathChoice.BERSERKER,
            equipment_preset="greataxe",
            asi_4=[("strength", 2)],
        )
    )
    monsters = (barbarian,)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Sorcerer Barbarian Duel",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SORCERER_BARBARIAN_DUEL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "barbarian_start": barbarian.position,
        },
    )


def create_class_party_mirror_scramble_arena() -> ValidationArena:
    """Create an enemy-side party from real class factories.

    Returns:
        Validation arena with Fighter, Barbarian, and Sorcerer monster-side
        class kits instead of bespoke monster factories.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Mirror Shield Fighter", (5, 7))
    enemy_barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Validation Mirror Berserker",
            position=(8, 7),
            faction="monsters",
            primal_path=PrimalPathChoice.BERSERKER,
            equipment_preset="dual_axes",
            asi_4=[("strength", 2)],
        )
    )
    enemy_archer = create_fighter(
        FighterConfig(
            level=5,
            name="Validation Mirror Archer",
            position=(11, 5),
            faction="monsters",
            fighting_style="archery",
            equipment_preset="archery",
            asi_4=[("dexterity", 2)],
        )
    )
    enemy_sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Validation Mirror Sorcerer",
            position=(11, 9),
            faction="monsters",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Magic Missile",
                "Scorching Ray",
                "Hold Person",
                "Haste",
                "Slow",
                "Fireball",
                "Lightning Bolt",
            ],
        )
    )
    monsters = (enemy_barbarian, enemy_archer, enemy_sorcerer)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Class Party Mirror Scramble",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=CLASS_PARTY_MIRROR_SCRAMBLE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "barbarian_start": enemy_barbarian.position,
            "archer_start": enemy_archer.position,
            "sorcerer_start": enemy_sorcerer.position,
        },
    )


def create_ranged_loadout_kiting_ring_arena() -> ValidationArena:
    """Create a ranged-heavy enemy side around terrain blockers.

    Returns:
        Validation arena that punishes policies which walk ranged enemies into
        melee while legal ranged attacks exist.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Kiting Barbarian", (3, 7))
    archer_captain = create_fighter(
        FighterConfig(
            level=5,
            name="Validation Kiting Archer Captain",
            position=(11, 7),
            faction="monsters",
            fighting_style="archery",
            equipment_preset="archery",
            asi_4=[("dexterity", 2)],
        )
    )
    goblin_archer = create_goblin_archer(name="Validation Kiting Goblin Archer", position=(12, 5), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    support_warlock = create_skeleton_warlock(
        name="Validation Kiting Warlock",
        position=(12, 9),
        faction="monsters",
        darkvision=True,
    )
    monsters = (archer_captain, goblin_archer, support_warlock)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Ranged Loadout Kiting Ring",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=RANGED_LOADOUT_KITING_RING,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "archer_start": archer_captain.position,
            "water_choke": WATER_POSITIONS[1],
            "difficult_band": DIFFICULT_TERRAIN_POSITIONS[0],
        },
        environment=environment,
    )


def create_concentration_control_crossroads_arena() -> ValidationArena:
    """Create a mixed support/control arena with friendly-fire pressure.

    Returns:
        Validation arena where concentration control spells are legal but must
        be compared against ally positioning and support alternatives.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Crossroads Sorcerer", (4, 7))
    guard = create_skeleton_warrior(name="Validation Crossroads Guard", position=(7, 7), faction="monsters", darkvision=True)
    control_sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Validation Crossroads Controller",
            position=(11, 7),
            faction="monsters",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Magic Missile",
                "Hold Person",
                "Web",
                "Hypnotic Pattern",
                "Slow",
                "Fireball",
            ],
        )
    )
    support_caster = create_caster(
        name="Validation Crossroads Support",
        position=(10, 5),
        faction="monsters",
        level=5,
        wardrobe="divine",
    )
    register_spells_by_name(
        support_caster,
        ["Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"],
        caster_level=5,
    )
    monsters = (guard, control_sorcerer, support_caster)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Concentration Control Crossroads",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=CONCENTRATION_CONTROL_CROSSROADS,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "guard_start": guard.position,
            "controller_start": control_sorcerer.position,
            "support_start": support_caster.position,
        },
    )


def create_teleport_escape_skirmish_arena() -> ValidationArena:
    """Create a ranged skirmish with teleport and escape pressure.

    Returns:
        Validation arena where a mobile caster and ranged escorts should prefer
        escape, range, and terrain-aware pressure over walking into melee.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Escape Barbarian", (3, 7))
    escape_mage = create_caster(name="Validation Escape Mage", position=(11, 7), faction="monsters", level=7)
    register_spells_by_name(
        escape_mage,
        ["Misty Step", "Dimension Door", "Blur", "Mirror Image", "Ray of Frost"],
        caster_level=7,
    )
    goblin_archer = create_goblin_archer(name="Validation Escape Goblin Archer", position=(12, 5), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    guard = create_skeleton_warrior(name="Validation Escape Guard", position=(9, 8), faction="monsters", darkvision=True)
    monsters = (guard, goblin_archer, escape_mage)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Teleport Escape Skirmish",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=TELEPORT_ESCAPE_SKIRMISH,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "escape_mage_start": escape_mage.position,
            "water_choke": WATER_POSITIONS[1],
            "difficult_band": DIFFICULT_TERRAIN_POSITIONS[0],
        },
        environment=environment,
    )


def create_darkness_reveal_labyrinth_arena() -> ValidationArena:
    """Create a dark multi-room arena around vision-changing spells.

    Returns:
        Validation arena that pressures subjective observation handling for
        darkness, fog, invisibility, reveal spells, and door navigation.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    create_standard_arena_floor(grid)
    first_barrier = _place_validation_directional_barrier(grid, column=5, door_y=6, label="Shadow")
    second_barrier = _place_validation_directional_barrier(grid, column=9, door_y=8, label="Dawn")
    darken_arena(grid)

    hero = _create_level_5_sorcerer("Validation Reveal Sorcerer", (2, 7))
    shadow_mage = create_caster(
        name="Validation Shadow Mage",
        position=(11, 6),
        faction="monsters",
        level=7,
        wardrobe="dark",
    )
    register_spells_by_name(
        shadow_mage,
        ["Darkness", "Fog Cloud", "Invisibility", "Greater Invisibility", "Silence"],
        caster_level=7,
    )
    reveal_mage = create_caster(
        name="Validation Reveal Mage",
        position=(12, 9),
        faction="monsters",
        level=11,
        wardrobe="divine",
    )
    register_spells_by_name(
        reveal_mage,
        ["See Invisibility", "Daylight", "Darkvision", "Light", "True Seeing"],
        caster_level=11,
    )
    scout = create_goblin_archer(name="Validation Shadow Scout", position=(10, 4), faction="monsters")
    register_goblin_nimble_escape(scout)
    monsters = (shadow_mage, reveal_mage, scout)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Darkness Reveal Labyrinth",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=DARKNESS_REVEAL_LABYRINTH,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "first_door": grid.get_object_position(first_barrier.door.uuid) or (5, 6),
            "second_door": grid.get_object_position(second_barrier.door.uuid) or (9, 8),
            "shadow_mage_start": shadow_mage.position,
            "reveal_mage_start": reveal_mage.position,
        },
    )


def create_guardian_zone_shrine_arena() -> ValidationArena:
    """Create a support shrine with persistent zone and healing pressure.

    Returns:
        Validation arena where support and persistent-zone spells should be
        visible to enemy policy beside ordinary attacks.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Shrine Fighter", (5, 7))
    wounded_guard = create_skeleton_warrior(name="Validation Shrine Wounded Guard", position=(8, 7), faction="monsters", darkvision=True)
    wounded_guard.health.take_damage(12, DamageType.BLUDGEONING, hero.uuid)
    shrine_keeper = create_caster(
        name="Validation Shrine Keeper",
        position=(11, 7),
        faction="monsters",
        level=9,
        wardrobe="divine",
    )
    register_spells_by_name(
        shrine_keeper,
        [
            "Spirit Guardians",
            "Guardian of Faith",
            "Beacon of Hope",
            "Mass Healing Word",
            "Flame Strike",
            "Sanctuary",
        ],
        caster_level=9,
    )
    archer = create_skeleton_archer(name="Validation Shrine Archer", position=(10, 5), faction="monsters", darkvision=True)
    monsters = (wounded_guard, archer, shrine_keeper)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Guardian Zone Shrine",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=GUARDIAN_ZONE_SHRINE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "wounded_guard_start": wounded_guard.position,
            "shrine_keeper_start": shrine_keeper.position,
            "shrine_center": (9, 7),
        },
    )


def create_trap_lever_killzone_arena() -> ValidationArena:
    """Create an arena where trap control is immediately actionable.

    Returns:
        Validation arena where nearby monsters can pull the standard trap lever
        instead of treating hazard control as unreachable map flavor.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Lever Barbarian", (3, 10))
    lever_guard = create_skeleton_warrior(name="Validation Lever Guard", position=(5, 11), faction="monsters", darkvision=True)
    hazard_warlock = create_skeleton_warlock(name="Validation Lever Warlock", position=(8, 11), faction="monsters", darkvision=True)
    goblin_archer = create_goblin_archer(name="Validation Lever Goblin Archer", position=(10, 9), faction="monsters")
    register_goblin_nimble_escape(goblin_archer)
    monsters = (lever_guard, hazard_warlock, goblin_archer)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Trap Lever Killzone",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=TRAP_LEVER_KILLZONE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "trap_lever": TRAP_LEVER_POSITION,
            "lever_guard_start": lever_guard.position,
            "spike_zone_sample": next(iter(SPIKE_ZONE_POSITIONS)),
        },
        environment=environment,
    )


def create_condition_lock_sanctum_arena() -> ValidationArena:
    """Create an arena around condition and support spell prioritization.

    Returns:
        Validation arena where enemy casters have real disabling, debuff, and
        support actions available beside ordinary attacks.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_barbarian("Validation Lock Barbarian", (4, 7))
    guard = create_skeleton_warrior(name="Validation Lock Guard", position=(8, 7), faction="monsters", darkvision=True)
    controller = create_sorcerer(
        SorcererConfig(
            level=7,
            name="Validation Lock Controller",
            position=(11, 7),
            faction="monsters",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Command",
                "Hold Person",
                "Fear",
                "Hypnotic Pattern",
                "Slow",
                "Banishment",
            ],
        )
    )
    support_caster = create_caster(
        name="Validation Lock Support",
        position=(10, 5),
        faction="monsters",
        level=5,
        wardrobe="divine",
    )
    register_spells_by_name(
        support_caster,
        ["Bless", "Bane", "Guiding Bolt", "Shield of Faith", "Sanctuary"],
        caster_level=5,
    )
    monsters = (guard, controller, support_caster)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Condition Lock Sanctum",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=CONDITION_LOCK_SANCTUM,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "guard_start": guard.position,
            "controller_start": controller.position,
            "support_start": support_caster.position,
        },
    )


def create_necrotic_anti_healing_duel_arena() -> ValidationArena:
    """Create an arena around anti-healing and necromancy pressure.

    Returns:
        Validation arena where a necromancer side can combine anti-healing,
        curses, burst damage, and ordinary escorts against a wounded hero.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Anti-Heal Fighter", (5, 7))
    hero.health.take_damage(8, DamageType.NECROTIC, uuid4())
    hero.loot_item(create_healing_potion(hero.uuid, heal_amount=14))

    guard = create_skeleton_warrior(name="Validation Necrotic Guard", position=(8, 7), faction="monsters", darkvision=True)
    archer = create_skeleton_archer(name="Validation Necrotic Archer", position=(10, 5), faction="monsters", darkvision=True)
    necromancer = create_caster(
        name="Validation Necromancer",
        position=(11, 7),
        faction="monsters",
        level=13,
        wardrobe="necromancer",
    )
    register_spells_by_name(
        necromancer,
        ["Chill Touch", "Blindness/Deafness", "Bestow Curse", "Blight", "Harm", "Finger of Death"],
        caster_level=13,
    )
    monsters = (guard, archer, necromancer)
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Necrotic Anti-Healing Duel",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=NECROTIC_ANTI_HEALING_DUEL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "guard_start": guard.position,
            "archer_start": archer.position,
            "necromancer_start": necromancer.position,
        },
    )


def create_damage_affinity_weapon_lab_arena() -> ValidationArena:
    """Create an arena that makes damage-type fit immediately observable.

    Returns:
        Validation arena where a monster-side Fighter can choose between
        piercing and bludgeoning melee attacks against a skeleton hero.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())

    hero = create_skeleton_warrior(
        name="Validation Vulnerable Skeleton Hero",
        position=(6, 7),
        faction="heroes",
        darkvision=True,
    )
    crusher = create_fighter(
        FighterConfig(
            level=5,
            name="Validation Crusher Captain",
            position=(7, 7),
            faction="monsters",
            fighting_style="two_weapon",
            equipment_preset="dual_wield",
            asi_4=[("strength", 2)],
        )
    )
    crusher.equipment.unequip(WeaponSlot.MELEE_MAIN)
    crusher.equipment.unequip(WeaponSlot.MELEE_OFF)
    crusher.equipment.equip(create_shortsword(crusher.uuid), WeaponSlot.MELEE_MAIN)
    crusher.equipment.equip(create_club(crusher.uuid), WeaponSlot.MELEE_OFF)

    monsters = (
        crusher,
        create_skeleton_archer(name="Validation Affinity Archer", position=(10, 5), faction="monsters", darkvision=True),
        create_caster(name="Validation Affinity Mage", position=(11, 8), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Damage Affinity Weapon Lab",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=DAMAGE_AFFINITY_WEAPON_LAB,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "crusher_start": crusher.position,
            "archer_start": monsters[1].position,
            "mage_start": monsters[2].position,
        },
    )


def create_resistance_weapon_counterplay_arena() -> ValidationArena:
    """Create a non-skeleton weapon-choice arena with mixed damage multipliers.

    Returns:
        Validation arena where a monster-side Fighter can compare piercing and
        bludgeoning attacks against a resistant shield Fighter.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())

    hero = _create_level_5_shield_fighter("Validation Resistant Duelist", (6, 7))
    _add_static_damage_affinity(
        hero,
        ResistanceStatus.RESISTANCE,
        DamageType.PIERCING,
        "Validation Piercing Resistance",
    )
    _add_static_damage_affinity(
        hero,
        ResistanceStatus.VULNERABILITY,
        DamageType.BLUDGEONING,
        "Validation Bludgeoning Vulnerability",
    )

    counter_fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Validation Counterplay Captain",
            position=(7, 7),
            faction="monsters",
            fighting_style="two_weapon",
            equipment_preset="dual_wield",
            asi_4=[("strength", 2)],
        )
    )
    counter_fighter.equipment.unequip(WeaponSlot.MELEE_MAIN)
    counter_fighter.equipment.unequip(WeaponSlot.MELEE_OFF)
    counter_fighter.equipment.equip(create_shortsword(counter_fighter.uuid), WeaponSlot.MELEE_MAIN)
    counter_fighter.equipment.equip(create_club(counter_fighter.uuid), WeaponSlot.MELEE_OFF)

    monsters = (
        counter_fighter,
        create_goblin_archer(name="Validation Counterplay Harrier", position=(10, 5), faction="monsters"),
        create_caster(name="Validation Counterplay Mage", position=(11, 8), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Resistance Weapon Counterplay",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=RESISTANCE_WEAPON_COUNTERPLAY,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "counter_fighter_start": counter_fighter.position,
            "harrier_start": monsters[1].position,
            "mage_start": monsters[2].position,
        },
    )


def create_field_cache_loot_race_arena() -> ValidationArena:
    """Create an arena that makes nearby loot a live decision surface.

    Returns:
        Validation arena with an adjacent chest whose contents become usable
        only after the actor spends an object interaction to loot it.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    create_standard_arena_floor(grid)

    hero = _create_level_5_archer_fighter("Validation Cache Runner", (4, 7))
    chest = StorageChest(
        source_entity_uuid=uuid4(),
        name="Validation Field Cache",
        use_action_templates=[LootAllAction(source_entity_uuid=uuid4(), template=True)],
    )
    chest.chest_inventory.add_item(create_scroll_of_fireball(chest.uuid))
    chest.chest_inventory.add_item(create_scroll_of_magic_missile(chest.uuid))
    chest.chest_inventory.add_item(create_acid_flask(chest.uuid))
    chest.chest_inventory.add_item(create_healing_potion(chest.uuid, heal_amount=14))
    chest.chest_inventory.add_item(create_weapon_coat(chest.uuid))
    chest.place_on_grid((5, 7))

    monsters = (
        create_skeleton_warrior(name="Validation Cache Bruiser", position=(9, 7), faction="monsters", darkvision=True),
        create_goblin_archer(name="Validation Cache Harrier", position=(11, 5), faction="monsters"),
        create_caster(name="Validation Cache Pressure Mage", position=(12, 8), faction="monsters", level=5),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Field Cache Loot Race",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=FIELD_CACHE_LOOT_RACE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "field_cache": grid.get_object_position(chest.uuid) or (5, 7),
            "frontline_start": monsters[0].position,
        },
    )


def create_cleanse_support_triage_arena() -> ValidationArena:
    """Create an arena where support turns have obvious injured allies.

    Returns:
        Validation arena with a poisoned frontline ally, a blinded ranged ally,
        and a support caster that can heal or restore them.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_shield_fighter("Validation Triage Fighter", (5, 7))

    wounded_guard = create_skeleton_warrior(name="Validation Poisoned Guard", position=(8, 7), faction="monsters", darkvision=True)
    wounded_guard.health.take_damage(10, DamageType.SLASHING, hero.uuid)
    wounded_guard.add_condition(Poisoned(source_entity_uuid=hero.uuid, target_entity_uuid=wounded_guard.uuid))

    blinded_archer = create_skeleton_archer(name="Validation Blinded Archer", position=(10, 5), faction="monsters", darkvision=True)
    blinded_archer.add_condition(Blinded(source_entity_uuid=hero.uuid, target_entity_uuid=blinded_archer.uuid))

    support_caster = create_caster(
        name="Validation Restoration Acolyte",
        position=(11, 7),
        faction="monsters",
        level=9,
        wardrobe="divine",
    )
    register_spells_by_name(
        support_caster,
        [
            "Lesser Restoration",
            "Greater Restoration",
            "Cure Wounds",
            "Healing Word",
            "Mass Healing Word",
            "Bless",
            "Aid",
        ],
        caster_level=9,
    )
    monsters = (wounded_guard, blinded_archer, support_caster)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Cleanse Support Triage",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=CLEANSE_SUPPORT_TRIAGE,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "wounded_guard_start": wounded_guard.position,
            "blinded_archer_start": blinded_archer.position,
            "support_start": support_caster.position,
        },
    )


def create_multi_target_missile_allocation_arena() -> ValidationArena:
    """Create an arena that exposes multi-entity spell targeting metadata.

    Returns:
        Validation arena where a Sorcerer has several visible, wounded enemies
        and multi-projectile spells are legal immediately.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Missile Sorcerer", (4, 7))

    wounded_warrior = create_skeleton_warrior(name="Validation Missile Warrior", position=(8, 7), faction="monsters", darkvision=True)
    wounded_warrior.health.take_damage(15, DamageType.FORCE, hero.uuid)
    wounded_archer = create_skeleton_archer(name="Validation Missile Archer", position=(10, 6), faction="monsters", darkvision=True)
    wounded_archer.health.take_damage(10, DamageType.FORCE, hero.uuid)
    wounded_goblin = create_goblin(name="Validation Missile Goblin", position=(10, 8), faction="monsters")
    wounded_goblin.health.take_damage(4, DamageType.FORCE, hero.uuid)
    monsters = (wounded_warrior, wounded_archer, wounded_goblin)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Multi-Target Missile Allocation",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=MULTI_TARGET_MISSILE_ALLOCATION,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "warrior_start": wounded_warrior.position,
            "archer_start": wounded_archer.position,
            "goblin_start": wounded_goblin.position,
        },
    )


def create_multi_projectile_no_aoe_lab_arena() -> ValidationArena:
    """Create a projectile-allocation arena without area damage spells.

    Returns:
        Validation arena where Magic Missile and Scorching Ray are the main
        multi-target spell affordances instead of Fireball or Lightning Bolt.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Validation Projectile Sorcerer",
            position=(4, 7),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Magic Missile",
                "Scorching Ray",
            ],
        )
    )
    _give_lit_torch(hero)

    wounded_warrior = create_skeleton_warrior(name="Validation Projectile Warrior", position=(8, 3), faction="monsters", darkvision=True)
    wounded_warrior.health.take_damage(28, DamageType.FORCE, hero.uuid)
    wounded_archer = create_skeleton_archer(name="Validation Projectile Archer", position=(10, 7), faction="monsters", darkvision=True)
    wounded_archer.health.take_damage(22, DamageType.FORCE, hero.uuid)
    wounded_goblin = create_goblin(name="Validation Projectile Goblin", position=(8, 11), faction="monsters")
    wounded_goblin.health.take_damage(7, DamageType.FORCE, hero.uuid)
    monsters = (wounded_warrior, wounded_archer, wounded_goblin)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Multi-Projectile No-AoE Lab",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=MULTI_PROJECTILE_NO_AOE_LAB,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "warrior_start": wounded_warrior.position,
            "archer_start": wounded_archer.position,
            "goblin_start": wounded_goblin.position,
        },
    )


def create_reaction_counterspell_lab_arena() -> ValidationArena:
    """Create an arena that makes reaction-based spell defense observable.

    Returns:
        Validation arena with Counterspell and Shield reaction handlers on the
        monster side, plus visible spells that can trigger those handlers.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())

    hero = _create_level_5_sorcerer("Validation Counterspell Sorcerer", (4, 7))
    register_counterspell_reaction(hero)

    abjurer = create_caster(name="Validation Counterspell Abjurer", position=(10, 7), faction="monsters", level=7)
    register_spells_by_name(
        abjurer,
        ["Magic Missile", "Fireball", "Lightning Bolt", "Greater Invisibility"],
        caster_level=7,
    )
    register_counterspell_reaction(abjurer)

    shield_mage = create_caster(name="Validation Shield Mage", position=(11, 5), faction="monsters", level=5)
    register_spells_by_name(
        shield_mage,
        ["Magic Missile", "Scorching Ray", "Mirror Image", "Blur"],
        caster_level=5,
    )
    register_shield_reaction(shield_mage)

    guard = create_skeleton_warrior(name="Validation Counterspell Guard", position=(8, 7), faction="monsters", darkvision=True)
    monsters = (guard, abjurer, shield_mage)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Reaction Counterspell Lab",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=REACTION_COUNTERSPELL_LAB,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "guard_start": guard.position,
            "abjurer_start": abjurer.position,
            "shield_mage_start": shield_mage.position,
        },
    )


def create_guardian_choke_body_block_arena() -> ValidationArena:
    """Create a choke-point arena around bodies and persistent zone objects.

    Returns:
        Validation arena with an enemy guard screening a Guardian of Faith
        caster behind the standard open doorway.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_barbarian("Validation Choke Barbarian", (3, 7))
    guard = create_skeleton_warrior(name="Validation Choke Guard", position=(7, 7), faction="monsters", darkvision=True)
    guardian_caster = create_caster(
        name="Validation Guardian Caster",
        position=(10, 7),
        faction="monsters",
        level=9,
        wardrobe="divine",
    )
    register_spells_by_name(
        guardian_caster,
        ["Guardian of Faith", "Spirit Guardians", "Sanctuary", "Healing Word", "Flame Strike"],
        caster_level=9,
    )
    archer = create_skeleton_archer(name="Validation Choke Archer", position=(10, 5), faction="monsters", darkvision=True)
    monsters = (guard, guardian_caster, archer)

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Guardian Choke Body Block",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=GUARDIAN_CHOKE_BODY_BLOCK,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "open_door": DOOR_POSITION,
            "hero_start": hero.position,
            "guard_choke": guard.position,
            "guardian_caster_start": guardian_caster.position,
            "archer_start": archer.position,
        },
        environment=environment,
    )


def create_multi_object_control_room_arena() -> ValidationArena:
    """Create a room with several object actions available immediately.

    Returns:
        Validation arena with an adjacent lever, loot chest, wall torch, and
        Fireball cannon so object priorities can be compared in one epoch.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()

    hero = _create_level_5_archer_fighter("Validation Object Controller", (5, 11))
    create_wall_torch(position=(4, 10), owner_uuid=uuid4(), lit=True)
    cannon = create_fireball_cannon(uuid4(), position=(6, 11), charges=2)

    chest = StorageChest(
        source_entity_uuid=uuid4(),
        name="Validation Control Cache",
        use_action_templates=[LootAllAction(source_entity_uuid=uuid4(), template=True)],
    )
    chest.chest_inventory.add_item(create_scroll_of_magic_missile(chest.uuid))
    chest.chest_inventory.add_item(create_acid_flask(chest.uuid))
    chest.chest_inventory.add_item(create_healing_potion(chest.uuid, heal_amount=12))
    chest.place_on_grid((5, 10))

    monsters = (
        create_skeleton_warrior(name="Validation Object Guard", position=(9, 11), faction="monsters", darkvision=True),
        create_skeleton_archer(name="Validation Object Archer", position=(10, 9), faction="monsters", darkvision=True),
        create_caster(name="Validation Object Mage", position=(11, 12), faction="monsters", level=5),
    )

    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: Multi-Object Control Room",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=MULTI_OBJECT_CONTROL_ROOM,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "trap_lever": TRAP_LEVER_POSITION,
            "control_cache": grid.get_object_position(chest.uuid) or (5, 10),
            "wall_torch": (4, 10),
            "fireball_cannon": grid.get_object_position(cannon.uuid) or (6, 11),
            "guard_start": monsters[0].position,
        },
        environment=environment,
    )


def create_srd_low_cr_patrol_arena() -> ValidationArena:
    """Create a mixed low-CR SRD patrol arena.

    Returns:
        Validation arena using several SRD-derived weak actors with different
        combat jobs.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_archer_fighter("Validation SRD Patrol Archer", (3, 7))
    hero.loot_item(create_scroll_of_magic_missile(hero.uuid))
    monsters = (
        create_srd_monster("bandit", name="SRD Patrol Bandit", position=(10, 4), faction="monsters"),
        create_srd_monster("guard", name="SRD Patrol Guard", position=(9, 7), faction="monsters"),
        create_srd_monster("kobold", name="SRD Patrol Kobold", position=(11, 9), faction="monsters"),
        create_srd_monster("wolf", name="SRD Patrol Wolf", position=(8, 10), faction="monsters"),
        create_srd_monster("acolyte", name="SRD Patrol Acolyte", position=(12, 6), faction="monsters"),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: SRD Low-CR Patrol",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SRD_LOW_CR_PATROL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "frontline_guard": monsters[1].position,
            "support_acolyte": monsters[4].position,
        },
    )


def create_srd_undead_crypt_arena() -> ValidationArena:
    """Create a dark undead SRD crypt arena.

    Returns:
        Validation arena with undead bodies that differ in speed, size, and
        condition profile.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    create_standard_arena_floor(grid)
    darken_arena(grid)
    hero = _create_level_5_shield_fighter("Validation Crypt Fighter", (3, 7))
    hero.loot_item(create_healing_potion(hero.uuid, heal_amount=16))
    monsters = (
        create_srd_monster("zombie", name="SRD Crypt Zombie", position=(10, 5), faction="monsters"),
        create_srd_monster("ghoul", name="SRD Crypt Ghoul", position=(9, 7), faction="monsters"),
        create_skeleton_archer(name="SRD Crypt Skeleton Archer", position=(11, 9), faction="monsters", darkvision=True),
        create_srd_monster("ogre_zombie", name="SRD Crypt Ogre Zombie", position=(12, 7), faction="monsters"),
    )
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: SRD Undead Crypt",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SRD_UNDEAD_CRYPT,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "ghoul_start": monsters[1].position,
            "ogre_zombie_start": monsters[3].position,
        },
    )


def create_srd_goblinoid_warband_arena() -> ValidationArena:
    """Create a terrain-heavy SRD goblinoid warband arena.

    Returns:
        Validation arena with darkvision soldiers, bruisers, and ranged modes.
    """
    reset_ai_validation_arena_state()
    grid = get_map()
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()
    hero = _create_level_5_barbarian("Validation Warband Barbarian", (2, 7))
    monsters = (
        create_srd_monster("kobold", name="SRD Warband Kobold", position=(9, 4), faction="monsters"),
        create_srd_monster("hobgoblin", name="SRD Warband Hobgoblin", position=(9, 7), faction="monsters"),
        create_srd_monster("bugbear", name="SRD Warband Bugbear", position=(11, 6), faction="monsters"),
        create_srd_monster("gnoll", name="SRD Warband Gnoll", position=(12, 9), faction="monsters"),
    )
    monsters[0].loot_item(create_acid_flask(monsters[0].uuid))
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: SRD Goblinoid Warband",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SRD_GOBLINOID_WARBAND,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "open_door": DOOR_POSITION,
            "hobgoblin_line": monsters[1].position,
            "water_sample": WATER_POSITIONS[0],
        },
        environment=environment,
    )


def create_srd_divine_cult_cell_arena() -> ValidationArena:
    """Create an SRD cult and divine-support cell arena.

    Returns:
        Validation arena centered on support, control, healing, and item
        pressure from SRD-derived humanoids.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_5_sorcerer("Validation Cult-Cell Sorcerer", (3, 7))
    hero.loot_item(create_scroll_of_hold_person(hero.uuid))
    monsters = (
        create_srd_monster("cultist", name="SRD Cell Cultist", position=(8, 7), faction="monsters"),
        create_srd_monster("guard", name="SRD Cell Guard", position=(9, 6), faction="monsters"),
        create_srd_monster("cult_fanatic", name="SRD Cell Fanatic", position=(11, 7), faction="monsters"),
        create_srd_monster("priest", name="SRD Cell Priest", position=(12, 9), faction="monsters"),
    )
    monsters[2].loot_item(create_potion_of_haste(monsters[2].uuid))
    monsters[3].loot_item(create_healing_potion(monsters[3].uuid, heal_amount=18))
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: SRD Divine Cult Cell",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SRD_DIVINE_CULT_CELL,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "fanatic_start": monsters[2].position,
            "priest_start": monsters[3].position,
        },
    )


def create_srd_elite_mercenary_contract_arena() -> ValidationArena:
    """Create an elite SRD mercenary-contract arena.

    Returns:
        Validation arena with high-armor martials and an SRD mage against a
        higher-slot hero.
    """
    reset_ai_validation_arena_state()
    create_standard_arena_floor(get_map())
    hero = _create_level_9_sorcerer("Validation Elite-Contract Sorcerer", (3, 7))
    hero.loot_item(create_potion_of_greater_invisibility(hero.uuid))
    monsters = (
        create_srd_monster("knight", name="SRD Contract Knight", position=(8, 7), faction="monsters"),
        create_srd_monster("veteran", name="SRD Contract Veteran", position=(10, 5), faction="monsters"),
        create_srd_monster("mage", name="SRD Contract Mage", position=(12, 7), faction="monsters"),
        create_srd_monster("bandit_captain", name="SRD Contract Captain", position=(10, 9), faction="monsters"),
    )
    monsters[1].loot_item(create_weapon_coat(monsters[1].uuid))
    encounter, controllers = _start_passive_validation_encounter(
        "AI Validation: SRD Elite Mercenary Contract",
        hero,
        monsters,
    )
    return ValidationArena(
        spec=SRD_ELITE_MERCENARY_CONTRACT,
        encounter=encounter,
        hero=hero,
        monsters=monsters,
        controllers=controllers,
        notable_positions={
            "hero_start": hero.position,
            "knight_start": monsters[0].position,
            "mage_start": monsters[2].position,
        },
    )


def _create_level_5_sorcerer(name: str, position: tuple[int, int]) -> Entity:
    """Create the standard validation Sorcerer hero."""
    hero = create_sorcerer(
        SorcererConfig(
            level=5,
            name=name,
            position=position,
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Magic Missile",
                "Burning Hands",
                "Thunderwave",
                "Scorching Ray",
                "Hold Person",
                "Shatter",
                "Invisibility",
                "Fireball",
                "Lightning Bolt",
            ],
        )
    )
    _give_lit_torch(hero)
    return hero


def _create_level_9_sorcerer(name: str, position: tuple[int, int]) -> Entity:
    """Create a higher-slot Sorcerer for resource-pressure validation."""
    hero = create_sorcerer(
        SorcererConfig(
            level=9,
            name=name,
            position=position,
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            asi_8=[("dexterity", 2)],
            spell_names=[
                "Fire Bolt",
                "Ray of Frost",
                "Magic Missile",
                "Thunderwave",
                "Scorching Ray",
                "Hold Person",
                "Shatter",
                "Invisibility",
                "Fireball",
                "Lightning Bolt",
                "Hypnotic Pattern",
                "Slow",
                "Haste",
                "Banishment",
                "Greater Invisibility",
                "Cone of Cold",
                "Cloudkill",
            ],
        )
    )
    _give_lit_torch(hero)
    return hero


def _create_level_5_shield_fighter(name: str, position: tuple[int, int]) -> Entity:
    """Create a durable sword-and-shield Fighter hero."""
    hero = create_fighter(
        FighterConfig(
            level=5,
            name=name,
            position=position,
            faction="heroes",
            fighting_style="dueling",
            equipment_preset="sword_shield",
            asi_4=[("strength", 2)],
        )
    )
    hero.equipment.equip(create_longbow(hero.uuid), WeaponSlot.RANGED_MAIN)
    _give_lit_torch(hero)
    return hero


def _create_level_5_archer_fighter(name: str, position: tuple[int, int]) -> Entity:
    """Create a ranged Fighter hero for skirmish validation."""
    hero = create_fighter(
        FighterConfig(
            level=5,
            name=name,
            position=position,
            faction="heroes",
            fighting_style="archery",
            equipment_preset="archery",
            asi_4=[("dexterity", 2)],
        )
    )
    _give_lit_torch(hero)
    return hero


def _create_level_5_barbarian(name: str, position: tuple[int, int]) -> Entity:
    """Create a melee Barbarian hero for crossfire validation."""
    hero = create_barbarian(
        BarbarianConfig(
            level=5,
            name=name,
            position=position,
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            equipment_preset="greataxe",
            asi_4=[("strength", 2)],
        )
    )
    _give_lit_torch(hero)
    return hero


def _give_lit_torch(hero: Entity) -> None:
    """Give a validation hero the standard lit arena torch."""
    torch = create_torch(hero.uuid)
    hero.loot_item(torch)
    torch.ignite(hero.uuid)


def _add_static_damage_affinity(
    entity: Entity,
    status: ResistanceStatus,
    damage_type: DamageType,
    name: str,
) -> None:
    """Add a fixture-specific resistance, vulnerability, or immunity modifier."""
    entity.health.damage_reduction.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            value=status,
            damage_type=damage_type,
            name=name,
        )
    )


def _give_item_gauntlet_loadout(hero: Entity) -> None:
    """Give a validation hero varied item-backed actions."""
    hero.loot_item(create_wand_of_magic_missiles(hero.uuid, charges=3))
    hero.loot_item(create_wand_of_fire(hero.uuid, charges=4))
    hero.loot_item(create_scroll_of_fireball(hero.uuid))
    hero.loot_item(create_scroll_of_magic_missile(hero.uuid))
    hero.loot_item(create_scroll_of_spike_growth(hero.uuid))
    hero.loot_item(create_potion_of_greater_invisibility(hero.uuid))
    hero.loot_item(create_weapon_coat(hero.uuid))


def _place_validation_directional_barrier(
    grid: GridMap,
    column: int,
    door_y: int,
    label: str,
) -> StandardBarrierObjects:
    """Place a vertical validation barrier with one closed door.

    Args:
        grid: Grid receiving the barrier objects.
        column: X coordinate of the barrier.
        door_y: Y coordinate left open as a closed door.
        label: Prefix used for object names.

    Returns:
        Barrier object bundle with the created door and walls.
    """
    walls = []
    door_position = (column, door_y)
    door: Optional[DirectionalDoor] = None
    for y in range(3, 12):
        position = (column, y)
        grid.set_tile(position[0], position[1], walkable=True, visible=True, name="Floor")
        if position == door_position:
            door = DirectionalDoor(
                source_entity_uuid=uuid4(),
                name=f"{label} Door",
                blocked_directions=("west",),
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
                is_open=False,
            )
            door.place_on_grid(position)
            continue
        wall = DirectionalWall(
            source_entity_uuid=uuid4(),
            name=f"{label} Wall",
            blocked_directions=("west",),
            blocked_channels=STANDARD_BLOCKING_CHANNELS,
        )
        wall.place_on_grid(position)
        walls.append(wall)

    if door is None:
        raise ValueError("Validation barrier requires a door within the wall range.")
    return StandardBarrierObjects(door=door, walls=tuple(walls))


def _start_passive_validation_encounter(
    name: str,
    hero: Entity,
    monsters: tuple[Entity, ...],
) -> tuple[Encounter, dict[UUID, Controller]]:
    """Start an encounter with passive controllers for all actors."""
    actors = (hero, *monsters)
    for actor in actors:
        add_opportunity_attack_handler(actor)
    Entity.update_all_entities_senses(max_distance=80)

    encounter = Encounter(name=name, source_entity_uuid=uuid4())
    controllers: dict[UUID, Controller] = {}
    for actor in actors:
        controller = PassController(source_entity_uuid=actor.uuid)
        controllers[actor.uuid] = controller
        encounter.add_combatant(actor, controller)

    encounter.roll_initiative()
    opening_faction = _OPENING_FACTION.get()
    if opening_faction is not None:
        opening_candidates = [
            entity_uuid
            for entity_uuid in encounter.initiative_order
            if (entity := Entity.get(entity_uuid)) is not None
            and entity.faction == opening_faction
        ]
        if not opening_candidates:
            raise ValueError(
                f"Opening faction {opening_faction!r} has no combatant in {name!r}."
            )
        opening_entity_uuid = opening_candidates[0]
        encounter.initiative_order = [
            opening_entity_uuid,
            *[
                entity_uuid
                for entity_uuid in encounter.initiative_order
                if entity_uuid != opening_entity_uuid
            ],
        ]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter, controllers
