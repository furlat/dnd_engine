# SRD levels 4–9: difficulty ranks 1 and 2, after the 36-spell implementation

15 October 2026. **Analysis only; no further implementation is authorized by this audit.**

The candidate pool contains **only spells present in SRD 5.1 or SRD 5.2**. BG3 is an implementation reference, never an additional source of eligible spell identities. Preference: **documented shipped BG3 adaptation > SRD 5.1 > SRD 5.2**. The human explicitly reconfirmed this boundary during the audit. No BG3-only spells, mods, cut content, renamed duplicates or alternate delivery variants count as additions.

## Result and counts

**22 recommended rank-1/2 additions: 1 rank 1 and 21 rank 2.** Of these, **17 are 5.1 spell identities and 5 are genuinely additional 5.2 identities**. Difficulty is a source-based engineering estimate, not a claim that new spells or every referenced interaction have already passed gameplay tests.

| Level | 5.1 spells | New 5.2 spells | Union | Implemented native | Missing | Rank 1 | Rank 2 | Rank 3 | Rank 4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 31 | 3 | 34 | 12 | 22 | 1 | 4 | 10 | 7 |
| 5 | 37 | 1 | 38 | 10 | 28 | 0 | 4 | 9 | 15 |
| 6 | 31 | 0 | 31 | 13 | 18 | 0 | 5 | 4 | 9 |
| 7 | 20 | 0 | 20 | 4 | 16 | 0 | 3 | 5 | 8 |
| 8 | 16 | 1 | 17 | 4 | 13 | 0 | 2 | 5 | 6 |
| 9 | 15 | 1 | 16 | 2 | 14 | 0 | 3 | 3 | 8 |
| **Total** | **150** | **6** | **156** | **45** | **111** | **1** | **21** | **36** | **53** |

The current implementation worktree has **166 public catalog spell roots**. Three existing roots—Aegis Spark, Necrotic Bless and Conjure Fiend—are outside this SRD pool. Entangle and Black Tentacles have native implementations outside the catalog. Thus the overall inventory is **168 native roots, of which 165 match the deduplicated SRD pool**; levels 4–9 account for 44 catalog roots plus Black Tentacles = 45. This audit does not remove or modify existing content.

Adding these 22 would produce **188 catalog roots / 190 native roots overall**, with **67 native level-4–9 SRD spells**. Black Tentacles still needs separate catalog exposure; exposing it is not a new spell implementation and is not counted among the 22.

## How the ranks are assigned

- **Rank 1:** very close to an existing spell; principally parameters/eligibility and ordinary catalog identity work.
- **Rank 2:** compose existing condition, action, damage, spatial, item or summon owners, with bounded spell-specific glue and narrow integration hooks. It does not mean “zero engine edits” or “one afternoon.”
- **Rank 3:** a small missing shared capability or unresolved ownership contract must be added first.
- **Rank 4:** major world/form/control/physics work, or the central effect requires RP/GM adjudication.

Ratings preserve each selected source profile’s central mechanics. They do not obtain a lower rank by discarding inconvenient branches, changing arbitrary shapes to a single sphere, replacing form HP with temporary HP, or using a non-SRD spell under another name. Summons reuse the approved autonomous allied model; no direct summon-control protocol or NDClient presentation work is assumed.

The audit reads the completed spell worktree at `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`, including its uncommitted 36-spell implementation. The original Windows checkout alone would undercount the current engine. Counts were recomputed from `SPELL_CATALOG_COMPOSITION_ROWS` and native source, rather than the older coverage ledger’s implementation statuses.

## Rank 1 — 1 spell

### Level 4 — 1

