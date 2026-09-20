# Trap state and variants — small feature plan

**Status: backend, narrative tests and paired visual replay validated September 19.** The user approved
this unit and requested the existing artwork task be redirected after backend
validation. The user subsequently approved damage to occupants on activation
and requested the complete lifecycle clips below.
This plan records the bounded implementation; the companion
[variant study](GROUND_TRAP_VARIANTS_2026-09-19.md) explores later content.

## Backend result

- `SpikeTrap` now retains Ready / Activated / Deactivated state and identity.
  Installation/removal still use the original spatial lifecycle. Entry triggers
  deployment once, raised entry applies the payload, and lowered disabled entry
  does nothing. Authored initially raised spikes are also perceptible.
- Frozen `TrapPayload` values compose the existing damage and save/Poisoned APIs.
  The three authored profiles share one handler. Poison damage respects damage
  resistance/immunity; save-gated Poisoned respects condition immunity and its
  ordinary duration. Lowering the trap does not cure an applied condition.
- A fixture observation hook feeds the existing affected-visible-cell sensory
  refresh. The same trap is observed once per refresh, with only observed cells;
  remembered cells and descriptions remain unchanged while unseen. Removal is
  learned by re-observing absence. Native and player deltas serialize these values.
- Finite levers lower the fixture without deleting it. A reusable lever is
  authored with `charges=-1, allow_activation=True`; its commands follow its own
  physical handle, so a remote trap mutation cannot change the local menu.
  Charges, handle and target state remain independent recorded facts.
- New descriptions come from backend state and are captured in the observer's
  value. The existing sheets are not yet bound to this new presentation state;
  renderer integration and visual clips remain the next part of the unit.

Validation on the WSL uv environment with this C: checkout:

- **128 tests passed in 13.56s** across spatial conditions, trap payload/discovery,
  sensory replay, environment controls, player projection, paired environment
  replay and the existing usable-item contract. New packet tests encode/decode
  both observers after resetting the native runtime; secret trap UUIDs and unseen
  network cells stay absent.
- **Four architecture checks passed**: DAG, dependency direction, no TYPE_CHECKING
  workaround, and neutral type composition. The former zero-dependency sensory
  assertion already rejected its existing `LightLevel` import; it now permits
  only exact passive value dependencies and also checks the added leaf modules.
- Focused Pyright is clean for trap/sensory types, sensory implementation,
  controls/builders/action definitions and affected player/presentation files.
  Broader touched-file checking still reports three preexisting diagnostics in
  BaseCondition/events/area conditions and 59 unchanged constructor-unpack errors
  in `build_environmental_replacement`, verified against HEAD. No blanket type
  suppression was added. Two separately attempted legacy spike-movement tests
  fail before trap execution because their fixture actors were never deployed.
- Independent anti-OOP review approved native state/sensory/replay ownership;
  independent anti-slop review approved native state, sensory and controls.
  Root also reviewed controls, including local handle and target separation.

Artwork request sent to the existing task `01a0b501-8a27-7413-ba24-4a36e5b140d2`
after these checks/reviews. It asks to preserve/pause the cannon work, deliver
approved spike geometry plus matching coating variants first, then explore the
wire/clamp/common-vent families. It includes the actual native state contract,
the user's pixel-density/palette correction, and direct-to-user artifact handoff.
This is a dispatched artwork request, not a claim that new sheets are finished.

Reproduce the gameplay lane with `uv run --no-sync python -m pytest -q` and:
`tests/engine/test_spatial_conditions.py`, `test_trap_payloads.py`,
`test_trap_discovery.py`, `test_environment_controls.py`,
`test_senses_light_stealth.py`, `test_sensory_initial_replay.py`;
`tests/game/test_player_projection.py`, `test_trap_player_replay.py`,
`test_environment_control_projection.py`, `test_paired_environment.py`;
`tests/manual/test_134_stackable_usable_item_legacy_contract.py`.
The WSL uv executable/environment paths remain those in `HOW_TO_TEST.md` and
the recovery environment notes.

**September 19 follow-up now authorized:** activation applies the shared payload
once to each current occupant. First entry into Ready uses that activation path
without an additional entry hit; entry into already-raised spikes keeps its
ordinary single hit. Same-state activation does not repeat the payload.

## Current clip acceptance unit

Record actual discovered actions in a native encounter, from both participants,
then render each saved subjective packet with all four camera corners:

1. Detected and undetected trap setups use native passive perception against
   authored concealment DC. Do not invent a Stealth roll or set discovery flags.
