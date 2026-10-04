# Goblin roster — required part of the final summoning/Fly phase

Date: 2026-10-03. Implementation authorized by the human.
Both remaining proposals were explicitly accepted: single-combatant riders and
Goblin17’s ordinary pistol. Current validation is recorded in the implementation ledger. This document is a required part of
[the final-phase plan](SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md), with the same
implementation checkpoints, final reviews and acceptance criteria.

## Scope and evidence precedence

Account for all **17 dedicated Goblin sheets** from `2D Orcs and Goblins - TopDown -
V1.0.zip`. Goblin01 already has a registered body rig; 02–17 do not. All use their
original proportions at **visual_scale 1.00**. Source cell dimensions and gameplay
Size are separate facts. No bounding-box normalization, resizing source files,
new weapon art, Orc port, broader roster expansion or new summoning choices.

Use the exact source/gear/animation crosswalk in
[audits/GOBLIN_ART_CROSSWALK_2026-10-03.md](audits/GOBLIN_ART_CROSSWALK_2026-10-03.md).
It is evidence and an implementation checklist, not a second runtime registry.
The latest item-first handoff and completed item-material receipts override older
bible labels. The approved ability dispositions override speculative signatures:
Disrupting Shot, entry-triggered Brace, Crossing Blades' no-reactions rider and
Driving Blow's free push do **not** return through this port.

Observed corrections: 08 holds a staff; 10 a trident; 13 a club; 14 a morningstar;
16 a shortsword and shield. **17 needs a correction to the item receipt:** its
scimitar is confirmed, but Attack5 body plus separate effects show one-handed
pointing/discharge with muzzle flash and smoke, not a bow draw. The earlier
Shortbow match is not accepted as verified art evidence. Names and UI must
reflect the corrected selection below. Purple clothing or colored cast artwork does not by
itself add psychic damage, poison, enchantments or resistance.

## 1. Identity, scale and existing Goblins

The currently registered dedicated Goblin01 has canonical ref
`content.neurodragon:creature:creature.goblin@1`. Keep that identity and adapt its
**authored default possessions** to the inspected axe skirmisher. Add sixteen
named ordinary creature recipes, rather than a duplicate second Goblin01. The
existing recipe's contract shape does not change. Materialized saved item
instances retain their identity/gear; this is a change to newly constructed
canonical content, not a rewrite of existing inventories.

Retain `GoblinParameters.weight` and the public
`BESTIARY_CREATURE_RECIPES_BY_ID["goblin"]` export unchanged. The raw modular `create_goblin`, `creature.goblin_archer` and
`creature.goblin_caster` remain available with their current kits and modular
presentation. Do not repurpose these two variants as the new fixed archers/mages.
No global change to `GOBLIN_APPEARANCE` or Size scaling. The bounded correction
already made in `bestiary_content._build_goblin` sets dedicated Goblin01 to 1.00;
materialization verified Goblin01=1.00, modular archer/caster=0.82. All new fixed
Goblin definitions explicitly choose 1.00 as well.

New refs use pack `content.neurodragon`, kind `creature`, version 1. Table IDs
below are semantic content IDs; vendor sheet numbers occur in client bindings
and source receipts, not native action dispatch.

## 2. Complete character, gear and ability selection

The table lists combat gear. Every cosmetic garment, bracer, boot, hat, quiver
and saddle in the crosswalk is also a real possession with its listed material
variant. Do not silently omit those items or add unseen backup weapons.

Profiles are defined below. Features use their existing native owners. `Nimble`
means bonus-action Hide/Disengage sharing the actual bonus-action budget.
`Protection` means existing FightingStyleProtection, with its actual shield,
visibility, adjacency and reaction rules. `Dual` means one configured Multiattack
containing main-hand Attack then off-hand Attack against its selected target.

