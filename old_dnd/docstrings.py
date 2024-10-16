size_docstring: str = """A monster can be Tiny, Small, Medium, Large, Huge, or Gargantuan. Table: Size Categories shows how much space a creature of a particular size controls in combat."""

modifying_creatures_docstring: str = """Despite the versatile collection of monsters in this book, you might be at a loss when it comes to finding the perfect creature for part of an adventure. Feel free to tweak an existing creature to make it into something more useful for you, perhaps by borrowing a trait or two from a different monster or by using a variant or template, such as the ones in this book. Keep in mind that modifying a monster, including when you apply a template to it, might change its challenge rating."""

type_docstring: str = """A monster’s type speaks to its fundamental nature. Certain spells, magic items, class features, and other effects in the game interact in special ways with creatures of a particular type. For example, an arrow of dragon slaying deals extra damage not only to dragons but also other creatures of the dragon type, such as dragon turtles and wyverns.

The game includes the following monster types, which have no rules of their own:

- **Aberration**: Aberrations are utterly alien beings. Many of them have innate magical abilities drawn from the creature’s alien mind rather than the mystical forces of the world.
- **Beast**: Beasts are nonhumanoid creatures that are a natural part of the fantasy ecology. Some of them have magical powers, but most are unintelligent and lack any society or language. Beasts include all varieties of ordinary animals, dinosaurs, and giant versions of animals.
- **Celestial**: Celestials are creatures native to the Upper Planes. Many of them are the servants of deities, employed as messengers or agents in the mortal realm and throughout the planes. Celestials are good by nature, so the exceptional celestial who strays from a good alignment is a horrifying rarity. Celestials include angels, couatls, and pegasi.
- **Construct**: Constructs are made, not born. Some are programmed by their creators to follow a simple set of instructions, while others are imbued with sentience and capable of independent thought. Golems are the iconic constructs. Many creatures native to the outer plane of Mechanus, such as modrons, are constructs shaped from the raw material of the plane by the will of more powerful creatures.
- **Dragon**: Dragons are large reptilian creatures of ancient origin and tremendous power. True dragons, including the good metallic dragons and the evil chromatic dragons, are highly intelligent and have innate magic. Also in this category are creatures distantly related to true dragons, but less powerful, less intelligent, and less magical, such as wyverns and pseudodragons.
- **Elemental**: Elementals are creatures native to the elemental planes. Some creatures of this type are little more than animate masses of their respective elements, including the creatures simply called elementals. Others have biological forms infused with elemental energy. The races of genies, including djinn and efreet, form the most important civilizations on the elemental planes. Other elemental creatures include azers, invisible stalkers, and water weirds.
- **Fey**: Fey are magical creatures closely tied to the forces of nature. They dwell in twilight groves and misty forests. In some worlds, they are closely tied to the Plane of Faerie. Some are also found in the Outer Planes, particularly the planes of Arborea and the Beastlands. Fey include dryads, pixies, and satyrs.
- **Fiend**: Fiends are creatures of wickedness that are native to the Lower Planes. A few are the servants of deities, but many more labor under the leadership of archdevils and demon princes. Evil priests and mages sometimes summon fiends to the material world to do their bidding. If an evil celestial is a rarity, a good fiend is almost inconceivable. Fiends include demons, devils, hell hounds, rakshasas, and yugoloths.
- **Giant**: Giants tower over humans and their kind. They are humanlike in shape, though some have multiple heads (ettins) or deformities (fomorians). The six varieties of true giant are hill giants, stone giants, frost giants, fire giants, cloud giants, and storm giants. Besides these, creatures such as ogres and trolls are giants.
- **Goblinoids**: Almost as numerous but far more savage and brutal, and almost uniformly evil, are the races of goblinoids (goblins, hobgoblins, and bugbears), orcs, gnolls, lizardfolk, and kobolds.
- **Humanoid**: Humanoids are the main peoples of a fantasy gaming world, both civilized and savage, including humans and a tremendous variety of other species. They have language and culture, few if any innate magical abilities (though most humanoids can learn spellcasting), and a bipedal form. The most common humanoid races are the ones most suitable as player characters: humans, dwarves, elves, and halflings.
- **Monstrosity**: Monstrosities are monsters in the strictest sense—frightening creatures that are not ordinary, not truly natural, and almost never benign. Some are the results of magical experimentation gone awry (such as owlbears), and others are the product of terrible curses (including minotaurs and yuan-ti). They defy categorization, and in some sense serve as a catch-all category for creatures that don’t fit into any other type.
- **Ooze**: Oozes are gelatinous creatures that rarely have a fixed shape. They are mostly subterranean, dwelling in caves and dungeons and feeding on refuse, carrion, or creatures unlucky enough to get in their way. Black puddings and gelatinous cubes are among the most recognizable oozes.
- **Plant**: Plants in this context are vegetable creatures, not ordinary flora. Most of them are ambulatory, and some are carnivorous. The quintessential plants are the shambling mound and the treant. Fungal creatures such as the gas spore and the myconid also fall into this category.
- **Undead**: Undead are once-living creatures brought to a horrifying state of undeath through the practice of necromantic magic or some unholy curse. Undead include walking corpses, such as vampires and zombies, as well as bodiless spirits, such as ghosts and specters.
"""

