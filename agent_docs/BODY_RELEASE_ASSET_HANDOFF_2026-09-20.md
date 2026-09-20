# Artwork handoff: compact material releases and matching deposits

Requested by the user before game implementation on September 20. Producer:
existing task `01a0b501-8a27-7413-ba24-4a36e5b140d2`, worktree
`/home/tommaso/.codex/worktrees/23a9/dnd_engine`. Keep all production artwork and
preview work there; do not edit the dirty main game checkout.

**Dispatch status:** sent September 20; producer acknowledged both documents and
started a separate `body-release-regions` bundle/preview. The reviewed tile-piece,
support-admission, presentation-timing and critical-quantity clarifications were
also sent. This is work in progress, not a claim that the new assets are delivered.

The companion [implementation plan](BODY_RELEASE_IMPLEMENTATION_PLAN_2026-09-20.md)
owns mechanics. Your approved `blood-fluid` implementation and frozen export
remain the visual reference: independent droplets, organic merged splats, dark
centers, thin margins, small-splat-to-pool growth. Preserve that work as a baseline.

## What to produce now

Produce tighter, precisely placed landing templates and their airborne material
counterparts. The engine will provide receiving regions; the art must fit them.
This is bounded material authoring, not further spell or cannon exploration.

1. Blood: retain the approved character, improve containment around a supplied
   landing region instead of inheriting the broad 96-droplet field as game reach.
2. Bone: small airborne chips and settled discrete fragments, using the same
   placement convention. Do not simply recolor liquid kernels or add a physics
   simulation to make them bounce.
3. Poison fluid: a distinct readable material appearance; visual preparation
   only, without deciding its future save/DC/damage behavior.
4. Corrosive demonic blood and dread demonic blood: readable counterparts for
   the two existing game materials. Reuse the prior approved identity/palette
   where available; keep them distinct from ordinary blood and poison fluid.

Support three release families (piercing, slashing, blunt) through shared
template parameters and native region placement. Offer a normal/critical visual
variant: critical can have more transient droplets/chips and stronger motion
detail but **the same containing region and retained material amount**. Do not
make a new full spritesheet for every family × material × camera combination.

## Coordinates and receiving-region contract

- Use local top-down/world coordinates, never baked isometric camera placement.
  Existing source uses tiles and seconds. Main layout +X follows impact direction.
- Author destination detail in a normalized unit disk/ellipse: centered at
  `(0,0)`, axes radius 1. The game transforms this to the recorded region's
  center, two radii, rotation and support height. Supply exact extent metadata.
- All settled marks, including organic satellites, must remain within that
  authored containing extent. Keep margins irregular; do not fill a geometric
  disk or tile solidly just to satisfy containment. Smaller sparse satellites
  can live inside the region's edge.
- Production may admit only some tile pieces of that ellipse. Keep the original
  common ellipse basis, intersected with the admitted tile bounds; do not fit
  a new ellipse, recenter or rescale the whole template into each tile. Show a
  single ellipse crossing a tile boundary with both sides admitted, then one
  side excluded. No duplicate particles, dark seam or satellites on the excluded
  receiving surface. An optional destination mask in the standalone preview can
  demonstrate this without implementing native collision.
- Keep the wound source a separate input from the receiving region. Moving or
  stretching a destination must not move the character's hand/body attachment.
  In a detached preview accept a source point and destination region separately.
- Supply target samples/coefficients sufficient to retarget the existing
  parabola. The renderer will derive horizontal velocities toward destinations;
  source/target heights must be explicit. Existing vertical motion, gravity,
  delay, sizes and tails can be reused as authored values.
- Each airborne particle's landing sample must agree with the center of its
  persistent contribution. A particle should not disappear at one place and
  produce a floor mark elsewhere. Camera changes only projection.
- Native gameplay owns walls, floor admission and persistent residue. Existing
  presentation injury/landing anchors own visual contact timing. Your demo must
  not claim native collision, event handling or a new authoritative clock.
- First native implementation admits only routes on the same support elevation
  as the grounded injury, including uniformly raised platforms. Independently
  elevated destination retargeting is useful artwork preparation; it does not
  imply that native cross-height deposition is part of this implementation.

The game layout is at most three compact regions per injury. For art review use
the explicit first-layout tuples from the implementation plan (piercing two,
slashing three, blunt one). Treat those as controls around your local template,
not as dimensions baked into every export. The local contract is stable even if
the user later tunes gameplay spread.

## Floor accumulation and material identity

Demonstrate fractions `0.2, 0.4, 0.6, 0.8, 1.0` using the approved replacement/
recomputed-field approach; repeated full-alpha stamping is incorrect. The game
will supply actual contribution amount/cap. Blood currently grows over five hits;
other existing material profiles currently retain one accepted contribution.

Critical and normal must have the same final deposit for equal supplied amount.
Additional transient critical droplets can share existing landing contributions;
their count must not create additional persistent lobes or quantity.
New directions before saturation can add separate retained patches. Saturation
means no further persistent growth; a preview may continue airborne particles
but must not show new floor stamps that then vanish. Do not clear old deposits
when rotating the camera or showing another hit.

Keep liquid materials visually related through the same deposition geometry.
Bone settled detail may need fragment artwork instead of fluid shading; expose
that as authored material data/assets, not a per-monster runtime.

## Deliverables and review

- Exact reusable data for local particle destinations/motion and persistent
  detail. Prefer the existing `particles.json`/deposit records and a small
  manifest describing coordinates, extent and material/family variants. Call out
  any unavoidable schema extension; do not redesign the game import contract.
- Transparent source images only where needed by the material; optional compact
  five-stage floor previews. Keep straight alpha and pixel treatment consistent
  with current game assets. No mandatory new Godot/TS runtime dependency.
- A preview displaying the source, receiving ellipse, individual landing points,
  settled marks and a containment overlay. Toggle guides for visual judgment.
- Side-by-side blood/bone/poison/corrosive/dread, normal/critical, narrow/wide/local
  layouts, accumulation stages and four cameras. Include a source that stays
  fixed while its destination moves, plus an elevated receiving-surface example.
- Human-readable delivery note with paths, selected defaults, measurements and
  limitations. Use ordinary numerical checks of endpoints/extents; no checksum
  audits or validators to be imported into game startup.

Please acknowledge the contract early. Work in stages: first precise blood
origin/endpoints/extent, then reuse the placement for material counterparts.
Provide reviewable assets and previews directly to the user in your task, and
send this production task a compact handoff when ready. Coordinate any required
contract adjustment before replacing the approved baseline. Do not block on game
implementation: standalone authoring can proceed against this region contract.


## Delivery and integration

The compact `templates.json` bundle from worktree `23a9` was delivered and is
integrated as `game/data/neuroclient/body-release-regions.json`. See the
[implementation result](BODY_RELEASE_IMPLEMENTATION_RESULT_2026-09-20.md).
Four normalized seeds, liquid kernels, bone polygons and all five material
palettes are available. Existing blood/bone/corrosive/dread profiles are bound;
poison remains art-only. Human visual review occurs in the gameplay gallery.
Clipped floor kernels remain locally reconstructible even when their particle
center is undisclosed; canonical air trajectories are never redirected by sight.
The producer's later broad-layout/skill preview is a separate future proposal.
