# Presentation authoring contract

The active local spell bundles use `schema: "dnd.spellStudioDrafts"`, `version: 3`.
They extend NeuroStudio's records. The unchanged imported reference retains
`neuroclient.spellStudioDrafts`, version 6. `StudioDraftFile` accepts that original
format and local versions 1, 2 and 3. At authoring load, supported v6/v1
attachments and pre-v3 composition are converted once into explicit records;
the sampler has one executor.
A future TS adapter needs these documented extensions, not the original v6
validator unchanged. This revision does not change recorded gameplay events.

This is a data/execution contract for the current Python client and a future TS
adapter. It is not another event protocol or a requirement to port the client now.

## Interrupted actions and linked reactions

`interruptions.json` selects authored prefixes by an explicit native outcome,
cancellation phase, and actual expenditure receipt. Anticipation/travel fractions
are presentation choices; they do not claim that the engine simulates projectiles
or cancels after applying damage. Ordinary invalid commands remain unanimated.
Canceled source tracks retain their original rates, equipment, sockets and media.
Destination effects/feedback are disabled; real completed children keep their own
causal presentation. Volley interruption precedes the earliest arriving delivery.
Declared but unexecuted allocations can supply attempted flight tracks with local
track IDs; they are not invented application events or hit outcomes.

Counterspell retains its separate native root and authorized trigger/result facts.
Consecutive linked roots may share one existing queue entry, but remain individually
reducible in native order and survive saved replay. The original NeuroStudio
Counterspell recipe owns its body, release frame and success/failure feedback.
Aligning that release to the interruption may delay the incoming start enough to
avoid a negative reaction start; neither body is sped up.

`nonProjectileBodyFraction` optionally places paid direct-cast interruption along
its original body duration, while `anticipationFraction` governs unpaid/release
anticipation and `travelFraction` governs emitted carriers. `reactions` maps a
recorded reaction behavior to `successByCamera`, `failureByCamera`,
`dissipationMask`, `durationMs`, `scale` and existing actor `castLayers` records.
These JSON values are portable authoring; they contain no native game rules.

A successful reaction retains only the logical travel sample already emitted at
the cutoff. Its neutral mask multiplies original coverage, preserving the frozen
frame, palette, placement and rotation; additive layers attenuate RGB. Full
native-canvas mask registration is shared across sparse parts. The tail extends
group completion, never the cancellation/child boundary. A failed reaction has
its own burst but neither freezes nor masks the incoming spell. With no emitted
carrier, the burst uses the caster's existing rig body anchor. Exact hand energy
is a source-only actor layer. This implementation does not install a canceled
area or claim formation-specific cloud suppression. Globe media remains separate.

## Ownership and packaging

| File / owner | Meaning |
| --- | --- |
| Each selected bundle's `spell-studio-drafts.json` | Explicit spell behavior in `spells`; child effects in `effectDrafts`, keyed by native effect identity |
| `projectile-assets.json` | Media dimensions, source phase ranges/rates, facing order, fixed registration and palette preview |
| `bindings.json` | Resource URLs to local files, spell ContentRefs, projectile storage and explicit `actionDeliveries` aliases to an owned spell draft; no authored child recipes |
| `neuroclient/attack-profiles.json` and source action recipes | Shared attack variants, with weapon overrides and damage-type defaults |
| `rigs/*.json` and root `neuroclient/bindings.json` | Rig identity, body registration, clips, slot categories and appearance bindings |
| `world_bindings.json` | Object transition/media bindings driven by permitted world state |
| `life-state-poses.json` | Optional DYING/STABLE body pose and finite entry/recovery selected by recorded life facts; existing lifecycle feedback stays imported |
| `condition-overrides.json` | Local persistent body poses and labels layered over imported condition recipes; no condition rules |
| `condition-recipes.json` / `condition-media.json` | Condition layer selection and static/paged media registration, including application, sustain and removal fade |
| `movement-media.json` | Condition-selected finite motion tracks, reference locomotion speed and authored actor action-rate policy |
| `spell_devices.json` | Independent device bodies, measured muzzle/bore contacts, operator gesture and launch settings; no spell selection or game targeting rules |
| `../../content_data/ledgers/neuroclient_authored_item_visuals.json` | Existing resolved equipment layer ledger, including sprite keys, tints, base bindings and variants |

Original reference records can be overridden by one selected local owner. Two
local bundles cannot own the same spell. A child effect retains the owning
spell's ContentRef; `spell.ice_knife.burst` is a child identity, not another paid
or independently catalogued spell. Importers copy media and update packaging;
they do not reconstruct behavior from another spell or overwrite selected drafts.

The original reference import/materializer remains an explicit source-conversion
tool. Ordinary content tuning belongs in selected local records. Re-running
source conversion is not required for gameplay or for editing local recipes.

Casting layers declare `sourceSheet` plus optional `palette` bake inputs. The
baker reads the original isolated category/clip sheet and writes the declared
output PNG. It does not alter flash timing, source selection or recipes. Runtime
uses the precolored sheet without applying the old hue transform again. Target
hit-flash palettes are separate: Chill uses a dark/noisy target treatment but a
full casting ramp. Neither operation changes the actor's equipment identity.

All these artifacts are ordinary JSON values. Resources are URL strings and
relative paths, not Python objects. A TS client resolves them through its asset
loader and reads the existing equipment ledger; it does not import Python item
registries. `AnimationData`, compiled timelines, `Path` values and Pygame surfaces
are runtime products, not portable authoring. Saved subjective events remain a
separate input stream.

## Additions to the original Studio vocabulary

| Field | Current consumer and observable meaning |
| --- | --- |
| `cast.enabled` | Cast compiler: a child delivery can run without repeating the caster gesture |
| `cast.holdReleaseForVolley` | Cast sampler: keep the release pose while the volley is released |
| Actor-layer `sourceSheet` / `palette` | Drawing / offline baker: selected isolated colored sheet and explicit bake treatment |
| `projectile.sourceSockets` | Attachment calculation: measured release/preparation coordinates in the actor source cell, overriding legacy source-anchor offsets |
| Source/target `basis: "rigRoot"` / `"body"` / `"tileCenter"` | Explicit rig root, rig body point or ground support; source sockets override source basis |
| Target `axisPx` | Zero-default signed reference pixels along the resolved source-to-target chord, independent of facing `forwardPx`; source `axisPx` retains its existing field |
| Phase `startFrame`, `durationMs`, `overlapRelease` | Phase compiler: authored preparation start/duration and permitted overlap with release |
| Phase `scale` | Registration and drawing: local phase scale overrides projectile scale |
| Phase `fineRotation` | Orientation: `none` or `isometricHybrid` overrides the projectile setting for this phase; absent/null inherits it |
| Phase `timeMap` | Phase sampler: elapsed milliseconds to source-frame progression; does not alter native causality |
| Phase `fitDuration` | Phase compiler: fit one source-frame sequence to the resolved interval by its media FPS; defaults to false and explicit `timeMap` retains precedence |
| Travel `overlapContactMs` | Sampler: continue/fade the arrived travel media after contact; damage is not delayed |
| `targetLocal` | Compiler/depth projection: effect at target with independent contact-after-release delay and optional temporary approach depth |
| Asset `anchorsByFacing` | Registration: measured normalized pivot per authored direction, rotated with the art |
| Optional asset travel phase | Impact-only assets need not invent unused travel frames |
| `projectileStorage` phases/layers/pages | Media loader: ordered alpha/additive layers, gain and page frame ranges; no game rules |
| `damage.hitFlash.palette` | Actor-media preparation: exact colors, gamma and optional noise/untinted shading, preserving silhouette |
| `area.surfaceReveal` | Playback: time already-recorded floor updates outward from the recorded contact; never generate native affected cells |
| `effectDrafts` | Child binding: select a typed recipe for an existing nested effect without a second caster action |
| Action-media `spellTintStrength` | Optional zero-default RGB blend weight for airborne body-release particles, using the owning spell’s primary color; current bindings use 0.06. Persistent residue palettes and native materials are unchanged. |
| Attack profile variants | Attack selection: explicit weapon identity overrides, damage-type fallback and authored critical variant |
| Media `viewFacing` | Fixed world basis for orbit-rendered artwork; camera rotation chooses the bank. Omitted values retain actor/delivery-facing selection. |
| Media `departure_ground` / `arrival_ground` attachments | Independently observed relocation endpoints on the existing body-action release clock |

Examples are the actual selected records: Fireball for phase scale/area reveal,
Eldritch Blast for measured sockets and volley preparation, Ice Knife plus its
child for body/ground separation, and Chill Touch for target-local time mapping.
Do not create a second normalized recipe language for these examples.

Travel and impact may select different rotation behavior. A directional shot
can retain hybrid rotation while its ground impact authors `fineRotation: "none"`.
This changes the sprite's extra screen rotation, not its directional row,
registered contact, launch path or arrival clock. Extended impact media continues
through the existing projectile impact/area-mask path. `area.sprite` is parsed
reference vocabulary without an executor; populating it does not render media.

The original `orientation.directionSource: "tangent"` now selects the nearest
screen octant throughout travel, with hybrid rotation correcting that row's
authored isometric angle to the instantaneous path direction. It includes the
device launch curve and any world-height arc. Preparation keeps the launch row;
impact retains the arrival row and its own fine-rotation setting. `target_vector`
keeps its approved fixed-row behavior. Measured pivots follow the selected image;
changing rows never changes the semantic socket, destination or travel clock.

For a non-looping travel sequence such as Web's silk, `travel.fitDuration: true`
sets media FPS to `sourceFrameCount * 1000 / resolvedDurationMs`. The entire
sequence therefore plays once over each flight, including shorter and longer
shots. It does not change the resolved duration, arrival anchor, phase range or
loop flag. Preparation and impact can use the same phase option. An explicit
`timeMap` continues to own source-frame sampling when present. Omitted/false
retains original FPS behavior, including ordinary looping projectiles.

## Coordinates and clocks

