# Action execution bridge — implementation work blocks

**Status:** implementation decomposition derived from the manual WP0 ledger

**Date:** 2026-08-13

**Semantic authority:** [`ACTION_EXECUTION_BRIDGE_MANUAL_LEDGER.md`](./ACTION_EXECUTION_BRIDGE_MANUAL_LEDGER.md)

**Production changes authorized by this document:** none by itself

This document expands the work order implied by the manual ledger. The ledger
defines the observed bridge defect and final disposition for each row. This
document groups those rows into implementation-sized vertical cuts and states
when each cut is actually complete.

It does not introduce an automated ledger, another runtime layer, or a second
semantic model. The ledger remains human-owned and is updated by hand after a
block is implemented and verified.

## Working rules for every block

Each block is vertical:

```text
engine execution
  -> subjective projection
  -> generated SDK contract
  -> existing NeuroClient mapper and intent graph
  -> live and replay verification
```

A block is not complete when only the engine or wire schema compiles. It is
complete when the same facts survive through the existing client graph and the
block's observable acceptance cases pass.

The following rules apply throughout:

1. Preserve the engine fact first. Do not replace a missing fact with a client
   inference, display-name lookup, renderer route, or later scene-state read.
2. Keep `subjectivePresentationMapper.ts`, `VisualTransaction`, `ClipIntent`,
   the current dispatcher, and the SDK journal as the one existing path. Enrich
   them in place; do not add a parallel graph, scheduler, reducer, or journal.
3. Animation, timing, media, colors, body clips, camera, sound, and local phase
   scheduling remain NeuroClient recipe decisions.
4. Privacy filtering may omit a protected fact or sever a private edge. It may
   not substitute a different identity, invent a causal bypass, or combine
   grants from different observers.
5. Do not keep an old wire shape as a compatibility path. A block is a hard cut
   across engine, projection, SDK, and client.
6. Test behavior at the smallest stable observable boundary described by
   `HOW_TO_TEST.md`: domain result, subjective projection, SDK decode/reduce,
   pure client mapping, then browser/live only where those layers own behavior.
7. Do not use arbitrary sleeps to prove ordering. Await the journal token,
   queue barrier, committed state, or another explicit completion signal.
8. Client preservation work happens in every semantic block. Block 8 is final
   closure and removal of old inference, not a deferred second client migration.

## Hard scope fence

This work is action-execution only.

It does not include:

- static world, terrain, tile, or ground representation;
- condition appearance authoring or redesign;
- spatial-effect appearance or general spatial-state redesign;
- actor rigs, ancestry/body appearance, portraits, general icons, or equipment
  art;
- general persistence, deployment, content-rollout, or zero-downtime migration
  architecture;
- new gameplay rules introduced only to improve presentation;
- changes to Banishment return/occupancy mechanics;
- a new event for an immediately blocked push;
- speculative thrown-weapon or ammunition facts that execution did not select;
- a server-side Fireball flight or manifestation-arrival phase.

## Dependency order

```text
Block 1: exact identity and privacy
                  |
Block 2: ordered action applications
                  |
Block 3: terminal action results
             /          \
Block 4: attacks     Block 5: movement
             \          /
             Block 6: reactions
                    |
             Block 7: spells
                    |
             Block 8: client/Studio/admission closure
```

Blocks 4 and 5 may proceed in parallel after Blocks 1–3. Block 6 requires both.
Block 7 consumes the common facts from Blocks 1–6. Block 8 begins only after
the semantic blocks work end to end.

## Exclusive primary row ownership

Each of the 104 manually checked ledger rows has one primary block. A later
block may regression-check an earlier row, but it must consume the earlier
mechanism rather than implement a second version.

| Block | Primary ledger rows | Row count |
|---|---|---:|
| 1. Exact identity and privacy | `X01–X10` | 10 |
| 2. Ordered action applications | `A01–A05`, `C05` | 6 |
| 3. Terminal action results | `A06–A20`, `C03–C04` | 17 |
| 4. Attacks | `AT01–AT09` | 9 |
| 5. Movement and displacement | `A21`, `M01–M17`, `C11` | 19 |
| 6. Reactions | `R01–R08` | 8 |
| 7. Spells | `B04`, `S01–S18` | 19 |
| 8. NeuroClient, Studio, and activation closure | `B01–B03`, `B05–B06`, `X11–X12`, `C01–C02`, `C06–C10`, `C12–C13` | 16 |
| **Total** | **Every ledger row exactly once** | **104** |

