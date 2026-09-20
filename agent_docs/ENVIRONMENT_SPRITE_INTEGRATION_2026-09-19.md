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
