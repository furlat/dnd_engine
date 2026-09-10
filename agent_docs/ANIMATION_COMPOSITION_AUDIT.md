# Animation composition audit

2026-09-10, `codex/recovery-design` working tree. This is a coverage record for
the active recovery plan, not a replacement plan or a mechanics repair backlog.
It compares the current Python code with the original source at
`/home/tommaso/Dev/NeuroClient/app`.

## The answer to “is it data driven?”

Partly, and the distinction matters. Authored recipes select clips, source
frames, speeds, anchors, projectile appearance, feedback and condition
appearance. Python still implements the finite primitives and causal dispatch.
Several authored domains remain unsupported. Importing a JSON field does not
mean the renderer executes it.

The original design also used coded primitives. `src/render/types.ts:768`
defines `ParallelIntent`, ordered `SequenceIntent.groups` and a finite
`ClipIntent` union. `AttackClip`, `CastClip`, `TakeDamageClip` and `ConditionClip`
interpret typed data and await their children. Recovering this composition does
not require a new JSON programming language, backend animation fields or a class
hierarchy with one executor per spell.

State reduction is a different responsibility. `game/presentation.py:813`
dispatches on existing event families and applies retained after-values. Damage
packets replace HP, condition facts add/remove a condition UUID, life events
replace life state, senses supplies positions, and turn events supply the
historical actor/round. These are coded protocol semantics, not authored
animation recipes and not a second D&D rules implementation. Original
`sdk/typescript/src/reducer.ts` and `subjectiveJournal.ts` likewise use the same
coded reducer for latest and historical state.

## What now has one owner

| Concern | Current owner and meaning |
| --- | --- |
| Engine rules, condition handlers, reactions, interception and committed movement | Existing engine. The renderer does not decide whether paralysis stops a step. |
| Subjectivity and attachment | Existing grants and sensory facts retained by `capture_lineage`; no party-wide vision union or rewritten disclosure policy. |
| Complete causal identity | `CompletedLineage`, ordinary event/lineage UUIDs, parent/child relationships and objective source indices. A condition sidecar retains passive facts without copying executable conditions. |
| Latest state | `encounter_play.receive` reduces every completed actual root immediately. |
| Historical progression | One pending deque and one active head in `game/encounter_play.py`. Native controller work can progress while that head is paused. Human input requires the corresponding settled displayed boundary. |
| Action/child composition | `game/choreography.py:68`, shared by standalone actions and reactions embedded in Move/Jump. It owns no queue, mutable playback clock or engine queries. |
| Primitive sampling | `animation.py`, `attack.py`, `condition_animation.py`: explicit elapsed time in, passive sample out. |
| Decorative feedback | `feedback.py`: passive number/badge tracks with authored lifetime and frozen launch contact, sampled by the existing presentation clock independently of a completed head. |
| Movement interpolation | `motion.py:70`: actual direct Step children, authored lead/duration/arc, complete reaction groups, then only committed continuation. |
| Rig pixels and condition color | `animation_draw.py`, `condition_draw.py`; the same actor drawer serves idle, movement, attacks and casts. |

The import direction remains presentation facts/data → primitive binding and
sampling → shared composition → movement/application → Pygame adapters. Frozen
records describe plans and samples; they are not entities with their own rule
lifecycles, schedulers or event registries. Pygame is confined to the adapters
and application. No TypeScript runtime is required to play the game.

## What the recursive cut preserves

The source mapper keeps each movement reaction subtree together and in cursor
order (`subjectivePresentationMapper.ts:1243`). `MoveClip.ts:71` and
`JumpClip.ts:142` wait each complete group. `AttackClip.ts:32` dispatches on-hit
children at melee contact; ranged delivery dispatches on arrival, and the
primitive waits both its body and delivery chain. `TakeDamageClip.ts:67`
attaches ordinary child effects at `conditionFrame`; lethal children dispatch
immediately. `CastClip.ts:547` dispatches the actual disclosed effect subtree.

The Python compositor now follows actual child lineages recursively:

- Attack contact or projectile arrival supplies the direct on-hit anchor.
- Each repeated Spell application keeps its own identity and arrival time.
- Nested Attack/Spell roots bind their own subtree. The parent primitive excludes
  their damage, avoiding duplicate ownership of the same consequence.
- TakeDamage descendants use the authored condition frame and impact delay;
  direct attack riders remain contact siblings. The engine's ancestry decides
  which relation applies.
- Condition leaves receive the nearest cast's existing condition delay/feedback
  override, retain actual condition UUID membership, and join real alpha fades.
- Postorder joins include only actual descendants. Cast recovery starts after
  the complete delivery subtree, including a longer condition fade or nested
  action. Release, impact, HP and child anchors are unchanged; only recovery and
  completion move. Attack joins also extend to their complete child subtree.