---

## Block 1 — Exact identity and privacy foundation

### Goal

Make every later observation bind to the exact action that actually executed,
while preventing private implementation identities from leaking through player
replication.

### Ledger rows

Primary ownership: `X01–X10`.

Concrete consumers later regression-checked by their domain blocks include
configured Multiattack (`AT08`), Retaliation and True Strike (`AT09`), movement
roots (`M02`), exact reaction roots (`R02`), spell roots/providers (`S02`,
`S03`), spell follow-up actions (`S16`), and Acid Flask (`S17`).

### Work included

#### Engine execution

- Preserve the selected `BehaviorBinding` on normally admitted actions (`X01`).
- Make direct/nested action construction retain the active authored binding
  instead of becoming an unbound generic action (`X02`).
- Freeze the exact active handler identity when a handler changes or emits an
  included action result (`X03`).
- Preserve the selected configured action identity for all ten configured
  Multiattack variants, including their nested attacks (`X04`).
- Separate exact source-item identity and neutral resource/location facts from
  `ItemPresentationState` renderer/UI classification (`X05`).
- Remove `ActionEvent.presentation_kind` and similar item presentation
  classifications as semantic authority (`X06`).
- Replace action-reachable open-context semantic values with closed typed facts
  (`X07`). Result-specific typed values defined here are consumed by Blocks 3
  and 6 rather than rediscovered there.
- Replace display-derived `SpellEvent.spell_id` and `EffectOrigin.source_id`
  binding authority with the exact selected content identity (`X08`).

#### Subjective projection and privacy

- Define truthful attribution roles for exact public definition, provider,
  configured action, and source item. Never put a provider ref into a
  definition-ref field or expose an OBSERVED/INTERNAL implementation as public
  (`X09`).
- Use the same observer's event-local evidence for every constituent of a
  disclosed identity or relationship. Do not stitch a definition seen by one
  observer to an endpoint seen by another.
- Preserve execution-owned application/causal identities when already present.
  Retain only exact authorized direct edges. When a parent is hidden, sever the
  edge rather than reparenting to the nearest visible ancestor (`X10`).

#### SDK and NeuroClient

- Generate a closed tagged attribution union rather than transporting display
  strings or ambiguous refs.
- Preserve the selected attribution and exact causal evidence in the existing
  mapper plan/transaction evidence.
- Keep binding selection keyed by a truthful tagged attribution row, not a bare
  ref whose role is lost.

### Required observable checks

- Every concrete direct-construction case listed under “Exact known runtime
  identity exceptions” in the ledger projects the correct exact action or a
  truthful lawful public/systemic attribution.
- All ten configured Multiattack identities remain distinct through SDK decode
  and client binding.
- Acid Flask never exposes its hidden spell implementation and still resolves
  through its truthful public item/provider/action identity.
- A hidden definition with a public provider uses the provider role without
  relabeling it as a definition.
- A private parent produces a severed edge, not a reparented visible edge.
- Registry or display-name changes after execution cannot change the frozen
  event identity.

### Exit gate

No included action reaches projection without one truthful binding subject or
closed systemic disposition. No client binding depends on an action display
name, presentation classification, or hidden implementation ref.

### Explicit exclusions

- Do not close whole-catalog client admission yet; that is Block 8.
- Do not redesign applications or terminal result payloads.
- Do not invent public aliases for private refs.
- Do not put art, VFX, delivery, or timing into semantic identity.
- Do not add another provenance graph or identity service.
- Do not change action, reaction, or spell mechanics.

---

## Block 2 — Ordered action applications

### Goal

Replace deduplicated target lists and first-target handling with execution-owned
ordered application records for generic actions, carried through the existing
client intent graph.

### Ledger rows

Primary ownership: `A01–A05`, `C05`.

Spell-specific adoption is completed in Block 7 through `S04–S10`.

### Work included

#### Engine execution

- Store applications as a closed tuple owned by the existing root action
  lifecycle. This is not a global application registry or a new graph.
- Give every allocated application an immutable execution-owned ID, execution
  index, tagged endpoint, terminal lifecycle, ordered result IDs, and optional
  exact direct predecessor (`A01`).
- Give every current `TargetType` an explicit disposition (`A02`):
  - `ENTITY`, `OBJECT`, and plain `POSITION` can own exact applications;
  - `MULTI_ENTITY` and `POSITION_AOE` preserve deterministic execution order;
  - `SELF` has an explicit root/application rule rather than an inferred target;
  - `POSITION_PATH` and `POSITION_LOS` remain on their specialized movement
    route and are not forced into generic application records.