| Art | Character / content ID | Profile | Actual weapon slots | Existing ability selection |
| --- | --- | --- | --- | --- |
| 01 | Ashhook, axe skirmisher / `creature.goblin` | G | Handaxe main; other hand empty | Nimble; ordinary axe Attack |
| 02 | Wispbinder, web mage / `creature.goblin_wispbinder` | C | Empty hands | Explicit caster list below; no weapon invented |
| 03 | Reedshot, archer / `creature.goblin_reedshot` | G | Shortbow ranged main; quiver backpack | Nimble; ordinary bow Attack |
| 04 | Buckler Rat, shield duelist / `creature.goblin_buckler_rat` | G | Scimitar main; Shield off | Nimble; ordinary Attack |
| 05 | Longpoint, spear skirmisher / `creature.goblin_longpoint` | G | Spear main; other hand empty | Nimble; actual spear rules, no reach from painted length |
| 06 | Ironhide, shield guard / `creature.goblin_ironhide` | G | Shortsword main; Shield off | Nimble + Protection |
| 07 | Briarling, paired-blade skirmisher / `creature.goblin_briarling` | G | Shortsword main; Dagger off | Nimble + Dual; no additional no-reactions condition |
| 08 | Redcap, staff web mage / `creature.goblin_redcap` | C | Quarterstaff main; other hand empty | Explicit caster list; ordinary staff Attack |
| 09 | Quicktail, bow raider / `creature.goblin_quicktail` | G | Shortbow ranged main; quiver backpack | Nimble; ordinary Attack; Disrupting Shot deferred |
| 10 | Spearline, trident guard / `creature.goblin_spearline` | G | Trident main; other hand empty | Nimble; ordinary opportunity attack, no entry Brace |
| 11 | Packtrail, mounted shield scout / `creature.goblin_packtrail` | R* | Handaxe main; Shield off; saddle inventory | Protection; bounded mounted-art decision below |
| 12 | Ashhide, armored mounted scout / `creature.goblin_ashhide` | R* | Handaxe main; Shield off; saddle inventory | Protection; armor scraps and bounded mounted-art decision |
| 13 | Thornrunner, club enforcer / `creature.goblin_thornrunner` | G | Club main; other hand empty | Nimble; ordinary Attack or independently chosen Shove |
| 14 | Buckler Hex, shield fighter / `creature.goblin_buckler_hex` | G | Morningstar main; Shield off | Nimble + Protection; name does not grant Hex |
| 15 | Gloomplate, paired-axe bruiser / `creature.goblin_gloomplate` | B | Two separate Handaxes, main/off | Existing Brute and Surprise Attack + Dual; no Nimble by default |
| 16 | Mossbreaker, shield skirmisher / `creature.goblin_mossbreaker` | G | Shortsword main; Shield off | Nimble; not an unarmed brawler |
| 17 | Gutterknife, sword-and-shot raider / `creature.goblin_gutterknife` | G | Scimitar melee main; proposed Pistol ranged main, pending human choice | Nimble; ordinary melee/ranged loadouts; corrected weapon selection below |

### Explicit initial stat profiles

These are authored adaptations with uncalibrated encounter CR, not claims of
unchanged printed SRD stat blocks. HP targets are construction-time values using
the existing `HealthConfig` correction pattern in `beasts.py`, never after-birth
HP mutation. Do not accidentally inherit player first-level maximum die HP.

| Profile | STR/DEX/CON/INT/WIS/CHA | HP | Hit dice | Proficiency | Gameplay Size | Walk speed |
| --- | --- | --- | --- | --- | --- | --- |
| G: baseline Goblin | 8/14/10/10/8/8 | 7 | 2d6 | +2 | Small | 30 ft |
| C: Mage adaptation | 9/14/11/17/12/11 | 40 | 9d8 | +3 | Small | 30 ft |
| B: Bugbear benchmark | 15/14/13/8/11/9 | 27 | 5d8 | +2 | Medium | 30 ft |
| R*: single mounted-looking combatant | 8/14/10/10/8/8 | 7 | 2d6 | +2 | Medium | 40 ft |

All are ordinary Humanoid/goblinoid content with Darkvision 60 ft. G uses the
existing Goblin stealth proficiency/expertise; B uses source Stealth/Survival
proficiency; C uses Arcana/History proficiency. R uses Goblin stealth. Every
creature gets existing normal blood once, ordinary standard actions, native
movement, senses, death and persistence. AC is **derived from actual equipped
items**, not copied from a stale text label. Clothes give no armor; selected
`armor.armor_scraps` uses its current AC13/maxDex0 and a real Shield adds its actual
bonus. No generic leather armor under every sheet. Record the resulting exact
AC and attack formula for all 17 in the construction receipt. Expected current
gear outcomes: cloth12, cloth+shield14, scraps13, scraps+shield15; eligible
cloth with Mage Armor15 (plus a shield only if actually equipped).

