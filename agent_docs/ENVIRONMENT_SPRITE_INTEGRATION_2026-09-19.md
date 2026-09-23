# Official lever and spike integration

**Current implementation:** actual lever bindings now use the selected Blender
sheet; plain and coated spikes use their supplied transparent cells through
explicit content identities. Persistent native trap state and observer discovery
drive these bindings. The user’s complete entry/re-entry/lower/safe-cross/occupied-
raise sequence has generated 14 paired four-camera clips with no reported gaps.
Final presentation review and saved-input replay are recorded with the
[trap acceptance unit](TRAP_STATE_PLAN_2026-09-19.md#current-clip-acceptance-unit).
The earlier staged-only checkpoint is superseded.

**September 19 design update:** the
[trap state plan](TRAP_STATE_PLAN_2026-09-19.md) now defines the proposed backend
work that precedes spike art integration. It supersedes the original assumption
that existing install/removal and revelation were sufficient physical state.
The [variant study](GROUND_TRAP_VARIANTS_2026-09-19.md) proposes content and small
art families; it does not authorize twelve parallel implementations.

The user approved integrating the delivered art into this branch. The earlier
art preview kept four old levers in a baked screenshot and placed an extra
candidate over it. Acceptance here is the actual game scene: its existing
instances, positions, directions, state and subjective disclosure.

## Selected inputs and scope

- Lever: `blender-lever-pixel/lever.png` and its already exported cells.
- Spikes: approved `candidate-v1/spikes-overlay.png` and its exported cells.
- Coated spikes: `ground-traps/coated/`, exact supplied cells; both poison
  profiles bind that shared material through authored content references.
- Source directory:
  `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/`.
- Both have seven frames and E/N/S/W rows, 256-square cells, pivot [128,208].
  Import the exact supplied pixels; preserve transparent floors and provenance.
- Use existing resource/prop bindings and the normal world painter. No preview
  screenshot, new decorative lever, new art generation, asset fingerprint audit
  or parallel scene renderer.

## Implementation boundary

1. Replace existing lever bindings with selected physical poses. Reusable
   controls already publish `is_engaged`; finite trap-lever charges do not mean
   handle position. Any needed persistent handle after-value belongs to that
   existing native item and its accepted action.
2. Extend passive world bindings for finite pose sequences. The existing Studio
   object-interaction recipe still owns hand contact/effect frame 3. Compile
   transitions from received state at that anchor and sample them with the same
   historical clock. Do not turn props into actor VFX or add an action dispatcher.
3. Complete the selected backend trap unit before binding spike art: persistent
   mechanical state, observer discovery and permitted state after-values, using
   the existing native sensory/event owners. A hazardous-cell boolean or display
   name is not an asset identity. Concealed traps stay hidden; discovery and
   later mechanical toggles retain the same fixture identity.
4. Draw authorized spikes through the shared world painter with actual support
   height and camera pose. Bind the recorded down/up states and transitions from
   the backend plan; do not infer a cooldown or reset cycle from animation frames.

## Validation and reviews

Exercise actual control-lever toggles (including failed occupied-door close),
the finite trap lever, first hidden trap disclosure, subsequent damage, linked
deactivation and an independent trap. Assert actual drawn asset/frame/contact
and scene instance counts, both subjective views, all four cameras, pause/seek,
and saved-event replay without native execution. Review the new objects on the
real stone/wood/earth floor assets, not transparency alone. Keep old captures
as historical evidence and publish a new gallery.

Anti-slop reviewer: `environment_native_review` checks native trap/lever meaning
and disclosure. Anti-OOP reviewer: `environment_timeline_review` checks passive
data, original timing ownership and reuse of existing rendering paths. Both
review the concrete implementation. Tests follow `HOW_TO_TEST.md`.

## September 20 — recovered art backlog and ranged-ammunition candidate

This is an intake record, not an implementation plan or a claim of runtime
integration. The existing art task confirmed the inventory below. Its current
prefab corrections retain priority; the thirteen damage-type response art is
queued behind that work. All source paths below are relative to
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/`.

### Trap workshop v7

`trap-workshop/PRODUCTION-HANDOFF.md` and `trap-studies-v7.zip` are the saved
handoff. The user positively reviewed this revision; its original dispatch was
held. The current request recovers that backlog. `manifest.json`,
`export-banks.json` and `wall-registration.json` describe the exports and explicit
style/material bindings.

- Six mechanisms: wall dart strip, jaw trap, gas vent, trapdoor/pit, swinging
  blade and crusher.
- Three aesthetics: Workshop, Brassbound and Fortress iron; blade and crusher
  also have stone/timber support variants.
- Twenty-four mechanism/style/material banks, four pressure-plate shapes,
  tripwire and a separate dart projectile: thirty banks, 1,424 cells.
- Mechanism sheets have twelve phases and four camera rows. These rows view
  one fixed world orientation; they do not provide four physical placements.
- Ready/activation/hold/reset poses are available. Broken, jammed and disarmed
  states are absent. Blade/crusher concealment does not conceal their supports.
- Dart launch uses the explicit release at column 3 / 0.25 seconds, not the
  older generic phase label at column 7. Snapshot muzzle sockets at launch;
  cartridge recoil must not move an already released projectile. The launcher
  fires along its fixed world normal; eight projectile aims do not grant the
  launcher unrestricted targeting.
- Gas vapor is provisional baked art. The pit mask does not implement a hole,
  falling or navigation. Gameplay must own detection, activation, obstruction,
  damage and state; art contact sockets alone do not define these rules.

### Dart reuse for bows and other ranged weapons

The user identified these darts as reusable bow ammunition. The supplied
`trap-workshop/dart-projectile/metadata.json` confirms a 2,048 × 1,024 sheet with
256-square cells: **eight world aiming directions across columns and four
camera views E/S/W/N down rows**. Columns are not animation frames despite the
nominal FPS field. `PROJECTILE_CENTER` supplies placement and `PROJECTILE_TIP`
supplies the directional axis; preserve the supplied socket registration.
Blender X maps to game X and Blender Y to negative game Y; lengths remain
authoring units, not game tile distances.

The current `ActionProjectile` and ranged attack profile select a geometric
bolt. `bind_attack` explicitly requires that geometry. Therefore this art is a
reusable candidate, **not yet a drop-in integrated bow sprite**. Its eventual
selection belongs in authored weapon profiles through the existing ranged
projectile path, retaining release/contact clocks, source/target attachment,
resting-target offsets, height and occlusion. A trap-specific renderer or a
second attack timeline is unnecessary. Existing exports are sufficient to
evaluate this reuse without requesting new renders.

### Other recovered handoffs

- `ground-traps/README.md` and `manifest.json`: plain/coated and bloodied spike
  variants, seven extension poses, E/N/S/W rows. The integration recorded above
  supersedes those older art-only status labels.
- `HANDOFF_LEVER_AND_TRAPS.md` and `blender-lever-pixel/README.md`: selected
  lever source and poses; use current game bindings to establish live status.
- `weapon-workshop/README.md` and `device-destruction/README.md`: cannon/projector
  art; `device-destruction/device-destruction-v2.zip` is the accepted fractured
  body revision, ending in persistent wrecks. Runtime cannon integration is
  tracked separately in the device implementation documents.
- `architecture-handoff/PRODUCTION-HANDOFF.md`, `WALL-REGISTER.md`,
  `backend-mapping.json`, `backend-evidence.json` and `handoff-status.json`:
  saved, previously undispatched wall/door package, 225 wall/frame configurations
  and ten door families. It excludes roofs and stairs. Current smaller indoor
  doors/furniture belong to the separate, actively revised house-prefab work.
- `PRODUCTION-FIREBALL-SCORCH-HANDOFF.md`, `firing-sequence/README.md`,
  `burnt-environment/scorch-production-manifest.json` and
  `scorch-painter/README.md`: floor/wall scorch and wall-aware blast material.
- `high56-region-replacement/HANDOFF.md`: authoritative material replacement;
  do not substitute earlier blood-painter/body-residue experiments.

The art task verified its deliveries, not this checkout's integration state.
No runtime asset scans, fingerprints or validation jobs are introduced by this
inventory.

### September 21 — enclosing trap occlusion supplement

Real blade/crusher damage clips exposed whole-sprite sorting of both arch
supports against an actor at the center. The accepted original v7 sheets remain
unchanged. The same producer supplied `trap-workshop/actor-occlusion-v7/HANDOFF.md`
with source-derived part ownership and horizontal mesh depth for every frame and
camera. Production imports only the two `ground-depth-rg.png` data atlases and
compact source camera registration; source audit scripts/hashes are not runtime
inputs. Optional `actor_depth` in the ordinary prop binding partitions the
original RGBA through existing world painter depths when an actor overlaps.

All four views now preserve actor-before/inside/after ordering without identity
ties or altered actor alpha. Forty-four focused checks and 157 combined
map/projection/mechanism checks pass. Ordinary door boundary probes with Idle
and TakeDamage bodies, open/closed leaf states and both sides showed no leak.
After the concurrent choreography parent lookup correction, all four paired
blade/crusher replays pass in
[the focused gallery](http://127.0.0.1:8767/runs/20260921T001132Z-fea6e9/index.html).
Contact and injury frames were inspected across all four cameras; near supports
occlude the body while blood remains independently drawn. This replays saved
native inputs rather than rerunning their mechanics. Independent code review
(gore_antislop) found no blocker; selected Pyright checks report zero errors.

The producer also delivered `output/environment-sprites/DOORS-AND-TRAPS-PRODUCTION-HANDOFF.md`
in the same art worktree. Keep that wider doors/debris/backend-family delivery
queued against the existing architecture inventory above. Its full contents
have not been inspected in this bounded correction;
neither importing these arch depth maps nor receiving that package authorizes
broader door mechanics changes.