- Preserve repeated endpoints as distinct applications rather than deduplicated
  target UUIDs.
- Freeze Weapon Coat's selected post-handler equipment endpoint once and make
  the mutation consume that same owner/slot/weapon UUID (`A03`).
- Preserve exact generic-action area geometry for Breath Weapon, Sunbeam
  follow-up actions, and other current geometry owners (`A04`).
- Freeze the selected typed `selection_parameter` on execution rather than
  leaving it only on action discovery objects (`A05`).

#### Projection and SDK

- Project the ordered authorized subsequence without renumbering the underlying
  execution identity or creating bypass edges.
- Preserve tagged Entity, Position, Object, and the one proven Equipment
  endpoint shape; do not coerce an Object into an Item merely because its
  runtime object happens to be item-backed.
- Generate one closed application lifecycle union. A generic completed
  application does not fabricate a spell-style AUTOMATIC result when execution
  owns no typed outcome; typed child results remain exact children.

#### NeuroClient

- Enrich the existing `ActionIntent` and `UseItemIntent` with the ordered
  application records and root-only result children (`C05`).
- Each application keeps its own ID, endpoint, lifecycle, result IDs, and child
  intents. Do not flatten them into `target_uuids`, first target, or `onEffect`.
- Local recipes may schedule/group application IDs, but cannot delete,
  duplicate, reorder across a causal edge, or invent an application.

### Required observable checks

- Zero, one, many-distinct, and repeated-endpoint application cases survive
  engine execution, privacy projection, SDK decode/replay, and client mapping.
- Entity, Position, Object, and Weapon Coat Equipment endpoints retain their
  exact identity and result ownership.
- A hidden application can be omitted without changing the IDs or direct edges
  of remaining applications.
- Selected generic geometry and typed selection parameters survive unchanged.
- Action and UseItem client plans contain the same application ordering and
  ownership as the delivered frame.

### Exit gate

No generic action renderer path depends on a deduplicated target list, a first
target, or a flat effect array as its semantic source.

### Explicit exclusions

- Do not change target legality, target ordering, convolution, or mutation
  mechanics.
- Do not convert movement paths/LOS traces into generic applications.
- Do not implement spell-specific routing here.
- Do not add renderer delivery, animation phases, or media to an application.
- Do not create a parallel application graph or service.

---

## Block 3 — Terminal action results

### Goal

Make every included action result replay-safe and self-contained at the engine
boundary, then preserve it through projection and the existing client result
intents without relying on later mutable state.

### Ledger rows

Primary ownership: `A06–A20`, `C03–C04`.

### Work included

#### Checks, damage, and healing

- Preserve check/contest roll, bonus, total, optional DC, and the engine-owned
  result when present. A no-DC completion remains total-only; do not invent a
  tie outcome (`A06`).
- Produce exactly one terminal damage result for applied, zero/no-damage,
  blocked, and canceled return paths (`A07`). The terminal observation must not
  be a new handler-visible gameplay event that changes mechanics.
- Carry authorized ordered `DamageType` plus `ResistanceStatus` component
  outcomes; never infer affinity from the final amount (`A08`).
- Give object damage an Object endpoint, structural HP semantics, and ordered
  destruction/location children without creature temp-HP or life-state fields
  (`A09`).
- Freeze healing before/requested/applied/resulting facts and one closed
  terminal disposition on all return paths (`A10`).
- Preserve temporary-HP previous/requested/resulting facts as a first-class
  result (`A11`).

#### Items, equipment, lifecycle, and handoffs

- Preserve item charge/quantity facts and exact action/application lineage
  (`A12`).
- Add exact before state to existing resulting item-location/transfer facts for
  Drop, PickUp, Loot All, consumption, destruction, and merges (`A13`).
- Make equipment-transition coverage and mapper consumption use the same typed
  transition context (`A14`).
- Preserve previous/current life state, reason, and exact cause in existing
  lifecycle intent/evidence (`A15`). Appearance remains local.
- Preserve action-caused condition identity, operation, disposition, subject,
  and exact application ancestry (`A16`).
- Keep the existing neutral spatial-effect lifecycle payload unchanged and
  repair only its exact action/application ownership (`A17`).
- Preserve reducer-owned state-only Door/Light transitions and their typed
  action parent (`A18`). Static representation is untouched.
- Add action causality to encounter-end feedback only when the current end was
  actually action-caused (`A19`).
