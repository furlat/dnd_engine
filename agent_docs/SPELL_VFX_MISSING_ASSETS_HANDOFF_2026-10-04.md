# Remaining spell VFX deliveries — for the human to forward

**October 4 acceptance update:** the human has accepted all delivered artwork,
including Restrained/Petrified and Disintegrate supplements. Historical candidate
review requests below are closed: do not commission replacements or wait for
another acceptance. G1–G4 remain the actual delivery/coverage requests. The
[implementation plan](SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md) owns backend
and client work. Earlier audit hashes predate this acceptance notice.

Prepared 4 October 2026 against game commit `95a47cd5ca5` and
`PRODUCTION_VFX_BACKLOG_HANDOFF_2026-10-03.md` in
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/`.

**Not sent to another chat.** The user will forward this document. This is a
bounded delivery request: preserve the already accepted artwork, complete the
specific coverage/isolated-component gaps below, and return local file paths.
It does not request new spell mechanics, character sprites, weapon artwork or
an overhaul of the accepted effects. Production integration remains with the
engine/client work, described in the companion
[ranking](SPELL_VFX_INTEGRATION_RANKING_2026-10-04.md).

## G1 — Cone of Cold: complete directed coverage

**Priority: first. Confirmed limitation for general integration.**

Existing accepted source:
`cold-weather-batch/cone-of-cold-v1/`, revision
`straight-alpha-volume-v4`; contracts `NOTES.md`, `spec.json`, `media.json`,
`approval.json`, `body-material.js` and the parent cold handoff.

The delivered connected volume uses **q0 / world +X only**. Its widening
near/middle/far surfaces, ground frost and muzzle are projected geometry, so
ordinary 2D rotation is not a valid substitute for another isometric direction.

Deliver either:

1. The missing **camera-relative native heading banks** needed to aim the cone
   across the game's eight facing directions/four camera corners; or
2. A validated reusable native geometry/material adapter with explicit
   transforms that reproduces the accepted appearance at those directions.

Establish the camera-relative equivalences first. Do not export 4×8 duplicate
banks merely because there are 32 combinations. Preserve the original q0/+X
reference, straight alpha, 32-FPS effect clock, formation/clear timing, varied
crystals and palette. Keep actor/floor out of the export. Existing recipient
contact and corpse material operators should be reused, not painted per creature.

Metadata must identify physical forward axis, source muzzle, origin/pivot,
layer registration, crop offsets and world dimensions. The native spell's
60-foot cone controls placement; no enlarged gameplay footprint to fit pixels.
Demonstrate opposing/side-on headings as well as the existing diagonal, with
identical source scale and an explicit heading/camera mapping table.

Do not generate XYZ by default. If registered component geometry cannot solve
a demonstrated overlap, identify that defect and the minimal required data first.

## G2 — Call Lightning V5: close the native-strike camera contract

**Priority: first. Coverage/reuse must be established; extra captures are conditional.**

Existing accepted source: `call-lightning-rework/REVISION_V5.md`,
`revision-v5-receipt.json`, preserved blue-local-v4 strike and native materials;
shared `electric-live-study/components.json`, `contact-renderer.js`,
`assets/arc-material.png`, `cast-assets/lightning-hands.png` and
`cast-assets/hand-sockets.json`.

The full accepted LeLu strike is explicitly a **single-camera pilot**. The
new electric contact geometry can be viewed from other cameras, but that does
not certify the native strike. The production game currently selects a different
older four-camera effect; those old banks are not proof of V5 coverage.

Deliver a registered camera-relative reuse contract and four-camera evidence
for the complete accepted strike. If the native geometry is not equivalent
under that reuse, export only the missing views. Preserve all approved material
layers, local impact and finite body electricity. Do not replace it with a
generic bolt, recolor an unrelated effect, invent a persistent storm cloud, or
export separate banks for each target configuration.

Include the ground strike anchor, vertical extent, layer/crop/pivot registration,
phase/contact timing, alpha convention and selected-file hashes. Empty ground,
multiple admitted recipients and repeat strikes should use the same components.
Actual damage recipients, 60-foot selection, existing seven-foot radius,
concentration/repeat action and event scheduling remain production-owned.

## G3 — Wind Wall: isolate the admitted missile-block gust

**Priority: next. Existing look; missing reusable delivery.**

Existing sources: `wall-spells-study/wind-contact-v3/README.md` and
`wall-spells-study/wind-modular-completion/HANDOFF.md`. Preserve the approved
gust/deflection appearance from the contact fixture and the existing wall modules.

Extract/adapt that **finite local block response** into an isolated component
or a documented reusable source-geometry recipe. It must attach to the actual
intersection supplied by the engine, accept the incoming projectile direction
and wall direction, and work under the game's camera-relative convention.
Do not include the demonstration arrow, character, floor, complete wall or
fixture target coordinates in a reusable effect bank.

Deliver anchor, axes, contact/start/end timing, layer ordering, original scale,
transparent bounds and the smallest necessary heading set/reuse mapping. No
maintained loop, new projectile rule, ordinary movement damage or guessed
deflection point. The interception owner/contact already survives recording and
disclosure (`game/player_facts.py:105`, `game/player_projection.py:220`).
Production must consume those retained facts and the actual incoming vector;
artist fixture timing cannot replace them.

## G4 — Wall of Thorns ring: conditional geometry correction

**Priority: resolve contract before capture. Do not stretch or silently change rules.**

Current evidence:

- `dnd/spells/wall_fields.py:261` creates a ring **20ft high**, radius10ft,
  width5ft (flat segments remain10ft high).
- Selected `game/data/world_bindings.json:4326` registers the supplied ring at
  **10ft high**, radius10ft, width5ft.
- `game/wall_assembly_media.py:59` rejects a ring whose registered height differs
  from the retained native geometry. This is a concrete integration block.
- Accepted source is `wall-spells-study/thorns-modular-completion/HANDOFF.md`
  with the separate `thorns-production-handoff/HANDOFF.md` appearance contract.

First confirm source physical dimensions and registration: a mislabeled height
requires corrected metadata/evidence, not new pictures. If the source really is
10ft and production retains its current20ft rule, deliver a **native20ft ring**
with the same radius/width and accepted material, formation, two-second sustain
and retirement. Preserve current flat modules. If the human instead approves a
10ft gameplay adaptation, the existing ring may suffice; the artist must not
make that backend decision.

Return physical dimensions, matching existing layer registration and camera reuse
mapping. The current modular ring is single-layer RGBA; do not add a front/back
split unless a demonstrated consumer need justifies it. Keep revoked Thorns XYZ
excluded. Partial player visibility is a
separate production composition problem; do not bake encounter visibility into
this ring or promise that a complete ring bank solves hidden sections.

## Existing candidates: prepare for human review, do not remake or promote

These files exist. Their status is **unapproved**, not missing artwork:

| Candidate | Existing entry | Needed next step |
| --- | --- | --- |
| General Restrained / Petrified | `shared-conditions-completion/HANDOFF.md` | Present the existing candidates and explicitly request human visual acceptance; existing spell acceptances did not approve them. Keep Web/Hold ownership separate. |
| Disintegrate save/lethal-dust/object outcomes | `wall-spells-study/disintegrate-outcomes/HANDOFF.md` | Present existing branches for human acceptance with exact files/revision. Accepted projectile/Force V2 are already released and must not be replaced. |

No revised design or fresh captures are requested for these candidates unless
the human rejects or changes the existing ones. Source approval still needs a
separate production implementation/verification pass afterwards.

## Work that stays with production, not a new-art order

- **October4 addition — Telekinesis transfer and real ledge descent:** use the
  accepted grounded-layering-v2 hand/grab/release with a finite creature move;
  no maintained suspension is requested. The engine now plans shared real-fall
  damage and recorded descent/contact for Shove and other existing movement.
  First use current rig airborne/injury/Prone/death poses and accepted impact
  media. Ground shadow, body height, cliff/wall occlusion and contact-before-
  damage timing are production work. A dedicated tumble pose/landing dust cue
  is a possible gap, **not a confirmed missing delivery or art order**. Request
  only a demonstrated gap, naming the affected rig family/phase and directions;
  no whole replacement character sheets. Details and acceptance are in packet6
  of [the implementation plan](SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md).
- **Heroes' Feast eating:** the table/blessing art exists. The current Eat action
  disables its actor track. Inspect/adapt existing rig poses and a hand-to-mouth
  interaction first; this finding does not justify a new character sprite sheet.
  Serving, buff and prop lifetime/immunity/healing decisions are backend work.
- **Ice Storm / Sleet Storm cameras:** their reusable falling modules/rotational
  weather have one native view, but valid camera-relative reuse remains possible.
  Production first tests that composition. Request additional views only for a
  reproduced mismatch, not automatically four of each. Actual impact-height fit
  is also initially registration work.
- **Death/portal camera and resolution limits:** Blight, the necrotic-family
  banks and Banishment/Dimension Door include q0-only native fixtures. Circle of
  Death is an overview-resolution export; Door needs a portal-plane orientation
  mapping; Blight's native veil is not certified on quadrupeds. Production first
  validates camera-relative/component reuse, target resolution and body-alpha
  fitting. If that fails, request the precise missing existing-source export
  with that evidence. No blanket four-camera, higher-resolution or per-creature
  export is requested now.
- **Produce Flame; Finger of Death; Eyebite; Sunbeam; Disintegrate:** supplied
  components/adapters are available. Real hand/weapon/target sockets, arbitrary
  trajectories, strict area clipping and depth belong to production. A preview's
  fixed positions must not be copied into gameplay.
- **Class VFX:** all21 `roar-cast-v5` sets have accepted components. Existing
  Melee1/Attack1 slash samples are not every weapon's trajectory. Production uses
  actual equipped-weapon paths and event contact. No new weapon art is requested.
- **Barkskin/Shillelagh and spirit/material effects:** supplied textures/operators
  need adaptation into the common sprite pipeline, not new sheets for each actor.
- **Surface steam:** finite quench wisps exist. They must not be relabeled a
  sustained SteamCloud. Actual producer/lifetime scope needs a backend decision;
  no new persistent-steam artwork is commissioned by this document.
- **Solar, Harm, Banishment, Dimension Door, Telekinesis, Antimagic, Chain:**
  native rules or retained event-contract questions stay on the engine side.
- **Force/Ice domes and lethal outcomes:** dome artwork exists but needs a shared
  client consumer. Cone's frozen corpse/thaw and Disintegrate's corpse/equipment
  consequences require authoritative native state; approved imagery cannot
  manufacture those outcomes.

## Delivery format and acceptance evidence

For each G-request, return one entry with exact selected files/revision, whether
it is new media or an existing-media reuse/metadata correction, and an explicit
list of remaining limits. Preserve originals; stage new exports separately.

Supply dimensions/units, physical axes, pivots/crop offsets, camera-relative
mapping, layer ordering, alpha convention, source frame clock, phase/contact
markers and genuine repeat boundaries. Pin byte counts and SHA-256s, including
shared dependencies. Keep fixture actors, terrain, preview UI and duplicate
diagnostic frames outside runtime payload. Native source/materials stay available
for adjustment; consumers should not need the Godot preview to play the effect.

Verification should show the requested directions and compositing layers with
the approved reference beside them. This verifies source delivery, not final
game integration. The human accepts appearance; the production lane verifies
real event timing, area/recipient disclosure, sockets, owner removal and sorting.

Do not add Prismatic Spray/Wall, persistent Shocked/electrified-water mechanics,
new character/weapon art, full spheres, tilted/stacked walls or speculative XYZ
exports to this batch. Do not message other chats; provide the completed files
to the human who forwarded this handoff.