The modular rig's anatomical target is source-cell `(64,60)`, authored once as
`root_body_anchor`. Ordinary torso spells select `basis: body` with zero target
offsets. Packaged rigs retain their own measured point. Fire Bolt preserves its
approved result through `basis: rigRoot`, `liftY: -64`, source `axisPx: 24` and
target `axisPx: -16`; its sprite now registers by its center. The modular rig root
is 41 pixels below support, so the visible base is `(41 - 64) * actorScale`
above support before the path insets. It deliberately differs from the torso's
`(60 - 128 + 41) * actorScale`. This is a conversion of working behavior, not
new hand/body tuning. Magic Missile uses `rigRoot`, source lift `-80`, source axis
inset 16 and a body target, retaining its volley and curved travel.

| Placement field | Units, default and precedence |
| --- | --- |
| `basis` | Required. `tileCenter` is projected support; `rigRoot` adds the rig's ground-origin padding; `body` uses its authored body point. Source and target use the same meaning. Ground deliveries always use ground support. |
| `liftY` / `forwardPx` / source `sidePx` | Required signed reference pixels; positive lift goes down screen. Forward/side use the projected canonical facing vector, then actor scale. |
| Source/target `axisPx` | Signed reference pixels along the actual adjusted chord, then the relevant actor scale. Target omission means zero. Negative target values inset toward source. Existing short-chord clamping prevents reversed paths. |
| `sourceAnchorsByFacing` | Optional source placement per camera-facing row; absent row uses `sourceAnchor`. View changes do not recompile time. |
| `sourceSockets` | Optional source-cell release/preparation points; override source basis, offsets and axis inset. Missing preparation frame falls back to the release socket. |
| Asset `anchor`, `anchorsByFacing`, sprite `anchor` | Normalized image coordinates. Directional asset pivot wins, then explicit sprite pivot, then scalar asset pivot. Every form registers the same image point at the attachment. |
| Sprite `offsetX` / `offsetY` | Additional screen-local reference-pixel displacement of the image; does not move the attachment or alter time. |

Transform order:

1. Project the recorded world contact and support height. Add temporary body lift
   independently. Camera quarter turns change the view, not the compiled clock.
2. Resolve source and recipient bases. For a source-cell point subtract half cell
   width horizontally and cell height minus rig ground-origin vertically, then
   apply actor scale and visual horizontal scale to x. Finite cast media and
   projectiles use this same calculation. Root and ordinary anchor offsets use
   actor scale; effect size is independent.
3. Apply source sockets when selected. A device replaces the actor attachment with
   its recorded measured muzzle and uses no actor source inset. Apply path insets
   along the resulting chord. Apply the recipient's authored resting-pose
   displacement without moving the launch contact. Existing Fireball/Sleep/Web
   device curves retain their measured bore and contact.
4. Sample the authored path and phase rotation. The pivot-to-image-center vector
   is scaled by phase scale (falling back to projectile scale), rotated with the
   art, then combined with sprite offsets. Convert reference pixels to viewport
   pixels through world scale and camera zoom; raster rounding stays in Pygame.
   Image dimensions never modify the body attachment. Scalar and directional
   pivot declarations have identical execution semantics.
5. Compile time from the retained reference trajectory plus independent height
   metric, never camera-projected distance. Studio's original reference metric
   includes rig-root padding even for geometric `tileCenter` contacts; display
   placement uses the declared ground basis. Per-camera offsets do not retime an
   already compiled cast. Existing travel FPS follows `projectile.fps`;
   preparation/impact use their phase FPS override when present.

Legacy conversion is restricted to supported retained records. Old non-body
sprite anchors become `rigRoot`; geometric anchors become `tileCenter`; old
non-body target `forwardPx` becomes `axisPx`. Uniform scalar canvas compensation
is folded into actor lift and a center image pivot. Already directional pivots
remain direct registrations. Unsupported phase-dependent/horizontal/socket
compensation needs explicit authoring rather than a second runtime mode. This
conversion leaves the imported source file intact. Local v2/v3 records need no legacy attachment compensation or runtime version
branch. V3 also authors its composition explicitly; v1/v2 infer that selection
once at intake from their retained storage contract.

`targetLocal.approachOffsetTiles` is a temporary sorting/contact-depth choice for
an already local effect. It does not mean the native actor moved or the effect
travelled that distance. Area/wall masking continues to use shared geometry and
permitted native affected areas, independent of sprite padding.

Current ground-delivery limitation: `targetAnchor.liftY`, `forwardPx` and `axisPx` are
applied only to actor targets. A `GroundContact` ends at its declared support;
the current executor has no authored ground-target offset. Sleep, Web and
Fireball currently author zero ground lift. Do not treat a nonzero lift value as
implemented support or change the native destination to compensate for media.

## Support and child weapon attacks

### Registered reactions and movement media

`bindings.actionDeliveries` maps a native action identity to an already-owned
spell draft. Hellish Rebuke remains its actual reaction ActionEvent inside the
triggering damage lineage. The existing cast binder executes its selected draft;
an older body-only action recipe cannot intercept it. Nested registered actions
own their own damage subtree, just like nested attacks and spells. This is a
shared delivery choice, not a synthetic SpellEvent or a second reaction system.

Misty Step's endpoint tracks remain on the existing relocation body clock.
Only received spatial facts supply arrival placement. Departure may use the
explicit source position or the actor's still-visible pre-head contact when a
departure witness receives no later spatial facts. It never borrows the arrival
contact from staged future observations or reveals the other endpoint. Separate
stationary back/front clouds do not interpolate or duplicate the actor.

`movement-media.json` uses `dnd.movementPresentation`, version 1. Its `walkMedia`
and `jumpMedia` retain Studio movement tracks with explicit condition selectors
(`whenConditions`, `unlessConditions`), fixed `viewFacing`, depth, alpha,
`contactFrame`, `emitIntervalMs` and `fitToMotion` extensions. Takeoff and landing
bursts register at actual endpoints; flight attaches to the same sampled body
trajectory. Trail emissions stay at their historical positions and do not fill
reaction pauses. A takeoff contact frame contributes grounded anticipation
after any pre-jump reaction; the rig then plays exactly one cycle during airtime.
Finite media tails live in caller-owned playback state and do not hold the next
action head.

Each committed voluntary step retains its resolved native speed. Playback
scales its travel duration and gait once against `referenceSpeedFeet` (30).
Dash membership selects trail intensity but does not double speed. Haste's
native doubled speed therefore affects motion once. Its separate authored
`actionPlaybackRates` entry (1.25) scales actor body, hand preparation and
release/contact together for attacks/casts. Spawned projectile travel and target
effects retain their independent clocks. Unhasted casts retain their approved
registration and timing; no Fire Bolt socket or target point is retuned.

`support_spells` keeps complete authored recipes separate from its media-only
importer. Finite back/front media retains the delivered FPS and ground pivot;
the body's vertical position is baked into that art. Apply no second torso
offset to these ground-registered wraps. Static condition halves use real
membership and existing composition groups; a selected recipe retains both
halves, without a second physical-layer cap.

A source-only spell can have no applications and no ground destination when
its finite tracks all attach to the source. It retains caster facing and the
ordinary release/contact clock. Healing commits the received `HealFact`
after-values at contact. Standalone cast samples retain passive HP snapshots;
the lineage compositor lets only actual damaging applications own HP/life
overrides, so passive snapshots cannot undo received healing. Light's native
field changes are children of condition application and
removal, and their received sensory changes commit at the owning contact.

`StudioSpellDraft.childAttack` explicitly delegates the spell's presentation to
its real direct child attack. Each pose row matches `rigId`, `weaponCategory`
and the actual attack `clip`, then supplies ordinary `StudioActorLayer` records.
It never changes the attack's profile, equipment, clock or outcomes. Literal
`sourceSheet` layers bypass generated rig-category lookup while keeping normal
actor slot ordering. True Strike currently has exact shortsword/Melee3/Attack6
and shortbow/Ranged1/Attack3 overlays; other weapons keep their real attack with
an explicit missing-media report. Their own fitted artwork remains outstanding.
There is no separate cast gesture, accuracy condition or overlay animation
clock. These passive fields need equivalent execution when adapting NeuroClient.

## Execution that accompanies the data

A TS adapter must reproduce complete-lineage joins, independently advancing
latest state and historical playback, gear at presentation time, reaction
interruption, preserved sub-tile positions, prelaunch jump reactions and one
body cycle per jump airtime. These are finite shared algorithms, not JSON rules
per spell. Area occlusion and procedural floor residue also require their shared
algorithms; copying JSON alone does not port them.

The existing condition support report distinguishes supported body appearance
from populated unsupported equipment/appearance tracks. Accepted potion/source
strip omissions and disabled recovery media remain outside the current work.
Selected movement media now has an executor, described below.
Unknown fields must not be silently accepted as evidence of interoperability.

Preserve approved composed results when changing representation. Numeric values
may change under a deliberate conversion; matching old JSON alone is insufficient.
Current captures and known defects are not automatically approved references.

## Persistent conditions and observed floor effects

`condition-overrides.json` uses `schema: "dnd.conditionPresentationOverrides"`,
`version: 1`. Its `conditions` mapping is keyed by the existing condition content
ID. Each row supplies optional `bodyPose` and `label: {text, color}` fields;
the loader merges only these fields into the imported recipe's `persistent`
record. Imported source files remain unchanged. Existing condition composition
priority selects the pose and label alongside its alpha/color treatment.

`bodyPose` holds the final frame of the named rig clip only when the actor would
otherwise be idle. Active gestures/hits and actual death keep their existing
body ownership. The current Sleep row selects `Die` and the label `Zzz`, without
changing native life state. Labels reuse the badge font and collision-aware
placement with fixed progress and the condition's alpha; they have no separate
expiry clock. Recorded condition application/removal controls both. The media
loader selects resting clips before playback, including intermediate condition
poses in an action lineage. A TS adapter must reproduce these two explicit local
extensions rather than silently discard them.

