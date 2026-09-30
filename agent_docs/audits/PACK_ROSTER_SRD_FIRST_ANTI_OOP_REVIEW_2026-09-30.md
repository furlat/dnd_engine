# Independent anti-OOP/ECS review: SRD-first art-led NPC roster

Date: 30 September 2026. Status: **approved as a content-design proposal, with
the implementation and evidence limits below**. Reviewed the reconciled
`ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md` and the three controlling
`PACK_ROSTER_SRD_FIRST_*` companions. This review adds no production content,
code, imports, or tests.

## Findings

The revised selection boundary is correct: all 259 entries are compared against
the complete SRD 5.1 catalogue before secondary 5.2 sources are considered;
whether a local factory exists does not limit source selection. The revised
coverage manifest reports 259 keys, 240 primary 5.1 profiles, 9 primary 5.2
profiles, and 10 no-fit proposals, with no missing, extra, or duplicate keys.
Its `fit_counts` (15 exact, 92 cosmetic, 64 loadout, 78 adapted, 10 no-fit)
sum to the same total. These counts establish documentation coverage, not
runtime or source-block parity.

The proposed ownership remains ECS-oriented. An NPC is composed from creature
facts, actual possessions, and actions/conditions owned by existing content and
systems. Shared profiles can serve many sprite rows; palette changes do not
create content classes. The reports identify `bestiary.py`, `srd_roster.py`,
`traits.py`, item/loadout definitions, and character builds as the relevant
current owners. Missing full source profiles are identified as content/support
gaps. No per-sprite classes, NPC manager/framework, parallel executor, late
imports, reflective `getattr`, or runtime scans of the 259-entry documentation
set are proposed.

The gear model preserves canonical sources: selected source profiles remain
unchanged unless a row explicitly removes/replaces equipment or names another
adaptation. The revised Goblin Archer mapping was checked against
`dnd/monsters/bestiary.py:408–410`: the **local bespoke** Goblin Archer kit is
shortbow, scimitar, and offhand dagger; the **local bespoke** Skeleton Archer
uses twin daggers. These are local composition facts, not published SRD source
kits. The new rows make visible kit a real possession, state changed
attack/AC/proficiency where applicable, and distinguish possession from baked
pixels. The updated ZombieCop4 row
selects protective gear as Studded Leather, explicitly labels the subtype a
conservative choice, recalculates AC, and leaves binding unverified. Added
plate choices for the named Orc/Demon rows and half-plate choices for Dinosaur
and Character rows likewise remain real possessions; armor wearability, size,
composition, and binding are open validation work. Intrinsic attacks are not carried equipment. Natural
armor does not stack with worn armor.

The source/action boundaries are coherent. Canonical Dretch natural attacks are
kept distinct from visible carried weapons; Dretch's local 22 HP and missing
Fetid Cloud/telepathy/extra offhand behavior are called out as parity gaps.
The selected Demon kits and full Mage/Lich/Wight/Shadow/Mastiff source profiles
are not reduced to whatever a local scaffold currently supports. The undead
Musket entries explicitly convert the 5.2 equipment to 5.1 ranged attack,
ammunition, and Loading behavior, omit Slow mastery, and constrain Loading to
one shot per action. The three Ogre Zombie adaptations retain 5.1 defenses and
Undead Fortitude, replacing only the unseen Morningstar with the named Slam;
they do not inherit 5.2 exhaustion immunity. 5.2 animal/dinosaur profiles are
explicitly secondary and row-level conversions specify the changed mechanics,
including Ankylosaurus's automatic prone effect becoming a 5.1 Strength save
while retaining its Huge-or-smaller limit, the Crocodile's correct grapple
target limit, and the Hippopotamus's concrete 5.1 initiative/save conversion;
the Allosaurus Pounce save/action-economy adaptation is also explicit. The
Erinyes rows no longer claim unsupported Devil's Sight or Parry, and the Imp
gear addition explicitly grants proficiency. These are design choices; runtime
conversions remain unimplemented.

The NaturalAttack limitation is reported accurately against its current owner
in `dnd/monsters/traits.py:584–700`: ranged metadata is represented, and the
action validates range/line of sight and enters the normal attack consequence
path. Its default `weapon_slot=MELEE_MAIN` remains in outcome/event plumbing.
That is not proof of player discovery, ranged outcome bonuses, effect delivery,
presentation, or slot-sensitive compatibility for the Toxic Spit candidate.
The reports correctly keep Toxic Spit pending and out of the selected
Allosaurus block.

Presentation remains downstream of native identity and admitted historical
facts. The master preserves causal event lineages, subjective capture, and
independent latest/history behavior; it forbids live-state replay and renderer
rule inference. It retains the current typed Studio/BodyRig/BodyClip/recipe
owners and proposes only a minimal rig-and-selected-recipe/profile-compatible
presentation association with partial overrides. It does not make BodyClip a
rule anchor map or introduce a new authoring framework. Existing last-sampled
frame timing `(frames - 1) / fps` remains the stated basis. Mounted Goblin
rider/steed identity is kept separate, with native relation and independently
targeted/moving/dead presentation explicitly unimplemented.

## Limits retained by approval

Approval covers the documentary design boundary and reviewed source evidence,
not local parity or gameplay correctness. Full source actions, traits, spell
lists, conditions, gear composition, new profiles, firearms/ammunition, mount
relations, NaturalAttack ranged discovery/outcomes/delivery, selected
animation bindings, half-plate wearability/AC, and per-rig recipe compatibility
still need their separately authorized content or implementation work. The
full source blocks and each selected 5.2-to-5.1 conversion should remain the
authority when that future work is planned. No production migration or
implementation is implied by this review.

No further architecture blocker was found in this reread. The above limits are
the explicit scope boundary, not prerequisites for accepting the roster study.