tags_docstring: str = """A monster might have one or more tags appended to its type, in parentheses. For example, an orc has the humanoid (orc) type. The parenthetical tags provide additional categorization for certain creatures. The tags have no rules of their own, but something in the game, such as a magic item, might refer to them. For instance, a spear that is especially effective at fighting demons would work against any monster that has the demon tag."""

ability_scores_docstring: str = """Every monster has six ability scores (Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma) and corresponding modifiers."""

strength_docstring: str = """Strength measures bodily power, athletic training, and the extent to which you can exert raw physical force. A creature with a Strength score of 0 is incapable of moving and is effectively immobile (but not unconscious)."""

dexterity_docstring: str = """Dexterity measures agility, reflexes, and balance. A creature with a Dexterity score of 0 is incapable of moving and is effectively immobile (but not unconscious)."""

constitution_docstring: str = """Constitution measures health, stamina, and vital force. A Constitution score of 0 means that the creature is dead."""

intelligence_docstring: str = """Intelligence measures mental acuity, accuracy of recall, and the ability to reason. Creatures of animal-level instinct have Intelligence scores of 1 or 2. Any creature capable of understanding speech has a score of at least 3."""

wisdom_docstring: str = """Wisdom reflects how attuned you are to the world around you and represents perceptiveness and intuition."""

charisma_docstring: str = """Charisma measures your ability to interact effectively with others. It includes such factors as confidence and eloquence, and it can represent a charming or commanding personality."""

alignment_docstring: str = """ A monster’s alignment provides a clue to its disposition and how it behaves in a roleplaying or combat situation. For example, a chaotic evil monster might be difficult to reason with and might attack characters on sight, whereas a neutral monster might be willing to negotiate.

The alignment specified in a monster’s stat block is the default. Feel free to depart from it and change a monster’s alignment to suit the needs of your campaign. If you want a good-aligned green dragon or an evil storm giant, there’s nothing stopping you.

Some creatures can have any alignment. In other words, you choose the monster’s alignment. Some monster’s alignment entry indicates a tendency or aversion toward law, chaos, good, or evil. For example, a berserker can be any chaotic alignment (chaotic good, chaotic neutral, or chaotic evil), as befits its wild nature.

Many creatures of low intelligence have no comprehension of law or chaos, good or evil. They don’t make moral or ethical choices, but rather act on instinct. These creatures are unaligned, which means they don’t have an alignment. """


armor_class_docstring: str = """ A monster that wears armor or carries a shield has an Armor Class (AC) that takes its armor, shield, and Dexterity into account. Otherwise, a monster’s AC is based on its Dexterity modifier and natural armor, if any. If a monster has natural armor, wears armor, or carries a shield, this is noted in parentheses after its AC value. """