`condition-recipes.json` uses `dnd.conditionPresentationRecipes`, version 1,
for local extensions and content identities absent from the imported source.
The original `neuroclient.conditionPresentationRecipes`, version 12, stays
readable and unchanged. Duplicate identities are rejected. It does not
infer a recipe from a related mechanical condition. Web's source-owned
`condition.spell.web.restrained` selects its two persistent layers; generic
Restrained or standing inside a Web does not select them. Repeated instances
retain their own UUID lifetime and deduplicate the visual recipe.

`ConditionLayer.drawOrder` is `behind_body` or `in_front_of_body` (default).
The selected static body layers compose around the actual sampled body at its
fractional position, height, body lift, scale and camera-relative facing. Their
union retains the original feet registration and one actor depth; the actor's
shared alpha applies once afterward. Shadow-only passes do not include them.
`condition-media.json` maps each layer asset ID to `category`, `animation` and
`images_by_facing`, referencing existing `assets.json` resources and their
measured feet pivots. Resource scale uses the world tile reference (128 pixels),
not the additional 64-pixel modular-rig multiplier. Selected images load into the
session's body media before playback. Static layers retain their existing
registration. Animated layers instead name paged `asset_id` and optional
`application_asset_id` media, with `application_fade_ms`, `removal_fade_ms`,
`scale` and an optional fixed `world_basis`. They never populate the body-row
cache with their entire animation. Original priority, exclusive groups and
deduplication choose the layers. `activeDuring` selects actual idle/walk/jump/
forced/attack/cast/hit/death activity; body attachment follows body lift, ground
attachment stays on the recorded support. Recoloring and equipment overlays
remain explicitly unsupported; current selected layers author neutral colors.

The retained condition UUID owns application/sustain/removal phase. The caller
registers each admitted head's bound transition dates on the independent
presentation clock. Sampling all cameras or seeking the same head is pure;
later action heads do not restart the loop. Initial or reacquired unknown
membership starts quietly in sustain. Removal fades only the removed owner's
admitted layers, and expired records retire when the next head is admitted.
Previous immutable mappings still support inspection of earlier heads. These
finite decorative tails do not postpone gameplay action joins.

False Life uses this same presentation path with the retained temporary-HP
grant UUID and source identity. It creates no synthetic condition event. A
weaker/equal rejected grant cannot replace ownership; partial damage preserves
it, while depletion or an accepted replacement removes it. Public initialization
and subsequent changes retain that identity, so replay never inspects native
health objects. Bless/Bane application crossfades to sustain at the authored
1.5–2 seconds; removal currently fades over 350 ms.

`world_bindings.json` spatial-effect animations may author `default_frame`
(default `0`). When a retained spatial observation has no `trap_state`, that
frame remains visible while the observation exists. Explicit trap states still
select `state_frames` and their existing finite transitions. This is a media
selection rule, not a synthetic native activation state. The floor painter uses
only received footprint cells, each cell's support height and disclosure; removal
of the observed effect removes its drawing. Default `placement: "cell"` expects
per-cell artwork. A whole-area image uses the continuous-field placement below.

A spatial binding may also author `creation_start_frame`. A witnessed native
`CREATED` event beneath a cast then starts the existing finite world transition
at that cast's contact. The transition addresses that effect UUID alone and
advances from `creation_start_frame` to `default_frame` at the binding's `fps`.
The last deployment frame is the resting picture; it has no second overlay or
swap. The complete head includes this finite duration, while native conditions
and other recorded state still commit at contact. Acquiring an old effect through
sensory updates does not replay creation. Sampling is absolute and seekable.

For a continuous field, `placement: "area"` and `origin_offset` register that
same image during deployment and rest. Each received footprint cell gets a
disjoint crop, at its own support height and below actors, through the ordinary
ground painter. No unseen cells are added. A missing disclosed anchor remains
undrawable rather than being inferred from a partial visible footprint. Web
authors `origin_offset: [-0.5, -0.5]` for its native even-width centered cube and
disables projectile impact media because the field itself owns deployment.

An optional `footprint_tiles: [width, height]` supplies the complete authored
rectangular footprint for natural overspill ownership. Raster support cells
outside that rectangle borrow the nearest native edge or corner owner. Such a
extra piece is drawn only while that owner is in the received effect footprint and
the receiving support is currently visible; its own height, light and painter
depth still apply. Hidden or removed edge cells cannot lend fringe. Full
visibility reconstructs the original picture without turning the rules envelope
into an alpha mask. This registration is authored once, never inferred from
partial visible bounds, and does not extend native targets, terrain or effects.
The original received interior cells keep their existing current/memory
disclosure and lighting; adding fringe does not remove remembered interiors.
Bindings without this field retain their ordinary per-cell clipping.

Web's frozen `delivery-web-v9` / `uneven-silk-v11` artwork retains all 144 flight
frames (fit to actual travel) and all 288 imported deployment frames. The authored
field binding plays frames 0–189 at 288 fps, starting at projectile contact and
settling after 656.25 ms. Frame 189 already equals the source's final ground
frame, so the redundant static tail does not extend the action. Its literal silk
color is RGB 205/210/199; baked opacity is
preserved. The selected target is the flight endpoint; `origin_offset` applies
the native even-cube centroid adjustment only to the field. Tether endpoints use
the new source's measured coordinates relative to its cropped image. Mage Web
does not create a tether; actual device concentration ownership does.

`world_bindings.json.spatial_media` binds maintained media by observed spatial
content ID, with `assetId`, `assetPhase`, `holdStartFrame`, `holdFrames`, `fps`
and `scale`. It reads the same finite sparse atlas parts and registered pivots
as casting. The current surface consumes a disclosed `LinePresentationGeometry`
origin/direction and observed footprint. Unregistered geometry remains absent;
the consumer never infers a hidden origin from edge cells. Native observation
owns existence, partial removal and cleanup. Visible support pieces retain
their own height and painter depth and use the existing physical boundary
compositor. Fringe ownership chooses the nearest cell in the full disclosed
line's discrete widened-Bresenham lattice, then requires the receiving support's
sight and that exact owner's received membership. The existing pure
`line_positions` geometry function supplies this lattice without accessing a
world or calculating recipients; it cannot be regenerated from only remaining
observed cells. This preserves natural art across diagonal lattice gaps while
still removing the visual partition owned by a removed or undisclosed cell.

For a witnessed `CREATED` child, an existing creation `WorldTransition` carries
the remaining finite duration of its matching cast media. Only that effect UUID
is suppressed until its intro finishes; older effects keep drawing. The
transition duration is relative, so enclosing movement/reaction clock shifts
remain correct. Late acquisition starts maintained flow without replaying a
traveling front. Flow samples the shared absolute `presentation_ms` clock; it
does not retain a second zone clock or run additional saves.

Gust currently uses frozen source frames 252–359 at 144 fps for this 750-ms
maintained window. The initial whole-wind cast ends at 1750 ms after release,
before the export's release/fade tail. The hold's thin ribbons and its imperfect
359-to-252 seam are limitations of the selected three-second demonstration,
not newly authored looping artwork. Its phase follows the presentation clock,
including at the finite-intro handover. Native concentration removal removes
the visible maintained zone immediately.

## Spell-device bodies and emission

`spell_devices.json` uses `schema: "dnd.spellDevices"`, `version: 1`.
`bindings` maps item ContentRef IDs to independent body identities in `devices`.
The actual spell comes from the native item grant and retained `SpellFact`;
neither a body ID nor this document chooses it.

Each body declares `cell`, ground `anchor`, world-facing `rows`, `fps`,
`releaseFrame`, `frameCount`, `scale`, `operatorRecipe`, `launchPitchDegrees`
and `controlDistanceFraction`. Its `pitchBanks` contain media packaging and
measurements:

- `sheets[quadrant]`: asset-relative paths; quadrants 0–3 use the same world aim.
- `muzzlePixels[quadrant][row][frame]`: cell-pixel contact, including recoil.
- `forwardScreen[quadrant][row]`: projected barrel direction at release.
- `muzzleHeightStepsByRow[row]`: release height above the ground support in
  unscaled map-height units. Body scale applies before adding native support.

`rows` are world directions E, SE, S, SW, W, NW, N, NE, with E along grid +x.
They are independent of the modular actor rig's isometric facing labels. The
eight rows follow operator-to-device direction; changing camera selects another
sheet without changing the world row. Choose the nearest authored pitch bank.

For a muzzle contact, project retained device placement and support height, add
`(muzzlePixel - anchor) * scale`, and convert once into the spell reference-pixel
space. Capture the release-frame contact for the complete projectile: later
recoil must not move it. Device body sampling is a clamped one-shot frame clock,
aligned so `releaseFrame` coincides with the operation recipe's release contact.

The optional launch control vector uses measured bore direction, scaled to the
device-to-target grid distance times `controlDistanceFraction`. Normalize its
horizontal world component consistently across the four camera measurements;
do not normalize each camera's projected length independently. The shared curve
then uses a cubic with first control point `source + launchControl` and second
point `target - delta/3 + perpendicular(delta) * 2*curvature/3`. Existing authored
curvature controls the later part; target registration remains spell-owned.
Without a device launch vector, the existing quadratic is unchanged. Respect
the spell's `fineRotation` choice; enabled travel rotation follows the tangent.

Native `cast_origin`, effective range and optional target sector describe game
targeting, not these media settings. Public binding obtains source-item placement
only from disclosed historical player state. Actor attribution stays on the
operator. A future TS consumer needs the same finite binding/sampling operations
alongside this JSON; it need not import the Python item builder or Pygame adapter.

`neuroclient/object-attack-recipe.json` locally authors the previously disabled
`action.attack_object` body track as `Attack1`, with contact/effect at frame 8.
The imported source row remains a historical reference. This is an explicit
default object strike, not a claim that body actions execute melee weapon-profile
variants. The review uses a longsword appropriate to that default. The existing
action binding's `interaction_target` accepts `source_item` or `target_item`;
the latter uses the retained action target UUID, faces the actor toward the
object and times child world changes at the authored contact. It uses the same
gesture/state compositor as levers and other object interactions.