- A movement reaction holds its subcell position until the whole group ends.
  A failed Step retains its rendered stop position; a committed Step continues.
  Legal state still records the uncommitted Step's origin. This supersedes the
  source origin-restoration behavior following the user's gallery review.
  No visual condition-name predicate substitutes for the committed result.
- Walk and Jump use the same action compositor. Jump retains the interrupted
  curve position/lift, and the shared map adapter converts source pixel lift to
  the current camera scale.

This restores a useful composition boundary. It does not implement every member
of the source `ClipIntent` union or prove a weapon-triggered spell executor
exists in the backend. The native on-hit case uses the existing configured
paralysis rider and real save/condition handlers; it is not a fabricated Hold
Person spell.

## Authored coverage, including explicit limits

| Domain | Data actually consumed | Current boundary |
| --- | --- | --- |
| Cast | Existing materialized Studio JSON, exact semantic binding, body/release, selected prepare/travel/impact, repeated applications, damage and enabled body recovery after children | The selected executor requires projectile delivery without an area. Self/touch/position/area and healing-specific presentation are not implemented by this compiler. Unbound cases retain their actual state and report gaps. |
| Projectile art | Existing sprite asset/phase metadata and CodexFX override bundle; original generated dart/bolt geometry primitives | Unsupported sprite color/orientation/media policies reject explicitly. The current Rune Dart comes from the authored CodexFX bundle. Loading other catalogs is not equivalent to having their art locally. |
| Attack | Existing attack recipe/profile predicates, body clip/speed, contact or release frame, ranged speed/minimum duration/endpoints, trajectory/depth, outcome feedback | Ranged geometry currently implements the source bolt primitive. Body media and hidden-slot profiles are rejected. Attack VFX currently draw a supported slash layer; other selected layers produce media gaps. |
| Per-rig mapping | Explicit body clip/frame/FPS, slots, resources and creature-content mappings in rig data | A missing ranged clip can retain the root rig's authored clock with Idle and an explicit missing-body gap. This is degraded art, not a claim that the creature has a ranged animation. |
| Walk/Jump | Source clips, walk speed/duration, jump duration bounds/arc, pre-reaction lead and badge, actual retained Step endpoints | Walk/jump media and recovery fields are parsed but not executed. Enabled pre-reaction body/media/recovery rejects motion binding. The default imported media/recovery fields are empty/disabled. |
| Damage/life | Retained direct packet HP/life after-values; authored hit/death body, palette, impact delay, flash and number frames | A primitive currently binds one direct damage packet per target application and a single final life transition. Standalone damage/heal/revive/forced movement and broader packet composition still need their respective source primitives. Actual state reduction already retains their supported facts. |
| Conditions | All 141 original recipe rows, exact behavior identity, composition priority/exclusivity/group limits, alpha, body tint/saturation/brightness, badge text/color/style, application/removal delay | Persistent/transition strips, equipment modifiers and appearance replacements are not executed; nonempty selected fields produce explicit gaps. `state_only` is intentional neutral authoring. Missing rows preserve membership with a gap and no fabricated transition. |
| Condition relationships | Trigger, immunity, suppression, grant and classification metadata remain losslessly parsed | These records do not become a second rules engine. Actual condition events remain authoritative. |

The current local spell selection is **three bound drafts**: Fire Bolt, Acid
Splash and Magic Missile. Fire Bolt and Magic Missile exercise the selected
projectile path; Acid Splash's area delivery is currently rejected. This is not
a complete spell catalog implementation. The copied action recipe file has
**88 rows**, of which the loader selects **five attack recipes**. Three have
selectable variants (`action.attack`, `reaction.opportunity_attack`,
`action.feature.extra_attack`); Frenzied Strike and natural attack have no
variants in that file and therefore do not bind through this selector.

The copied condition document contains 141 rows: 32 `state_only`, 16 with body
color, three with non-neutral alpha, four with equipment modifiers and one with
appearance layers. It currently contains no persistent or transition strips.
Those counts overlap; they describe authoring, not 141 distinct implemented
executors. The strict schema round-trips every original row unchanged.

Condition appearance uses the source composition across current memberships.
Visual recipe deduplication does not collapse actual condition UUIDs. Body color
applies only to the original body/equipment slots. Aura, slash, effect layers and
shadow retain their own color policy. Hit flash overrides the color filter;
condition alpha still applies to the entire actor, including its shadow. The
pixel adapter follows Pixi's exact equal-channel saturation matrix, then tint
and brightness, rather than substituting a luminance approximation. Sources:
`ConditionOverlayController.ts:22,198`, `AnimatedEntity.ts:970`, and the local
Pixi `ColorMatrixFilter.mjs:152,202,496`.