- Delete/move ItemAction animation fields and presentation classifications into
  existing client recipes (`A20`).

#### NeuroClient

- Enrich existing Damage, Heal, Die, Revive, condition, and equipment intents
  with immutable neutral payload and source evidence (`C03`).
- Add a member to the existing `ClipIntent` union only for an included rendered
  result that currently has no semantic intent owner. A result that is always
  intentionally state-only needs evidence/disposition, not an invented clip.
- Keep floating numbers, badges, flashes, and labels as optional local children;
  they cannot be the only semantic owner (`C04`).

### Required observable checks

- Every cancellation/no-change/applied path returns one deterministic terminal
  observation and replays identically.
- Damage affinity remains absent when unauthorized and exact when authorized;
  the client never derives it from zero damage.
- Object damage never gains creature-only fields.
- Healing and temporary HP never read the later live entity to reconstruct
  before/resulting pools.
- Item transfer/merge/destruction retains exact before/after ownership.
- Condition and spatial-effect appearance bytes/recipes remain unchanged while
  action ancestry becomes exact.
- Door/Light remains state-only, and general encounter lifecycle remains
  unchanged.

### Exit gate

Every included action result either has one exact rendered semantic owner in
the existing intent graph or one explicit state-only/no-visual disposition.
No local badge or later state read substitutes for a missing engine result.

### Explicit exclusions

- No condition appearance redesign.
- No spatial-effect state, geometry, layer, descriptor, or visual redesign.
- No static world, terrain, tile, ground, Door, or Light representation work.
- No general encounter or turn-presentation redesign.
- No changes to damage, healing, inventory, equipment, death, or condition
  mechanics.

---

## Block 4 — Attacks

### Goal

Carry the complete neutral attack execution while removing the server/client
carrier inference that currently turns equipment slot into presentation
delivery.

### Ledger rows

Primary ownership: `AT01–AT09`.

This block consumes Block 1 identity for configured/nested attacks and Block 3
terminal damage results.

### Work included

- Preserve attacker, target, canonical `AttackOutcome`, damage types, and
  ordered impact-result children (`AT01`).
- Carry canonical resolved `Range` and `is_long_range`, which execution already
  owns but projection currently drops (`AT02`).
- Delete ranged-slot → `PresentationProjectile.BOLT` inference (`AT03`).
- Preserve exact disclosed source item and selected `WeaponSlot`; allow an
  absent/coarse source when privacy does not authorize exact classification
  (`AT04`).
- Replace display-name-based Bite/Claws/Slam rider/effect matching with one
  canonical mechanical intrinsic-attack distinction, preserving existing
  behavior (`AT05`).
- Add no throw-mode or ammunition fields where execution made no such selection
  (`AT06`).
- Enrich the existing `AttackIntent` with the neutral payload while keeping
  body animation, contact/projectile presentation, local trajectory, speed,
  anchors, and media under `localRecipe` (`AT07`).
- Preserve the configured Multiattack root on its child attacks (`AT08`).
- Preserve exact Retaliation and True Strike ancestry; reuse the working
  Opportunity Attack binding-copy pattern rather than inventing a second
  identity route (`AT09`).

### Required observable checks

- Reach and ranged attacks retain exact range/outcome/source facts through
  decode and replay.
- Critical miss remains distinct from ordinary miss.
- Changing a client recipe between contact and projectile presentation cannot
  change attack facts or child results.
- All ten configured Multiattack variants select the correct child attribution.
- Retaliation and True Strike expose one exact outer identity plus their nested
  attack, with no display-name fallback.
- Existing Bite/Claws rider behavior is unchanged after mechanical matching no
  longer uses names.

### Exit gate

`AttackIntent` is the one attack semantic owner, and no engine/projector field
selects Bolt, projectile media, animation frames, or local travel timing.

### Explicit exclusions

- Do not change attack rolls, advantage, range validation, damage, hit riders,
  Multiattack composition, or intrinsic-attack mechanics.
- Do not add thrown mode or ammunition facts absent from current selection.
- Do not create a server projectile/impact phase.
- Do not replace the existing attack runner or intent graph.

---

## Block 5 — Movement and displacement

### Goal

Preserve truthful voluntary/forced movement causality and settle each resulting
entity position exactly once, without redesigning the world or changing
movement mechanics.

### Ledger rows

Primary ownership: `M01–M17`, `A21`, `C11`.

### Work included

#### Voluntary movement

- Preserve family, trajectory, committed anchors/elevation, endpoint outcome,
  and the exact movement facts consumed by presentation (`M01`).