A device body may author `destruction` with `fps`, `frameCount`, `pitchBanks`
(`pitchDegrees` and four camera `sheets`), `wreckItemId`, and four `wreckSheets`.
The break strips retain the body's cell size, feet anchor and world-facing rows.
Wreck sheets have one column. They contain the same pixels as the final break
frame for every initial pitch; no second overlay or fade is implied.

Only an observed native `ItemLocationStateEvent` with `location=DESTROYED`
becomes an `ObjectDestroyedFact`. Its old contact must have been observed at
the actual removal's entry, and its optional replacement UUID must separately
be observed. Ordinary removals and remembered objects do not imply destruction.
The exact fact binds an existing `WorldTransition` at the parent's contact. Its
small payload retains placement, content ID, facing, pitch, replacement UUID and
duration, never the media catalog. The native device and its links disappear at
contact; that observed replacement draws the finite strip for `frameCount/fps`
seconds, then its ordinary persistent wreck. Historical facing transfers to the
replacement. First acquiring an already existing wreck does not replay breaking.
The transition uses the same absolute playback clock and can be sought backward.

Completed item `TakeDamageEvent` results project to `ObjectDamageFact` only for
an observed item or its witnessed destruction contact. Positive applied damage
binds a finite `hit_flash` world transition at the parent's contact; misses,
zero damage and canceled damage do not flash. Devices reuse the global damage
context's resolved hit-flash color and duration (currently 150 ms). The actor-only
damage pose/frame offsets do not apply to a device body. On a lethal hit the
same flash follows the explicit observed replacement during its breakdown.
Raster tinting affects derived surfaces only; source art and settled wrecks stay
unchanged. Separate hit times remain separate transitions during motion merging.

## Sustained spatial links

The existing `world_bindings.json.spatial_effects` row may add `tether` with
`frames_by_facing`, `endpoints_by_facing` and `fps`. Each facing selects asset
IDs and two endpoint pixels in those assets' cropped coordinates. The selected
resource's `scale` controls transverse width. The renderer fits the longitudinal
axis between the actual endpoints with nearest-neighbor sampling; it does not
uniformly enlarge the cable thickness when a target is farther away. Static
media uses a one-frame list. Authored loops use the existing presentation clock.

Displayed item facts carry public HP, concentration capacity and slot records
(`slot_uuid`, `spell_id`, `spell_name`). They contain no remote recipients or
effect positions. A disclosed spatial observation may link a known item and
slot and provide its actual `anchor_position`. The renderer requires that
matching slot, current item contact and visible anchor; it never derives an
origin from the bounding box of partially visible footprint cells.

The cable begins at the device's measured muzzle for the displayed body frame
and ends on the recorded anchor's ground support. The same measured offsets
already locate projectiles at release. Affine media sections enter the existing
world painter at their interpolated world positions, so intervening geometry
and per-section visibility remain part of normal composition. Source pixels and
transforms are cached; sampling performs no source audits or file reparsing.
Removing the slot, device or disclosed effect removes the cable directly from
the displayed state. Seeking restores it from retained values without a second
lifecycle registry or native engine access. These bindings and endpoint rules
are renderer-independent; only affine pixel sampling is Pygame-specific.

## Anchored cast media and maintained fields

The selected `cantrips` and `area_spells` bundles extend the same Studio draft.
A draft may deliver through `media` when it has no traveling projectile. The
cast body, complete lineage, damage callback frames, conditions, pushes and
world transitions keep their existing owners. No spell name selects a drawing
branch. `cast.sourceSockets` uses the same rig-cell registration as projectile
sockets for a track attached to the source hand.

Each `media` track names an asset/phase and an attachment (`source_hand`,
`source_ground`, `target_body`, `target_ground`, or `area_ground`). Its signed
`startOffsetMs` is relative to cast release. Its source FPS, optional duration,
loop and time map describe only media sampling. `depth` selects world/ground or
back/body/front ordering. `onMiss: omit` suppresses target media for an observed
miss; it does not infer a miss from zero damage. The selected Shock target arcs
use this option, while its preparation arcs still play. A saving throw does not
remove a spell's field artwork or produce a damaging reaction by itself.

`contact` declares the presentation delay after release, optional speed in tiles
per second, and optional per-cell contact offsets in milliseconds. Contacts are
compiled in world coordinates once. Native cube orientation is resolved before
camera rotation. `timeMapsByFacing` may map each direction's source frames onto
that same clock; changing the camera cannot move damage or a child push in time.
The original damage callback still controls when the displayed HP/number changes
after the contact reaction starts.

`worldOffsetsByFacing` registers cell-sliced art relative to its area origin;
quarter-turn inversion converts those view-grid offsets to world positions.
`bodyOffsetsByFacing` is an authored TakeDamage displacement curve in actor-cell
pixels for body-following media. `orientation: target_vector` rotates the selected
canonical facing bank toward the received target-body anchor, including height
and directions between banks. The track's authored `scale` remains authoritative:
target distance does not enlarge either the cloud or its pixels. A source's
reach/contact mismatch must not be hidden by enlarging the entire raster. This
mode changes neither range nor eligibility.

A moving, single-target puff uses the existing `projectile` travel/impact phases.
The art is local to its pivot; the shared projectile path owns palm-to-body
translation and the impact remains at that body. Poison uses scale 0.5 in rig
units (one world pixel per source pixel before zoom), ordinary 400-ms minimum
travel and speed 1000, and existing tangent bank selection. Its local travel and
impact are consecutive source frames at 144 Hz. They do not bake a second world
trajectory into the media. The superseded Poison distance/contact calibration
field and sampler were removed: measuring contact at one frame did not prevent
the subsequent baked cloud from travelling beyond the recipient.

Packed storage may use `partsByFacing`: each phase frame contains rectangles
`{file, rect, offset}` in one logical registered canvas. These are lossless storage
partitions. Their offsets and common pivot survive cropping. Adjacent unrotated
parts share rounded canvas edges at fractional zoom, preventing one-pixel gaps.
The existing bounded source-frame cache owns page decoding; runtime does not
assemble a large empty canvas or scan/checksum source assets.
Nondirectional exports may instead provide one `parts` frame array, shared by
every facing. It has the same rectangle and registration meaning; it does not
duplicate eight identical address tables or infer missing directional artwork.

Persistent condition layers and spatial media use the source-membership,
full-footprint ownership and maintained-loop contracts documented above in the
condition/spatial-field section. They reuse these atlas and registration records;
they do not introduce another native lifecycle or visual membership registry.

### Control media, pose sockets and turn activation

Condition application/removal `effects` use the same registered paged media as
persistent layers. A transition declares `startOffsetMs`, `durationMs`, attachment,
rear/front `drawOrder`, colors, priority and allowed `lifeStates`. Its finite
window starts at the received condition callback; body playback and descendants
retain their existing causal timing. Persistent layers may delay their start or
fade in while continuing their own animation phase. Unknown initial membership
enters the sustained loop without inventing an application.

`body` and `ground` attachments preserve their existing registration. `head` and
`face` resolve `BodyRig.pose_sockets[attachment][clip][facing]` against the actual
sampled body frame, including reverse playback. The points and optional
`offsetX`/`offsetY` are source actor-cell pixels, transformed by the actor's scale.
These sockets are separate from incoming projectile body/rest endpoints. An
unmeasured clip or fixed rig does not receive an invented standing head socket.

Native condition UUIDs remain the membership owners. Contributors to the same
effective visual recipe share its original presentation date; removing one does
not restart the loop or play its clear while another remains. The final removal
owns the clear. Removing Sleep during its fade-in preserves its current opacity
and advances frames through the clear rather than brightening or freezing it.

An optional `activation` declares `trigger: owner_turn_start` and finite effects.
The existing retained choreography supplies actual received `TURN_START` dates.
Command's pending indicator ends when its execution crest begins. The crest
extends the complete lineage as needed, while actual Flee movement starts at
the native turn event; it does not wait for the crest. Pending removal before
that turn plays the clear without inventing execution. Prone from Grovel remains
an independently owned native condition after Command expires.
Admission passes already-witnessed activated condition UUIDs to the binder from
those retained dates. Normal expiry after execution reserves no canceled-effect
duration; it does not reconstruct an execution phase from spell names or native
private flags.

All timing and attachment records are passive JSON. Sampling produces frame,
opacity and placement from received state and retained presentation dates.
Pygame supplies image transforms and composition, not condition ownership or
spell-specific timing rules.

Maintained spatial media declares `layers` with `assetId`, optional
`applicationAssetId` and `side` (`rear`, `center`, `front`), plus the common
hold window, FPS, scale and optional `removalFadeMs`. Native observation owns
existence. Received creation/removal facts supply local dates at head admission;
ordinary loss of sight is not mechanical removal. The layer frames continue
advancing during a clear. A field acquired without its creation enters sustain.

Line media keeps its established floor/propagation masking. A spherical shell
uses its received fixed center and radius to register complete tall rear/front
surfaces around occupants. The center must currently be observed and have known
support. This is an open-floor shell presentation; arbitrary intersections with
walls are not claimed by that registration. Gust retains its original single
center layer, finite intro and maintained global frame window.

## Condition rest poses and finite entry/exit

Condition transition `bodyAnimation` is passive authoring data: `bodyClip`,
`bodyPlaybackSpeed`, `reversed`. The existing local condition-body override
file exposes these as `applicationBody` / `removalBody`. Bind a finite body
gesture only when aggregate membership changes the selected persistent
`bodyPose`. It begins at the real condition callback and participates in the
existing lineage join. Alpha retains its own original transition duration.
Absolute sampling supports seeking; native HP/life/membership do not wait for
a gesture to finish. Sleep plays mapped `Die` forward, holds its last frame,
and reverses it on removal while alive. Incoming damage retains flash/number
timing but has no separate standing flinch. Lethal hits stay down.