hit_points_docstring: str = """
A monster usually dies or is destroyed when it drops to 0 hit points.

A monster’s hit points are presented both as a die expression and as an average number. For example, a monster with 2d8 hit points has 9 hit points on average (2 × 4½).

A monster’s size determines the die used to calculate its hit points, as shown in Table: Hit Dice by Size.

### Table: Hit Dice by Size
| Monster Size | Hit Die | Average HP per Die |
|--------------|---------|--------------------|
| Tiny         | d4      | 2½                 |
| Small        | d6      | 3½                 |
| Medium       | d8      | 4½                 |
| Large        | d10     | 5½                 |
| Huge         | d12     | 6½                 |
| Gargantuan   | d20     | 10½                |

A monster’s Constitution modifier also affects the number of hit points it has. Its Constitution modifier is multiplied by the number of Hit Dice it possesses, and the result is added to its hit points. For example, if a monster has a Constitution of 12 (+1 modifier) and 2d8 Hit Dice, it has 2d8 + 2 hit points (average 11).
"""


speed_docstring: str = """ A monster’s speed tells you how far it can move on its turn.

All creatures have a walking speed, simply called the monster’s speed. Creatures that have no form of ground-based locomotion have a walking speed of 0 feet.

Some creatures have one or more of the following additional movement modes."""

burrow_docstring: str =  """ A monster that has a burrowing speed can use that speed to move through sand, earth, mud, or ice. A monster can’t burrow through solid rock unless it has a special trait that allows it to do so.
"""

climb_docstring: str = """ A monster that has a climbing speed can use all or part of its movement to move on vertical surfaces. The monster doesn’t need to spend extra movement to climb.
"""

fly_docstring: str = """ A monster that has a flying speed can use all or part of its movement to fly. Some monsters have the ability to hover, which makes them hard to knock out of the air (as explained in the rules on flying in the Player’s Handbook). Such a monster stops hovering when it falls unconscious.
"""

swim_docstring: str = """ A monster that has a swimming speed doesn’t need to spend extra movement to swim. """


saving_throws_docstring: str = """The Saving Throws entry is reserved for creatures that are adept at resisting certain kinds of effects. For example, a creature that isn’t easily charmed or frightened might gain a bonus on its Wisdom saving throws. Most creatures don’t have special saving throw bonuses, in which case this section is absent.

A saving throw bonus is the sum of a monster’s relevant ability modifier and its proficiency bonus, which is determined by the monster’s challenge rating (as shown in the Proficiency Bonus by Challenge Rating table).

### Table: Proficiency Bonus by Challenge Rating
| Challenge Rating | Proficiency Bonus |
|------------------|-------------------|
| 0                | +2                |
| 1/8              | +2                |
| 1/4              | +2                |
| 1/2              | +2                |
| 1                | +2                |
| 2                | +2                |
| 3                | +2                |
| 4                | +2                |
| 5                | +3                |
| 6                | +3                |
| 7                | +3                |
| 8                | +3                |
| 9                | +4                |
| 10               | +4                |
| 11               | +4                |
| 12               | +4                |
| 13               | +5                |
| 14               | +5                |
| 15               | +5                |
| 16               | +5                |
| 17               | +6                |
| 18               | +6                |
| 19               | +6                |
| 20               | +6                |
| 21               | +7                |
| 22               | +7                |
| 23               | +7                |
| 24               | +7                |
| 25               | +8                |
| 26               | +8                |
| 27               | +8                |
| 28               | +8                |
| 29               | +9                |
| 30               | +9                |
"""

skills_docstring: str = """The Skills entry is reserved for monsters that are proficient in one or more skills. For example, a monster that is very perceptive and stealthy might have bonuses to Wisdom (Perception) and Dexterity (Stealth) checks.

A skill bonus is the sum of a monster’s relevant ability modifier and its proficiency bonus, which is determined by the monster’s challenge rating (as shown in the Proficiency Bonus by Challenge Rating table). Other modifiers might apply. For instance, a monster might have a larger-than-expected bonus (usually double its proficiency bonus) to account for its heightened expertise.
"""