- Preserve exact causing behavior for Move, aggressive movement, flight,
  Command-driven movement, and similar current producers (`M02`).
- Carry canonical `MovementTerminationReason` (`M03`).
- Preserve the existing jump arc/elevation evidence without reconstructing it
  from later actor state (`M04`, `M05`).
- Preserve connector identity/endpoints/revision. Remove `presentation_key` from
  action transport. Do not silently call `TraversalConnectorKind` mechanical
  while its current contract defines it as a presentation family; either
  reauthor it as a genuine physical connector form or keep it local (`M06`).
- Add explicit disclosed cross-head locomotion continuity/sever/terminal facts
  through the existing replication runtime and `LocomotionSessionOwner`, not a
  new scheduler (`M07`).
- Preserve Opportunity Attack at its current provisional pre-edge boundary;
  the edge still commits or rejects according to existing execution (`M08`).

#### Forced movement and relocation

- Replace the common forced-movement distance fields with truthful
  kind-specific facts: Push displacement, Compelled Path planned/actual path
  cost, and Reposition endpoints (`M09`, `M11`).
- Preserve ordered committed anchors/elevation, closed blocked state, and exact
  equality with the final entity state patch (`M10`).
- Delete `blocked_by` display text; keep only the existing closed boolean until
  a real typed blocker resolver exists (`M12`).
- Move duration, target clip, brace frame, playback speed, motion curve, facing,
  and recovery to existing client recipe data (`M13`).
- Emit a neutral teleport observation only when the existing Misty Step or
  Dimension Door position mutation commits (`M15`).
- Around Banishment, preserve only exact action-owned exit/return causality and
  any already-executed separate occupant displacement. Do not redesign
  presence/world state or return mechanics (`M16`).

#### Shove and client settlement

- Preserve Shove outcome/children while moving Kick/contact-frame/speed policy
  to the local recipe (`A21`).
- Replace the frame-wide cue-empty settlement rule with exact per-entity patch
  ownership, so one head may render entity A while state-settling entity B
  (`M17`, `C11`).
- Live and replay use the same settlement evidence.

### Required observable checks

- Voluntary path, Jump, connector transfer, interrupted movement, and
  Opportunity Attack boundaries preserve the same committed endpoint and
  causal order as before.
- Elevation and termination survive SDK decode/replay even though current
  animation remains planar.
- Eyebite movement cost is never relabeled as geometric displacement.
- Telekinesis Reposition and push displacement no longer share a fake distance
  meaning.
- Mixed heads settle the exact changed entity patches once each; unchanged
  upserts do not snap.
- Banishment behavior, returned cell choice, occupancy behavior, and grid
  mutation are unchanged.

### Exit gate

Every action-owned changed entity position has one exact rendered or state-only
settlement owner. Backend timing/clip policy is absent from movement transport.

### Explicit exclusions

- Do not add a zero-displacement `ForcedMovementEvent` for an immediately
  blocked Shove, Thunderwave, or Gust (`M14`).
- Do not change Banishment removal, return, occupancy, displacement, or grid
  mechanics (`M16`).
- Do not redesign world, grid, terrain, tiles, ground, connectors, or presence
  representation.
- Do not add new three-dimensional movement playback.
- Do not expose hidden path, terrain, or selection facts merely for animation.

---

## Block 6 — Installed reactions

### Goal

Give each installed reaction one exact trigger, one truthful phase/result
mutation, and one client presentation root, while retaining existing reaction
mechanics.

### Ledger rows

Primary ownership: `R01–R08`.

This block consumes exact handler/action identity from Block 1, terminal results
from Block 3, attack stages from Block 4, and movement boundaries from Block 5.

### Reaction-by-reaction work

| Row | Reaction | Required repair |
|---|---|---|
| `R01` | Opportunity Attack | Keep it as the reference pattern: exact step trigger, active reaction binding copied to nested Attack, and edge commit/reject order unchanged. |
| `R02` | Retaliation | Preserve the positive post-mitigation damage trigger and exact reaction attribution on the counterattack. |
| `R03` | Protection | Preserve the before-roll disadvantage mutation, trigger attack, and before/after advantage state. |
| `R04` | Divine Smite | Replace open context with typed selected-level and damage-packet append facts; keep controlled details private and attach the append/result at the real impact phase. |
| `R05` | Parry | Preserve its post-roll/pre-effect HIT→MISS mutation and exact attack stage. |
| `R06` | Counterspell | Preserve exact cast trigger and success/failure result; remove fabricated touch delivery from client presentation. |
| `R07` | Hellish Rebuke | Produce one reaction root and one emitted remote countereffect attached to the exact incoming damage trigger. |
| `R08` | Shield | Distinguish post-roll attack prevention from terminal Magic Missile-linked Damage cancellation; the spell application remains automatic. |