`BodyRig.rest_pose_anchors[clip][facing]` authors the final pose's body contact
in the rig's full cell, beside its standing `body_anchor`. Root modular bindings
use `root_rest_pose_anchors`. `ActorContact.rest_pose` is derived from retained
condition presentation, never written into native gameplay events. Incoming
spell and ranged-attack endpoints add the pose's displacement relative to the
standing point **after** the existing authored insets. Use the target's facing
rotated by camera, not the incoming projectile's facing. This preserves approved
standing registrations, including Fire Bolt's preserved root-relative placement.
Anchored body media uses the same displacement; ground-registered area media
keeps its ground anchor. No per-frame bone tracker or dynamic pixel scan exists.

## Recorded life states and downed bodies

`life-state-poses.json` supplies optional `lifeState.bodyPoses` rows for `dying`
and `stable`. The map defaults to empty; other keys are not supported. A row has
required `bodyPose` (rig clip identity) and optional `applicationBody` /
`removalBody`, using the same `bodyClip`, `bodyPlaybackSpeed`, `reversed` values
as finite condition animation. These are presentation selections, never native
conditions. Native downing installs capability modifiers without synthesizing
an Unconscious condition; only the received `LifeFact` supplies life changes.

Current rows enter mapped `Die`, hold its final frame and reverse it on recovery.
DYING→STABLE with the same pose holds continuously. Downed→DEAD keeps the existing
down pose; it does not rise and fall again. Actual death keeps its established
death context. Clearing the downed owner does not clear a still-present Sleep
pose or other recorded condition. Incoming spells target the downed rig's same
resting-body displacement used by Sleep. No current-engine lookup is required.

The owning damage application commits its recorded HP/life result at the authored
HP callback: impact delay plus floating-number frame timing for a nonterminal
hit. Falling begins there and extends the existing finite join as needed. Later
applications retain their order and state, without restarting an ongoing fall.
A lineage that contains STABLE→DYING→DEAD retains all its native transition
identities, with its final result owned once by that damage application.
Separate healing/revival and condition removals remain independent fact owners.
Damage, flash and number timing is preserved; downed bodies do not perform a
standing TakeDamage flinch. Absolute sampling and replay remain seekable.


## Finite mechanisms and pressure controls

A `world_bindings.json.spatial_effects` record may provide `activation_frames`,
`contact_frame`, and named `transition_frames` such as `false:true` and
`true:false`. Frame sequences are finite; resting pose comes from `state_frames`.
The contact index uses the record's FPS. `depth` selects ground or ordinary world
sorting. `placement: anchor` draws one prop at the disclosed native anchor;
`origin_offset` is forward/right in that prop's native direction. This places a
tripwire once on its boundary rather than duplicating it across footprint cells.

The public mechanism activation fact supplies disclosed origin/direction,
accepted footprint, reached endpoint and optional target contact. Its finite
cycle is explicit even when the mechanism returns to the same Ready state.
`pressed` is an independent observed property. Private control links are never
presentation input; the renderer does not infer a remote consequence from a
plate or lever animation.

An optional mechanism `projectile` contains directional sprite IDs, authored tip
vectors, measured muzzle offsets per prop view, muzzle height and travel speed.
It binds a camera-independent travel interval once. Rendering selects the
canonical sprite and residual rotation for that actual path. A disclosed actor
endpoint uses the same rig body/rest attachment as other incoming deliveries.
Hidden origin, visible segment and target are separately optional. Sampling
reads retained player facts and metadata, with no native lookup, asset scan or
per-frame target inference. These numeric records are portable to a TypeScript
consumer; Pygame owns only raster loading/transforms and draw commands.

### Enclosing fixture depth

An optional prop `actor_depth` registers an authored horizontal-depth atlas:
`asset_id`, `cell`, `rows_by_pose`, `depth_range`, and
`pixels_per_unit_by_pose`. Ordinary RGBA PNG channels encode uint16 depth as
`R + 256*G`; zero is unregistered, and nonzero values decode linearly from
1..65535 to the supplied authoring range. The projected pixels-per-unit value
comes from the source camera basis. It converts source depth into the existing
unzoomed world painter depth, with the ordinary image asset scale applied.

Blade/crusher registrations use the exact v7 source mesh/camera poses. Original
color/alpha sheets are unchanged. When an actor overlaps that fixture, its image
is partitioned at the existing intersecting painter depths, then submitted as
ordinary alpha draw commands. Thus the actor can stand between the near and far
supports without a UUID tie selecting the entire sprite's foreground. Partial
alpha remains ordinary compositing; actor, smoke and projectile surfaces are
not modified. Cached source data is read only when that fixture is drawn.

This retains the existing vertical billboard convention for actors. Registration
is presentation geometry, not native collision, occupancy, damage or a second
world model. Ordinary walls and doors retain their boundary placement/sorting.

### Door, hardware and prop banks

`environment_art.json` binds native item IDs to finite `banks`, `doors`, `traps`,
`props` and legacy `wrecks` aliases. A bank declares its image path, cell, source rows, image mounting
pivots, scale, explicit sample times (or FPS), duration and optional matching
depth atlas. `ground_origins_by_pose` describes the source geometry origin for
depth; it is independent of the mounting pivot. Depth encoding ranges are fixed
decoder ranges, not the observed minimum/maximum of a particular export.

Door `pose_offset` follows the source workshop convention: physical edge equals
source row plus offset. A client rendering a known edge selects source row minus
that offset while leaving the adjoining frame on the physical edge. Openings
are selected by recorded swing and played in reverse for closing. Destruction
keys select closed/open, swing and explicit clear/jammed wreck identity; trap
keys select recorded `ready`, `activated` or `deactivated` state. Sampling holds
the exact last frame.

Prop entries are passive state tables. An optional `state_field: "is_open"`
selects `true`/`false` intact and destruction banks; fixed props use `default`.
Chest pre-break openness is retained in `ItemRemnantState.door_open`. Each
selected reconstructed intact image is the break bank's exact frame zero; an
original static sprite must not replace it at the transition. Opening remains
the existing state change at interaction contact unless authored opening media
are explicitly supplied. The offline prop importer packages declared accepted
metadata paths and merges their image/timing registrations; it does not author
native behavior or replace the state bindings.

A break bank may author `state_change_frame` (zero-based; absent means contact).
The break and hit flash still start at the existing impact. At this frame's
authored sample time, historical playback admits the destruction-owned spatial
and sensory after-values and their newly observed actors. Until then it retains
the prior received physical shape and visibility while drawing the active break
bank. This prevents an intact first frame from revealing actors or map space
behind the object. Actor admission uses causal event ownership, including initial
action staging; the final state remains ordinary event reduction. Native rules
and the latest state do not wait for animation. Damage/conditions in other causal
branches keep their existing times. `release_frame` remains a separate liquid
rupture anchor; device cleanup and unmarked banks keep their existing timing.
The current markers are authored for the six opaque freestanding interior props.

Public item facts carry native integrity, outcome, door mechanism/swing and the
factual pre-break configuration. A dedicated native `ItemDestructionEvent`
authorizes a witnessed break at its event-entry observation. Its actual spatial
children commit the new state; the destroyed body retains its original UUID and
content ID. Old replacement-UUID recordings retain their historical semantics.
Disclosed spatial mechanisms may carry their observed
`anchor_item_uuid`; that body is drawn once through its hardware item. Native
events contain no sprite IDs, timing or frame instructions. A later initialization
can display the same wreck directly without replaying its destruction. These
records and selection rules require no Python-specific behavior in a future
TypeScript renderer; image loading, transforms and alpha partitioning remain
renderer adapters.

### Deposited liquid media

`world_bindings.json.deposit_media` maps material content/residue IDs to a
`radiusCells` and an ordered `variants` array of the existing maintained-media
bindings. Native `MaterialDepositSource` retains only a destruction lineage UUID,
world origin and radius. Existing spatial/tile owners retain actual coverage and
quantity; the source frame does not discover an object or additional cells.
The variant is `deposit_uuid.int % len(variants)` (TypeScript: UUID hex to
`BigInt`, then remainder). Every piece, perspective and camera uses that variant.

An environment break bank can declare `release_frame`. Its sample time offsets
the witnessed destruction transition on the historical presentation clock.
Only the public `ObjectDestroyedFact` admits this start, matched by lineage UUID;
phase UUIDs differ. No start means cold sustained material. An intro can continue
across later action heads without extending their durations. Current native
membership still removes/transforms the material normally.

The liquid bundle uses ordinary sparse `ProjectileFramePart` addresses. Optional
`footpoint: {file, bounds: [low, high]}` points to lossless RGBA8 position data with
the same rectangle and canvas offset as its air color. Decode local world X as
`low + (256*R+G)*(high-low)/65535`, Y as
`low + (256*B+A)*(high-low)/65535`. The A channel is data, not opacity; color alpha
alone owns coverage. Apply identical nearest pixel placement to color/data.
Godot Z is engine Y. Four numeric source camera bases map to existing
`view_facing("E", quadrant)` rows E/S/W/N; no diagonal camera is synthesized.

Floor media is partitioned by the existing cell-plane projection. Air is admitted
by its exported world footpoint's received native cell, then partitioned at
overlapping painter depths. Those transient depth arrays belong to the raster
adapter; portable data remains the packed position atlas and registration.
Lighting follows each disclosed receiving cell. Replacing a barrel contribution
does not remove ordinary injury ellipses from that tile. Unhandled sources retain
the prior pool fallback rather than silently disappearing.

The approved capture has 864 intro and 288 sustain observations at 144 Hz, on a
384×384 canvas with pivot (192,192), final scale 2×camera.zoom. Importing preserves
the original pages/offsets and creates phase windows; it does not author behavior,
retint pixels or audit source hashes. Raw and color pages share the existing
lazy bounded cache. Nearest-particle ownership at overlapping transparent splash
pixels is the export's documented approximation; it is not full 3D transparency.

### Condition body presentation and maintained media