vulnerabilities_resistances_immunities_docstring: str = """Some creatures have vulnerability, resistance, or immunity to certain types of damage. Particular creatures are even resistant or immune to damage from nonmagical attacks (a magical attack is an attack delivered by a spell, a magic item, or another magical source). In addition, some creatures are immune to certain conditions.
"""

armor_weapon_tool_proficiencies_docstring: str = """Assume that a creature is proficient with its armor, weapons, and tools. If you swap them out, you decide whether the creature is proficient with its new equipment.

For example, a hill giant typically wears hide armor and wields a greatclub. You could equip a hill giant with chain mail and a greataxe instead, and assume the giant is proficient with both, one or the other, or neither.
"""

senses_docstring: str = """The Senses entry notes a monster’s passive Wisdom (Perception) score, as well as any special senses the monster might have. Special senses are described below.

- **Blindsight**: A monster with blindsight can perceive its surroundings without relying on sight, within a specific radius. Creatures without eyes, such as grimlocks and gray oozes, typically have this special sense, as do creatures with echolocation or heightened senses, such as bats and true dragons. If a monster is naturally blind, it has a parenthetical note to this effect, indicating that the radius of its blindsight defines the maximum range of its perception.
- **Darkvision**: A monster with darkvision can see in the dark within a specific radius. The monster can see in dim light within the radius as if it were bright light, and in darkness as if it were dim light. The monster can’t discern color in darkness, only shades of gray. Many creatures that live underground have this special sense.
- **Tremorsense**: A monster with tremorsense can detect and pinpoint the origin of vibrations within a specific radius, provided that the monster and the source of the vibrations are in contact with the same ground or substance. Tremorsense can’t be used to detect flying or incorporeal creatures. Many burrowing creatures, such as ankhegs and umber hulks, have this special sense.
- **Truesight**: A monster with truesight can, out to a specific range, see in normal and magical darkness, see invisible creatures and objects, automatically detect visual illusions and succeed on saving throws against them, and perceive the original form of a shapechanger or a creature that is transformed by magic. Furthermore, the monster can see into the Ethereal Plane within the same range.
"""

languages_docstring: str = """The languages that a monster can speak are listed in alphabetical order. Sometimes a monster can understand a language but can’t speak it, and this is noted in its entry. A “—” indicates that a creature neither speaks nor understands any language.
"""

telepathy_docstring: str = """Telepathy is a magical ability that allows a monster to communicate mentally with another creature within a specified range. The contacted creature doesn’t need to share a language with the monster to communicate in this way with it, but it must be able to understand at least one language. A creature without telepathy can receive and respond to telepathic messages but can’t initiate or terminate a telepathic conversation.

A telepathic monster doesn’t need to see a contacted creature and can end the telepathic contact at any time. The contact is broken as soon as the two creatures are no longer within range of each other or if the telepathic monster contacts a different creature within range. A telepathic monster can initiate or terminate a telepathic conversation without using an action, but while the monster is incapacitated, it can’t initiate telepathic contact, and any current contact is terminated.

A creature within the area of an antimagic field or in any other location where magic doesn’t function can’t send or receive telepathic messages.
"""

challenge_docstring: str = """A monster’s challenge rating tells you how great a threat the monster is. An appropriately equipped and well-rested party of four adventurers should be able to defeat a monster that has a challenge rating equal to its level without suffering any deaths. For example, a party of four 3rd-level characters should find a monster with a challenge rating of 3 to be a worthy challenge, but not a deadly one.

Monsters that are significantly weaker than 1st-level characters have a challenge rating lower than 1. Monsters with a challenge rating of 0 are insignificant except in large numbers; those with no effective attacks are worth no experience points, while those that have attacks are worth 10 XP each.

Some monsters present a greater challenge than even a typical 20th-level party can handle. These monsters have a challenge rating of 21 or higher and are specifically designed to test player skill.
"""