### Shared engine/projection/client work

- Reuse exact reaction `ContentRef`, existing `EventType`, `EventPhase`,
  `HandlerDispatchOutcome`, trigger presentation/application identity, ordered
  emitted result IDs, and typed before/after mutation facts.
- Add a minimal attack-stage discriminator only where the executed phase cannot
  otherwise be expressed. Do not add a generic renderer scheduling phase.
- Project controlled and coarse variants according to the same-observer privacy
  rule. If trigger/application relationship authorization fails, omit the
  reaction relationship rather than guessing a nearby Attack or Spell.
- Keep one reaction semantic payload in the existing intent graph. Local
  preamble, body clip, badges, media, and schedule offsets remain recipe data.

### Required observable checks

- Exercise each of the eight installed reactions at its real event boundary.
- Verify exact trigger, phase, handler identity, before/after mutation, ordered
  emitted result IDs, and final authoritative result.
- Verify controlled/coarse privacy cases without leaking selected resources or
  hidden handler identities.
- Verify no handler root plus emitted action produces duplicate actor
  presentation.
- Verify replay produces the same reaction/child ordering as live mapping.

### Exit gate

All eight reactions produce one exact semantic root and preserve their real
trigger/result relationship without client phase guessing.

### Explicit exclusions

- Do not change reaction eligibility, resource use, rolls, damage, AC,
  interruption, or timing mechanics.
- Do not expose controlled/private handler details for presentation.
- Do not add a generic scheduling label as engine causality.
- Do not reinterpret Shield's Magic Missile case as a canceled spell
  application.

---

## Block 7 — Spell execution

### Goal

Carry exact spell identity, applications, results, and area geometry through one
normalized existing Cast intent while making all manifestation routing/timing
client-local.

### Ledger rows

Primary ownership: `B04`, `S01–S18`.

This block consumes the identity/privacy foundation, application substrate,
terminal results, attacks, movement/teleport, and reaction relationships from
Blocks 1–6.

### Work included

#### Catalog and exact identity

- Preserve exact-ref recipe coverage for all 116 current catalog rows (`B04`,
  `S01`).
- Use exact selected spell behavior identity instead of normalized display IDs
  (`S02`).
- Preserve lawful source-item/provider attribution (`S03`).
- Ensure Acid Flask resolves through its truthful public item/provider/action
  identity rather than its hidden implementation (`S17`).

#### Applications and results

- Adopt the Block 2 application substrate for spells: root-owned ordered
  Entity, Position, and Object applications with execution IDs and ordered
  result children (`S04`, `S06`, `S07`).
- Support successful zero applications and privacy-filtered zero applications
  (`S05`).
- Preserve repeated/multi applications independently; never choose a first
  endpoint or derive route from visible count (`S08`).
- Replace lossy mapper `SpellApplicationOutcome` with canonical AUTOMATIC,
  ATTACK carrying the full canonical `AttackOutcome`, or SAVE carrying
  `succeeded`. Damage resistance/immunity remains on Damage results (`S09`).
- Preserve per-application cancellation as a distinct terminal lifecycle,
  without conflating it with a canceled Damage result (`S10`).

#### Geometry and causality

- Carry exact immutable sphere, cone, line, cube, and cylinder geometry,
  including origin/direction and the currently dropped cone angles, line widths,
  and cylinder heights (`S11`).
- Freeze Chain Lightning's actual selected earlier predecessor during its
  existing target-selection loop; do not change candidate selection or tie
  behavior. Privacy can sever the direct edge but never add a bypass (`S12`).
- Preserve exact identity/geometry on Sunbeam Strike, Eyebite Strike,
  Telekinesis Grab, Breath Weapon, and other generic follow-up roots (`S16`).

#### Renderer boundary and Cast intent

- Add no server flight/arrival phase for Fireball or another spell whose current
  gameplay has no rule-visible in-flight state (`S13`).
- Delete legacy runtime/cue/SDK projectile/delivery/VFX authority that mixes
  morphology, range, target count, route, and assets (`S14`).