2. The walker enters and takes damage, exits, re-enters already-raised spikes
   and takes damage again, then exits.
3. The other character uses the reusable lever to lower the spikes. The walker
   enters, exits and re-enters safely, remaining on the disabled footprint.
4. The operator activates the same lever; the stationary walker takes the normal
   payload as the spikes rise. Keep gesture/contact, state and damage together.
5. Cover plain, poison-damage and save-gated Poisoned profiles through the same
   fixture authoring. Capture native HP/state/condition evidence and replay the
   persisted public input without invoking the engine again.

Use the already approved staged spike/lever sheets. New coating art from the
artwork task is optional and cannot block this proof. Extend existing passive
bindings and historical sampling rather than adding a clock or bespoke scene.
Anti-slop reviewer: `environment_asset_scan`; anti-OOP review: root and
`environment_timeline_review` reviewing each other's changes. These reviews
include checking that the clip producer changes starting data only, then uses
real actions and events throughout the captured sequence.

### Implementation and validation

The requested ten-action encounter now runs through native action discovery and
turn progression. The same `trap_history` producer supplies both the seven
parameterized acceptance tests and seven paired review cases. Deterministic dice
choose damage/save results; they do not create events, teleport actors, assign
HP or bypass the actual action. Setup publishes the placed lever's initial
floor state through its ordinary API before the recorded baseline.

Activation damages each distinct current occupant under the native state-change
lineage. First entry delegates to that activation once; already-raised entry
applies one payload. Explicit plain/poison-damage/Poisoned content identities
select plain/coated art, while all profiles keep one native handler. Both views
decode their own saved public packets after the native runtime has closed.

The original Studio interaction recipe owns contact frame 3. Finite prop poses
and FPS live in world-binding data shared by drawing and timeline compilation;
their end time joins the existing head even when no visible actor gesture or
damage animation keeps it alive. Entry consequences use the existing child
compositor at the reached cell. State contact/arrival anchors survive nested
damage callbacks; ordinary forced movement keeps its existing interpolation.

Only a permitted `SpatialEffectStateFact` animates spikes. Sensory deltas remain
the persistent state writer, and reacquisition after an unseen toggle selects
the received endpoint without replaying hidden motion. The local native-history
reducer also retains spatial lifecycle causality without applying state twice.

Validation so far:

- 134 native/public/architecture checks passed in 22.54s, including all seven
  narratives, payload/discovery, subjectivity and dependency boundaries.
- 39 focused presentation/movement/teleport/condition checks passed in 36.62s,
  with the two already documented stair-occlusion expected failures. New checks
  cover first discovery, both lever operations, occupied activation, coated
  identities, four camera poses, seeking, unseen reacquisition and transition
  duration without an actor animation.
- Changed presentation/data/public/recording modules pass focused Pyright.
- Initial full capture and final fresh-process saved replay: 14/14 passed,
  zero gaps, 259 frames each at 24 FPS; each clip lasts about 10.79s. All 14
  final recordings use byte-identical saved public inputs and reproduce the same
  final gameplay states as capture. Root inspected actual four-view raster frames for hidden
  versus detected initial traps, first/repeated damage, lowered safe occupancy,
  lever contact and raising beneath the walker, including coated/Poisoned art.
- Final architecture/lifecycle/narrative follow-up: 20 tests passed in 15.53s.
  Final changed-module typecheck is clean. The five gallery/CLI/server checks
  also pass; old and new galleries link to the searchable saved-run archive.

