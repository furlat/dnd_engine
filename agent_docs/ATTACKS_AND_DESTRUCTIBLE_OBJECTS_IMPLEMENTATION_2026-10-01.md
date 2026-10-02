# Shared attacks and destructible objects — implementation

October 1, 2026. Implements the
[approved plan](ATTACKS_AND_DESTRUCTIBLE_OBJECTS_PLAN_2026-10-01.md).
Approved implementation and focused verification are complete. The full-project
run finished **6,161 passed, 338 failed, 146 errors**;
the separate complete `tests/engine` rerun passed **1,775 tests**. Exact results
are in the [suite triage](audits/ATTACK_FULL_SUITE_TRIAGE_2026-10-01.md).
The [integrity review](APP_INTEGRITY_REVIEW_2026-10-01.md) records wider app
defects for discussion. Those remain our responsibility; the user asked that
their repairs be discussed separately while this approved plan is completed.

## Result

`AttackObject` and its live presentation recipe are removed. Ordinary attacks
select creatures or eligible placed objects, using the selected source, normal
cost commitment, reach/range, attack roll and typed damage. Objects have authored
AC and use their existing Health/destruction lifecycle. Material defaults and
individual overrides belong to native item authoring. This is the object-AC rule
accepted with the plan, replacing the former automatic object hit.

Extra Attack, Frenzied Strike, natural/unarmed attacks, Multiattack and reaction
attacks retain their own eligibility and costs while using the shared strike
route. Opportunity attacks remain main-hand reaction attacks without an Extra
Attack grant. Off-hand attacks may go first and retain their existing bonus cost.
Natural attacks and True Strike pass local source/damage data instead of
temporarily modifying equipment. `AvailableActionsResult.attack_actions` is a
pure query over discovered actions; it creates no additional registry or actions.

Fire Bolt accepts eligible objects through its existing spell path. Its device
variants use the emitter's origin, range and sector. Sanctuary, Twinned Spell
and Globe retain their existing creature/spell constraints; the new target mode
does not silently bypass them or make every spell affect objects.

Fireball damages eligible unattended objects and continues through barriers it
actually destroys during the same cast. Native stages stay inside the original
envelope, process each recipient once, respect surviving barriers and Globe,
and publish `AreaReachEvent` with real destruction dependencies. This structural
damage/breach behavior is the explicit game rule approved in the plan.
Its effective target-mode override still uses the existing shared selected-target
route when changed away from area targeting; it never damages extra geometric
bystanders in that mode. The reproduced override regression is fixed.

## Current damaging-spell applicability

This records implemented permissions, not a claim that all tabletop object rules
are implemented. The audit covered the current 110 root spell identities,
composed Hellish Rebuke, damage riders, persistent fields and granted actions.
Damage type or visual material never grants object permission.

| Spells | Actual application | Placed object permission |
| --- | --- | --- |
| Fire Bolt | Spell attack and fire damage | Yes |
| True Strike | Spell-owned child weapon Attack and local radiant rider | Yes, through the shared Attack route |
| Fireball in normal area mode | Creature Dexterity saves; objects take typed damage without a creature save; finite structural breach | Yes, eligible unattended targetable/breakable objects |
| Ray of Frost, Chill Touch, Shocking Grasp, Guiding Bolt, Inflict Wounds, Scorching Ray, Eldritch Blast | Creature attack rolls; authored repeated allocations retained | No |
| Ice Knife | Creature attack followed by creature Dexterity-save burst, hit or miss | No |
| Magic Missile | Automatic creature damage per dart, existing Shield interaction | No |
| Sacred Flame, Acid Splash, Call Lightning/its granted Strike, Chain Lightning, Disintegrate | Creature Dexterity saves with spell-specific selection | No |
| Poison Spray, Blight, Harm, Finger of Death | Creature Constitution saves | No |
| Burning Hands, Lightning Bolt, Ice Storm, Flame Strike | Creature Dexterity-save areas | No |
| Thunderwave, Shatter, Circle of Death, Cone of Cold, Sunburst | Creature Constitution-save areas | No |
| Prismatic Spray | Creature random-color effects: Dexterity damage saves or Constitution/Wisdom follow-up effects | No |
| Sunbeam/its granted Strike | Creature Constitution save per beam | No |
| Cloudkill, Insect Plague, Spirit Guardians, Guardian of Faith, Incendiary Cloud | Creature spatial triggers, saves and per-spell timing/budget | No |
| Spike Growth | Automatic damage on qualifying creature movement | No |
| Hellish Rebuke | Reactive creature Dexterity save | No |
| Bestow Curse, damage option | Creature curse; later caster hits trigger the necrotic rider | No |
| Evard's Black Tentacles (implemented outside the current root catalog) | Creature Dexterity entry save; automatic damage on an already restrained creature's turn | No |
| Power Word Kill, Divine Word | Creature HP-threshold lethal effects; PWK uses InstantDeath, current Divine Word uses lethal force damage below its threshold | No |

Shatter and Disintegrate remain creature-only in this implementation. Extending
them is a separate rule/content change. Enlarge/Reduce modifies later creature
weapon damage, without its own permission to target objects. Non-damaging
support/control spells are outside this table. Explicit Fireball target-mode
overrides preserve selected recipients and do not invoke geometric breach.