**Charm Monster** — Bard, Druid, Sorcerer, Warlock, Wizard. Pool: [SRD 5.2 only, p. 114](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf#page=114). BG3: No documented shipped spell. Preferred profile: **5.2**.

Use the 5.2 creature-general charm: no concentration, combat save advantage, and damage from the caster or its allies ends the charm. Reuse the existing charm application and damage-removal pattern; change eligibility and source metadata.

Reuse: `CharmPerson`; `AnimalFriendshipEffect`; `Charmed`.

Boundary / interactions: Honor Charmed immunity, Protection from Evil and Good and Calm Emotions; verify that the correct damage sources break it. No BG3 version was found.

## Rank 2 — 21 spells

### Level 4 — 4

**Aura of Life** — Cleric, Paladin. Pool: [SRD 5.2 only, p. 111](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf#page=111). BG3: No documented shipped spell. Preferred profile: **5.2**.

Compose a moving allied 30-foot aura: necrotic resistance, prevention of maximum-HP loss, and 1 HP at the start of an eligible downed ally’s turn.

Reuse: `SpiritGuardiansZone / MembershipAreaCondition`; `ProtectionFromPoison`; `HarmEffect`; `LifeDrainReduction`; `native healing`.

Boundary / interactions: The HP-loss prevention must cover both Harm and repeated Life Drain updates, including an already-present reduction owner. It prevents further reductions; it does not silently restore previous losses. Heal living/downed allies, never dead bodies; test aura entry/exit and Antimagic clipping.

**Phantasmal Killer** — Wizard. Pool: [SRD 5.1, p. 167](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=167). BG3: [Yes](https://bg3.wiki/wiki/Phantasmal_Killer). Preferred profile: **BG3**.

Use BG3’s bounded psychic damage-over-time and immobilizing fear-style control, with its own condition identity and retained casting source. No fabricated nightmare or narrative simulation is needed.

Reuse: `DissonantFearEffect`; `PhantasmalForceEffect`; `target-turn expiry`; `concentration links`.

Boundary / interactions: Check frightened immunity and Calm Emotions / Heroism / Protection from Evil and Good, repeated saves, damage timing, overlapping casts and concentration removal. Exact save/tick cadence belongs in the later spell card.

**Resilient Sphere** — Wizard. Pool: [SRD 5.1, p. 175](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=175). BG3: [Yes](https://bg3.wiki/wiki/Otiluke%27s_Resilient_Sphere). Preferred profile: **BG3**.

Use BG3’s short-lived condition: invulnerability, half speed, blocked outward attacks/spellcasting and blocked incoming spell effects. This avoids a rolling, pushable physical sphere model.

Reuse: `Sanctuary action admission`; `Slow movement modifiers`; `damage affinities`; `spell/condition event handlers`.

Boundary / interactions: Test ongoing damage, healing, non-damage conditions, self effects, items, breath attacks and mixed weapon/spell packets. Do not replace this with resistance or an Antimagic zone that also suppresses another occupant in the same XY column. Boundary details need an explicit rule card; existing Globe/Antimagic rules remain intact.

**Vitriolic Sphere** — Sorcerer, Wizard. Pool: [SRD 5.2 only, p. 172](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf#page=172). BG3: No documented shipped spell. Preferred profile: **5.2**.

Compose a Dexterity-save acid burst with the failed-save-only delayed acid packet. Store each recipient’s delayed packet and original source independently.

Reuse: `Fireball save/AoE pipeline`; `AcidArrowEffect`; `native elemental exposure`.

Boundary / interactions: A successful save gets half initial damage and no later packet; test resistance/immunity at both deliveries, recasts, expiry and source attribution. No BG3 version was found.

### Level 5 — 4

**Antilife Shell** — Druid. Pool: [SRD 5.1, p. 116](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=116). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose a moving, creature-type-filtered boundary. Constructs and Undead can cross; other creatures are kept out. Use existing requester-aware crossing checks rather than an opaque solid wall.

Reuse: `moving SpiritGuardians membership`; `WindWallZone.blocks_crossing_between`; `wall shell geometry`.

Boundary / interactions: Preserve ranged/reach attacks and casting through the barrier. Test the rule that moving the shell so a protected creature is forced through it ends the spell; test forced movement, teleportation and suppression. No BG3 implementation was found.

**Conjure Elemental** — Druid, Wizard. Pool: [SRD 5.1, p. 128](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=128). BG3: [Yes](https://bg3.wiki/wiki/Conjure_Elemental). Preferred profile: **BG3 style, SRD forms**.

Reuse the single autonomous allied summon lifecycle and authored elemental choices. New creature recipes, elemental attacks and local traits are content composition; creation, initiative, dismissal and defeat already exist.

Reuse: `SummonSpell`; `SummoningSystem`; `summon forms/recipes`; `NaturalAttack`; `elemental surfaces`.

Boundary / interactions: Form/loadout selection must stay within SRD content and the approved adaptation. BG3’s named variants or their non-SRD spells are not automatically eligible additions. The four base elemental bodies are new work; do not claim they already exist. Decide the higher-slot form list explicitly and test one-active-instance replacement and rest lifetime.

**Dispel Evil and Good** — Cleric, Paladin. Pool: [SRD 5.1, p. 136](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=136). BG3: [Yes](https://bg3.wiki/wiki/Dispel_Evil_and_Good). Preferred profile: **BG3**.

Reuse the self-protection condition and add BG3’s granted Break Enchantment action. BG3 removes the tabletop Dismissal branch, which would otherwise involve extra planar semantics.

Reuse: `ProtectionFromEvilAndGoodEffect`; `control-removal preparation`; `ConcentrationActionMarker`.

Boundary / interactions: Break only eligible source-owned charm/fear effects and finish the sustaining effect as specified. Do not claim a possession system exists; this branch only acts on effects the engine represents. Preserve all listed creature types rather than copying BG3’s aberration bug.

**Summon Dragon** — Wizard. Pool: [SRD 5.2 only, p. 166](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf#page=166). BG3: No documented shipped spell. Preferred profile: **5.2**.

Author the 5.2 Draconic Spirit recipe with retained caster attack/DC, slot-scaled health and attacks, resistance choices and a breath action. Reuse ordinary autonomous summoning and supported flight movement.

Reuse: `SummonSpell`; `SpellSummonParameters`; `NaturalAttack / MultiattackAction`; `breath AoE`; `Fly`.

Boundary / interactions: Test each elemental choice, slot scaling, multiple attacks, breath saves, concentration and defeat. No free hovering or separate flight project is implied. The spell is Wizard on the base 5.2 list; Draconic Sorcerer access is subclass access.

### Level 6 — 5

**Blade Barrier** — Cleric. Pool: [SRD 5.1, p. 122](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=122). BG3: [Yes](https://bg3.wiki/wiki/Blade_Barrier). Preferred profile: **BG3**.

Use a permeable damaging wall with Dexterity saves, slashing packets, difficult terrain and concentration. The wall geometry and contact lifecycle already exist.

Reuse: `WallFieldZone`; `WallOfThorns`; `WallDamageSpec`; `native difficult terrain`.

Boundary / interactions: Test cast appearance, entry/re-entry, turn exposure and overlap/suppression. Retain caster DC; do not copy BG3’s documented fixed-DC bugs or accidentally add Wall of Thorns’ opaque optics.

**Flesh to Stone** — Warlock, Wizard. Pool: [SRD 5.1, p. 145](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=145). BG3: [Yes](https://bg3.wiki/wiki/Flesh_to_Stone). Preferred profile: **BG3**.

Use the BG3 restrained stages followed by native Petrified. Store the stage and original save DC in a dedicated spell condition; the actual petrified transform already exists.

Reuse: `Restrained`; `Petrified`; `staged target-turn handlers`; `GreaterRestoration`.

Boundary / interactions: Test initial and subsequent saves, concentration loss at each stage, completed petrification, immunity, Greater Restoration, death and Antimagic. Verify the final save schedule before implementation; do not treat the tooltip as proof of a three-failure tabletop counter.

**Freezing Sphere** — Wizard. Pool: [SRD 5.1, p. 147](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=147). BG3: [Yes](https://bg3.wiki/wiki/Otiluke%27s_Freezing_Sphere). Preferred profile: **BG3**.

Support both BG3 choices: immediate cold explosion and a temporary portable sphere. The latter is a real transferable item with a throw action and timed explosion; use its current holder/floor position.

Reuse: `Fireball / ConeOfCold`; `CreatedItemsLifetime`; `AcidFlaskSpell`; `ice surfaces`; `item transfer lifecycle`.

Boundary / interactions: Test throw, transfer, drop, timed explosion while held, item destruction and exact-once retirement. Goodberry / Flame Blade provide item ownership, not an already-complete grenade. Preserve caster/DC attribution after transfer and apply normal cold/ice interactions.

**Irresistible Dance** — Bard, Wizard. Pool: [SRD 5.1, p. 158](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=158). BG3: [Yes](https://bg3.wiki/wiki/Otto%27s_Irresistible_Dance). Preferred profile: **BG3**.

Compose BG3’s no-initial-save control, later recovery saves, attacker advantage and Dexterity-save disadvantage, using a separate condition.

Reuse: `HideousLaughterEffect`; `native action/movement denial`; `advantage modifiers`; `concentration`.

Boundary / interactions: Honor charm immunity; test later saves and all action channels. Do not reuse Paralyzed wholesale: automatic Strength/Dexterity failures and automatic melee criticals are not dance effects. Do not copy the old BG3 no-repeat-save bug.

**Planar Ally** — Cleric. Pool: [SRD 5.1, p. 168](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=168). BG3: [Yes](https://bg3.wiki/wiki/Planar_Ally). Preferred profile: **BG3 style, SRD forms**.

Use BG3’s direct allied combat summon rather than negotiation/payment roleplay. Author eligible celestial/elemental/fiend forms using SRD bodies, supported traits and SRD spell loadouts.

Reuse: `SummonSpell`; `SummoningSystem`; `existing fiend recipes`; `native spell grants, healing and natural attacks`.

Boundary / interactions: Actual BG3 Djinni/Deva/Cambion loadouts include non-SRD spells; those are not approved dependencies. Agree the SRD-valid form list before implementation. New bodies are content work, not existing assets. Test autonomous actions, rest/recast cleanup and exact ownership.

### Level 7 — 3

**Arcane Sword** — Bard, Wizard. Pool: [SRD 5.1, p. 119](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=119). BG3: No documented shipped spell. Preferred profile: **5.1**.

Use an invulnerable spatial sword anchor plus the caster’s granted bonus action to move it and make a melee spell attack from its position. Reuse Spiritual Weapon’s attack math, not its autonomous creature behavior.

Reuse: `DancingLightsEffect / MoveDancingLights`; `Moonbeam relocation`; `SpiritualWeaponStrike`; `spell-attack pipeline`.

Boundary / interactions: The 5.1 sword consumes the caster’s bonus actions and has no creature HP pool. Test first-cast attack, movement and attack range, concentration, target visibility and Antimagic at the sword/target. No BG3 implementation was found.

**Delayed Blast Fireball** — Sorcerer, Wizard. Pool: [SRD 5.1, p. 133](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=133). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose a persistent bead/payload, caster-turn damage growth and an exact-once explosion when released or concentration ends. Use the existing item/condition/event owners for touching and throwing it.

Reuse: `GlyphOfWarding trigger payload`; `Fireball`; `created-item ownership`; `concentration-removal handlers`.

Boundary / interactions: Test voluntary release, involuntary concentration loss, successful/failed touch saves, transfer/throw, expiry and suppression. Do not silently reduce it to a delayed automatic Fireball; the interactable bead is part of the spell.

**Forcecage** — Bard, Warlock, Wizard. Pool: [SRD 5.1, p. 147](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=147). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose non-concentration force enclosure variants with native wall boundaries and a Charisma-save gate on magical escape. Preserve the difference between barred cage and sealed box.

Reuse: `WallOfForceZone / SolidWallZone`; `WallRing / shell geometry`; `PortalTransferEvent`; `Banishment placement/removal admission`.

Boundary / interactions: Test projectile and spell propagation per variant, visibility, too-large occupants, blocked formation, teleport success/failure and removal. No BG3 spell was found. This is more demanding than another damaging wall, but does not need general planar travel.

### Level 8 — 2

**Feeblemind** — Bard, Druid, Warlock, Wizard. Pool: [SRD 5.1, p. 142](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=142). BG3: No documented shipped spell. Preferred profile: **5.1**.

Use 5.1 Feeblemind: psychic damage, Intelligence save, source-owned Intelligence/Charisma score constraints and magical activation/casting denial. Existing score constraints avoid replacing the entity or its entire stat block.

Reuse: `ability-score min/max constraints in ModifiableValue`; `spell/item admission`; `GreaterRestoration / Heal`.

Boundary / interactions: Honor Heal and Greater Restoration cures and normal source removal. Test score buffs/items, nonmagical attacks and disabled magic items. Preserve the long recovery interval using native time conventions; do not invent a short combat duration. Befuddlement is its 5.2 rename, not another spell.

**Holy Aura** — Cleric. Pool: [SRD 5.1, p. 155](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=155). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose the fixed set of allies chosen in the initial radius, their light/save/defense buffs and the fiend/undead melee-hit blindness retaliation.

Reuse: `Bless save modifiers`; `Blur attacker disadvantage`; `Light`; `FireShield retaliation`; `Blinded`.

Boundary / interactions: The 5.1 recipients are selected on casting; this is not a moving aura that constantly adds/removes allies. Test concentration links, successful hits versus misses, natural/unarmed/weapon melee, ranged exclusion and blinded immunity.

### Level 9 — 3

**Foresight** — Bard, Druid, Warlock, Wizard. Pool: [SRD 5.1, p. 147](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=147). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose attack/check/save advantage, attacker disadvantage, single-active-cast ownership and a narrow surprise-immunity contribution checked by encounter startup.

Reuse: `EnhanceAbility / Bless / Blur`; `native source-owned modifiers`; `Encounter surprise admission`.

Boundary / interactions: Test every check/save/attack family, overlapping advantage, replacing the previous cast and both surprise turn-skip and reaction lockout paths. A condition name alone does not bypass the current CombatantState.surprised flag.

**Power Word Heal** — Bard, Cleric. Pool: [SRD 5.2 only, p. 154](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf#page=154). BG3: No documented shipped spell. Preferred profile: **5.2**.

Fully heal one living recipient, clear exactly the 5.2 listed charm/fear/paralysis/poison/stun conditions and offer a reaction-funded stand from Prone.

Reuse: `HealSpell / MassHeal`; `GreaterRestoration`; `explicit control removals`; `native StandUp and reactions`.

Boundary / interactions: Test NoHealing, dead versus downed, each listed condition, unrelated conditions, reaction availability and stand-up cost. Keep the prone reaction separate from free global prone removal. No BG3 version was found.

**Weird** — Wizard. Pool: [SRD 5.1, p. 192](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf#page=192). BG3: No documented shipped spell. Preferred profile: **5.1**.

Compose a 30-foot sphere’s initial Wisdom saves with separate frightened/psychic damage-over-time recipients and end-turn recovery. Keep 5.1 rules because no BG3 Weird implementation was found.

Reuse: `Fear / HypnoticPattern multi-recipient concentration`; `PhantasmalForceEffect ticks`.

Boundary / interactions: Do not silently turn it into mass BG3 Phantasmal Killer: 5.1 frightened movement and the save-before-damage order remain. Test recipient-by-recipient removal, fear immunity, Heroism / Calm Emotions and concentration.

## The six additional 5.2 spells at these levels

| Spell | Level | Classes in 5.2 | Rank |
| --- | ---: | --- | ---: |
| Aura of Life | 4 | Cleric, Paladin | 2 |
| Charm Monster | 4 | Bard, Druid, Sorcerer, Warlock, Wizard | 1 |
| Vitriolic Sphere | 4 | Sorcerer, Wizard | 2 |
| Summon Dragon | 5 | Wizard | 2 |
| Tsunami | 8 | Druid | 4 |
| Power Word Heal | 9 | Bard, Cleric | 2 |

Feeblemind → Befuddlement is a rename and counts once, under 5.1 Feeblemind. Branding Smite → Shining Smite is also a rename, at level 2 and outside this audit. Shared spell names with rewritten 2024 mechanics are not “new 5.2 spells.” In particular, Giant Insect and Conjure Celestial do not automatically take their easier rewritten 5.2 profiles when 5.1 has priority.

Class lists above follow the preferred 5.1 profile for existing names and 5.2 for new names. For reference, 5.2 additionally gives Bard access to Phantasmal Killer, Sorcerer access to Freezing Sphere, and Warlock access to Weird; its Flesh to Stone list is Druid/Sorcerer/Wizard rather than 5.1 Warlock/Wizard. These class-list revisions are not additional spell identities or an implicit class-rules migration.

## Rank 3 — missing capabilities; not included in the 22

### Level 4 — 10

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Arcane Eye | Wizard | No documented shipped spell | A remote movable sensory origin and its information ownership are missing; a light anchor or summon alone does not give the caster the eye’s observations. |
| Compulsion | Bard | No documented shipped spell | Needs a sustained directional movement policy and safe-route handling; one immediate push or Command: Flee is not the full spell. |
| Confusion | Bard, Druid, Sorcerer, Wizard | [Yes](https://bg3.wiki/wiki/Confusion) | BG3 simplifies outcomes, but still needs temporary everyone-hostile targeting, a random-target AI policy and reliable turn control/restoration. |
| Conjure Minor Elementals | Druid, Wizard | [Yes](https://bg3.wiki/wiki/Conjure_Minor_Elemental) | BG3 has paired mephits as well as an Azer. The current one-birth-per-cast summon admission has no atomic multi-body cast/placement/cleanup. Do not count an Azer-only subset as the whole spell. |
| Conjure Woodland Beings | Druid, Ranger | [Yes](https://bg3.wiki/wiki/Conjure_Woodland_Being) | BG3 includes Dryad → Wood Woad summoning and an independently surviving child. The current rebind requires the immediate summoner in the next encounter; separating persistent ownership from the dead Dryad’s creation identity needs a small lifecycle extension. The aura and attacks themselves reuse existing systems. |
| Dominate Beast | Druid, Sorcerer | [Yes](https://bg3.wiki/wiki/Dominate_Beast) | BG3 ally AI avoids telepathic command language, but a reversible allegiance/controller owner for an existing creature, including human-controlled targets and conflicting casts, is not implemented. |
| Faithful Hound | Wizard | No documented shipped spell | The static bite is easy; a caster-private invisible sentry with its own sensing/barking/password recognition is not an ordinary current summon or light. |
| Locate Creature | Bard, Cleric, Druid, Paladin, Ranger, Wizard | No documented shipped spell | Requires location tracking/disclosure without leaking subjective hidden entity data; current perception is not an unrestricted target registry API. |
| Polymorph | Bard, Druid, Sorcerer, Wizard | [Yes](https://bg3.wiki/wiki/Polymorph) | BG3 sheep-only is much smaller than arbitrary beast selection, but still requires reversible form/action/stat and separate form-HP ownership. Temporary HP or killing/replacing the entity is not an equivalent. |
| Private Sanctum | Wizard | No documented shipped spell | Some attack/teleport blocking is reusable; the full ward also needs sound, remote-sensor and planar detection privacy boundaries. |

### Level 5 — 9

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Animate Objects | Bard, Sorcerer, Wizard | No documented shipped spell | Summoning exists, but converting selected existing objects into a group and restoring their identities/remaining damage is new state ownership. |
| Arcane Hand | Wizard | No documented shipped spell | The four modes share forced movement/grapple/attack pieces, but need one movable attackable object with caster-funded commands, interposition and grapple ownership; an autonomous creature summon would change its action economy and targeting. |
| Contagion | Cleric, Druid | [Yes](https://bg3.wiki/wiki/Contagion) | Save-stage counters and most conditions are easy; the full BG3 set also includes Mindfire’s confused hostile behavior, shared with the missing control-policy work. |
| Dominate Person | Bard, Sorcerer, Wizard | [Yes](https://bg3.wiki/wiki/Dominate_Person) | Same reversible existing-creature allegiance/controller need as Dominate Beast; BG3 does not make it a new summon. |
| Mislead | Bard, Wizard | No documented shipped spell | Needs a controlled illusory double with remote sensory exchange; ordinary invisibility only covers one half. |
| Passwall | Wizard | No documented shipped spell | Needs reversible terrain openings, original geometry ownership and safe closure around occupants, not just object destruction. |
| Planar Binding | Bard, Cleric, Druid, Wizard | [Yes](https://bg3.wiki/wiki/Planar_Binding) | BG3 avoids long-term command semantics, but still needs reversible control of an existing creature and interaction with its summon ownership. |
| Raise Dead | Bard, Cleric, Paladin | No documented shipped spell | Revival is now native. Death age/body eligibility, long casting and the diminishing long-rest penalty remain new state and rules. |
| Tree Stride | Druid, Ranger | No documented shipped spell | Teleport primitives exist, but eligible tree anchors, tree type matching and entrance/exit ownership are missing. |

### Level 6 — 4

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Create Undead | Cleric, Warlock, Wizard | [Yes](https://bg3.wiki/wiki/Create_Undead) | BG3’s one mummy removes group creation difficulty. Corpse selection and summoning exist, but consuming/claiming the exact corpse atomically does not; prevent repeated raising and Revivify of a consumed body. The mummy’s rot/curse package is also new content. |
| Forbiddance | Cleric | No documented shipped spell | Creature-type damage zones are reusable; a selectable persistent travel ward with password and long-duration/permanence rules still needs bounded ward/zone authoring. |
| Instant Summons | Wizard | No documented shipped spell | Exact item ownership exists, but persistent marking, remote retrieval and holder/location disclosure need additional item/location policy. |
| Wind Walk | Druid | [Yes](https://bg3.wiki/wiki/Wind_Walk) | BG3’s bounded mist form helps; reusable form ownership, action replacement, equipment/size/stat overlay and safe restoration are still missing. |

### Level 7 — 5

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Conjure Celestial | Cleric | No documented shipped spell | Summon lifecycle is ready. Decide and author the legal CR4/CR5 celestial form repertoire and its unsupported traits before calling this rank 2; BG3’s level-6 Deva scroll is not this SRD spell and must not replace it silently. |
| Fire Storm | Cleric, Druid, Sorcerer | No documented shipped spell | Needs connected freely arranged cube selection/preview and a deduplicated union of recipients. Current compound positions mean a length-limited path, not a general multi-area selection. |
| Project Image | Bard, Wizard | No documented shipped spell | Remote illusory viewpoint/sensory ownership is missing; not satisfied by a normal creature duplicate. |
| Resurrection | Bard, Cleric | No documented shipped spell | Native revival is a strong base, but age/body restoration, long casting and caster/recipient recovery penalties need state beyond Revivify. |
| Symbol | Bard, Cleric, Wizard | No documented shipped spell | Glyph is now a good foundation. The complete payload set and trigger semantics include insanity/discord behaviors that need the missing control policy; do not count only its easy damage/sleep options. |

### Level 8 — 5

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Antipathy/Sympathy | Druid, Wizard | No documented shipped spell | Requires persistent attract/repel movement policy, eligible creature-kind matching, repeat exposure and temporary immunity ownership. |
| Dominate Monster | Bard, Sorcerer, Warlock, Wizard | No documented shipped spell | Shares the reversible allegiance/controller requirement with Dominate Beast/Person; remains rank 3 in the current engine. |
| Glibness | Bard, Warlock | No documented shipped spell | A check-roll floor can use native roll replacement, but generic Charisma check identity is not retained everywhere; Counterspell currently calls random.randint directly. Shared check routing is needed to avoid a social-skill-only fake implementation. |
| Maze | Wizard | No documented shipped spell | Banishment return placement is reusable, but Entity.has_runtime_agency is false for every spatially suspended actor, and BaseAction rejects it before discovery/execution. A mazed target must still choose and pay for an escape check: this requires a small explicit off-map agency/action capability, not an exception hidden inside a spell handler. |
| Mind Blank | Bard, Wizard | No documented shipped spell | Psychic/charm immunity is easy. Complete divination immunity also needs a school/source-aware target/detection ward, including ongoing Hunter’s Mark and future remote sensors; the existing Globe registry is level/position based. |

### Level 9 — 3

| Spell | Classes | BG3 | Why it stays above rank 2 |
| --- | --- | --- | --- |
| Meteor Swarm | Sorcerer, Wizard | No documented shipped spell | Damage packets exist, but four independent centers plus one-hit-per-creature union, discovery and area preview need a real multi-area targeting contract. Reusing the wall path would impose invented distance/path constraints. |
| Prismatic Wall | Wizard | No documented shipped spell | Needs independently removed color layers, per-layer crossing saves and specific interaction/removal predicates; ordinary Wall of Force is not the seven-layer spell. |
| Storm of Vengeance | Druid | No documented shipped spell | Most individual weather/damage pieces exist. Ten-phase automatic state, round-three target choice, object damage and unified storm attack/concentration policies need a bounded staged area owner; not counted as a simple cloud clone. |

The best shared follow-ups are: independent multi-area selection (Fire Storm and Meteor Swarm); reversible allegiance/controller ownership (Dominate Beast, Dominate Person, Dominate Monster and Planar Binding, with Confusion/Contagion needing their own AI policy); corpse claims (Create Undead); grouped/nested summon ownership (Minor Elementals and Woodland Beings). These are capability opportunities, not extra approved implementation scope.

## Rank 4 — full exclusions from this batch

### Level 4 — 7

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Control Water | Cleric, Druid, Wizard | No documented shipped spell | Volumetric water levels, flows, floods and whirlpools are not the current surface model. |
| Divination | Cleric | No documented shipped spell | The useful answer is narrative/GM adjudication. |
| Fabricate | Wizard | No documented shipped spell | General object fabrication/material conversion is not a fixed temporary-item spell. |
| Giant Insect | Druid | No documented shipped spell | 5.1 transforms several existing insects; reversible body/stat ownership and multiple transformed subjects are missing. Its easier 5.2 single summon does not override the stated source preference. |
| Hallucinatory Terrain | Bard, Druid, Warlock, Wizard | No documented shipped spell | False terrain must affect perception and belief separately from actual navigation/support. |
| Secret Chest | Wizard | No documented shipped spell | Persistent extradimensional storage and retrieval need world/inventory ownership outside current encounters. |
| Stone Shape | Cleric, Druid, Wizard | No documented shipped spell | Arbitrary permanent geometry, passages and shaped objects need world editing beyond authored wall placement. |

### Level 5 — 15

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Awaken | Bard, Druid | No documented shipped spell | Permanent intelligence/language and personality/obedience changes involve narrative creature creation. |
| Commune | Cleric | No documented shipped spell | GM/deity question-answer adjudication. |
| Commune with Nature | Druid, Ranger | No documented shipped spell | World knowledge and narrative environmental answers. |
| Contact Other Plane | Warlock, Wizard | No documented shipped spell | Planar questions/adjudication rather than current combat mechanics. |
| Creation | Sorcerer, Wizard | No documented shipped spell | Arbitrary user-described materials/objects and their variable lifetimes need fabrication/world modeling. |
| Dream | Bard, Warlock, Wizard | No documented shipped spell | Dream encounters and message/narrative resolution. |
| Geas | Bard, Cleric, Druid, Paladin, Wizard | No documented shipped spell | Understood commands and compliance adjudication are the central effect. |
| Hallow | Cleric | No documented shipped spell | The full persistent site ward includes language, travel and creature-entry choices beyond a combat-only fear/resistance aura. |
| Legend Lore | Bard, Cleric, Wizard | No documented shipped spell | Narrative lore generation/knowledge. |
| Modify Memory | Bard, Wizard | No documented shipped spell | Editing remembered events and interpreting behavior is not an engine combat condition. |
| Reincarnate | Druid | No documented shipped spell | New body/ancestry identity and restoration are much broader than native corpse revival. |
| Scrying | Bard, Cleric, Druid, Warlock, Wizard | No documented shipped spell | Remote world targets, familiarity and cross-location information disclosure exceed an encounter-local camera. |
| Seeming | Bard, Sorcerer, Wizard | [Yes](https://bg3.wiki/wiki/Seeming) | BG3 has disguises, but identity/social recognition and per-observer illusion inspection are absent; a changed name/sprite is insufficient. |
| Telepathic Bond | Wizard | No documented shipped spell | Language-independent telepathic communication needs a communication/narrative layer. |
| Teleportation Circle | Bard, Sorcerer, Wizard | No documented shipped spell | Persistent destination registry and cross-map/world transfer. |

### Level 6 — 9

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Contingency | Wizard | No documented shipped spell | Arbitrary declared circumstances plus suspended chosen-spell execution require a trigger language/adjudicator. |
| Find the Path | Bard, Cleric, Druid | No documented shipped spell | A known destination across the world and supernatural route guidance exceed local pathfinding. |
| Guards and Wards | Bard, Wizard | No documented shipped spell | A fully configurable persistent building ward, doors, stairs, illusions and conditional extras exceed current area composition. |
| Magic Jar | Wizard | No documented shipped spell | Possession, retained class features, alternate bodies and soul/death restoration require major identity/control ownership. |
| Mass Suggestion | Bard, Sorcerer, Warlock, Wizard | No documented shipped spell | Natural-language instructions and reasonable-course adjudication. |
| Move Earth | Druid, Sorcerer, Wizard | No documented shipped spell | Large-scale terrain excavation/support/height changes. |
| Programmed Illusion | Bard, Wizard | No documented shipped spell | Arbitrary sensory scenes and user-declared activation circumstances need illusion/trigger systems. |
| Transport via Plants | Druid | No documented shipped spell | Cross-world travel and familiar plant destination registry. |
| Word of Recall | Cleric | No documented shipped spell | Sanctuary registry and cross-location group travel. |

### Level 7 — 8

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Etherealness | Bard, Cleric, Sorcerer, Warlock, Wizard | No documented shipped spell | A second overlapping plane with distinct support, collision and perception. |
| Magnificent Mansion | Bard, Wizard | No documented shipped spell | Persistent extradimensional rooms, entrance travel, servants and provisions. |
| Mirage Arcane | Bard, Druid, Wizard | No documented shipped spell | Large perceived-and-interactable false terrain with real movement implications. |
| Plane Shift | Cleric, Druid, Sorcerer, Warlock, Wizard | No documented shipped spell | Cross-plane transfer and destination identity; combat banishment alone would discard the travel spell. |
| Reverse Gravity | Druid, Sorcerer, Wizard | No documented shipped spell | Free vertical trajectories, falling and suspended bodies; the separate multi-floor/flight work is not implemented. |
| Sequester | Wizard | No documented shipped spell | Stasis, aging and arbitrary future waking triggers plus anti-scrying privacy. |
| Simulacrum | Wizard | No documented shipped spell | A constrained creature duplicate must preserve identity, limited spell resources, recovery restrictions and ownership without copied runtime UUID graphs. |
| Teleport | Bard, Sorcerer, Wizard | No documented shipped spell | World destinations, familiarity, mishaps and group transfers; a same-map teleport would omit its core purpose. |

### Level 8 — 6

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Animal Shapes | Druid | No documented shipped spell | Multiple reversible beast bodies, equipment/class features and form HP. |
| Clone | Wizard | No documented shipped spell | Long-term maturing backup bodies, soul transfer and world persistence. |
| Control Weather | Cleric, Druid, Wizard | No documented shipped spell | Large regional weather, gradual progression and travel/environment simulation. |
| Demiplane | Warlock, Wizard | No documented shipped spell | Persistent separate spaces and portals across them. |
| Earthquake | Cleric, Druid, Sorcerer | No documented shipped spell | Terrain fissures, collapsing structures, falling and burial/escape physics. |
| Tsunami | Druid | No documented shipped spell | The 5.2 moving tall wave carries/swims/lifts creatures and changes dimensions; ordinary wet terrain plus push would omit its core behavior. |

### Level 9 — 8

| Spell | Classes | BG3 | Reason |
| --- | --- | --- | --- |
| Astral Projection | Cleric, Warlock, Wizard | No documented shipped spell | Separate projected bodies, cords, planar travel and death/soul rules. |
| Gate | Cleric, Sorcerer, Wizard | No documented shipped spell | Interplanar portal destinations and named-being summoning/adjudication. |
| Imprisonment | Warlock, Wizard | No documented shipped spell | Multiple prisons, long-term existence and arbitrary release conditions. |
| Shapechange | Druid, Wizard | No documented shipped spell | Arbitrary high-CR reversible creature forms with retained class/mental rules. |
| Time Stop | Sorcerer, Wizard | No documented shipped spell | Reentrant turn scheduling, other-entity effect detection and early termination; Haste resources are not extra isolated turns. |
| True Polymorph | Bard, Warlock, Wizard | No documented shipped spell | Creature/object conversions, persistent identity changes and arbitrary forms. |
| True Resurrection | Cleric, Druid | No documented shipped spell | Bodiless recreation and long-term identity/soul restoration go beyond current native revival. |
| Wish | Sorcerer, Wizard | No documented shipped spell | Arbitrary spell duplication and open-ended GM effects; no BG3 adaptation removes that scope. |

## Current implemented level-4–9 inventory

- **Level 4 (12):** Banishment; Black Tentacles; Blight; Death Ward; Dimension Door; Fire Shield; Freedom of Movement; Greater Invisibility; Guardian of Faith; Ice Storm; Stoneskin; Wall of Fire.

- **Level 5 (10):** Cloudkill; Cone of Cold; Flame Strike; Greater Restoration; Hold Monster; Insect Plague; Mass Cure Wounds; Telekinesis; Wall of Force; Wall of Stone.

- **Level 6 (13):** Chain Lightning; Circle of Death; Conjure Fey; Disintegrate; Eyebite; Globe of Invulnerability; Harm; Heal; Heroes' Feast; Sunbeam; True Seeing; Wall of Ice; Wall of Thorns.

- **Level 7 (4):** Divine Word; Finger of Death; Prismatic Spray; Regenerate.

- **Level 8 (4):** Antimagic Field; Incendiary Cloud; Power Word Stun; Sunburst.

- **Level 9 (2):** Mass Heal; Power Word Kill.

Black Tentacles is the one entry above with native code but no public catalog root. The other 44 are public catalog roots. Existing implementation fidelity may have deliberate adaptations (for example Finger of Death); this audit measures presence and uses current capabilities as references, rather than silently certifying every existing spell against every SRD clause.

## Why some old exclusions changed and others did not

The historical `agent_docs/to_archive/claude_docs/SORCERER_SPELL_ANALYSIS.md` “Systems Status” and the archived `SORCERER_SPELL_SYSTEM.md` “Not Implementing” table classified all summoning, domination, confusion and polymorph as unavailable. Their blanket summoning blocker is superseded by the current native summon lifecycle. It does not prove group summons, object animation, possession or form replacement exist. The historical Wall of Fire / Wall of Stone blockers are also superseded by native wall fields and real sections.

Relevant current source anchors:

| Capability | Current repository reference | Audit consequence |
| --- | --- | --- |
| Current inventory | `dnd/content_system/spell_catalog_composition.py:SpellCatalogCompositionRow` | 166 composed public spell roots; include reactions/extensions rather than counting only school classes. |
| Single-body summons | `dnd/summoning/system.py:SummoningSystem; dnd/summoning/forms.py` | Birth, deployment, initiative, AI, concentration and retirement exist; one committed birth per cast and immediate-summoner rebind are real limits. |
| Summon provenance | `dnd/types/summoning.py:SummonOrigin` | Creation/continuing anchor is one summoner UUID; independently surviving nested ownership is not yet a demonstrated reusable contract. |
| Physical/magical attack packets | `dnd/spells/hit_effects.py; dnd/core/events.py:DamageRollResultEvent` | Use existing hit/source ownership; do not replace native attacks with invented damage delivery. |
| Temporary items | `dnd/items/created_items.py; dnd/spells/transmutation.py:GoodberryBatch; dnd/items/spell_items.py:AcidFlaskSpell` | Creation, transfer and retirement are reusable; timed detonation and its source/location still need spell-specific glue. |
| Wall geometry and damage | `dnd/spells/wall_fields.py:WallFieldZone; dnd/spells/wall_constructions.py:SolidWallZone` | Blade Barrier, typed Antilife boundaries and force enclosure composition have concrete native references. |
| Compound positions | `dnd/core/action_types.py:PositionPathSelection; dnd/core/base_actions.py:position_selection_error` | Current multiple points are path vertices with segment/length restrictions, not independent AoE centers. |
| Score constraints | `dnd/core/values.py:add_min_constraint / add_max_constraint; dnd/blocks/abilities.py` | Feeblemind can constrain two scores without body/stat replacement. |
| Control and sensory conditions | `dnd/conditions.py; dnd/creature_transforms.py; dnd/spells/enchantment.py` | Separate spell conditions, immunity aliases, action denial and removal preparation exist; a controller takeover policy does not. |
| Allegiance changes | `dnd/entity.py:set_faction` | A factual faction change exists; reversible competing control sources and player/controller transfer are not implied. |
| Petrification | `dnd/conditions.py:Petrified; dnd/spells/abjuration.py:GreaterRestoration` | Flesh to Stone needs staged saves/content, not a new petrification engine. |
| Revival/remains | `dnd/entity.py:prepare_revival / commit_revival; dnd/core/life_types.py:RemainsDisposition` | Intact/disintegrated remains and revival exist; corpse consumption, body restoration and death-age clocks are not present. |
| Typed modifiers/roll replacement | `dnd/core/events.py:SkillCheckD20RollResultEvent; dnd/spells/abjuration.py:try_counterspell` | Generic check events lack full ability context; Counterspell still bypasses them with random.randint, so Glibness is not a trivial existing floor. |
| Surprise | `dnd/encounter.py:_apply_surprise_reaction_lockouts / start_turn` | Foresight requires checking immunity in both paths; advantage modifiers alone are incomplete. |
| Protection | `dnd/core/base_conditions.py:SpellProtectionRegistry; dnd/spells/abjuration.py` | Existing protection is level/position based. Integrate ordinary policies; do not redesign Globe or Antimagic as incidental work. |

## Decisions to carry into a later implementation plan

1. **Summon form lists:** use only SRD spell identities and SRD-valid spell dependencies. BG3 is the behavioral model, not permission to import its full summon ability catalogue. Agree elemental upgrades, Draconic Spirit scaling and Planar Ally bodies/loadouts explicitly.
2. **Resilient Sphere:** settle the exact BG3-style incoming/outgoing effect boundary, including healing and already-running effects, before implementation. Its rank-2 estimate assumes bounded condition/action/damage handlers, not a generalized spatial shell redesign.
3. **Off-map Maze escape:** held at rank 3 because suspended actors have no runtime agency. Any future support needs an explicit owned action capability; do not hide a bypass in a condition handler.
4. **Delayed/portable payloads:** retain actual bead/item interaction and exact source attribution; do not delete the inconvenient interaction branches to keep the rank.
5. **Long recovery/duration rules:** follow existing native time/rest conventions. No fake per-spell calendar or arbitrary shortened Feeblemind duration.
6. **No source fallback for convenience:** a 5.2 rewrite does not outrank 5.1 merely because it is easier. Any such change needs a human decision.
7. **Qualification:** a later implementation plan must include observable per-spell acceptance and interaction cases, anti-slop and anti-OOP reviewers, and the plan-adherence sub-agent required by AGENTS.md. This audit does not claim those future implementation reviews or gameplay tests have already happened.

## Sources and verification limits

The 5.1 census uses the checked-in 319-entry spell source ledger for names and freshly extracted official PDF headings for levels. Class lists were read from the official 5.1 spell lists; the six added 5.2 spell names/levels/classes were checked against its official descriptions and the publisher’s new-spell list. Base-class lists are shown; subclass extensions and Bard Magical Secrets are not expanded into every row.

Official sources: [SRD 5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf), [SRD 5.2](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf), and the publisher’s [SRD conversion guide, spell changes](https://media.dndbeyond.com/compendium-images/srd/guide/converting-to-srd-5.2.1.pdf#page=11). The repository pins 5.2; the newer 5.2.1 publication was not silently substituted. This work includes spell names/classification and original engineering analysis of material from SRD 5.1 and SRD 5.2 by Wizards of the Coast LLC, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

BG3 presence was cross-checked against the [shipped spell inventory](https://bg3.wiki/wiki/List_of_all_spells) and linked spell pages, including relevant condition/variant details. [Cut-content descriptions](https://bg3.wiki/wiki/Spells/Cut_content) are not evidence of a shipped implementation. Named/portable/upcast variants count under the one SRD root. NPC/item availability alone would not exclude a genuine implementation; no additional missing SRD roots at levels 7–9 were found there. The already-present Finger of Death and Power Word Kill are examples of high-level spells BG3 does implement through special availability.

This was a source/catalog/documentation audit. Census assertions check unique names, source union, implemented/missing partitions and every difficulty assignment. No engine or client code was changed, and no new gameplay test run is claimed.