Caster02/08 use existing Intelligence spellcasting at level 9: DC14, spell attack
+6, slots 4/3/3/3/1 at levels 1–5. Register exactly Fire Bolt, Magic Missile, Mage
Armor, **Web**, Fireball, Greater Invisibility, Ice Storm and Cone of Cold, plus
existing Shield and Counterspell reactions. This replaces the existing Mage
selection's Misty Step with Web; do not construct a Mage and remove registrations
later. Register this exact list during initial construction. No newly implemented
spell/condition is required, and no weapon/staff focus exemption is inferred.
Use current spell-component and hand admission unchanged. Web's Restrained,
concentration, escape and fire interactions remain owned by Web.

Both Dual configurations use the existing Multiattack action and real item
instances. Brute stays owner-side; a looted axe does not retain the creature's
extra die. Source clips and weapon-hand variants cannot grant extra attacks,
bonus actions or reactions. Haste/Slow/Extra Attack and off-hand costs continue
through the existing attack machinery; this packet changes none of that code.

### Two mounted sheets: explicit bounded proposal

The human was asked whether to accept one combatant or defer these two. Pending
that answer, this plan proposes **one ordinary entity** for each baked rider/wolf:
one HP pool, turn, AI, square, reaction budget and terminal animation. No mount
entity, mount/dismount, rider surviving mount death, separate bite, charge or
free extra action. R's speed/HP/Size above make the abstraction explicit. Saddle
is ordinary inventory gear with no functional mounting system. This proposal is
not an assertion that the human already selected it; an answer choosing deferral
removes11/12 from implementation while preserving their complete evidence rows.
The other 15 do not depend on this product choice.

### Goblin17: corrected ranged gear proposal

The human has been asked to choose a simple pistol or defer this ranged binding.
Plan the following bounded correction if accepted: one composed
`content.neurodragon:item:weapon.pistol@1` in the existing authored-item path,
1d8 piercing, Dexterity, range 30/90 ft, one-handed Ranged/Martial properties,
ordinary physical loot. Use existing authored-item weight behavior; no new
weight seam is required. Add `WeaponKind.PISTOL` as cold item identity,
not a new action or firearms proficiency; no Loading/ammunition rules, off-hand
bonus shot, special damage condition or custom executor. Existing ranged-weapon
proficiency and Attack costs apply. Melee/ranged loadouts remain independent.

Fixed17 uses its own observed source weapon and muzzle accent. A modular looter
uses the already installed Musket donor category/material, explicitly an
approximate long-gun silhouette for this pistol; no new artwork, cropping,
resculpting or multiplicative recoloring. This is a proposed visible compromise,
not a claim that existing modular art contains a true pistol. Use current ground
item extraction and existing ranged projectile selection. The source accent
belongs to the fixed rig; modular attacks use existing ranged release effects.

Reclassify any supposed quiver only after checking its own source region; a
carried strap/pouch does not prove arrows. The audit retains the old receipt row
for traceability but it is not an instruction to spawn a fictitious shortbow.
If the human chooses deferral, keep17 as a scimitar combatant with the inactive
painted ranged prop disclosed and no invented Shortbow item/attack. Do not mark
that version a completed pistol integration. This decision does not block the
other 16 ordinary character definitions.

## 3. Item construction, ownership and transfer

The crosswalk's 84 frozen possession placements describe 36 distinct
base-item/appearance pairs; Goblin17's corrected ranged selection supersedes its
misclassified row. Reconcile final counts after that decision. Existing appearance
registration alone is not a durable native item.
For a selected variant lacking a named native recipe, compose one immutable
variant definition from the existing base in `dnd/content/items/roster_item_definitions.py`
and register it through the current authored-item declaration/build path. Deduplicate
by `(base_ref, visual_variant_id)`; reuse existing matching definitions. Do not
make one subclass, factory or copy per NPC, or generate all color combinations.

The resulting item owns its `visual_variant_id`, so drop, ground rendering,
pickup, modular equipment and persistence retain the selected color/material.
Use existing palette replacement/glow; no multiply tint, novel weapon geometry
or newly commissioned artwork. Where modular geometry is approximate, retain the
existing disclosed approximation; don't falsify the weapon's rules to match it.

Use existing `CreaturePossessionGrant`: held/worn objects are EQUIPPED, saddle and
other unslotted carried objects INVENTORY. None of this manufactured Goblin gear
is natural INTRINSIC equipment. Construction without default possessions omits
those items; it retains real creature features. No ammo counting, quiver storage,
new magical property or component exemption is smuggled in from older proposals.