experience_points_docstring: str = """The number of experience points (XP) a monster is worth is based on its challenge rating. Typically, XP is awarded for defeating the monster, although the GM may also award XP for neutralizing the threat posed by the monster in some other manner.

Unless something tells you otherwise, a monster summoned by a spell or other magical ability is worth the XP noted in its stat block.

### Table: Experience Points by Challenge Rating
| Challenge Rating | XP      |
|------------------|---------|
| 0                | 0 or 10 |
| 1/8              | 25      |
| 1/4              | 50      |
| 1/2              | 100     |
| 1                | 200     |
| 2                | 450     |
| 3                | 700     |
| 4                | 1,100   |
| 5                | 1,800   |
| 6                | 2,300   |
| 7                | 2,900   |
| 8                | 3,900   |
| 9                | 5,000   |
| 10               | 5,900   |
| 11               | 7,200   |
| 12               | 8,400   |
| 13               | 10,000  |
| 14               | 11,500  |
| 15               | 13,000  |
| 16               | 15,000  |
| 17               | 18,000  |
| 18               | 20,000  |
| 19               | 22,000  |
| 20               | 25,000  |
| 21               | 33,000  |
| 22               | 41,000  |
| 23               | 50,000  |
| 24               | 62,000  |
| 25               | 75,000  |
| 26               | 90,000  |
| 27               | 105,000 |
| 28               | 120,000 |
| 29               | 135,000 |
| 30               | 155,000 |
"""
special_traits_docstring: str = """Special traits (which appear after a monster’s challenge rating but before any actions or reactions) are characteristics that are likely to be relevant in a combat encounter and that require some explanation.

- **Innate Spellcasting**: A monster with the innate ability to cast spells has the Innate Spellcasting special trait. Unless noted otherwise, an innate spell of 1st level or higher is always cast at its lowest possible level and can’t be cast at a higher level. If a monster has a cantrip where its level matters and no level is given, use the monster’s challenge rating.
- **Spellcasting**: A monster with the Spellcasting special trait has a spellcaster level and spell slots, which it uses to cast its spells of 1st level and higher. The spellcaster level is also used for any cantrips included in the feature. The monster has a list of spells known or prepared from a specific class. The list might also include spells from a feature in that class, such as the Divine Domain feature of the cleric or the Druid Circle feature of the druid. The monster is considered a member of that class when attuning to or using a magic item that requires membership in the class or access to its spell list.
- **Psionics**: A monster that casts spells using only the power of its mind has the psionics tag added to its Spellcasting or Innate Spellcasting special trait. This tag carries no special rules of its own, but other parts of the game might refer to it. A monster that has this tag typically doesn’t require any components to cast its spells.
"""

actions_docstring: str = """When a monster takes its action, it can choose from the options in the Actions section of its stat block or use one of the actions available to all creatures, such as the Dash or Hide action.

- **Melee and Ranged Attacks**: The most common actions that a monster will take in combat are melee and ranged attacks. These can be spell attacks or weapon attacks, where the “weapon” might be a manufactured item or a natural weapon, such as a claw or tail spike.
- **Creature vs. Target**: The target of a melee or ranged attack is usually either one creature or one target, the difference being that a “target” can be a creature or an object.
- **Hit**: Any damage dealt or other effects that occur as a result of an attack hitting a target are described after the “Hit” notation. You have the option of taking average damage or rolling the damage; for this reason, both the average damage and the die expression are presented.
- **Miss**: If an attack has an effect that occurs on a miss, that information is presented after the “Miss:” notation.
- **Multiattack**: A creature that can make multiple attacks on its turn has the Multiattack action. A creature can’t use Multiattack when making an opportunity attack, which must be a single melee attack.
- **Ammunition**: A monster carries enough ammunition to make its ranged attacks. You can assume that a monster has 2d4 pieces of ammunition for a thrown weapon attack, and 2d10 pieces of ammunition for a projectile weapon such as a bow or crossbow.
"""

reactions_docstring: str = """If a monster can do something special with its reaction, that information is contained here. If a creature has no special reaction, this section is absent.
"""