## Presentation and retained events

The renderer consumes source kind/slot and actor-or-object contact data. A bow
shot, sword strike and unarmed strike use the actual selected visible equipment.
Objects have no fabricated actor rig, creature vitals or blood. Hit flash,
damage numbers and destruction use ordinary received events.

Native reach stages are admitted at their prerequisites' authored structural
clearance. Geometry, visibility and newly revealed bodies commit together.
Subjective projection removes dependencies on undisclosed destruction facts.
The renderer neither reruns propagation nor reveals a future actor to bind an
earlier frame. Saved native/public packets still replay after an engine reset.

One explosion advances across all stages. If a dense sequence of slow collapses
would outlast its original impact, the existing frames are fitted continuously
over that sequence and the original tail; no restart or frozen final frame is
introduced. The two-door review fits within the original impact duration.
Desert C7's measured clearance is frame 4 (250 ms at 16 fps); its original
12-frame destruction pixels and 750 ms duration are unchanged.

The neighboring replay tests also caught two integration defects now corrected:
a witness could reveal an attacker before destruction admitted its world
support, and completed attack Idle frames used the action clock instead of the
ordinary presentation clock. Both now use the existing state/timeline owner.
The independent ECS review also caught future wreck geometry being staged before
a lethal strike. Binding now supplies only absent world support; known object
geometry stays historical until an actual preceding event changes it. Lethal
contacts therefore target the intact object, not its shorter wreck.
Remote levers retain their nested item actions through a scoped, validated exact
controller link; direct distant item use still fails.

The strict canonical server event manifest is regenerated from current native
models, including attack source/contact data, typed object damage/destruction and
area reach dependencies. No validator was relaxed. Separate real object-attack,
Fire Bolt and door-breach cases exercise JSON wire decoding after runtime reset.
This does not repair the older server item/behavior DTOs or durable-character
adapters, which remain documented for discussion.

Fireball's existing player log keeps one isolated branch per creature plus its
causal residue entries. The failing total-child assertion counted residue as
additional targets; explicit target/save/damage and residue assertions now pass
without changing production logging. Obsolete AttackObject icon metadata and
presentation documentation are removed; archived source evidence is preserved.

## Verification

| Check | Result |
| --- | --- |
| Complete current `tests/engine` | 1,775 passed |
| Economy/progression preservation lane | 269 passed; includes the 144-case Haste × Extra Attack × Action Surge × Slow grid across creature/object/mixed targets, plus 18 spending-order cases |
| Final cold breach, object attack and True Strike checks | 15 passed |
| Destruction visibility/clearance in four cameras | 9 passed |
| Historical geometry staging, movement, portal and discovery replay | 43 passed; separate new lethal-contact regression passes |
| Existing cloud propagation and field presentation after staging correction | 72 passed |
| Area media/occlusion and spell handoff replay | 166 passed |
| Device destruction and ordinary/object attack playback | 61 passed |
| Environment/device/prop destruction and body playback after final staging change | 167 passed |
| Existing spell palette contracts | 29 passed |
| Recorded history, tether and Web | 63 passed |
| Window presentation | 42 passed |
| Source/dependency architecture and object targeting | 33 passed |
| Changed production modules and new breach tests | Typing: zero errors |
| Final saved-input gallery | 8/8 clips passed; zero presentation gaps |
| Final target overrides, spell-family metadata and staged Fireball breach | 49 passed |
| Isolated per-target combat logs and separately accounted residue | 4 passed; typing clean |
| Canonical event wire contract and cold objective timelines | 29 passed, including three new real object-attack/spell/breach records decoded after runtime reset; test-module typing clean |

These runs overlap; their counts are not a sum of distinct tests. The mandatory
full `tests` run also exposes broken production adapters, content contracts and
legacy fixtures. Consult the triage for its actual final result and the
explicit reruns of failures corrected after that process started. It must not be
reported as a fully green project suite.

Current-run logs are retained locally under `.runtime/attack-review/validation/`.
Tests use the project's Python 3.13 environment at
`/home/tommaso/.cache/dnd-engine/venv`, with source under `/mnt/c/.../dnd_engine`
and dummy SDL video/audio drivers for rendering. Full-suite assertions use
`--assert=plain --tb=short` to avoid recursive entity dumps on legacy failures.

Independent [anti-slop](audits/ATTACK_OBJECT_ANTISLOP_STUDY_2026-10-01.md),
[ECS](audits/ATTACK_OBJECT_ECS_STUDY_2026-10-01.md) and
[correctness](audits/ATTACK_OBJECT_CORRECTNESS_STUDY_2026-10-01.md) reviews record
the concrete findings, fixes and their boundaries.

## Review clips

[Open the shared attack review](http://127.0.0.1:8767/runs/20261001T131720Z-b09a30/index.html).
Four real scenarios, each from both observers and all four camera corners:

- Bow followed by sword against the same object.
- Bow followed by a genuine unarmed attack.
- Fire Bolt hitting an object.
- Fireball breaching two closed doors and reaching the creature beyond them.

The review uses original H1 paving, native captured events, and the normal
saved-input pipeline. Clips are available for human feedback; passing automated
checks does not imply human visual approval. No new artwork or Git operation
was part of this implementation.