The human already accepted that fixed artwork can still depict lost gear,
particularly on the final corpse frame. Keep that limitation explicit. Native
drop/loot/swap must be correct; do not prohibit it, delete items, mark them bound,
or invent a kit-compatibility renderer/fallback system to hide this accepted art
limitation. A modular looter must show the transferred item/material correctly.

## 4. Source clips to existing animation semantics

Use the existing BodyRig JSON/data-loader path, not Goblin-specific code in
presentation/choreography. The crosswalk provides exact original filenames for
every row, source-frame counts, matching shadows, candidate gestures and item
colors. Vendor PNGs specify neither FPS nor semantic impact frames. Author these
measurements and record them as our timing choices, never vendor metadata.

- Idle/Walk/Run use the exact listed idle/movement banks. No new semantic action
  for every differently numbered vendor attack. Idle/breathing remains grounded.
- Weapon Attack selects the inspected matching hand/swing/shot through existing
  action qualifiers and body contexts. Main/offhand hits remain native children
  of the normal Attack/Multiattack lineage. Measure source hit/release milestones
  and source sockets; never copy a root humanoid bow origin or frame blindly.
- Bow03/09 Attack1 contains a genuine release near frame 11. Attack2 is a melee
  bow swing; Attack3 an aiming hold. Neither is another ranged release. Source
  animation availability does not add the optional bow-tip bonus attack.
- Goblin17 Attack4 is a jumping scimitar cut; Attack5 points/discharges the other
  weapon during frames 3–7, with actual muzzle flash 5–8 and smoke through 10.
  Under the proposed Pistol selection, bind Attack5 to ordinary ranged Attack,
  source release 5, matching original Effects/Attack5 and a measured per-facing
  muzzle socket. This release is our authored marker, to be verified in native clips.
  Do not label it a bow draw or add Fire damage from the muzzle flash. The normal
  projectile/impact recipe remains the only delivery and damage owner.
- Caster02/08 use reviewed directional cast gestures for existing spell recipes;
  normal recipe target effects/projectiles remain shared. Their source effects
  can supply the matching local caster accent once, not a second attack/damage
  event and not a reason to add a new condition.
- Goblin08 has a real Quarterstaff but no inspected physical strike bank.
  Its ordinary staff Attack therefore has an explicit source-binding gate:
  inspect the available staff-bearing gestures and propose a clearly disclosed
  neutral gesture through existing BodyContext if none shows a strike. Do not
  silently label a casting clip a staff swing, disable native Attack, invent a
  magic damage rider, or claim this reachable action visually complete before
  that presentation is reviewed. The gate concerns presentation only; the
  existing Quarterstaff and Attack rules remain unchanged.
- TakeDamage, Die, Prone and recovery reuse shared semantic contexts. Die1's final
  hold and reverse recovery are candidates, with per-facing measured ground/rest
  anchors. Preserve the final-phase ground-depth correction; no sliding sprite
  origin or rules-position adjustment to fix painter order.
- All existing Block banks have six frames; caster Attack4 has eight; mounted
  Take Damage has six. Others are mostly 15. Set duration and hit/number/settle
  milestones inside the **actual** frame domain. Do not copy a 15-frame default
  into a 6-frame clip. Inventory absence is explicit, not silently padded frames.
- Each body/shadow pair keeps the same facing/frame/time and original pixels.
  Calibrate separate shadow alpha against combined references. Actual visible
  source spell effects stay separate. Empty Effects/Attack placeholders are not
  imports. Inspect any slash already present before adding a shared slash; never
  double it because a registry slot happens to exist.
- Ordinary interactions with no dedicated source action use an explicitly
  declared neutral gesture/hold through existing recipe semantics. This is an
  honest presentation reuse, not a new native ability. Root fallback must not
  select a humanoid-only bank or unseen weapon for a fixed rig.
- Existing Fly, jump, crawl, teleports and condition-driven poses must resolve
  through the same per-rig capability/action map. No Goblin flight uses Run as
  flight. This phase's shared Fly profile supplies trajectory; held airborne
  poses/wind preserve non-winged anatomy. Report a missing pose explicitly.