- If retained, reauthor optional physical description as exact-ref catalog-only
  text/closed suggestion: noncausal, optional, ignorable, never an Event/cue/SDK
  field or binding/admission discriminator (`S15`).
- Normalize the existing `CastIntent` around exact range, geometry,
  applications, lifecycle, and result children. Keep manifestation/area phase
  graph, projectile/contact form, media, body clip, easing, and timing in the
  separate local recipe consumed by the existing `CastClip` (`S18`).

### Required observable checks

- All 116 exact refs still resolve after legacy route fields are removed.
- Zero, Entity, Position, Object, repeated, multi, attack-resolution,
  save-resolution, and canceled application cases survive decode/replay/mapping.
- Critical miss remains canonical and affinity remains on Damage results.
- Full geometry is field-for-field equal at the client semantic boundary.
- Branching Chain Lightning preserves each actual direct parent; hiding a
  parent produces a severed edge, never a synthetic chain.
- Fireball client phase timing can change without changing engine event order,
  application order, or final state.
- Changing/omitting an optional catalog physical description cannot alter
  runtime spell causality or binding admission.

### Exit gate

No runtime spell presentation depends on legacy delivery/projectile/VFX fields,
visible target count, first-target selection, or live scene geometry.

### Explicit exclusions

- Do not change targeting, saving throws, attack rolls, damage, cancellation,
  Chain Lightning selection, or any spell mechanic.
- Do not create an interruptible/collidable Fireball flight state.
- Do not make optional physical description causal or required for admission.
- Do not restore legacy route/VFX authority under new names.
- Do not migrate static world, ground, terrain, or general spatial-effect
  representation.

---

## Block 8 — NeuroClient, Studio, and activation closure

### Goal

Close the action-only hard cut after Blocks 1–7: one complete existing client
graph, one production mapper for live/replay/Studio, pre-stream binding/media
admission, safe head recovery, and removal of every retired inference path.

### Ledger rows

Primary ownership:

- structural rows `B01–B03`, `B05–B06`;
- cross-cutting client boundary rows `X11–X12`;
- NeuroClient/Studio rows `C01–C02`, `C06–C10`, `C12–C13`.

This block also performs final regression/cleanup for renderer-policy rows
already implemented by their semantic owners: `A20`, `A21`, `AT03`, `AT07`,
`M13`, `R06`, `S13`, `S14`, and `S18`.

### Work included

#### One existing client path

- Keep `subjectivePresentationMapper.ts` as the single mapping boundary for
  live and replay (`B01`, `C01`).
- Keep the existing `VisualTransaction`/`ClipIntent` union, dispatcher, queue,
  and reducer as the only graph (`B02`, `C02`).
- Preserve exact neutral semantic evidence before selecting a local recipe.
  Move frames, clips, speeds, delivery/VFX/art keys, and other renderer policy
  fully into existing local recipe owners (`X11`).
- Enrich the existing mapper/plan/transaction evidence with immutable bundle
  generation/digest and field-use/ownership proof where needed. Do not put
  client bundle provenance in the SDK journal or add another evidence graph
  (`X12`).

#### Action/Spell Studio

- Remove backend tint, VFX profile, visual variant, route hint, and asset-tag
  reads from action recipe compilation/Studio semantic construction (`C06`).
  General presentation storage outside action compilation is not deleted.
- Replace Action/Spell Studio fact fabrication with explicit SDK-valid frames
  that run through the production mapper (`C07`).
- Synthetic authoring frames are valid only when labelled synthetic and fully
  explicit. Consumers may substitute declared opaque run/entity IDs and apply
  one rigid transform consistently; they may not change content identity,
  endpoint count/kind, outcome, geometry, path, or result ownership (`C08`).
- Keep existing Studio repository/persistence owners. Do not expand this block
  into a new general persistence/source-store system or migrate condition
  authoring.

#### Admission and resources

- Preserve current exact recipe closure (`B03`) and make missing exact
  definition/role/variant/disposition rows a hard failure before stream
  attachment (`B06`, `C09`).
- Compile and prepare only action-owned media selected by the resolved recipes
  before activation.
- Detach actor/ancestry/general-icon/rig prerequisites from action admission
  while keeping their diagnostics visible through existing control-plane
  reporting (`C10`).

#### Head recovery and local time

- Preserve the SDK's authoritative/presentation replicas and opaque one-use
  token (`B05`).
- Keep a failed pre-commit head pending and non-overtakable, while giving
  staging/clip failures an explicit scene restoration or reload owner before
  retry. Distinguish pre-commit failure from already-committed postcommit sync
  failure (`C12`).