Condition recipes may declare passive `persistent.bodyScale`, `liveCopies` or
`bodyDistortion` records. Their owner and selected state come from ordinary
public condition membership; the renderer never looks up native entities or
selects behavior by a spell's name. These optional records extend the existing
condition recipe vocabulary and are portable to another renderer.

`bodyScale: {enlarge, reduce}` selects a positive multiplier from the member's
retained `size_change`. Current authored factors are 1.175 and 0.75. The existing
condition transition interpolates the multiplier over its `durationMs`, even if
finite smoke lasts longer. One resolved actor contact transforms body, gear,
pose sockets, projectile/body contacts and attached effects around the unchanged
ground anchor. Reusing a resolved contact is idempotent; it does not multiply
scale a second time. Native size, occupancy and reach remain native facts.

`liveCopies` contains world-cell `slots`, a four-color `palette`,
`paletteMaximum`, `opacity`, `emergeMs`, `dissipateMs`, `waveFrequency`,
`waveSpeed`, `minimumOpacity`, `secondaryRowFrequency` and `slotPhase`.
Optional `layers`, `applicationEffects` and `removalEffects` belong to each
copy slot. The retained native `duplicate_count` admits stable slot indices;
count reductions fade only the removed slots at the corresponding event contact.
Copy bodies use the actor's current pose, equipment and resolved size. Each
slot receives its own world depth; copies are neither native entities nor
recursive copies of shadows or the actor's other condition shells. Local
pixel-alpha waves use the shared absolute presentation time and stable slot
index. Palette mapping uses body luminance; it does not recolor the real actor.

`bodyDistortion` declares four-color `palette`, `paletteMaximum`, `waves`
(`amplitudePx`, `rowFrequency`, `timeFrequency`), `bandHeightPx`, `bodyOpacity`,
`contours` and `trails`. Bands displace composed body/equipment raster rows;
`amplitudePx` and band height refer to final raster pixels, while row/time
frequencies are radians per row/per second. Contours declare world-cell `offset`
and `oscillation`, per-second `frequency` and `opacity`. The effect can distort
an idle body without inventing movement. Trails declare `ageMs` (at most 240 ms)
and `opacity`; they sample genuine prior moving/jumping/forced-movement poses,
including the equipment and scale at that time. No changed world position means
no historical trail. Teleports and loss of observation cut continuity.

Current and historical bodies use the same pure pose resolver. The existing
admitted action heads retain only the recent 240 ms of bound inputs and one
predecessor for an idle interval. All cameras sample the same explicit time;
there is no pixel accumulation, recursive frame rendering, independent simulation
clock or network-visible presentation history.

`ConditionLayer.opacity` and `ConditionTransitionEffect.opacity` default to 1
and multiply the selected media once. They express authored per-track gains;
source-baked shader gains must not be applied again. Body-only fading is applied
before independent layer media, allowing a vanished copy's smoke to finish.

Condition media registrations may declare `application_mode: "sequence"`;
this plays `application_asset_id` once using its phase FPS, then starts the held
`asset_id` phase and keeps its clock uninterrupted across later heads. The
default remains `crossfade` for existing records. Cold acquisition starts the
held phase without an invented application. An optional
`removal_mask_asset_id` registers a coverage-mask phase with the identical
canvas, pivot, camera and display transform as the live shell. Alpha 255 retains
a shell pixel and alpha 0 removes it. At removal, the source shell's existing
phase continues while removal age selects the mask frame; only alpha coverage
changes. The mask is not a new clock or a bank for every possible source phase.
An ended mask ends the layer. Existing records without masks retain their
ordinary authored removal fade.

A `whenEnergyType` on a condition layer matches the member's retained
`energy_type`. This selects only the corresponding registered pair. Removal
retains that actually selected pair, never all candidate palettes. The selector
uses an existing damage-type value; it does not introduce a generic variation
rule engine or derive the element from display names.

### Maintained spatial fields and terrain contacts

`world_bindings.json.spatial_media` remains the one content-to-media binding.
A layer can declare `composition: "floor" | "clump" | "volume"`; omission keeps
existing `legacy` shell/line sampling. `offsetCells` registers an authored piece
relative to the retained native geometry, and `delayMs` preserves source-authored
formation/clearing stagger. Neither field moves the native affected cells.
`applicationAssetId`, `assetId` and optional `removalAssetId` select finite apply,
maintained hold and finite clear phases. A cold observation begins at hold;
visibility loss alone does not invent a clear. Explicit removal media uses its
actual phase duration; old `removalFadeMs` records retain their behavior.

Floor media uses the received footprint and visible support cells. Clumps retain
individual authored anchors for ordinary painter order. Volume media uses the
same raw `footpoint` registration described above for liquid air, supplying
aligned per-pixel world depth to the existing compositor. Current
`visible_volume_positions` grants the observed volume's geometry independently
of floor or actor sight: native observation excludes that volume's own optical
obscuration while retaining walls, other obscurers, light and range. Remembered
volume cells alone do not authorize current drawing. The observed
`anchor_elevation_steps` places a cold volume even when no ground under it has
been seen; it does not disclose tile contents. Ground/clump media still requires
its ordinary known support. The export retains its documented nearest-surface
ownership approximation at overlapping translucent pixels.

For XY air volumes, the known outer map bounds are not a wall. An authored
sample outside those bounds may borrow its nearest currently admitted edge
cell's support height. Ownership is resolved in displayed world coordinates,
including movement, while the original pixel position and per-pixel painter
depth remain unchanged. Received propagation barriers still block the short
edge-owner-to-sample segment at that support height. This cosmetic overhang
creates no gameplay cells and grants no unknown in-bounds cells; floor/clump
media keeps its existing support requirements. The inputs are the existing
event-retained world bounds, effect membership and historical geometry.

Optional `movementSpeedCellsPerSecond` gives presentation speed to an actual
same-owner old/new intrinsic geometry transition. The binding uses existing
lineage/sensory after-values and the existing historical action clock. It keeps
application/hold age and stages received geometry at visual arrival. It neither
publishes a private footprint event nor changes gameplay membership or damage.

Uniform removal may author `removalFadeMs` with `removalEasing` (`linear` by
default, or `smoothstep`). This reduces opacity while the current application
or hold clock continues, including removal before formation finishes. It does
not restart formation or require redundant constant-alpha image sequences.
An explicit `removalAssetId` continues to own its authored clear phase instead.

For a spherical volume, optional `referenceRadiusFeet` declares the native
radius represented by its source export. The received geometry radius divided
by that reference scales the registered pixels/pivot, raw world XY footpoints
and `offsetCells` together. A base-radius observation is unchanged. No scale is
inferred from an image, spell name or occupied cell count; other compositions
and omitted references preserve their original registration. This permits an
upcast area to depict its actual occupancy through the same authored recipe.

The offline volume importer accepts only a published `complete: true` delivery
with four numerically registered cameras covering both declared phase windows.
Color and raw coordinate rectangles must match. These checks happen before
copying a delivery; gameplay startup and rendering do not audit source packages.
Image files remain unchanged, including the raw coordinate stream's A byte.

`contactMedia` is an optional map from `ground_entry` or `damage` to the existing
`StudioMediaTrack` type. Ground entries use actual grounded spatial facts;
intermediate airborne jump cells do not emit floor splashes. Damage contacts use
actual positive applied damage and an explicitly known originating spatial effect,
not merely a matching damage type at a particular position. The native damage
packet's existing `effect_id` can cross into `DamageFact` only when that observer
already knows the corresponding spatial identity. Unknown terrain stays unknown.
Multiple observed owners do not duplicate a single damage contact.

These finite cues feed the existing retained movement-media owner and do not
extend the action join. Grease splashes therefore continue while walking; save
outcomes and their body transitions remain separate received facts. Thorn contact
plays at actual damage. Both registrations use authored four-camera media rather
than a spell-name branch or a second event executor. All added values are passive
JSON/typed packet data usable by a future TypeScript implementation.

## Native condition values and causal interception

`ConditionState` retains the native condition's optional `duplicate_count`,
`size_change` (`enlarge` / `reduce`), and `energy_type` (`DamageType`). A
`CONDITION_STATE_CHANGED` event replaces that same condition owner's after-value
and evaluated actor stats. It does not remove/reapply the condition or restart its
application age. Mirror Image publishes the update as a child of the real attack
that consumed an image; final depletion uses ordinary condition removal. Passive
actors also retain native resolved and structural base `Size` values. Visual scale
and copy spacing remain authored presentation data, separate from these mechanics.

An observed area retains its native `area_geometry` and `anchor_elevation_steps`
when its intrinsic frame is disclosed. `anchor_position` keeps its existing
observed-cell semantics; a disclosed volume frame does not imply its center cell
is visible. Fixed ground fields retain their previously established geometry
across later fragment observations even when the center is no longer seen. Anchor elevation
registers the visible volume even for a cold observer who has never seen the floor
beneath it. It is not a floor observation. `visible_volume_positions` is the current
observer-granted geometry mask of an optically obscuring owner. First-surface sight
establishes that owner; expansion follows the same native optical routes while
excluding only this owner's own obscuration. Walls, other obscuring owners, range,
and first-surface lighting still apply. It does not add ground cells, occupants, or
contents to visibility. Remembered `positions` and current volume admission remain
separate; losing sight clears the latter without inventing unseen removal.

Shield attribution is an optional `intercepted_by_condition_uuid` on an actual
attack or taken-damage fact. Native interception sets it when the condition really
blocked that attack/dart. Natural misses, hits through the increased AC, and
critical hits do not receive it. A canceled child retains its actual parent
lineage from registration, rather than becoming a separate replay action.

`ConditionRecipe.reactionCastBinding` optionally references an existing Studio
body-cast draft. A real intercepted condition application supplies that binding;
no synthetic cast event is created. The gesture uses the existing body clip,
release frame, equipment scope, and hand layers. Its release reveals the condition
before incoming contact. The compositor can delay the parent's entry to fit the
reaction pre-roll; both authored tracks keep their playback speed. Further hits
blocked by the same active condition do not replay the application gesture.