limited_usage_docstring: str = """Some special abilities have restrictions on the number of times they can be used.

- **X/Day**: The notation “X/Day” means a special ability can be used X number of times and that a monster must finish a long rest to regain expended uses. For example, “1/Day” means a special ability can be used once and that the monster must finish a long rest to use it again.
- **Recharge X–Y**: The notation “Recharge X–Y” means a monster can use a special ability once and that the ability then has a random chance of recharging during each subsequent round of combat. At the start of each of the monster’s turns, roll a d6. If the roll is one of the numbers in the recharge notation, the monster regains the use of the special ability. The ability also recharges when the monster finishes a short or long rest. For example, “Recharge 5–6” means a monster can use the special ability once. Then, at the start of the monster’s turn, it regains the use of that ability if it rolls a 5 or 6 on a d6.
- **Recharge after a Short or Long Rest**: This notation means that a monster can use a special ability once and then must finish a short or long rest to use it again.
"""

grapple_rules_docstring: str = """Many monsters have special attacks that allow them to quickly grapple prey. When a monster hits with such an attack, it doesn’t need to make an additional ability check to determine whether the grapple succeeds, unless the attack says otherwise.

A creature grappled by the monster can use its action to try to escape. To do so, it must succeed on a Strength (Athletics) or Dexterity (Acrobatics) check against the escape DC in the monster’s stat block. If no escape DC is given, assume the DC is 10 + the monster’s Strength (Athletics) modifier.
"""

equipment_docstring: str = """A stat block rarely refers to equipment, other than armor or weapons used by a monster. A creature that customarily wears clothes, such as a humanoid, is assumed to be dressed appropriately.

You can equip monsters with additional gear and trinkets however you like, and you decide how much of a monster’s equipment is recoverable after the creature is slain and whether any of that equipment is still usable. A battered suit of armor made for a monster is rarely usable by someone else, for instance.

If a spellcasting monster needs material components to cast its spells, assume that it has the material components it needs to cast the spells in its stat block.
"""

legendary_creatures_docstring: str = """A legendary creature can do things that ordinary creatures can’t. It can take special actions outside its turn, and it might exert magical influence for miles around.

If a creature assumes the form of a legendary creature, such as through a spell, it doesn’t gain that form’s legendary actions, lair actions, or regional effects.
"""

legendary_actions_docstring: str = """A legendary creature can take a certain number of special actions—called legendary actions—outside its turn. Only one legendary action option can be used at a time and only at the end of another creature’s turn. A creature regains its spent legendary actions at the start of its turn. It can forgo using them, and it can’t use them while incapacitated or otherwise unable to take actions. If surprised, it can’t use them until after its first turn in the combat.
"""

legendary_lair_docstring: str = """A legendary creature might have a section describing its lair and the special effects it can create while there, either by act of will or simply by being present. Such a section applies only to a legendary creature that spends a great deal of time in its lair.

- **Lair Actions**: If a legendary creature has lair actions, it can use them to harness the ambient magic in its lair. On initiative count 20 (losing all initiative ties), it can use one of its lair action options. It can’t do so while incapacitated or otherwise unable to take actions. If surprised, it can’t use one until after its first turn in the combat.
- **Regional Effects**: The mere presence of a legendary creature can have strange and wondrous effects on its environment, as noted in this section. Regional effects end abruptly or dissipate over time when the legendary creature dies.
"""

npc_customizing_docstring: str = """There are many easy ways to customize the NPCs.

- **Racial Traits**: You can add racial traits to an NPC. For example, a halfling druid might have a speed of 25 feet and the Lucky trait. Adding racial traits to an NPC doesn’t alter its challenge rating.
- **Armor and Weapon Swaps**: You can upgrade or downgrade an NPC’s armor, or add or switch weapons. Adjustments to Armor Class and damage can change an NPC’s challenge rating.
- **Spell Swaps**: One way to customize an NPC spellcaster is to replace one or more of its spells. You can substitute any spell on the NPC’s spell list with a different spell of the same level from the same spell list. Swapping spells in this manner doesn’t alter an NPC’s challenge rating.
- **Magic Items**: The more powerful an NPC, the more likely it has one or more magic items in its possession. An archmage, for example, might have a magic staff or wand, as well as one or more potions and scrolls. Giving an NPC a potent damage-dealing magic item could alter its challenge rating.
"""