- Pin one immutable client presentation authority on the existing normal plan
  and transaction. A bundle swap cannot remap an accepted head midway.
- Local animation duration may vary but cannot reorder engine heads,
  applications, parents, or results (`C13`).

### Required observable checks

- Cue and intent dispatch remain exhaustive at 18 and 25 current variants, or
  at the deliberately updated hard-cut counts with no unhandled member.
- Every wire-emittable action subject/role/variant has one exact recipe, explicit
  generic policy, state-only/no-visual disposition, or installation failure.
- A missing binding or broken action-owned media asset fails before stream
  attachment and leaves the old active generation unchanged.
- Broken general actor/ancestry/icon data remains observable in diagnostics but
  cannot block or mutate action activation.
- Action Studio, Spell Studio, live play, and replay produce the same semantic
  transaction from the same SDK frame.
- Studio recipe/art changes cannot mutate neutral frame bytes.
- Precommit mapping/resource/staging/clip failure cannot spend or overtake the
  head; recovery restores/reloads the scene before retry.
- State-only and rendered heads retain exact pinned bundle provenance.
- Local timing changes do not alter journal order or final state.
- No old renderer-shaped backend field or client inference remains reachable.

### Exit gate

The action bridge has one exact engine-to-client semantic route, one existing
client graph, one pre-stream closure gate, and no fallback to display names,
backend art, route inference, first-target flattening, or frame-wide position
settlement.

### Explicit exclusions

- Do not add another graph, dispatcher, scheduler, reducer, replay path, or SDK
  journal responsibility.
- Do not make actor rigs, ancestry/body appearance, portraits, general icons,
  or equipment art prerequisites for action admission.
- Do not redesign condition visuals or migrate condition authoring/persistence.
- Do not redesign static world, terrain, tile, ground, or spatial-effect
  visuals.
- Do not create deployment, content-rollout, or general persistence
  architecture.
- Do not use backend milliseconds as causal ordering.

---

## Cross-block handoffs

The following overlaps are dependencies, not duplicate implementation work:

| Foundation | Consumed or regression-checked by |
|---|---|
| Direct/configured/handler identity (`X02–X04`) | Multiattack/Retaliation/True Strike (`AT08–AT09`), movement identity (`M02`), reactions (`R02–R08`), spell follow-ups (`S16`) |
| Source/provider/privacy identity (`X05`, `X08`, `X09`) | attack source (`AT04`), spell identity/source (`S02`, `S03`), Acid Flask (`S17`) |
| Direct causal/application identity (`X10`) | generic applications (`A01`, `C05`), condition/spatial children (`A16`, `A17`), reactions, and spells (`S04`, `S08`, `S10`, `S12`) |
| Generic area geometry (`A04`) | attack/spell follow-ups and complete spell geometry (`S11`, `S16`) |
| Terminal damage/affinity (`A07`, `A08`) | attacks, spell applications, Divine Smite, Shield, and other reactions |
| Item/equipment results (`A12–A14`) | UseItem application plans and item-sourced attacks/spells |
| Renderer-policy removal (`X11`) | ItemAction/Shove, attacks, movement, Counterspell, spells, Studio, and final admission cleanup |
| Journal and local time (`B05`, `C12`, `C13`) | every client block; implementation owner remains Block 8 |

## Per-block completion protocol

For each block:

1. Select only that block's primary ledger rows plus named dependency checks.
2. Write the observable input/output cases before production edits.
3. Implement the vertical hard cut across engine, projection, SDK, existing
   client intents, and replay.
4. Run the smallest deterministic domain/projection/SDK/client checks first;
   run browser/live checks only for resource, queue, GPU, or real integration
   ownership.
5. Confirm all explicit exclusions remain unchanged.
6. Update the manual ledger by hand with implemented/verified evidence for the
   rows actually completed.
7. Do not begin a dependent block until the current exit gate is satisfied.

## Final completion condition

The eight blocks are complete only when all 104 ledger rows have an implemented
or deliberately unchanged/out-of-cut disposition backed by observable evidence,
and all of the following remain true:

- engine facts and causality are not inferred by the renderer;
- the SDK journal remains generic and authoritative for head ordering;
- NeuroClient uses its existing mapper/transaction/intent graph;
- Studio uses explicit SDK-valid frames and the production mapper;
- action binding/disposition/action-media closure happens before stream
  attachment;
- static world/ground and condition appearance remain untouched;
- no gameplay mechanic was changed merely to improve presentation.