Final [paired trap gallery](http://127.0.0.1:8767/runs/20260918T233243Z-33b2d6/index.html).
The [all-runs archive](http://127.0.0.1:8767/) preserves access to earlier captures.
Artifacts live under `.runtime/animation-review/runs/20260918T233243Z-33b2d6/`;
they are not temporary test-directory outputs. Reproduce with
`python -m devtools.animation_review --tag trap-lifecycle`; use the separate
`capture` module only when intentionally regenerating the native encounter.

Independent native/anti-OOP review approved observation boundaries, occupant
parentage, explicit authoring and real scenario actions. Presentation anti-slop
review found and prompted the hidden-reacquisition and actorless-duration fixes;
the final independent `final_trap_review` approved those corrections. These are concrete review
findings and tests, not a claim that every future environmental behavior is done.

## Agreed direction

### Bloodied tile study — ownership agreed, implementation paused

The subsequent skeleton/demon expansion and practical implementation sequence are
owned by the [full body-release/residue plan](BODY_RELEASES_AND_RESIDUES_PLAN_2026-09-19.md).
This section retains the source study and evolution of the agreed ownership.

The delivered clean/coated and bloodied sheets share one geometry; the separate
transparent blood layer reconstructs both bloodied variants. Retracting hides
the stained shafts without clearing the stain. The user proposes a reusable
Bloodied condition rather than another internal trap state.

Native study found that Tiles already host ordinary conditions and publish their
application/removal with tile after-values. A spike mechanism is itself a
condition, so it is not an existing condition host. The user explicitly chose
Bloodied tile state to select the bloodied variant of spikes on that tile.
Keep that art binding specific and preserve the fixture's existing disclosure.
The user chose the tile. Its property is mechanically inert for now and may
participate in elemental/magic interactions later. The subsequent direction is
initially one map-wide damage handler, then refined to **a handler on each
creature releasing blood or another authored substance when damaged**. Reuse
one shared processor with different body data; no per-monster implementation.
The user also suggested poisonous fluid, bone fragments and smoke as alternate
releases driving presentation. The earlier spike-only trigger and map-owned
subscription proposals are superseded. The request to study before implementing
still applies. No Bloodied feature code has been implemented, and a dedicated
Entity boolean is not an agreed design.

#### Findings from the existing engine

- `Entity.feature_sources` already holds source-owned semantic features, with
  `add_feature_source`, `remove_feature_source` and `has_feature`. Composition
  installs features before birth; `EntityCreatedEvent.feature_ids` records them.
  A body-owned feature such as `body.blood` was the initial candidate. The refined
  requirement calls for an authored release identity/configuration. Existing
  body composition can install its shared handler; avoid storing the same
  configuration independently in a boolean, a feature and a handler profile.
- `CreatureType` has no subtype field. Skeletons, zombies and ghouls all use
  `UNDEAD`, so a type-only rule cannot distinguish those bodies. Appearance is
  gameplay-inert, poison immunity is not evidence of lacking blood, and terrain
  `Material` does not currently model creature bodies. The active monster modules
  supply no vampire precedent. Do not infer biology from names or sprite rigs.
- `Entity.receive_damage` resolves defenses and HP, emits `DamageAppliedEvent`,
  then processes life-state consequences. **`DAMAGE_APPLIED / EFFECT`** is the
  existing ordinary-handler boundary for actual damage consequences, also used
  by other rules. `TAKE_DAMAGE / EFFECT` is earlier, before HP changes. No new
  completion hook or mitigation calculation is needed.
- `DamageAppliedEvent` separates normal and temporary HP damage. A handler can
  inspect the damaged creature and its current committed cell, then parent the
  tile condition application to that exact damage event. This preserves the
  complete lineage and runs before death removes world presence. Ordinary
  `Trigger.event_target_entity_uuid` filters already scope a damage handler to
  its creature. `Entity.add_event_handler` supplies ownership/registration, and
  existing removal releases it. No map scan or new map lifecycle is needed.
- Ordinary tile condition application/removal already publishes `resulting_tile`.
  World projection retains observed tile state through existing sensory rules.
  `WorldTileState` currently exposes condition names only; a stable semantic
  membership representation is needed for data bindings, rather than matching
  descriptions or adding a separate stain registry.

#### Recommended shape, still a proposal

1. Body/creature composition installs an ordinary target-filtered damage handler
   with an authored release identity: blood, poisonous fluid, bone fragments or
   smoke are the user's examples. All instances share the same processor. The
   configuration describes the released substance and any persistent consequence;
   it contains no sprites or particle settings. Incoming damage type remains a
   separate fact: poison damage does not imply the victim releases poison.
   No additional feature flag is needed merely to enable that installed response.
   Existing BehaviorBinding carries provenance/identity, not the profile's data;
   existing configured-processor composition can supply the authored parameters.
2. At `DAMAGE_APPLIED / EFFECT`, record the actual release under its damage cause
   and apply any authored tile consequence. Keep **release occurrence** separate
   from **persistent residue**: another injury can produce another splash on an
   already Bloodied tile. Do not remove/reapply the condition to animate that.
   Release facts must survive subjective serialization, without live body lookups.
   The exact event payload extension is still to be chosen; current DamageFact
   carries damage type/HP results, but no released substance. Which injuries
   qualify and whether temp-HP-only absorption counts remain gameplay choices.
3. Existing Studio recipe/media data maps a permitted release fact to its burst
   at the causal injury time. Persistent tile state maps to a ground trace;
   Bloodied plus an already known spike fixture selects the delivered bloodied
   variant/overlay at the fixture's existing pose and frame. Native deposition
   determines the affected tile; particle trajectories never mutate game state.
   Re-observing an existing stain must not replay the original injury burst.
4. The tile property persists through lowering/removing the trap and departure
   of the creature. A smoke burst need not leave a persistent surface or imply
   an obscuring area. Poisonous fluid does not automatically apply Poisoned.
   Those mechanics require their own authored behavior if later requested.
   Blood burst and ordinary floor-stain art remain missing; the spike overlay
   alone is not proof of either. No magic or cleaning actions are implemented.

When implementation is authorized, acceptance should extend the actual walking /
lever narrative, add an ordinary non-trap injury and a non-blood-bearing creature,
and verify saved subjective replay and tile persistence. Retain both viewpoints
and all four cameras. Two qualifying hits on one tile must produce two releases
while retaining one Bloodied condition. The legacy private `game.presentation.reduce_lineage`
misclassifies tile condition owners; current public playback uses the guarded
player projection/world-fact path. Any correction for direct legacy consumers
should stay local, not become a replay redesign.

Read-only anti-slop/data review: `bloodied_data_review`. Read-only anti-OOP/event
review: `bloodied_native_review`. Both found existing mechanisms sufficient for
the proposed shape; neither resolves the remaining gameplay choices or constitutes
implementation/test evidence. Both also reviewed and supported the per-creature /
release refinement, including the need for explicit public release facts and the
absence of a redundant feature flag. Source anchors: `dnd/entity.py` feature ownership
and `receive_damage`, `dnd/core/events.py` DamageAppliedEvent/WorldTileState,
`dnd/core/base_tiles.py`, `dnd/core/base_block.py` condition application,
`dnd/content/characters/builds.py`, and `game/player_projection.py`.

Backend state governs mechanics, descriptions and the information players
receive. It contains no sprite frames, animation duration or rendering cues.
Handlers react to native events and commit state/effects under the actual cause.
Complete parent/child lineages remain the unit of historical playback.

| Mechanical state | Physical state | Spike behavior |
| --- | --- | --- |
| Ready | Down | Entry raises the spikes and resolves their effects. |
| Activated | Up | Remain raised until deactivated. Preserve current entry damage for this first spike family. |
| Deactivated | Down | No entry trigger/damage; retain the fixture's identity and footprint. |

Use one explicit mechanical state; derive these physical/behavioral properties
instead of maintaining contradictory armed/extended/disabled booleans. Discovery
is independent and observer-specific: unknown means no sprite or description;
discovered down means the retracted trap; discovered up means raised spikes.
Previously discovered traps remain known through deactivation/reactivation.
Ordinary sight rules still determine whether the observer receives a new state.

Activation from Deactivated raises the spikes, as the user requested. Returning
to Ready would be a distinct reset command, not an automatic timer or an alias
for activation; a player-facing reset action is outside the first slice.

## First implementation, in order

1. **Give the existing trap a persistent mechanical state.** Keep its existing
   spatial owner and position-indexed handler. `SpatialCondition.activate()` and
   `deactivate()` currently mean install/remove: preserve those lifecycle APIs.
   An installed, mechanically Deactivated trap is still present. Its hazard
   answer and handler consult its state; removing/destroying it remains separate.
   Add a parented state-change after-value through the existing event publication
   path. Do not introduce a generic state-machine runtime or per-variant classes.
2. **Keep discovery and received state coherent.** Reuse the existing native
   detection gate and reveal mechanism. Retain observer-local discovered identity
   and last-observed state; toggling does not erase knowledge. Record permitted
   identity, observed cells and state in sensory/player after-values. The current
   hazard boolean is insufficient, and global reveal alone is not per-observer
   memory. An unseen remote toggle does not refresh a remembered description or
   disclose the rest of a trap network. Preserve the existing perception rules.
3. **Drive descriptions and controls from native state.** Author descriptions
   for Ready (retracted/armed), Activated (raised) and Deactivated (retracted/
   disabled). The normal description/discovery surface selects the permitted
   state; text is not an independent mutable copy or a renderer guess. Connect
   explicit activate/deactivate actions and existing lever targeting to the same
   transition behavior, retaining parentage. A finite lever's charges and a
   reusable lever's handle remain their own item state, not the trap's state.
4. **Prove content reuse with three spike profiles.** Plain piercing spikes;
   piercing plus poison damage; piercing plus a Constitution save against the
   existing Poisoned condition. Author damage dice/types and, where applicable,
   save DC, condition identity and duration as data on the shared owner. Poison
   damage and Poisoned are different effects with their existing resistance,
   immunity and lifecycle handling. The native damage/save/condition APIs execute
   them; existing descriptive effect-profile metadata is not a general JSON
   executor. Add only the small shared payload composition these profiles need.
5. **Then resume real-scene art integration.** Bind the selected lever and spike
   sheets to recorded state. Down-to-up and up-to-down transitions reuse the
   shared historical timeline; interaction contact remains the Studio anchor.
   Detection of an already retracted trap must not animate deployment. Render
   existing instances on real floors from both observers and all four cameras.
   Keep backend processing independent of playback and replay saved packets.

## Acceptance for the first slice

Test boundary: native entry/control actions and observer sensory events in;
trap state, damage/conditions, descriptions and permitted saved player facts
out. Tests use actual handlers and public actions, then replay saved bytes after
runtime reset. Backend work precedes artwork handoff and visual acceptance.

- First entry: one Ready→Activated transition and one payload; later entry into
  raised spikes: one payload. Crossing Deactivated spikes: neither damage nor
  activation. UUID and placement survive all mechanical toggles.
- Two observers with different detection outcomes; discovery before triggering;
  triggering reveals through the normal rules; discovery survives toggles and
  leaving/re-entering sight. No remote description/state leak while unseen.
- The three profiles use the same trigger/state implementation. Check actual
  poison damage mitigation separately from save success/failure and Poisoned
  immunity/removal. Deactivating the device does not cure an existing condition.
- Description, hazard answer and permitted state agree. State transitions and
  effects are under their actual entry/control lineage. Saved input reproduces
  them after the native runtime is gone.
- Once integrated: actual scene replacement, down/up poses, activation/lowering,
  pause/seek and four-camera paired clips. Art previews are not gameplay proof.

**Gameplay decision resolved:** the user explicitly requested a stationary
occupant taking damage when the other character activates the lever. Use the
same native payload, without double damage on first entry. Authored poison balance values can be chosen
when defining the first content profiles; they do not require another framework.

## Where this can grow without forcing one model onto everything

Ground devices can share discovery memory, persistent identity, causal handler
composition, recorded state, descriptions and controls. Damage/condition payload
variants should reuse those pieces. Doors and lights retain their own existing
states and actions; they do not need the trap's three-state enum.

Released consequences have their own lifetime: disabling a dispenser does not
remove its spilled oil, fire, gas or conditions already applied. The current
spike owner and material surfaces use the exclusive transforming ground layer;
co-located device plus lingering material therefore needs an explicit ownership/
occupancy design before that family is implemented. It is not a prerequisite
for the three spike profiles, and is not solved by pretending a surface is a
mechanical trap state. Escape actions, projectiles, pits and cooldowns are later
family-specific needs, not mandatory fields for every trap.

## Source owners and review

| Existing owner | Reuse / focused change |
| --- | --- |
| `dnd/spatial/environmental_conditions.py:SpikeTrap` | Persistent trap data and entry handler; currently hardcodes piercing damage and global reveal. |
| `dnd/spatial/area_conditions.py:SpatialCondition` | Footprint and install/removal lifecycle; existing detection gate. |
| `dnd/core/events.py`, `dnd/blocks/sensory.py`, `dnd/types/senses.py` | Causal state publication and observer after-values; existing affected-cell subscriptions/deltas. |
| `dnd/entity.py`, `dnd/conditions.py` | Native damage, saving-throw and condition owners, including Poisoned. |
| `dnd/items/environment_interactables.py` | Existing trap lever and reusable light/door control actions. |
| `game/player_projection.py`, `game/player_reduction.py` | Permitted saved facts, remembered state and replay; no live engine queries. |
| `game/choreography.py`, `game/data/world_bindings.json` | Later shared timing and passive art binding. |

Anti-slop reviewer: `environment_native_review`. Anti-OOP reviewer:
`environment_timeline_review`. Variant/design study: `environment_asset_scan`.
Both reviewers approved the written plan and companion study on September 19,
with no requested corrections. This is design review, not implementation or
test evidence. Review the resulting implementation against the same state
ownership, first-profile reuse and observer contract; neither a twelve-trap
implementation nor a new authoring framework is part of this slice.
Follow `HOW_TO_TEST.md` when implementation resumes.