Full registration acceptance lists every reachable shared body semantic and its
exact rig binding (including passives, reactions and source/target spell roles),
not just a clip-directory inventory. No species branch or new event traversal.

## 5. Module ownership and dependency direction

- `dnd/monsters/goblins.py`: one bounded passive definition table, exact possession
  tuples, one construction function and the 16 new content declarations. Reuse
  `create_creature_entity`/EntityConfig and existing trait/action/spell owners.
  The table holds cold data; it is not a rules engine or subclass hierarchy.
- `dnd/monsters/bestiary_content.py`: existing canonical Goblin declaration remains
  single-owned here; delegate its construction to the shared Goblin builder with
  the Ashhook definition. No second declaration for the same ref. Preserve raw
  `bestiary.py` modular factories, archer/caster content and their equipment.
- `dnd/monsters/multiattack_definitions.py`: two configured action definitions for
  Briarling/Gloomplate, using existing main/offhand steps and shared executor.
- Existing item definition/declaration modules own only missing selected variants;
  `creature_possessions` installs exact grants. Register creature/item/action
  declarations once through the existing builtin inventory and exact dependencies.
- `game/data/rigs/goblin01.json`…`goblin17.json`: original media registration,
  source provenance, semantic contexts, materials, sockets/anchors and clocks.
  Bind semantic creature refs to these rigs through the current loader/index.
- Existing rig importer/asset installer: add explicit Goblin selections using
  current import/manifest primitives; original source remains private/preserved.
- Existing test and standard review-gallery owners supply native input/replay;
  no new browser gallery format or scenario framework.

Import direction: builtin composition → Goblin declarations → native data and
shared construction/features; bestiary_content → Goblin builder → bestiary's
Nimble helper, with **no** import back into bestiary_content or builtin. Renderer
uses projected content identity and its own data. Native content never imports
`game`, source PNG paths or sprite variant numbers. Local imports, getattr,
runtime type switches to evade a cycle and duplicate event owners are forbidden.

## 6. Implementation sequence and proof

1. Freeze crosswalk, identity/kit migration and stat table; get independent
   anti-slop and anti-OOP/ECS/import-DAG design approvals. Preserve any unanswered
   mounted choice as a narrow gate, not permission to implement mount mechanics.
2. Add only missing selected durable item variants; verify material transfer on
   actual native item instances. Then construct canonical Goblin01 + 16 variants,
   with all ordinary and structure-only modes checked. Independent native review.
3. Import/register exact original clips and layers; exercise source mapping,
   current body qualifiers and reachable contexts. Shared infrastructure changes
   are limited to the already planned final-phase fixes. Independent data review.
4. Integrate into final-phase gallery: all 17 appearances at 1.00 beside a modular
   human and legacy modular Goblin, real paving, four cameras. Every admitted
   character shows movement, its actual attacks, received hit/blood and death;
   cover Prone/recovery/peer-and-wall sorting. Spellcasters demonstrate Web and
   at least distinct cast delivery roles; dual wielders both hands; shield users
   real Protection; bow users actual source release and loadout selection.
5. Exercise item drop/loot/equip on a modular recipient and retain properties/
   palette on ground and body. Exercise hidden/reacquired actors and recorded
   replay. Preserve native attack budgets and terminal event ordering. No new
   Goblin event types or per-species render handlers.
6. Include in the combined source-freeze full native/game suites and type/DAG
   checks already required by the parent plan. Reconcile failures and obtain both
   independent final implementation approvals. Do not claim completion from
   metadata or a handful of nonlethal outgoing-attack clips.

Planning completion is not implementation completion. This amendment does not
claim the remaining sixteen Goblins or new media are installed. The current
scale correction is the sole new Goblin code change in this planning pass.

## Implementation clarification — current direct Protection owner

Current Fighter progression has retired the legacy Protection CRI declarations.
Reuse `create_protection_handler` with a direct `BehaviorBinding` whose provider
and root are the Goblin content ID, owned by that entity. Do not reinstate retired
class-feature declarations or import Fighter progression. Independent ECS source
review confirmed this existing direct owner before construction.

Goblin17’s old quiver row accompanied its incorrect Shortbow classification.
The source carries a pistol with a shoulder strap/pouch; the inspected bank does
not establish a functional quiver. This batch adds its actual Pistol and omits the
fictitious arrow equipment (83 total possession placements). Modular pistol loot
retains the explicitly approved existing Musket donor approximation.