`ConditionRecipe.interceptionEffectsByDirection` maps the eight incoming world
directions to arrays of the existing `ConditionTransitionEffect` record. Direction
means travel **from source toward target**. A pair can reference registered front
and back condition media with fixed `world_basis: "E"`; the four camera rows then
select view independently of incoming direction and defender facing. The actual
block's contact time owns the finite emission. These tracks use the existing
retained nonblocking media tail, so a contact effect does not pause movement or
lengthen the attack's mechanical timing.

## Registered XYZ surfaces and attributable protection (September 23)

An authored multi-material packet has ordered components: for example smoke
followed by additive fire. Its draw commands share a passive `world_depth_group`.
The world painter partitions that group against common external peer depths and
preserves component order within each band; siblings are not independent world
occluders. Sorting their independently changing mean depths would reorder alpha
and additive blending and make an unchanged export flicker. This grouping affects
composition only, not native spell rules, event reduction or playback clocks.

`ProjectileFrameStorage.surfaceFrames` is an alternate storage encoding within
existing projectile sampling, not a new recipe executor. `frameIndices` maps
phase-local frames onto source sample IDs. Either `pattern` selects a loose
direction/file, `archive: {file, memberPattern}` selects that same packet inside a
ZIP container, or `componentsByFacing` selects ordered per-facing components.
These address alternatives are exclusive; the container changes neither time
nor decoded packet bytes. `coordinateBasis: "camera_local_xyz"` is explicit.

`bounds` decodes all three uint16 axes, `verticalScale` converts source height to
host height steps, and `blendModes` retains component order. Binary packets use
an eight-byte little-endian width/height/signed-pivot-offset header followed, per
component, by RGBA8, big-endian XYZ uint16 triples and a separate ownership byte.
Coordinates never pass through color management or alpha premultiplication.
Ownership zero retains original color only for raw reference composition. With
physical clipping active, unresolved coverage is cleared conservatively rather
than leaking through a wall, floor or protection sphere. Other owned samples
support masking and painter depth. Normal smoke precedes additive fire;
masked additive samples clear RGB as well as alpha.

A source coordinate is relative to its authored camera bank. Rotate its XZ
**vector**, then add the recorded impact position. Convert source Y once and add
recorded support elevation. Color and numeric samples retain identical nearest
resampling, crop, pivot and canvas registration. XYZ impacts use authored banks,
never residual screen rotation. Existing projectile travel keeps its authored
trajectory, size, anchors and timing.

Fireball retains 48 playback samples over two seconds, selecting source frames
0,6,...,276,287 from the full 288-frame delivery. Requested packets alone are
decoded. Their RGBA, XYZ and ownership bytes count toward the existing shared
cache ceiling. There is no startup scan, asset hashing or eager frame loading.

Native `SpellEvent.suppressions` attributes admitted protection to a provider
and affected positions. Player projection exposes only previously/currently
observed providers and permitted positions. A client resolves geometry from
that received spatial observation; it never queries native registries or treats
an absent public tile as proof of protection. `effect_source_position` captures
the actual native emission (including devices), independently of actor-facing
`source_position`.

`SpatialMediaLayer.suppressionAssetId` selects a finite authored contact response
using the existing stationary-media clock. `SpatialMediaBinding.surfaceHeightScale`
registers its exclusion sphere; `suppressionDirection` identifies the authored
contact direction. Globe uses fixed four-camera golden apply/hold shell halves,
with independently selected nearest-quarter response banks. Application is
96 samples at 144 Hz; hold is 576 samples; removal continues hold while fading
for 600 ms. A blocked projectile uses its existing trajectory to locate contact
with the disclosed sphere. An admitted area blast excludes only eligible owned
samples inside the sphere. Outside-to-outside projectile crossing is not itself
native suppression. Response art currently has a fixed contact altitude and four
horizontal orientations; neither field claims arbitrary 3D contact normals.

Connected Fireball rendering uses continuous visibility around observed wall
corners within the original radius, plus disclosed solid support outlines.
Camera occlusion uses the submitted wall/door billboards, including their cap,
alpha edges and holes, together with received finite boundary depth. Adjacent
collinear sprites share their connected finite edge extent, so overlapping caps
do not open cracks at cell seams. Far-side samples are hidden; contact, near-side
samples and samples outside the artwork remain. This is a visual billboard
model, not a reconstructed thick wall or an increase in native wall height.
Calls without registered scene artwork retain the finite native-plane fallback;
center-solid camera occlusion retains its existing received bounds. It does not
stencil color into native square cells or rerun gameplay eligibility. Other spell propagation
policies remain unchanged. Undisclosed obstacles/map holes do not become render
geometry; backend targeting remains authoritative for them.


### Seven-source component and attachment extension

`surfaceFrames.componentsByFacing` carries ordered component records with a
relative file `pattern` or `archive: {file, memberPattern}`, native ground `pivot`
and `blendMode`. A packet's signed
crop offset gets `round(pivot)-pivot` exactly once before registration. This
supports Thunderwave's 18 components without adding its cell positions twice.
The older single-file multi-component `pattern` remains valid for Fireball.
`positionScale` is the source's authored coordinate calibration.
`referencePixelScale` records the unzoomed pixel scale at which that calibration
matches the picture. Camera zoom never changes physical coordinates.

`projectile.<phase>.viewFacing` supplies a fixed world view basis for radial
impacts independently of the incoming projectile. Media tracks already use the
same `viewFacing` convention. Native clocks and finite phase frame counts remain
on their existing records.

A media track can declare `emissionPointByFacing`: source pixels from the
whole-effect origin to a baked attachment point. Resolve the ordinary rig socket,
subtract that source displacement after media scale, then translate both image
and XYZ by the resulting difference. This retains hand alignment for different
body sizes without resizing an area or moving the authoritative propagation
origin. No Python spell identity participates in this calculation.

`SpellEvent.area_propagation` and the matching public `SpellFact` retain the
existing native shape policy. Historical archives are upgraded at deserialization
(Fireball connected, other historical spells line-of-effect); explicit stored
values always win. Physical barriers and support heights come from retained
player observations. Compatible ramp/stair edges interpolate only toward an
observed neighbor. Unknown terrain is not a zero-height floor. Gust's maintained
XYZ samples reuse the existing disclosed line-owner rule and lifetime clock.
# Recipient support media

`StudioMediaTrack.scaleWithActor` (default false) multiplies the authored media
scale by its attached actor's visual scale. Ground-attached recipient spells
opt in; area-ground media keeps its existing map scale. `viewFacing` remains
independent of actor facing and selects the fixed-world camera bank.

Condition layer media may set `sustain_start_ms` (default zero): its loop frame
zero begins at that local application age during an authored application/hold
crossfade. The finite application retains its original clock. Unwitnessed or
reacquired memberships go straight to the quiet loop; removal advances the same
loop phase while applying the existing finite alpha fade. No native timing or
healing amount is inferred from these presentation fields.


## Portable execution details (September 24)

The values in `tests/game/fixtures/presentation-values.json` accompany this
contract. They describe ordinary JSON inputs and numeric/sample expectations;
`test_presentation_contract.py` checks them through existing Python consumers.
They are useful inputs for a future TS adapter, not a second runtime, image
baseline framework or generated schema. Python dataclasses, paths, surfaces and
compiled timelines stay outside the interchange data.

### Composition and source addressing

Current local v3 projectile phases and `StudioMediaTrack` select `composition`:

| Value | Meaning |
| --- | --- |
| `billboard` | Existing registered image with its selected attachment and painter placement; planar area ownership may still clip it. A source carrying XYZ does not implicitly enable volume composition. |
| `xyz_volume` | Paired registered color/XYZ/ownership, then shared propagation, support and world-depth composition. Projectile use is currently impact-only. Cast media requires authored orientation and map scale. |

Maintained spatial layers additionally select `floor`, `line_floor`, `xy_volume`
or `clump`. `floor` uses the admitted planar footprint; `line_floor` uses the
received line geometry; `xy_volume` uses the raw per-pixel world-cell owner;
`clump` places the existing authored support clumps. Their existing lifecycle
stays in the spatial binding. Maintained `xyz_volume` consumes received line or
sphere geometry, with the observed support/ownership rules described below.
Old `volume` becomes `xy_volume` and `legacy`
resolves once during intake. Active local bindings use explicit modes. A filename,
resource prefix, optional diagnostic tuple or presence of binary data never
selects a new gameplay effect.

A color phase has exactly one nonempty source: a pattern, pages, common sparse
parts, or facing-specific sparse parts. A phase selects either color layers or
surface packets. Each surface component selects one loose pattern or archive.
Storage preserves logical asset IDs and source phase indices; sharing physical
payloads does not share pivots, bounds, scale, alpha or clock settings.

`PackedFootpoint.coordinateBasis` is `world_xy`: RG and BA contain big-endian
uint16 values for X and Y offsets in grid cells, relative to the effect origin.
Its alpha byte is numeric data. Color and footpoint pages use the same `rect`;
neither premultiplication nor color treatment may touch the numeric page.
`PackedSurfaceFrames.coordinateBasis` is `camera_local_xyz`: X/Z are camera-bank
local grid vectors and Y is source height before `verticalScale`. The source
convention is declared in data, not guessed from image dimensions.

### Transform and sample arithmetic

- World X/Y positions are grid cells (five game feet per cell). Host unzoomed
  projection is `screenX = 64*(viewX-viewY)` and
  `screenY = 32*(viewX+viewY)-64*heightSteps`. Camera rotation is around
  `(31.5,31.5)`; displacement vectors rotate without that translation. Apply zoom
  and screen pan after projection. Positive source/image Y points down the raster;
  positive physical height points up.
