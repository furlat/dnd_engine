from enum import Enum

class RollOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Critical Hit"

class HitReason(str, Enum):
    NORMAL = "Normal"
    CRITICAL = "Critical"
    AUTOHIT = "AutoHit"
    AUTOMISS = "AutoMiss"

class CriticalReason(str, Enum):
    NORMAL = "Normal"
    AUTO = "Auto"

class SourceType(str, Enum):
    CONDITION = "Condition"
    ABILITY = "Ability"
    ITEM = "Item"
    ENVIRONMENT = "Environment"
    FEATURE = "Feature"
    SPELL = "Spell"
    OTHER = "Other"

class AdvantageStatus(str, Enum):
    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"

class AutoHitStatus(str, Enum):
    NONE = "None"
    AUTOHIT = "Autohit"
    AUTOMISS = "Automiss"

class CriticalStatus(str, Enum):
    NONE = "None"
    AUTOCRIT = "Autocrit"
    NOCRIT = "Critical Immune"

class ResistanceStatus(str,Enum):
    NONE = "None"
    RESISTANCE = "Resistance"
    IMMUNITY = "Immunity"
    VULNERABILITY = "Vulnerability"
    
class Size(str, Enum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"

class MonsterType(str, Enum):
    ABERRATION = "Aberration"
    BEAST = "Beast"
    CELESTIAL = "Celestial"
    CONSTRUCT = "Construct"
    DRAGON = "Dragon"
    ELEMENTAL = "Elemental"
    FEY = "Fey"
    FIEND = "Fiend"
    GIANT = "Giant"
    HUMANOID = "Humanoid"
    MONSTROSITY = "Monstrosity"
    OOZE = "Ooze"
    PLANT = "Plant"
    UNDEAD = "Undead"

class Alignment(str, Enum):
    LAWFUL_GOOD = "Lawful Good"
    LAWFUL_NEUTRAL = "Lawful Neutral"
    LAWFUL_EVIL = "Lawful Evil"
    NEUTRAL_GOOD = "Neutral Good"
    TRUE_NEUTRAL = "True Neutral"
    NEUTRAL_EVIL = "Neutral Evil"
    CHAOTIC_GOOD = "Chaotic Good"
    CHAOTIC_NEUTRAL = "Chaotic Neutral"
    CHAOTIC_EVIL = "Chaotic Evil"
    UNALIGNED = "Unaligned"

class Ability(str, Enum):
    STR = "Strength"
    DEX = "Dexterity"
    CON = "Constitution"
    INT = "Intelligence"
    WIS = "Wisdom"
    CHA = "Charisma"

class Skills(str, Enum):
    ACROBATICS = "Acrobatics"
    ANIMAL_HANDLING = "Animal Handling"
    ARCANA = "Arcana"
    ATHLETICS = "Athletics"
    DECEPTION = "Deception"
    HISTORY = "History"
    INSIGHT = "Insight"
    INTIMIDATION = "Intimidation"
    INVESTIGATION = "Investigation"
    MEDICINE = "Medicine"
    NATURE = "Nature"
    PERCEPTION = "Perception"
    PERFORMANCE = "Performance"
    PERSUASION = "Persuasion"
    RELIGION = "Religion"
    SLEIGHT_OF_HAND = "Sleight of Hand"
    STEALTH = "Stealth"
    SURVIVAL = "Survival"

class SensesType(str, Enum):
    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"

class DamageType(str, Enum):
    ACID = "Acid"
    BLUDGEONING = "Bludgeoning"
    COLD = "Cold"
    FIRE = "Fire"
    FORCE = "Force"
    LIGHTNING = "Lightning"
    NECROTIC = "Necrotic"
    PIERCING = "Piercing"
    POISON = "Poison"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    SLASHING = "Slashing"
    THUNDER = "Thunder"

class Language(str, Enum):
    COMMON = "Common"
    DWARVISH = "Dwarvish"
    ELVISH = "Elvish"
    GIANT = "Giant"
    GNOMISH = "Gnomish"
    GOBLIN = "Goblin"
    HALFLING = "Halfling"
    ORC = "Orc"
    ABYSSAL = "Abyssal"
    CELESTIAL = "Celestial"
    DRACONIC = "Draconic"
    DEEP_SPEECH = "Deep Speech"
    INFERNAL = "Infernal"
    PRIMORDIAL = "Primordial"
    SYLVAN = "Sylvan"
    UNDERCOMMON = "Undercommon"

class ActionType(str, Enum):
    ACTION = "Action"
    BONUS_ACTION = "Bonus Action"
    REACTION = "Reaction"
    MOVEMENT = "Movement"
    LEGENDARY_ACTION = "Legendary Action"
    LAIR_ACTION = "Lair Action"

class UsageType(str, Enum):
    RECHARGE = "Recharge"
    AT_WILL = "At Will"
    CHARGES = "Charges"

class RechargeType(str, Enum):
    SHORT_REST = "Short Rest"
    LONG_REST = "Long Rest"
    ROUND = "Round"



class StatusEffect(str, Enum):
    DISADVANTAGE_ON_ATTACK_ROLLS = "Disadvantage on Attack Rolls"
    ADVANTAGE_ON_DEX_SAVES = "Advantage on Dexterity Saving Throws"
    HIDDEN = "Hidden"
    DODGING = "Dodging"
    HELPING = "Helping"
    DASHING = "Dashing"

class DurationType(str, Enum):
    INSTANTANEOUS = "instantaneous"
    ROUNDS = "rounds"
    MINUTES = "minutes"
    HOURS = "hours"
    INDEFINITE = "indefinite"

HEARING_DEPENDENT_ABILITIES = {Skills.PERCEPTION, Skills.PERFORMANCE, Skills.INSIGHT}

class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"

class TargetType(str, Enum):
    SELF = "Self"
    ONE_TARGET = "One Target"
    MULTIPLE_TARGETS = "Multiple Targets"
    AREA = "Area"
    ALLY = "Ally"  # Added this line

class ShapeType(str, Enum):
    SPHERE = "Sphere"
    CUBE = "Cube"
    CONE = "Cone"
    LINE = "Line"
    CYLINDER = "Cylinder"

class TargetRequirementType(str, Enum):
    HOSTILE = "Hostile"
    ALLY = "Ally"
    ANY = "Any"

class AttackType(str, Enum):
    MELEE_WEAPON = "Melee Weapon"
    RANGED_WEAPON = "Ranged Weapon"
    MELEE_SPELL = "Melee Spell"
    RANGED_SPELL = "Ranged Spell"

class ArmorType(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"

class WeaponProperty(str, Enum):
    FINESSE = "Finesse"
    VERSATILE = "Versatile"
    RANGED = "Ranged"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    LIGHT = "Light"
    HEAVY = "Heavy"