creature_traits_docstring: str = """You can create a themed version of an existing creature by giving it one or more of the following traits or actions:

- **Crackling**: This creature crackles with electricity. If you attempt a melee attack against it, you must succeed on a Constitution saving throw or take 1d8 lightning damage. The DC equals 10 + the creature’s highest ability modifier.
- **Soaked**: This creature is immune to fire damage. It magically creates enough drinking water for five creatures (including itself) each day.
- **Whirling**: Whenever this creature makes an attack, it can move its speed.
- **Arcane Armor**: Increase the AC of this creature by 2 and its CR by 1. When this creature takes damage from an attack, it can use its reaction to gain resistance to the triggering damage type until the end of its next turn.
- **Ensorcelled**: Weapon attacks made by this creature do force damage. Melee weapons (including natural weapons like fists, teeth, and claws) emit dim light to a range of 10 feet. The light is a color of your choosing.
- **Mage’s Mobility**: The creature learns one cantrip that requires a spell attack, and whenever it takes the Disengage action, it can choose to cast it. Its attack bonus equals its highest ability modifier + its proficiency bonus.
- **Doom’s Herald**: Once per turn, when the creature hits with a weapon attack, you must succeed on a Charisma saving throw or gain 1 doom point. The DC equals 10 + the creature’s proficiency bonus. A creature possessing doom points reduces its saving throw rolls (including death saving throws) by its current number of doom points. Spells like remove curse and greater restoration can reduce a creature’s accumulated doom points by one. Otherwise, all doom points disappear when the creature completes a long rest.
- **Hate Sense**: This creature knows the location of all creatures within 60 feet of it that aren’t constructs or undead.
- **Visions of the End**: The creature conjures visions of death to horrify its enemies as an action. Any creature within 60 feet that it can see must succeed on a Wisdom saving throw or become frightened of it for 1 minute. The DC equals 10 + the creature’s proficiency bonus. A frightened target can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success.
- **Incorporeal Movement**: The creature can move through other creatures and objects. It takes 5 (1d10) force damage if it ends its turn inside an object.
- **Invisibility**: As an action, the creature magically turns invisible until it chooses to end the effect. The invisibility ends early if the creature attacks or casts a spell. Any equipment the creature wears or carries is also invisible.
- **Waking Dream**: The creature is immune to any effects that would put it to sleep or cause it to become unconscious.
- **Beast Friend (1/Day)**: As an action, the creature summons four beasts of CR 2 or lower that appear in unoccupied spaces within 60 feet of it. The beasts act on their own initiative, but they obey all commands issued to them by the creature (no action required). Each beast disappears when it drops to 0 hit points.
- **Pixie Dust**: The creature gains a flying speed of 30 feet. If it already has a flying speed, it increases by 30 feet.
- **Unseelie Blessing**: The creature has advantage on saving throws against being charmed, and magic can’t put it to sleep.
- **Wild Heart**: At the beginning of each of the creature’s turns, it can use a bonus action to roll a d20. If it rolls lower than its Constitution ability score, it regains hit points equal to its Constitution modifier.
- **Eye-Watering Aroma**: Whenever you begin or end your turn within 10 feet of this creature, you must succeed on a Constitution saving throw or become blinded as your eyes fill with stinging tears. The DC equals 10 + the creature’s proficiency bonus. The condition ends as soon as you move at least 10 feet away from the creature. Targets with more than two eyes have disadvantage on the saving throw.
- **Rending Thorns**: Whenever this creature succeeds on a melee attack by rolling a 19 or 20, your AC is reduced by 1, in addition to suffering the normal effects of the attack. This reduction to AC ends after you take a short or long rest.
- **Wreath of Briars**: When you hit this creature with a melee attack, it can use its reaction to force you to make a Dexterity saving throw, taking 2d8 piercing damage and dropping whatever you are currently holding on a failed save or half as much damage on a successful one. The DC equals 10 + the creature’s proficiency bonus.
- **Plague Form**: The creature has resistance to necrotic damage and immunity to poison damage.
- **Putrid**: Whenever the creature takes bludgeoning, piercing, or slashing damage, all creatures within 5 feet of it take 1d6 poison damage.
- **Toxic Strike**: If the creature hits with a melee attack, the target must succeed on a Constitution saving throw or be poisoned for 1 minute. If the target fails the save by 5 or more, the target is also paralyzed while poisoned in this way. The DC equals 10 + the creature’s proficiency bonus.
- **Half There**: This creature is literally halfway between this plane of existence and another. Attacks against it have disadvantage. Successfully grappling the creature brings it fully into this plane for the duration, removing any benefit to the creature from this feature.
- **Infuriating Redirection**: Once per round, as a reaction to being targeted by a ranged attack, the creature can open a portal to redirect the attack to another creature within 30 feet.
- **Pop Out**: At the end of this creature’s turn, if it did not move, it can teleport to any unoccupied space within 20 feet.
- **Evaporating Aura**: Whenever you enter an area within 20 feet of this creature for the first time in a turn, or start your turn there, any water, wine, spirits, or other nonmagical fluids you carry evaporate and disappear.
- **Hot as Hells**: Whenever you enter an area within 5 feet of this creature for the first time in a turn, or start your turn there, you must succeed on a Constitution saving throw or take fire damage equal to 1d6 + the creature’s proficiency bonus. The DC equals 10 + the creature’s proficiency bonus.
- **Singeing Blow**: Whenever this creature hits with a melee attack, it deals extra fire damage equal to its proficiency bonus.
- **Ritualist**: This creature knows three ritual spells of your choice. These spells can be from any spell list, but they can’t be of a level that exceeds this creature’s proficiency bonus. The creature can cast each of these spells once per long rest without expending material components. If a ritual requires a saving throw, the DC equals 10 + this creature’s proficiency bonus.
- **Superior Focus**: This creature has advantage on Constitution saving throws to maintain concentration.
- **Blessing of Vitality**: The creature regenerates 10 hit points at the start of its turn. If the creature takes necrotic damage, this trait doesn’t function at the start of the creature’s next turn. The creature dies only if it starts its turn with 0 hit points and doesn’t regenerate.
- **Divine Protection**: If you target the creature with an attack or a harmful spell, you must first make a Wisdom saving throw (DC equals 10 + this creature’s proficiency bonus). On a success, you attack as normal, and you are immune to this feature for 1 minute. On a failed save, you must choose a new target or lose the attack or spell. If the creature attacks another creature, that target is immune to this feature for 1 minute.
- **Heavenly Wrath**: Whenever this creature makes a successful weapon attack, they deal an additional 1d8 radiant damage.
- **Dancing Shadows**: While standing in dim light or darkness, the creature can use their bonus action to teleport to a different unoccupied space of dim light or darkness it can see within 30 feet.
- **Shadow Cloak**: Whenever the creature takes damage, it can use its reaction to create a 10-foot-radius sphere of magical darkness centered on itself. The darkness remains until dispelled or until the beginning of the creature’s next turn. The creature can use this feature a number of times equal to its proficiency bonus.
- **Shadow Sight**: The creature has darkvision out to a range of 60 feet (if they don’t already have darkvision) and can see in magical darkness out to the same distance.
- **Ephemeral**: The creature is not completely grounded in material space, and attacks against it have disadvantage. If the creature is hit by an attack, this trait is disrupted until the end of its next turn.
- **Incorporeal**: This creature can move through other creatures and objects as if they were difficult terrain. It takes 5 (1d10) force damage if it ends its turn inside an object.
- **Shapeless**: This creature is invisible except to creatures with truesight or under the effects of spells like detect magic or see invisibility.
- **Enhanced Spellcasting**: Any spells this creature casts have their saving throw DC increased by 1.
- **Potent Spellcasting (CR 10 or Higher Creature Only)**: Creatures have disadvantage on saving throws made to resist spells cast by this creature.
"""

