# Trap mechanisms and reusable environment triggers

**Current implementation:** the delivered trap mechanisms, pressure controls,
tripwires and independent gas backend are implemented. See the
[implementation and validation record](TRAP_MECHANISMS_IMPLEMENTATION_2026-09-21.md).
The original study below is retained as design history; its planning-only and
unfinished statements are superseded by that record. Portal timed presentation
and clean maintained gas artwork remain pending separate media delivery.

Status: backend study and implementation proposal, reviewed by independent
anti-slop and ECS reviewers with amendments incorporated; no runtime changes
in this pass. Review evidence is recorded at the end. This extends the completed
[spike unit](TRAP_STATE_PLAN_2026-09-19.md) and the
[recovered art inventory](ENVIRONMENT_SPRITE_INTEGRATION_2026-09-19.md#september-20--recovered-art-backlog-and-ranged-ammunition-candidate).
It does not replace the queued damage-material work or four-spell handoff.

**September 21 amendment:** the user proposes a magic portal inside the hatch
because the map cannot represent two floors at the same X/Y. The recommended
replacement below is a one-way teleport trap. The earlier physical pit/fall
slice is superseded as the proposed implementation direction; no new vertical
occupancy or falling system is part of this trap unit. This remains planning.

**September 21 reuse amendment:** the user also requests bare portals using
the same behavior and points to the portal removed from the magical-hand VFX,
plus the existing portal library. Make native portal transfer a shared spatial
behavior. A hatch is one authored presentation/activation variant, not the
owner of a separate teleport implementation. Reuse existing source artwork
before requesting new renders. Amendment review is recorded below.

## 1. What the user asked for

The delivered traps need genuine backend implementations, following existing
conditions, handlers, event progression, spatial ownership and subjectivity.
Pressure plates and other trigger fixtures must work independently of levers.
The user explicitly selected **both** pressure-plate behaviors:

- held controls, such as a door held open while the plate is occupied;
- press-triggered traps, which receive one activation on each new press.

Trigger, mechanism and consequence have distinct meanings. Stepping on a plate
does not mean the actor is standing in the connected trap's damage footprint.
A mechanism's reset animation does not decide when it can fire again. Disabling
a gas vent does not implicitly erase gas it already released.

The objective is reusable gameplay composition with recorded, replayable facts.
The artwork is a consumer of those facts. This plan does not authorize a new
circuit editor, scripting language, trap-class hierarchy or renderer physics.

## 2. Findings in the current checkout

| Existing owner | What is already implemented | Relevant limitation |
| --- | --- | --- |
| `dnd/spatial/environmental_conditions.py::SpikeTrap` | Stable spatial identity/footprint; Ready, Activated and Deactivated; entry admission; revealed/remembered state; occupants damaged on raising; data-authored damage and optional Poisoned save | Physical behavior and description are spike-specific. It is not a generic trap mechanism. |
| `dnd/types/traps.py` | Frozen damage/condition/payload records and mechanical state | Condition payload currently means Poisoned specifically, not an arbitrary effect interpreter. |
| `PullLeverAction` / `TrapLever` | Exact linked spike condition, finite or reversible control, native state publication | Explicitly checks `SpikeTrap`; not reusable by simply relabeling another mechanism. |
| `LeverLink` / `ControlLever` | Explicit private door/light connection; child native actions; observed handle state | One typed link, currently limited to door/light. Selection currently uses the target's available action, so plate operation must not assume a conscious operator. |
| `BaseCondition.admits_occupancy_transition` | Ground/air entry and exit admission, including same-cell layer changes | Does not itself aggregate several occupants or coalesce movement within a multi-cell sensor. |
| `SpatialCondition` and `EventQueue.add_spatial_handler` | Footprint-owned indexed subscriptions, ordinary cleanup and sensory updates | Pressure input is not yet an authored fixture. |
| `SpatialRestraintSource` / `EscapeSpatialRestraintAction` | Exact-source restraint leases and action-costed escape | Default manifestation is magical; a mechanical jaw must explicitly use mundane semantics. |
| Existing surfaces, `AreaCondition`, Cloudkill | Area membership, saves, damage, turn fences, duration, environmental interactions | Copying Cloudkill would also copy movement, magical provenance and spell-specific rules. A gas vent is not automatically that spell. |
| `GridMap.set_tile_elevation` | Real support-height mutation and typed elevation events | Not a fall resolver. It rejects height edits with center objects or connector endpoints. No general fall-damage owner was located in the inspected runtime. |
| `PerceivedSpatialEffect`, player projection and `SpatialEffectStateFact` | Last observed fixture identity/cells/state, recorded sensory deltas, typed trap transitions | Transition projection currently understands `trap_state`, not a plate's pressed state or a finite dart shot. |

Existing tests already exercise walking onto spikes, jumping over versus landing
on them, Misty Step crossing versus arrival, interrupted jump landing, remembered
discovery, poison rules and lever-driven activation under occupants. Preserve
those contracts. Discovery is not an avoidance save, and knowing a trap exists
does not automatically disable it.

Important placement detail: spikes occupy the exclusive transforming ground
surface layer. Merely making a plate overlap that same layer is insufficient:
later exclusive surface installation still examines the incumbents. Fixed
sensor/mechanism owners should use the existing non-transforming overlapping
`FIELD` collection, with explicit **ground occupancy admission** where needed.
That does not make them magical. Verify plate + spikes + released surface in
both installation orders. Do not migrate all old surfaces or invent another
spatial registry for this feature.

## 3. Composition and ownership

### Trigger fixture

A pressure plate owns its installed footprint, mechanical pressed state and
ground-contact subscription. Use the existing independent spatial-condition
lifecycle for this fixed, discoverable sensor; a companion visible item and
duplicate fixture identity are unnecessary for the initial implementation.
Its registered handler evaluates accepted native spatial changes. Its footprint
is normally one tile; plate shape/style is presentation data.

A tripwire is a different sensor: it detects a crossing of an authored segment.
Do not silently substitute whole-tile entry if that lets creatures cross the
line without triggering, or triggers them while moving alongside it. Start with
grid-boundary-aligned wires and existing before/after movement geometry. Do not
add arbitrary 3D cable collision or an editor as prerequisites.

### Connection

The connection is private passive data referencing an exact target identity and
a concrete operation. Initially it must express only:

- press -> activate mechanism;
- press/release -> request the two authored door/light states;
- an explicit control -> enable, disable or reset a supported mechanism.

Extract the small shared control operation from the existing lever path when
the plate makes it necessary. Keep item targets and spatial-condition targets
explicitly typed. Do not choose behavior from display names, media IDs,
`getattr`, arbitrary callables in serialized data or a generic command-language
interpreter. Ordinary native processors own validation and effects.

The existing occupied-door guard lives in `CloseDirectionalDoorAction` and
action availability, **not** in `DirectionalDoor.close()` itself. Extract that
validation/application boundary for reuse; calling `.close()` from a new
automatic handler would bypass a real rule. Do not turn a plate's occupant
into the acting user just to pass through interactive action discovery.

Start with one exact target per connection, as today. A list of independently
authored links can be added when an actual encounter needs several outputs;
logical gates, source voting and cyclic networks are outside this unit. A plate
and a lever can both operate one mechanism without introducing a global manager.
Use explicit state requests rather than toggle requests so repeated delivery
does not accidentally invert the target.

### Mechanism

The mechanism owns placement/orientation, readiness/disabled state, supported
activation behavior and its authored payload. Existing spikes keep their known
raise/lower/entry behavior. A dart shot or blade stroke is a finite activation,
not a permanently raised spike hazard.

Use the current condition/handler composition style and finite typed data.
Cosmetic aesthetics, poison coating, damage amounts and orientations must not
create implementation subclasses. Distinct rule owners are justified for
actual differences such as capture, a released cloud or portal relocation.
Do not grow `SpikeTrap` into a switchboard for every mechanism.

### Consequence

Damage uses the normal damage API, so defenses, death, reactions and body
material releases continue working. Saves use real saving-throw requests and
correct magical/mundane/poison context. Restraints use exact-source membership.
Released areas own their footprint and lifetime. Portal relocation uses the
existing native position commit. These do not live in the plate handler or renderer.

## 4. Pressure-plate behavior in detail

The first scope is grounded creature occupancy, not inferred mass from sprite
size. A creature does not need to be conscious, friendly or voluntarily moving
to exert contact. Dead/unconscious entities that remain deployed remain physical
occupants. Do not remove pressure merely because HP became zero. Loose-item
counterweights and weight thresholds need a later explicit object-contact rule;
this first slice must not claim to support them.

| Native transition | Plate result |
| --- | --- |
| First eligible ground occupant arrives | Released -> Pressed; emit one press and execute its link |
| Another occupant arrives while occupied | Remain Pressed; no extra press |
| One leaves while another remains | Remain Pressed; no release |
| Last occupant leaves or genuinely leaves the world | Pressed -> Released; execute the held-control release operation |
| Jump travels through the tile in AIR | No press |
| Jump lands on the tile | Press once at landing |
| Ground occupant takes off from the tile | Release if it was the last ground occupant |
| Misty Step arrives on the plate | Press from real arrival; no intermediate plate contacts |
| Forced movement reaches/leaves the plate | Same actual contact rule; no voluntary-action gate |
| Movement stays inside a multi-cell sensor | Retain pressure; no synthetic release/press between internal cells |

Resolve pressure from the authoritative local footprint and the transition's
before/after contact. Verified: `GridMap._commit_entity_membership` commits the
new tile membership before `_publish_entity_membership` publishes LEFT then
ENTERED. The sensor therefore queries only its local footprint and compares
the resulting grounded occupancy with its previous pressed state. Moving within
that footprint sees the already committed destination and keeps pressure.
No second occupant registry is required. Prove same-cell layer changes and
nested consequence-driven movement as well, without duplicating press edges.
Commit the sensor's new pressed state before invoking its linked consequence.
Nested movement then observes the current state rather than delivering the
same press twice. A refused output does not undo contact or cancel the already
committed movement; its own native request records that refusal.

Install under an existing occupant by establishing the true initial pressed
state and its connected consequence under the installation lineage. Build an
empty encounter before deployment when no initial contact is intended; do not
emit a fabricated walking event or add a presentation-only bypass to obtain it.
Installation, removal and handler cleanup use the normal native lifecycle.

For held controls, the physical plate state and target result are separate.
Releasing a plate must still release it if a door refuses to close because its
doorway is occupied. Preserve that close rule; do not crush/teleport the actor.
Proposed behavior: the door retains the pending desired close and retries on
the relevant doorway occupancy change while the held request remains current.
Re-pressing cancels that pending close. This is an event-bound request at the
existing target, not polling. Review this against native action semantics before
implementation; never make the plate visually stick down to claim success.

The target owns the one pending request, including its originating control
identity and desired value. A newer explicit state request supersedes it;
there is no implicit OR/AND aggregation of controllers. The initial held-door
scenario has one controller. Retrying after the doorway clears is a child of
that **new occupancy event**, with the original request retained as factual
provenance; it must not append children to a previously completed lineage.
Removing a pressed plate withdraws its held input and cancels its old pending
request before requesting its authored release value under removal. Removing
the target cancels its pending request
and owned subscription. Previously emitted pulse consequences remain intact.

For press-triggered traps, each Released -> Pressed transition requests one
activation. No per-frame firing, no repeat because another actor entered an
already held plate, no firing caused by renderer recovery. The linked mechanism
decides whether it is ready. A disabled or spent mechanism can decline while
the plate still physically presses. Release does not implicitly rearm jaws,
erase gas or lower raised spikes.

## 5. Delivered mechanisms and the required native contracts

The following rules are proposed authored contents, not claims about official
D&D trap statistics. Dice, DCs, ranges and durations are content parameters;
initial acceptance fixtures must state concrete values and expected outcomes.
Do not bake those balance choices into shared dispatch code.

| Mechanism | Native behavior to implement | State/lifetime distinction | Existing pieces to reuse |
| --- | --- | --- | --- |
| **Wall dart strip** | On an accepted pulse, fire from fixed placed origin/direction along the authored lane, stop at blocking geometry or a reached target, resolve its authored hit/save and damage | A finite shot can leave the launcher ready for the next press. Every shot needs an event even if final state stays Ready. Coating is payload data. | Native grid/edge propagation and damage/save APIs; shared ranged projectile presentation later |
| **Jaw trap** | Ground contact or linked activation closes it; eligible occupant saves against capture, takes authored piercing damage and receives the exact jaw restraint on failure | Empty sprung jaws, captured creature, released/reset and disabled are distinct rule facts. A closed jaw does not repeatedly bite entrants like raised spikes. | Ground contact; saves; mundane restraint membership and existing escape action/cost |
| **Gas vent** | Activation creates a stationary authored cloud in the actual reachable area, with its own exposure and duration | Vent readiness and existing cloud lifetime are independent. Stopping release does not automatically cure conditions or erase a released cloud. | Area ownership, initial/entry/turn admission, saves, poison damage/Poisoned, obscuration if explicitly authored |
| **Swinging blade** | An accepted pulse resolves one authored sweep footprint and a save/damage outcome for occupants reached in that activation | One stroke is finite; art oscillation does not inflict extra hits. Persistent round-driven oscillation is separate content, not assumed. | Spatial geometry, normal saves and slashing damage |
| **Crusher** | An accepted pulse resolves a downward impact over its authored footprint and bludgeoning damage | Retraction/readiness follows authored native activation policy. Crushing damage does not automatically imply pinning or an impassable block. | Same finite area-strike owner as blade where only footprint, save and payload differ |
| **Portal hatch** | Opening exposes a magical ground-contact entrance; relocate affected creatures to its authored exit tile | Ready/armed, active entrance and disabled remain mechanism states. The destination is elsewhere on the same map, not a second floor under this cell. | Existing native position commit, LEFT/ENTER facts, grounded arrival and observer updates; add the shared portal-owned relocation operation |

Bare portals are another requested content using that same relocation behavior,
with no hatch body. They are not a seventh trap executor.

### Dart geometry and resolution

Keep the native muzzle position/direction in world units, separate from exported
pixel sockets. The fixed launcher is not permitted to home toward whoever stood
on the remote plate. Its three supplied muzzle sockets are presentation assets;
the authored gameplay content decides whether one activation fires one lane or
a three-lane volley. Do not silently triple damage because the art has three
ports.

First content proposal: one straight shot per press, finite range, stopped by
the first blocking boundary/center obstruction and first eligible creature.
A shot into an empty lane is still a real activation and has a recorded end
point. Doors open/closed, all cardinal orientations and elevated supports need
native cases. An art rotation cannot decide collision.

An autonomous trap is not a hidden fabricated Entity. Verified:
`Attack.validate_range` requires a live Entity source and its equipped weapon
range; other weapon checks use that source's senses and equipment. This is not
currently a device-neutral attack resolver. The initial proposal is therefore
an explicitly authored Dexterity-save dart, not an undocumented bypass of
weapon attacks. A later attack-roll dart needs an honest non-creature attack
source contract. Preserve exact trap source identity and causal damage ownership.

### Jaws and escape

Use one captured identity per single-cell jaw. On success, the initial proposal
is a sprung empty trap rather than an indefinitely armed trap immediately
rolling again. Escape costs use the existing escape action; releasing this jaw
must not remove an unrelated Web or other restraint source. A mechanical jaw's
condition must not gain magical tags because the current shared manifestation
defaults that way. Reset is a real reachable interaction and cannot reopen
through a captive without first releasing that exact source.

There is a concrete shared-owner dependency, not merely a possible tag concern:
`SpatialRestraintSource._find_manifestation` reuses an existing `Restrained`,
and its removal leaves that manifestation unchanged while another source
survives. Web -> jaw -> remove Web can therefore leave a magical-tagged
manifestation representing only mundane jaws. Freedom of Movement reads that
tag in `dnd/spells/abjuration.py`. The jaw slice must resolve the remaining
sources' actual semantics and test both installation orders and removal orders,
plus exact-source escape and Freedom of Movement. A jaw-only constructor
override is insufficient. This is bounded work at the shared restraint seam;
it does not justify a general condition rewrite or block plates/darts.

### Gas exposure

First content proposal: a stationary, finite-duration poison cloud with explicit
appearance, entry and turn exposure policy. Reuse one first-per-turn admission
contract where appropriate so a single arrival does not unintentionally cause
two exposures. A successful save does not apply Poisoned and remove it again.
Poison damage immunity and Poisoned immunity are different rules.

Do not import Cloudkill's caster-relative movement, spell DC provenance,
concentration, 5d8 damage or heavy obscuration by accident. Choose whether this
particular gas obscures as content. Overlapping releases require an explicit
same-content area policy; do not add a global stacking manager.

### Portal hatch — proposed replacement for the physical pit

The user is right about the representation limit: each map cell has one support
height. A cover and a usable pit bottom at the same X/Y are not two separately
occupiable floors. Changing the Tile height would change the whole cell; it
would not create that missing model. The physical pit proposal is therefore
superseded here, rather than turning this trap into a vertical-world project.

Recommended initial content: **one ground-contact portal entrance and one
authored exit tile on the same map**. The exit can be elsewhere in the dungeon
or at a different existing terrain height. It is a position, not a new world,
floor stack, portal-network registry or camera-dependent point.

#### Shared native portal; hatch and bare presentations

One installed spatial owner composes passive portal configuration with the
existing ground-contact handlers and native transfer processor. That owner
retains its footprint, authored exit, native enabled/activation state, content
identity and existing discovery rules. Configuring another look does not create
another transfer path. Do not create a trap owner and a portal owner that both
subscribe to the same entry and can transport twice.

| Authored content | Native differences | Presentation differences |
| --- | --- | --- |
| Hatch portal trap | May start concealed/armed; contact or a connected trigger opens/activates it, including occupants present at activation | Hatch motion, portal inside the aperture, optional locally masked disappearance |
| Bare world portal | May start visible and active; uses the same ground-entry transfer and enable/disable operations | No hatch prop; selected portal opening, idle, closing and entry/exit accents |
| Another portal color/style | No difference unless its content explicitly changes a gameplay field | Another authored media binding, palette, framing or animation recipe |

The visible hatch does not require an extra authoritative `portal_active`
boolean mirroring the mechanism state. Keep one owner of activation and derive
presentation from its observed native state. Bare portals need no artificial
lever-use or trap-opening action before an already active entrance can work.
Both can be controlled through the existing planned control-link boundary.

All shared destination validation, blocked-exit behavior, grounded arrival,
movement interruption, event ancestry and endpoint disclosure below apply to
both contents. Initial bare portals retain the same one-way/same-map contract.
There is no implied return portal, cooldown, cross-map travel or extra spell
rule merely because a donor effect depicts those ideas.

Native entrance footprint and any supported orientation are authored world
data. A horizontal or upright effect must fit that entrance, not define it by
pixel overlap. The initial shared trigger is ground entry; do not infer a new
plane-crossing rule or affect an airborne passerby from the shape of the VFX.
Discovery/hazard policy is authored separately from the art; a bare portal
does not acquire concealment, damage or hostile allegiance from a spooky style.

- Ready can use a concealed/closed hatch. Activation opens the portal and
  resolves eligible grounded occupants; later ground entry into an active
  entrance resolves the same relocation. Disable closes the entrance and
  stops future transfers. Closing does not retrieve transported creatures.
- Jumping over the entrance does not trigger it; landing on it does. Opening
  beneath a grounded occupant can transport them. No fall damage or flight
  state is implied by the visual descent into the aperture.
- Validate the authored exit exists, admits the creature and is unoccupied
  before changing its position. The exit need not be visible to the victim:
  this is an involuntary trap, not that creature casting Misty Step. Proposed
  blocked-exit behavior: the transfer fails and the creature stays at the
  entrance; no silent search for another tile. The entrance can remain active.
- First content uses a one-way entrance with an inert exit outside the entrance
  footprint. This avoids inventing chained/bidirectional portal semantics.
  It is still possible for the exit tile to have an ordinary ground hazard.
  Arrival must apply that real contact and its ordinary consequences once.
- The step onto the entrance pays its normal movement cost. Transfer does not
  spend the victim's bonus action, spell slot or travel-distance movement.
  Revalidate/stop the old walking path after the actual relocation; do not
  resume that path from its old next cell. No intermediate cells are traversed.

This position-divergence contract also applies to forced movement and jump
landing. Inspection found concrete seams: the optional walking controller
guard can return CONTINUE when absent; Shove iterates its precomputed cells
after each entry callback; Jump writes the planned landing cell to its local
endpoint after the ground-entry callback. Portal integration must stop obsolete
continuation and preserve actual final position in completion facts on all
three paths. This is required wiring for the new feature, not a claim that
existing non-portal clips already fail. Retain paid/traversed distance separately
from teleport distance and any subsequent ordinary arrival consequence. Record
the actual portal exit separately from a later paid hazard retreat; the latter
must not replace the former as the apparent teleport destination in playback.

**Verified reuse:** `MistyStep._apply` already calls
`Entity.update_entity_position(..., occupancy_layer=GROUND)` and resolves paid
entry retreats. That native commit publishes actual LEFT/ENTER facts and
updates senses. Reuse this rule boundary, with portal-owned causality and the
appropriate entry consequences. Do not construct a fake Misty Step spell event
or inherit that spell's visible-destination, range, caster or cost constraints.
Its current implementation is a precedent, not a complete generic portal API.

The portal activation/transfer records the affected creature and granted
relocation facts under the real trigger lineage. The existing presentation relocation
binding is action-oriented, so add the necessary binding for portal activation
through the shared path; do not assume raw positional facts alone already
produce the desired portal animation. A departure-only observer sees the
disappearance, an exit-only observer sees arrival, and the victim receives
their normal sensory change. None receives a hidden remote endpoint merely
because an event has a causal link.

#### Recover existing art before requesting more

Confirmed source evidence, under the VFX task worktree
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/`:

- `output/weapon-vfx/ice-spells/ChillSmoke.gd::_apply_visibility_filters`
  explicitly hides the original `portal` node. The production-v8 README says
  the portal disc/flash was removed from Chill Touch. The earlier
  `pack_chill_horizontal.py` identifies its donor as Community
  `VFX/Scenes/VFX_DemonPunch.tscn`. Recover that portal component on its own;
  do not restore the hand, debris, attack or old timing into current Chill Touch.
- `output/weapon-vfx/godot-library/inventory.json` identifies LeLu
  `PortalVFX/Scenes/VFX_Portal_DoorHell.tscn`, `VFX_Portal_Squared.tscn`,
  `VFX_Portal_TypeA.tscn`, `VFX_Portal_TypeB.tscn`, and Binbun
  `assets/BinbunVFX/portal_vfx/effects/gate/gate_portal_vfx_02.tscn`, among
  other catalogued entries. These are source candidates, not new approved
  production exports. Do not count showcase/duplicate scenes as distinct looks.
- The prior [environment asset study](ENVIRONMENT_ASSET_STUDY_2026-09-18.md)
  records `PortalOpen/` and `PortalIdle/` in the Fantasy/Desert tileset archives.
  Those have one inspected projection, and the supplied opening clip is marked
  looping; neither all-camera suitability nor one-shot behavior is established.

Choose compatible existing sources for opening/active/closing and finite
entry/exit accents. Keep the effect independently selectable through authored
presentation bindings so it works with or without a hatch body. First inspect
the actual candidates for aperture registration, camera coverage, complete
lifecycle, pixel treatment and actor/wall occlusion. Ask the Godot task only for
the missing isolation, views or export needed by the selected source, rather
than generating a new portal family by default. No new art request is dispatched
by this planning amendment.

A brief visual sinking/disappearance is presentation of teleportation, not a
second logical Z position. Any body mask stays local to the aperture and uses
the shared historical timeline. A visible portal does not reveal a view of the
remote destination. Integration and geometry remain owned by this task.

## 6. Native events, disclosure and independent playback

Preserve the existing event model and complete parent/child lineages. Example:

```text
Move / Jump / Misty Step / forced relocation
  committed spatial contact
    plate pressure change
      linked native activation / target state request
        mechanism change or finite activation
          saving throw / damage / condition / area creation / relocation
```

An autonomous trigger incurs no invented attack action cost on the walker.
Movement must still respond to real death, restraint or relocation under
its existing revalidation rules. Backend processing can finish ahead of
playback. No native wait for a sprite frame, media duration or projectile flight.

Use existing typed item/spatial events for committed state changes. Add only
the missing factual surface: pressed after-values and before-values for a
plate, and a typed finite mechanism activation with the resolved geometry and
identity required to replay a shot/stroke. Save, damage and condition outcomes
stay in their existing authoritative child events; do not duplicate them in
the activation record. A finite activation cannot be
reconstructed from final Ready alone. Keep media paths, frame indices, muzzle
pixel sockets and effect colors out of native payloads.

Extend the existing encode/decode registry, observation records and player-fact
projection together. `SpatialEffectStateFact` currently projects only trap
state transitions; merely adding backend fields would leave plate animation
unconnected. Keep these additions typed and data-only; choose the concrete
shared state record after the first plate/dart examples establish the fields.
Do not create an untyped property bag or parallel replay format.

Disclosure follows the established sensory rules:

- hidden plate/trap contributes no identifying art until legitimately known;
- seeing a plate does not disclose its private target link or a remote trap;
- the trigger and recipient observers can see different parts of one complete
  causal lineage; neither receives the other's sensory snapshots;
- seen discovery persists; an unseen state change does not update memory;
- visible gas/activation can be observed without inventing knowledge of its
  hidden origin; origin and endpoint data are granted independently as the
  existing projectile visibility contract permits;
- names/descriptions follow observed backend state, including disabled versus
  ready even if both use the same physical pose.

The existing `SpatialEffectChangeEvent` projection requires a known fixture and
currently visible observed cells. Keep that gate for its state; it cannot alone
admit a shot from an unseen launcher to a visible victim. The finite activation
needs the smallest separate projection of its granted segment/footprint, with
an optional disclosed origin. If only impact is granted, play only that visible
consequence. Never recover hidden origins or control links from stale fixture
memory, and never infer a permission to render a whole line from seeing its end.

Explicitly test a visible remote victim and unseen launcher, and the reverse.
Do not add a global actor/fixture snapshot to make replay convenient. Initial
world, placement and sensory facts are events too. Replay must work after
clearing the native runtime, with only the saved observer stream.

## 7. Presentation and supplied-art constraints

Art integration follows a working native slice. Use existing Studio recipes,
object transition bindings, shared projectile/area media and lineage timing.
Plate contact and mechanism hit/release are authored presentation anchors;
they do not become backend timestamps. Interrupted movement must hold at the
correct contact rather than snap to a tile center or pause midway through a
jump that has not landed.

Workshop v7 mechanism rows are four views of one fixed world orientation,
not four independent world placements. Match the actual camera mapping; the
older spike rows use a different order. Preserve explicit style/material
bindings and wall registration. Dart release is column 3 / 0.25 seconds in
the art handoff, not the stale phase label at column 7.

The separate dart sheet has eight aiming columns and four camera rows; columns
are not temporal frames. Use center/tip registration and shared tangent
rotation for noncanonical directions. Reusing that media for bows belongs in
authored weapon profiles while retaining their release/contact clocks; it does
not require a trap-specific projectile renderer.

Gas vapor is baked provisional art. Do not let it claim an area larger than the
native cloud or remain after the received cloud ends. Broken/jammed/disarmed
art is absent: ask the existing art task only after the actual native state and
minimum missing depiction are established. Current prefab and damage-material
art queue remains intact.

The artwork handoff discusses projectile speed and swept collision in its
preview. This does not require real-time projectile simulation in the backend:
resolve the native firing segment and obstruction through existing world
geometry when the activation is processed. The independent presentation
timeline owns visible flight speed and duration.

## 8. Implementation order and completion evidence

Each slice leaves a working native feature and replayable facts. The whole
scope is not complete merely because the first plate or clip works.

1. **Plate + existing targets.** Add its passive configuration, indexed ground
   contact handler and observed pressed state. Connect held door/light and
   press-activated spikes through the shared target-operation boundary. Keep
   current lever behavior intact. Prove rejection does not corrupt plate state.
2. **Finite activation + darts.** Add the smallest typed activation record and
   native ray resolution, then one dart content profile and poisoned variant
   through existing payload owners. Prove empty shots, blockers, targeting,
   repeat press and complete causal recording. This is the first genuinely new
   mechanism and the proof that a sensor and its danger area are independent.
3. **Blade and crusher.** Reuse one finite area-strike resolver for actual shared
   semantics; author different footprints, damage and media. Add no pinning or
   per-frame collision unless the chosen rules require it.
4. **Jaw capture + tripwire sensor.** Compose exact-source mundane restraint,
   escape/release/reset and crossing-based input. These are rule differences,
   not cosmetic variants. Keep direct jaw ground contact and remote activation
   distinct from tripwire detection.
5. **Gas vent.** Compose a stationary cloud with chosen exposure/lifetime rules;
   preserve sensor, device and released-area identities. Prove disabling the
   emitter does not retroactively cancel already resolved damage or erase a
   separately authored lingering area.
6. **Shared portals, bare and hatch.** Implement one bounded one-way transfer
   owner/processor, destination admission and real entry consequences. Author
   both a bare active portal and a hatch-controlled variant. Verify the same
   path interruption, paired endpoint visibility and event-only replay
   contracts for both. Recover existing portal media before requesting new
   exports. No support-height/falling work.
7. **Authored art + gallery for each completed mechanism.** Wire native facts
   through shared presentation; use exact delivered banks where adequate.
   Paired observer recordings, four cameras, deterministic saved-input replay.
   Tests pass before claiming the feature integrated; clips await human review.

Likely file boundaries: neutral passive types in `dnd/types/`; native sensor and
mechanism handlers beside `dnd/spatial/`; a small shared environment-control
processor beside `dnd/items/`; content composition in existing builders and
registration; minimal typed event/sensory extensions in existing modules;
projection/choreography/world-media adapters and authored JSON under `game/`.
Avoid adding more to the large environmental condition module merely because
SpikeTrap currently lives there. Keep dependencies a DAG; builders may compose
leaf rule owners, but those owners must not import high-level builders.
Concretely, the sensor may depend on a small actuator module, which depends on
existing door/light and leaf mechanism owners. Mechanisms do not import their
sensors, and passive type modules import neither. Review this direction before
moving shared code; no late import is an acceptable circularity workaround.

## 9. Acceptance matrix and review clips

Follow `HOW_TO_TEST.md`: exercise real native actions/events and observable
state, not method-call counts or source-text assertions. Keep mechanics in the
fast in-memory lane; record scenario events once and render afterward.

| Area | Required evidence |
| --- | --- |
| Pressure | Walk in/out/back; two occupants; within-footprint motion; takeoff and landing; jump-over; Misty Step departure/arrival; forced movement; unconscious deployed occupant; clean removal |
| Held outputs | Open/close door and light on/off; inverted authored values; occupied doorway rejects closing honestly; eventual close/repress behavior follows the selected pending-request rule |
| Pulse outputs | One activation per new press; no repeat while held; re-entry; disabled target; source and target on different tiles; lever remains usable |
| Darts | Empty lane; hit/save success and failure; poison defenses; wall/door blocking; lane does not home; world orientation independent of camera; raised support; activation still recorded when state is unchanged |
| Area strikes | Correct swept/impact footprint; no behind-wall victims; each intended target once per activation; repeat activation independent of video frame count |
| Jaw | Capture success/failure; exact-source escape; reset/release; no duplicate bite on closed jaws; Web/jaw installed and removed in both orders; unrelated restraint survives; mundane/magical distinction and Freedom of Movement reflect actual remaining sources |
| Gas | Appearance/entry/turn admission; save result; immunity distinction; actual duration; overlapping-release policy; independently lingering cloud; sight changes if authored |
| Portal hatch | Opening under an occupant; entry while active; jump-over versus landing; valid/blocked exit; no intermediate traversal or victim spell cost; walking/shove stop their old paths; jump completion retains actual exit; paid/traversed distance excludes transfer; real exit hazard contact; disable and subsequent safe passage; departure-only and arrival-only observers |
| Bare portal and visual variants | Same transfer/admission/ground-contact/visibility tests with no hatch prop; initially active entrance; disable/enable; one entry causes one transfer; changing only media keeps native results unchanged; no hidden exit revealed by portal art |
| Observation | Undetected/detected, visible/unseen remote target, remembered state, later sight acquisition, no private link leakage, both actor perspectives |
| Serialization | Exact new native facts round-trip; public replay after native reset reproduces allowed state and causal timing; no live-object lookup from renderer |
| Performance | Local indexed subscriptions, no map scan per step/frame, no startup asset audit, no new worker/queue, no serialized-event round-trip on the engine's hot path |

Keep a small narrative gallery, rather than every test permutation as video:

1. Press plate -> remote darts; leave -> re-enter -> second shot; close door in
   firing lane -> next activation is blocked. Record trigger and victim views.
2. One character holds a plate opening a door; the other crosses; last occupant
   leaves and the door closes. Include the occupied-doorway case.
3. Walk onto/leave a plate, jump over, then jump-land on it; show the linked
   effect without changing camera/actors between comparable cases.
4. Jaw captures, escape fails then succeeds, reset, re-entry; retain another
   restraint in one native test without multiplying the main gallery.
5. Blade and crusher fire over occupied versus empty footprints; disable and
   cross safely; reactivate from a remote trigger.
6. Vent releases its actual cloud; step out/back; disable vent while the cloud
   remains for its declared lifetime.
7. Portal opens under an actor and delivers them elsewhere; another actor jumps
   across safely, then lands on the entrance and transfers. Include a blocked
   exit and a disabled entrance. Repeat the core transfer with a bare portal
   using the same positions/actors. Record both entrance and exit observers;
   keep hatch and bare clips together for comparison.

Every clip is generated from native actions, not scripted renderer state. Add
gallery tags and traces through the existing review tool. Pixel-diff framework
work remains deferred; use ad hoc saved-input comparisons if an existing
approved visual is touched.

## 10. Decisions and independent review

Confirmed: both held controls and press-triggered traps; existing subjectivity;
real ground contact; separate trigger/mechanism/consequence ownership; no
runtime timing or art data in backend; no flight project.

Proposed content choices still to settle at the corresponding slice: dart
save/attack semantics and lane count; concrete damage/DC values; jaw reset and
capture rules; gas exposure/obscuration/duration; each portal's authored exit and
the proposed blocked-exit behavior. Shared bare/hatch portal support and reuse
of existing portal art are now explicitly requested.
Do not use asset phase labels to resolve any of them. These choices do not block
the pressure-plate owner and its tests against existing targets.

Anti-slop review: checks requested value, scope, actual code evidence, whether
shared mechanisms are justified, and whether deferred work is honestly named.
Anti-OOP/ECS review: checks passive configuration, condition/handler ownership,
native event lifecycles, import DAG, disclosure and record-only replay.
Concrete implementation will also be reviewed at those boundaries.

Existing native baseline run during this study:

```text
tests/engine/test_trap_ground_contact.py
tests/engine/test_trap_payloads.py
tests/engine/test_trap_discovery.py
tests/engine/test_environment_controls.py
42 passed in 3.17 seconds
```

Executed through WSL/uv, source on `/mnt/c`, environment
`/home/tommaso/.cache/dnd-engine/venv`. This verifies the existing contracts; it
does not prove the proposed new fixtures or mechanisms work.

September 20 review results (before the portal amendment):

- **`graphics_antislop`: GO for the staged plan.** Independently checked
  FIELD/OVERLAPPING coexistence, commit-before-publication occupancy queries,
  autonomous actuation, finite activation, dart source constraints and the pit
  boundary. Requested the occupied-door validation/retry contract and mixed
  restraint-order coverage; both are incorporated.
- **`graphics_ecs_review`: GO with amendments.** Required pressure commit before
  linked consequences, target-owned request cleanup/supersession, retry under
  the new event lineage, preservation of native door validation, no duplicate
  save/damage outcomes, explicit optional-origin activation projection, and the
  jaw/Web manifestation correction. All are incorporated above.

These are design reviews based on inspected code, not certification of an
implementation. Both reviewers made no code changes. The tests above are the
existing baseline. Production changes, new tests and visual evidence belong to
the implementation slices, with each result reported against this plan.

September 21 portal-amendment review:

- `graphics_antislop`: GO. Required actual-position divergence handling for
  walking, forced movement and jump landing, based on inspected existing code.
  Incorporated above and in acceptance; no vertical-world or portal framework
  is needed.
- `graphics_ecs_review`: GO. Independently ran a native diagnostic using an
  entry handler and real Move/Jump actions: walking continued its stale path
  after successful relocation, and jumping retained the relocated actor but
  reported the planned landing cell in completion. This confirms the required
  integration seams rather than hypothesizing failures. Required preserving
  the portal exit separately from any subsequent paid arrival-hazard retreat;
  incorporated above. No files were edited by the reviewer.

Both reviews cover the proposed replacement, not a completed portal feature.

September 21 shared bare/hatch portal and art-reuse review:

- `graphics_antislop`: GO, no further amendments. One owner/shared transfer path
  with authored initial state, discovery and optional hatch is appropriately
  bounded. Isolate existing art components, verify registration/camera/lifecycle
  and request only missing exports. Cosmetic variants must preserve mechanics.
- `graphics_ecs_review`: GO, no further amendments. Shared ownership and passive
  configuration preserve native ground contact, exit validation, movement
  interruption and complete causal events. Endpoint-specific disclosure and
  art-only substitutions are covered; isolated donor media must not restore
  donor gameplay or timing. No additional architecture is required.

Both reviews are of this documentation amendment. No runtime implementation or
new asset generation was performed.

## September 21 — implemented portal backend slice

The subsequent user instruction explicitly authorized starting game-side
implementation while the Godot task prepares the portal/hatch media. See
[the implementation record](PORTAL_BACKEND_IMPLEMENTATION_2026-09-21.md) for
ownership, exact scope, reproduction evidence and the remaining presentation
boundary. The earlier statements that the portal is planning-only are superseded.

Implemented: shared bare/hatch owner, real lever control, ground-contact transfer,
destination admission, arrival hazards and paid retreat, complete transfer
lineages, stale-route termination, per-cell Shove/Thunderwave/Gust contact,
retained recording, independent public endpoints, and nested spatial/light
completion fixes. No portal artwork, timed portal presentation or clip approval
is claimed. Pressure plates and the other mechanism slices remain pending.

Implementation review:

- `graphics_antislop`: GO after review of the native owner, honest lever union,
  bounded shared push loop and saved replay. Required retaining spatial ordering
  across timed groups; incorporated.
- `graphics_ecs_review`: GO after reproduced missing retreat-child lineage,
  timed-group ordering and unintended spell push agency restriction were fixed.
  Also reviewed the attached-light correction and independent endpoint grants.
- Existing jump/OA tests found that ordering must suppress only an enclosing
  transition's stale completion, rather than forbid intentional presentation
  retiming. The reducer now uses that recorded declaration/completion interval;
  the original jump takeoff test and both incremental portal recordings pass.

Final validation (WSL uv environment, source on `/mnt/c`):

- **131 passed, 2 expected failures in 40.53s**: portal native/public replay,
  fear, levers, trap ground contact, Misty Step, life-state ownership, forced
  movement history/playback, player projection and occupancy replay. The two
  preexisting expected failures are the documented stair/body occlusion cases.
- **63 passed in 37.50s** in the additional spell-family, presentation-coverage
  and portal-replay selection (overlaps the final lane).
- Selected explicit pyright check: **0 errors** for portal implementation,
  native actions/lever and recording/projection/reduction files.
- Broader exploratory lane: 218 passed, 2 expected failures, **4 architecture
  failures**. The implementation record identifies the untouched retired-server
  import and older leaf/symbol checks, plus four older broad typecheck findings.
  They were not relabeled as successful tests or silently repaired by restoring
  retired server code.

Final ECS review also approved the interval-limited ordering rule after the
original multiple-OA jump regression and both incremental portal recordings
passed. No further blocker was identified in the implemented backend scope.

## September 21 — delivered traps resumed after priority correction

The portal-only slice did not complete this plan. The user explicitly corrected
that priority: implement the traps whose v7 assets are already available before
waiting for portal presentation. Portal art stays in its separate production task.

Current implementation connects local grounded pressure to exact private item or
mechanism links. Held door requests preserve occupancy validation, supersession
and fresh-lineage retry; plate pressure never pretends an occupied door closed.
Finite darts, blades and crushers share authored lane/area geometry, native saves
and damage, with an explicit finite activation even when the resting state returns
to Ready. Public recording retains pressed edges and witnessed activation geometry
without the private control link. Tripwires test a real grounded edge crossing;
teleport arrivals and airborne travel do not count as crossings.

The first eight saved-input review clips cover blade/crusher and held door/light,
with both native observers and four cameras. These are integration checks pending
human visual approval. Dart flight, jaw escape/reset, gas lifetime and the complete
review selection are still being integrated. No portal presentation completion or
whole-plan completion is claimed by the first gallery.

The new movement-spell art handoff remains queued separately at the Godot task's
`output/weapon-vfx/movement-review/HANDOFF.md`. Its HTML demo speeds are not
production constants; only SE exports are delivered. This does not interrupt the
trap slice. All rejected `magic-material-responses` experiments were retracted by
the art task; none were imported, and approved High56 blood remains unchanged.