- The reference rig has `TILE_W = 64`; host tiles are 128 pixels wide. Thus an
  authored media scale of `.5` gives `.5*128/64 = 1` unzoomed output pixel per
  source pixel. Actual raster scale additionally multiplies camera zoom and,
  only for records opting in, actor scale. Physical coordinates never change
  with camera zoom. `referencePixelScale` records the source's calibrated
  unzoomed pixel factor, independently of the current recipe size. The present
  deliveries use 1, except Color Spray's existing `0.8888888895833333` correction.
  Its existing `positionScale` correction is retained too. These defaults
  preserve the approved calibration; changing recipe size now changes the
  paired geometry by the same factor as its picture.
- For uint16 value `u`, decode `low + u*(high-low)/65535`. XYZ then multiplies
  `positionScale * finalPixelScale / (cameraZoom * referencePixelScale)`;
  source Y additionally multiplies `verticalScale` when placed
  in the world. X/Z inverse-rotate from the selected camera bank, then add the
  recorded effect origin. Shared attachment displacement applies to both color
  and geometry; it does not relocate native propagation origin.
- Packet storage starts with little-endian `uint16 width, uint16 height,
  int16 offsetX, int16 offsetY`; then each component stores row-major RGBA8,
  big-endian XYZ uint16 triples, and uint8 ownership. Logical coordinate access is
  `[x,y,channel]`; file scan order is rows before columns. Source ownership zero
  is unknown, not a valid world point.
- A component's signed packet offset is relative to its source pivot. The loader
  adds `round(sourcePivot)-sourcePivot+assetPivot` once. This preserves a shared
  logical canvas across sparse/packed storage; it does not add a world-cell
  offset again.
- For unrotated source part offset `o`, size `n`, pivot `p`, anchor `a` and final
  scale `s`, each raster axis uses `left=round(a+(o-p)*s)` and
  `right=round(a+(o+n-p)*s)`. Size is `right-left`; nonpositive parts are omitted.
  Adjacent parts therefore share the same rounded edge. `round` uses nearest
  integer with ties to even, including negatives. JavaScript `Math.round` alone
  does **not** reproduce this rule.
- Nearest scaling follows the installed Pygame-ce/SDL integer center sampler:
  `step=floor(sourceSize*65536/outputSize)` and
  `sourceIndex=floor((floor(step/2)+outputIndex*step)/65536)`. Its fixed-point
  truncation matters at ties: 2→3 selects `[0,0,1]`, while 4→2 selects `[1,3]`.
  Color, raw XY, XYZ and ownership retain the same indices. This is the
  [SDL 2.32.10 nearest scaler](https://github.com/libsdl-org/SDL/blob/release-2.32.10/src/video/SDL_stretch.c#L831)
  used by the current adapter; a TS port must implement the same sample rule.
  The uint16 decode uses float32 arithmetic in the current adapter; comparisons should allow its
  finite precision, not silently replace it with a different sample.
- Color-only residual rotation is clockwise radians. Rotate the pivot-to-part
  center by that angle, rotate the raster, then round the destination relative
  to the rotated raster center. XYZ uses authored camera banks and rejects
  residual screen rotation. Porting the color raster rotator requires pixel
  comparison where exact Pygame edge coverage matters; the JSON fixtures do not
  claim that every graphics library rasterizes rotation identically.

Support clipping uses only received supports. A compatible observed slope edge
interpolates toward its observed neighbor; an unknown support remains unknown.
Raised surfaces, caps and protection spheres are independent constraints.
Cleared additive samples must clear RGB as well as alpha. Normal and additive
components retain source order inside common world-depth bands. This painter
representation is not a general solution for two translucent volumes that
interpenetrate at each pixel; a source carries its owned sample, not a full
volumetric ray or hidden fragments.

### Clocks, source frames and lifecycle joins

Times are milliseconds; FPS is source frames per second. A uniform source sample
uses `floor(elapsedMs*fps/1000 + 1e-10)`, modulo the frame count for a loop or
clamped to the last frame otherwise. Callers own the active interval and do not
ask that sampler to invent pre-start behavior. Track FPS overrides phase FPS,
which overrides asset FPS. The existing traveling projectile's separate FPS
contract is retained as described above.

A `timeMap` linearly interpolates source-frame position between successive
elapsed-millisecond keys and floors it with `1e-9` boundary tolerance. Frames
are clamped to the source range. Facing-specific time maps override the common
map for that bank; they change source sampling, not contact or engine time.
Duration is explicit `durationMs`, otherwise the common map's final elapsed key,
otherwise `frameCount*1000/fps`. Source `frameIndices` apply after phase-local
sampling. Camera-facing selection advances two entries per quarter turn in the
authored eight-direction order; it never changes the compiled timeline.

Finite recipe media starts at release plus `startOffsetMs`. Both direct and
projectile casts join its end with body/delivery completion before recovery.
A negative absolute start is rejected. Independent contact tails retain their
existing nonblocking lifetime; maintained condition/spatial media remains tied
to recorded membership and removal. A loop flag controls frame repetition,
not endless action ownership. Condition sustain/removal phase behavior is
unchanged. Complete lineages reduce independently from this presentation clock.

Stationary contact cues receive an already resolved world position and height.
Their producer owns attachment resolution, including body height for Shield's
interception response; the stationary sampler does not reinterpret that authored
attachment as a ground socket. Unsupported sampling transforms remain explicit.

Coverage reports enumerate the initialized bindings, including conditions,
objects, devices, portals, spatial and deposit media. A bound portal cue counts
as a portal presentation. Selected binding, actual causal coverage, supported
executor fields, passing replay checks and human visual approval remain separate
claims. No report scans media to discover gameplay or turns an absent cue into
an automatic missing-animation diagnosis.

### Support conditions: choices, finite responses and body material

`ConditionState.enhanced_ability` is an optional ability identity, parallel to
the existing energy-type selection. `ConditionLayer.whenAbility` selects a
matching authored layer; missing historical choice does not select a default.
Enhance Ability records its configured choice on the same paid spell event as
`effect_id = support.enhance_ability.<ability>`, consumed by existing
`effectDrafts`. Its ordinary registration still defaults to Strength; this
presentation binding does not introduce a six-choice action interface.

`ConditionChangeFact.consumed` distinguishes consumption from ordinary removal.
Only the condition actually consumed receives it, not descendants removed as
linked cleanup. `HealFact.source_condition_uuid` identifies a producing condition
for real periodic healing. Both are optional legacy-compatible facts retained
through native archive and subjective public JSON. A canceled parent still
retains its terminal child lineage edges; cancellation does not erase a
completed reaction or condition removal.

A recipe's `responses` contains `consumed` or `healed` triggers and existing
`ConditionTransitionEffect` records. Consumption plays once at the removal
contact and replaces the maintained/removal media. Healing plays once per
positive, unblocked heal owned by that condition. Binding uses membership at
the causal fact, so a final pulse survives later expiry in the same lineage.
Responses are keyed by event and condition identity, follow the actor's current
presented contact, and retain only unfinished tails. Their finite end extends
existing choreography completion; maintained loops never hold up the queue.
Neither path changes game time or manufactures an event.

`StudioMediaTrack.requireRemovedConditionTag` optionally gates a target media
track on actual completed, uncanceled removal with that tag in its cast lineage.
Remove Curse uses `curse`. Multiple matching removals on one recipient produce
one release; a clean recipient gets no release and no invisible media delay.

`persistent.bodyRamp` contains colors, `mapping: maximum_rgb`, gain,
`applicationMs` and `removalMs`. Stoneskin's five-band material maps
`min(4, floor(clamp(max(R,G,B)/255 * 1.35, 0, 1) * 5))` to its authored palette.
The current composed body/equipment row supplies the pixels; alpha, pose and
equipment changes are preserved. Shadow and independent VFX are excluded.
Hit flash keeps priority. The existing bounded palette cache stores immutable
mapped rows, never keys by blend time.

New support-condition billboard media is privately packed at 32 FPS. Source
time selection uses `floor(k * 144 / 32)` and preserves phase duration, four
camera banks, paired layers, canvas, pivot and crop offsets. Production ships
only selected packed pages; 144 Hz originals remain in the private source
archive. Casting-hand sheets retain their separate rig clock. The offline
packer and importer own pixel storage and registration; authored JSON owns
selection, lifecycle and timing. This billboard adapter does not resample
position/XYZ banks or redefine an existing cloud's loop.

### Maintained XYZ fields and observed protection surfaces

The six spherical clouds use existing `xyz_volume` layers and packed
RGBA/XYZ/ownership samples. Camera-local XYZ is transformed once. The full declared
sphere lattice, clipped only to known map bounds, assigns each sample an owner;
decorative air outside that lattice borrows its nearest geometric edge. Only
then is that owner checked against the received observation. Missing interior
or edge owners never reassign their pixels to a visible neighbour. This is the
spherical counterpart of existing line-field fringe ownership, not a dilation of
gameplay occupancy. The receiving cell supplies its observed support height.
Ownership stays in the received after-geometry coordinates during movement;
only the registered image, genuine XYZ and support lookup are translated. This
prevents a map-clipped owner from drifting inward and becoming a temporary wall.
Final composition uses the same registered wall
silhouettes, finite geometry and `ExcludedSphere` cuts as transient XYZ spells.
Source Y must survive packing, scaling and cropping alongside its matching color.

Maintained effects retain `suppressions` from actual native footprint resolution.
Each receipt identifies the provider and actual overlap. The subjective boundary
adds only previously/currently disclosed provider geometry, content identity and
height, and permits only observed overlap cells. This allows cloud samples above
or outside the sphere without restoring suppressed gameplay cells. Missing cells
alone never imply protection. Movement retains before/after exclusion geometry
through the interpolation; additional owner cells come from the after receipt.
Removing a provider does not retroactively recompute an existing native footprint.

A currently observed cloud/protection intersection can expose an active, already
known protection surface through `visible_volume_positions`. It does not expose
the ground or occupants. Real walls, other obscurers, range/light limits, unknown
providers and removed providers remain respected. A sphere shell is submitted
when its footprint or surface is currently observed, using received anchor height;
its center ground tile need not be visible. Remembered membership alone is
insufficient. Actual geometric occlusion then determines which shell pixels show.