## Source parity corrections validated in this checkpoint

Two review findings were fixed in this same working checkpoint:

1. **Decorative feedback lifetime.** Original `FloatingText.ts:83` returns
   immediately while its fade continues independently. `game/feedback.py` now
   extracts the existing authored number/badge tracks, including the source
   pre-reaction label. The application retains them until their own expiry,
   fixes their launch contact, and filters duplicate feedback from the group
   drawer. A neutral-alpha Dodge badge can survive its immediate causal join;
   fading overlays neither delay player input nor create another action queue.
2. **Cast recovery after longer children.** Original `CastClip.ts:118–137`
   awaits the complete delivery/child chain before movement recovery. The
   compositor now computes descendant joins in postorder and shifts only the
   parent's recovery/completion. The actual Fire Bolt/concentration-removal test
   below validates this timing with recovery enabled and disabled.

Remaining source parity limits are the unsupported domains in the table: shove
reaction groups, enabled walk/jump recovery/media, pre-reaction body/media and
separate turn/action body tracks, plus broader delivery/effect primitives. A
backend weapon-triggered nested cast was not fabricated for this exercise;
recursive nested action ancestry is implemented, but that full mechanical
scenario remains unexercised. These are capability boundaries, not new mechanics
repair prerequisites. Their future implementations should consume existing
source records through the same owners.

## Evidence and review judgment

`tests/game/test_movement_interruptions.py` exercises actual Move and Jump with
a configured longsword opportunity rider: failed save/paralysis, successful
save, miss, death and committed/noncommitted continuation. Its authored-data
variant changes the real Paralyzed alpha/duration and proves the whole reaction
waits beyond the attack body. `test_attack_animation.py` covers native melee,
later-edge retained HP, ranged release/arrival and per-rig clocks.
`test_ranged_map_draw.py` checks actual ranged pixels on the map.
`test_playback_placement.py` covers the completion-to-idle boundary in all four
views, continued movement from a retained pose and fresh facts at that pose.
`test_body_lift.py` checks body/projectile attachment agreement and unchanged
support shadows. `test_feedback_layout.py` checks original actor pixels with
stacked feedback at screen edges. Paralyzed still uses the original saturation
`0.35` and brightness `0.86`; the port did not add a new condition shader.

`test_choreography_recovery.py` uses the existing public Fire Bolt scenario with
a native Concentrating recipient. The actual failed Constitution save removes
that condition beneath TakeDamage. After engine reset, changing only valid
Studio recovery/condition authoring proves unchanged release/impact/HP anchors,
condition removal at its authored frame/delay, an idle caster during the longer
fade, and recovery frame zero at the completed child join. Both enabled/disabled
recovery cases pass (12.22 seconds including the existing scenario setup).
`test_feedback.py` verifies independent Dodge/attack/repeated-cast overlay
lifetime, source duration and retained application identities. Its final five
cases also include a real opportunity reaction: toggling only the authored
reaction badge preserves movement timing and settled state while suppressing
that badge. All five pass.

`test_gameplay_history.py` proves positions, condition expiry, turn histories,
real grants and replay after engine reset. `test_encounter_play.py` checks a
paused historical head while native enemy decisions advance. These are gameplay
contracts; a source-text check alone would not establish them.

The final real X11 encounter run settles 26 lineages and reaches victory at
frame 200, with displayed history equal to latest. Its explicit media gaps are
the fixed Goblin rig's missing ranged body/slash clips. Evidence and captures
are under `.runtime/reaction-composition/final-encounter`; the adjacent
`final-encounter.json` records the result. A separate 32-frame X11 review shows
walking/jumping reaction holds, actual condition appearance, continuation and
terminal positions in two camera views.

The condition leaf and public drawer tests (`test_condition_animation.py`,
`test_condition_draw.py`) pass nine cases, including all-row round-trip,
duplicate condition UUIDs, exclusion priority, seeking, a later neutral wrapper
not overwriting an active alpha transition, exact pixels by slot, hit-flash
priority and shadow alpha. Their changed modules pass Pyright.

**Anti-slop judgment:** the shared compositor and condition leaf remove a real
flattening problem and make authored changes flow through common primitives.
The implementation must still report the limits above. Loading all recipes or
playing one encounter does not establish universal animation coverage.

**Anti-OOP judgment:** the new owners are passive plans plus functions over
existing retained identities. They add no per-spell executor hierarchy, new
mechanical event vocabulary, live-condition copies or independent action queue.
Further source primitives should join this same composition boundary; adding
more wrappers around the same state would not improve the design.
