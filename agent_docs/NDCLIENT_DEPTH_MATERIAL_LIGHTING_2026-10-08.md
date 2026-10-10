# NDClient: depth, materials, lighting and interaction geometry

Implementation companion to [the master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).
This design now incorporates the measured standalone Fireball GPU proof. Its
[receipt](audits/ndclient-plan-20261008/FIREBALL_PROOF.md) distinguishes demonstrated
depth/normal/light behavior from remaining production and visual requirements.
The [compact-media contract](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md)
now settles N−1's representation and source-field decisions. Production remains
stopped until the human resumes it. N1/N3/N5 implement and measure this design in
the shared client/Studio path; no additional standalone demo is a prerequisite.

**Whole-renderer principle:** derive visual requirements from existing content and
events, then implement them using Pixi/GPU primitives. The Python paths below explain
historical behavior and failures; they do not prescribe algorithms to translate.
Keep semantics and intended appearance, not CPU image operations or cache structures.
The [NeuroClient/Pixi component matrix](NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md)
identifies existing functions to recover and the relevant official docs/API checks.

| Responsibility | Target design from Pixi capabilities | What causes work |
|---|---|---|
| Camera and ordinary sprites | Shared TextureSource regions and world RenderGroup; separate screen UI | Pan/zoom changes transform/culling, no image reconstruction; frame/bank changes update source views |
| Floors/walls/props/elevation | Support/face geometry, registered UVs, finite opaque/translucent policy | Disclosed geometry/state changes; ordinary animated art changes frame, not gameplay geometry unless authored |
| Modular/fixed bodies and equipment | Batched layer quads, shared mask/material programs, authored clip/socket evaluation | Sample current clip/parameters; do not bake palette and camera combinations into CPU bitmaps |
| Projectiles and beams | Direction bank plus projected tangent, quads/ribbons/compact depth geometry as needed | Absolute trajectory, release socket and appearance samples; no image rotation/raster per display frame |
| Bursts/clouds/domes | Settled plane/mesh, ellipsoid or scalar-depth assignments and shader intersections | Compact displayed geometry/disclosure updates and effect time; no runtime full XYZ |
| Blood and ground effects | Batched analytic particles; receiver-local coverage and active material increments | Release/landing/changed contribution, not replay of every old stain on each frame |
| Colour/material/light | Finite GPU material functions and compact historical fields | Parameters/small changed ranges; post-processing only when composition requires it |
| Highlight/picking | Shader silhouette outline and compact CPU hit geometry on presented state | Pointer or presented geometry changes; no viewport readback on each hover |

Pixi RenderGroup, TextureSource, Mesh/Shader, buffers and layers supply execution
mechanisms. They do not supply our physical semantics automatically. A small number
of measured passes is preferable to one Filter, RenderGroup or custom class per
entity. A shader is not a reason to move native rules onto the GPU or to construct
a generic node graph. See the pinned [reference reading map](references/pixijs-8.22.0-20261008/README.md).

## 1. Why ordinary Y sorting is insufficient

The [mathematical/Pixi refinement](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md)
provides the concrete surface-depth reconstruction and volume/transparency choices,
wall geometry shared with receiving light, and source-reviewed lighting-library
ideas. It reinforces this chapter's physical/disclosure separation: cells do not
stencil admitted sprite overhang. The Fireball handoff selects two bands and local
depth peeling; the compact-media chapter fixes the remaining family assignments,
fields and source-specific calibration. N1/N3 measure those choices, including their
explicit approximations. Existing proof lights do not replace the effective-light
field baseline in §5 below.

`game/projection.py:painter_key` uses camera-rotated **unraised ground contact**,
physical boundary-edge offsets, composition phase and stable identity. Height moves
the drawing on screen and selects supporting geometry; it is not subtracted from
the sort key as though a flying actor had walked north. Body `ground_depth` sockets
and registered source offsets also affect contact. A prone frame must not change
ordering merely because its occupied pixels moved up the sheet.

`game/fixture_depth.py` further splits fixture and registered surface pixels around
overlapping painter contacts. `floor_composition.py`, `area_media.py` and
`volume_media.py` handle receiving silhouettes, slopes, finite vertical supports,
apertures and ownership. Together they allow a creature to be inside a cloud or a
fire ring. These are not expressible as one `sprite.zIndex` per wall or effect.

NeuroClient `render/worldDepth.ts` provides useful deterministic tie-breaking, but
`effectWorldDepthFromScreenY` and flat X+Y ordering are insufficient. Pixi's
[RenderLayer](references/pixijs-8.22.0-20261008/guides/concepts/render-layers.md)
separates logical parents from draw order; it does not compute this game's physical
ordering. A GPU Z buffer alone also does not order translucent samples correctly.

## 2. Coordinate and registration contract

### NeuroMapEditor reference: preserve the separation, not a second world

The inspected `/home/tommaso/Dev/NeuroMapEditor` uses independent `ZGrid` identity,
explicit `projectionOffsetPx` and separate `VisualTilemap` composition policies in
`src/model/types.ts`. `src/model/lattice.ts` has 128×64 macro and 64×32 child lattice
math; `src/render/orderPhaseOne.ts` deliberately excludes grid identity and pixel
calibration from physical ordering. `spritePresentation.ts` and `alphaPicking.ts`
preserve pivots/transforms/alpha for presentation and selection. These are useful
source references for the earlier multilayer-grid idea.

Its phase-one order is camera-independent and tied to imported Unity composition
groups/traversal. `docs/PHASE_ONE_IMPLEMENTATION_RECORD.md` records objects and
roofs as active (roofs hidden by default); the README's earlier deferral is stale.
Therefore it is not already the production game's complete height/occlusion system.
Recover the distinct notions of logical support, image calibration, visual layer
and picking coordinates. Adapt lattice/transform/mask functions where compatible.
Do not copy its editor store, inferred height rules or independent ZGrid topology
into the player SDK state. Native received supports/elevation remain authority.
An editor-only pixel calibration must never create a walkable floor in the client.
The [foundation repair plan](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md#multi-z-preserve-the-distinction-rather-than-inventing-engine-state)
records the current native single-support-per-XY boundary and the distinct need
for multiple visual pieces at their authored heights. It governs the immediate
repair of the client that bypassed parts of this registration contract.

### Production spaces

Keep explicit, distinct spaces in functions and records:

| Space | Units and ownership |
|---|---|
| Native world | Cells, support elevation steps, disclosed slopes/volumes; no fixed positive-coordinate assumption |
| Registered source | Original frame pixels/pivot/footpoint; offline XYZ bounds/scales; runtime scalar depth/normal and categorical/source-piece ownership |
| Camera world | Quarter-rotated world XY and unscaled isometric pixels |
| Screen | Camera pan/zoom, CSS position, device-pixel ratio |
| Local material | Explicit source UV or rest position reconstructed from current point and captured piece transform; never guessed from screen position |

Current registration uses 128×64 tile projection and 64 pixels per elevation step.
Keep those authored units; pan/zoom are matrices. Select a camera centre from scene
geometry/configuration instead of perpetuating Python's fixed 64×64-map centre.
Changing the centre only translates a transform; it does not change native IDs or
expose global coordinates that were not received.

Source RGBA, XYZ, owners, footpoints, depth, normals and masks use consistent crop,
frame, camera bank and source registration. The
[compact-media contract §2](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md#2-finite-representations-and-complete-family-assignment)
fixes runtime geometry, paired-page registration, typed bases and precision.
Full XYZ is offline provenance only. Runtime RG16 depth bytes and oct8 normals
are raw numeric RGBA8; categorical/source-piece planes are R8UI/R16UI. All use
nearest sampling, no gamma conversion, premultiplication, mipmaps or lossy
compression. Source XYZ is big-endian, existing environment contact-depth RG is
little-endian, and the runtime packed depth is big-endian. Decode/convert at the
named offline owner, not by guessing a byte order during a draw. Source
`material_rest_xyz` uses the captured current-to-rest piece transform route;
it cannot be interpreted as current camera depth.

Flat directional projectiles choose the nearest authored heading and apply the
permitted small residual alignment to the projected path tangent. Their release
comes from the actual rig socket at its authored frame. Registered depth banks do
not receive arbitrary screen rotation that leaves their companions behind. Use the
registered camera/world transform, with explicit direction capability per media.
Path flight height, source/target body height and physical support are distinct.

## 3. Composition design

Use one world RenderGroup for camera transforms and a separate screen-space UI
root. Keep draw submission ordered by passive render records, not a tree of spell
controllers. Coarse layers provide world background and screen overlays; **do not
put every raised floor behind every actor or every wall in front of every actor**.

Records retain plane/contact/phase/stable keys, owner, support, bounds, source
registration, depth policy, blend and complementary-mix identity. They contain no
`pygame.Surface` or viewport-sized arrays. A draw family selects a finite material
program and buffers, not a spell-specific renderer.

### 3.1 Ordinary and compact registered draws

N−1's design is settled: Fireball retains its two genuine depth bands; directionless
clouds use one shared colour bank and the specified two-contribution ellipsoid
approximation; existing true front/back shells retain their distinct appearance;
directional surface media retain their banks with scalar depth. Bodies use their
registered contact billboard, ordinary walls/doors their calibrated faces, and
irregular props their converted source depth. The compact-media chapter supplies
the complete assignments, including rest-fracture and receiver deposits.
**Exact replication of Python's occupied
depth means is withdrawn.** It is an implementation heuristic, not a visual or
gameplay requirement. No huge source-depth prefix tables or synchronous readback
should be built to preserve it.

Ordinary billboards retain physical contact and authored ties. Use a spatial index
for actual overlaps; chosen geometry supplies physical depth to shaders. Opaque
depth and translucent composition are distinct. Do not expand an entire volume
into a CPU image/draw for every particle contact. The common policy is solid depth,
directly ordered transparency where valid and local depth peeling at crossings,
with separate selection attachments, stable ties and conservative finite bounds.
N1/N3 acceptance covers actors inside volumes and overlapping clouds, with aperture,
support, exclusion and disclosure handling. One opaque depth texture alone does
not solve arbitrary transparent composition.

Parts of an authored composite retain sibling order. Coplanar ground samples remain
below their supported bodies/contact shadows. Complementary samples compose once
with their weights; normal/add/screen conventions remain explicit. Camera pan only
changes projection/culling, not pixels or unrelated ordering. Detailed volume,
blood and ground ownership, fields and algorithms are settled in the compact-media
contract. N1/N3 implement them; N5 measures combined real-event workloads.

Opaque means final alpha exactly 1 after source/material/cutaway processing.
Fractional alpha, antialiased edges, additive samples and
faded wall coverage participate in transparent composition with solid depth writes
disabled. Source alpha zero with nonzero combined radiance is additive coverage,
not empty padding. Stable authored ties preserve body layers and complementary
samples without moving their physical depth. Do not copy the proof's alpha>=0.5
opaque shortcut into production.

### 3.2 Grid and ground feedback

Reuse NeuroClient `grid.ts`'s mesh/uniform technique and analytical line drawing,
not its singleton flat rectangle. Draw on each admitted support mesh, including
slope interpolation and raised landings. Place grid/path/AoE feedback above that
floor's material and below its walls/props/bodies. A raised floor's grid participates
in that floor's depth group; a global final overlay is forbidden.

Hovered cell changes update a small uniform/selection buffer. Camera movement
updates its matrix. Terrain geometry updates only for changed support facts.
The displayed path and AoE footprint come from native preview values. Do not
recompute pathfinding, footprint legality or spell range in the shader.

## 4. Finite shader/material collection

Depth-free UI and resolved overlays keep Pixi's built-in Sprite batching. World
quads requiring physical depth use explicit shared Mesh/Shader geometry/state and
shared texture views. Pinned Mesh/MeshPipe disable
ordinary batching for custom shaders/depth state; explicitly combine compatible
geometry/instance attributes and measure draw count. Sharing a compiled GlProgram
does not batch separate Mesh objects. Keep differing material resources/parameters
scoped correctly and preserve translucent order when combining draws.
A Filter is used only when the effect needs a composed intermediate image; each filter incurs render-target work.
Do not allocate a full-screen filter per actor/effect. Cache programs, not a new
shader instance for every spell. RenderLayer attachments cannot escape the filter
scope of a logical parent whose composite they need.

| Operation | Data inputs | Implementation decision |
|---|---|---|
| Original sprite/frame | Source texture/rect, pivot, alpha convention | Textured quad/shared atlas; accepted source art retained |
| Exact palette swap | Source/target colours, tolerance, isolated mask | Fragment colour replacement; preserve original alpha; no multiply tint |
| Palette ramp | Resolved palette, gamma, precomputed source luminance range, noise texture | Reuse current `spell_palette.py` semantics; compute percentile metadata offline, not on every rendered frame |
| Full material transfer | Existing finite material kind/parameters, donor texture/normal, isolated sheet mask, phase | Share body/action/hand material functions; sample donor under original silhouette |
| Directed media | Explicit mesh/ribbon parameters and sampled trajectory | Registered geometry/UV; noise_ribbon, darkness_mesh and plasma_trail remain finite operators |
| Support/volume composition | Settled compact geometry, finite support planes, apertures and received field ownership | Shader physical clipping and receiving-surface mapping, independent of fog; implemented/accepted at N1/N3 |
| Blood/air particles | Existing finite templates, absolute trajectories, shared landing schedule, admitted receivers | Batched geometry/attributes, no per-particle images or gameplay simulation |
| Water/deposits/ground effects | Existing material, normal/noise, historical contribution/receiving face | Local reusable coverage + active increments/material clocks, not repeated CPU raster or new chemistry |
| Object outline | Final physical silhouette, admitted identity and hover/Alt state | Local mask contour in device pixels; no coloured rectangle around transparent padding |
| Wall cutaway | Received visible ground coverage, wall top/base/aperture registration | Fade covering upper face; keep base/aperture identity and lighting |
| Light response | Displayed effective treatment field, position/normal and receiving material response | Same functions for floor/wall/body/equipment/effect; emission and receiving response are independent; §§4.1–5 |
| Bloom | Source emission where available; Fireball bright-pass from combined visible radiance is an explicit approximation | Shared bounded treatment; never blur HUD or every body layer separately |

Full material operators already include maximum_rgb, luminance_texture,
bark_texture, wither_texture, fracture_wave, energy_burn, rising_bands, etched_burn,
flowing_film and frost_texture. Retain their authored material meaning and useful
formulas in shared shader functions instead of inventing a general
shader-node DSL. Visual operators use deterministic sample time/seed so backwards
Studio seek is stable.

Order of work is explicit: source decode → authored palette/material treatment →
world light response for the receiving material → authored emissive contribution →
physical cut/depth and blending. Presentation admission/knowledge is decided before
world draws. Do not modify source alpha to simulate world lighting. Display text,
head markers and UI are not darkened by world treatment. Exact colour matching is
validated unlit first, then light response separately; illumination is not a colour
swap substitute.

### 4.1 Proven emitting and receiving material

**Both at once.** The delivered Fireball stores combined radiance/transmittance;
it has no separate smoke-albedo/emission channels. The working proof preserves
that appearance and adds received light across the **whole effect**, using its
existing depth and normals. No old smoke captures, palette classification mask,
additional texture, or separate relighting pass is required. This does not claim
to reconstruct physically separate fire/smoke materials from combined colour.

The proof's per-fragment calculation, in linear light, is:

```
P = sourceToWorld * (pixelRayOrigin + pixelRayDirection * decodedDepth)
N = normalize(inverseTranspose(sourceToWorld.linear) * decodedNormal)
J = sum(visibleLight * lightColour * intensity * attenuation * max(dot(N,L),0))
C0 = decodedCombinedRadiance
coverage = max(opacity, clamp(maxComponent(C0), 0, 1))
C = C0 + coverage * diffuseReflectance * J
alpha = originalOpacity
```

`visibleLight` here is the light-to-receiver geometry test; camera occlusion uses
`P` against scene depth separately. The demo uses neutral linear reflectance
`[0.18,0.18,0.18]`, quadratic range falloff, warm/cool scene lights and the Fireball's
own point light. Reflectance/coverage are an authored approximation, not recovered
albedo. Preserve source premultiplication/additive conventions. Do not apply another
opacity multiply during blending. Production bounds `J` using §5's audience and
headroom policy; the proof's synthetic lights do not implement that policy.

Emissive appearance, diffuse response and the light cast onto neighbours are
independent. The Fireball emitter uses the delivery's **fitted visual curve**:
v1 peaked at 0.22 s; the selected v4 retimes that peak to 0.44 s, relative intensity
0.04 to 1.64375 s, and ends at 1.916667 s. Always sample the selected manifest's curve.
The proof scales
intensity by four; that is a scene calibration, not a magic-spell rule. A flame can
retain bright pixels while its scene light fades; smoke can keep receiving another
light afterward. Never infer the emitter curve by thresholding an image each frame.

**Minimal source/export work.** Extend the current media-registration/material
owners used by `game/animation_types.py` and the existing presentation exporter
once in N0; generate the authored TypeScript declarations from those types. The
[compact contract §2.2](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md#22-exact-existing-owner-additions)
defines the exact finite types, formats and defaults. This table maps those same
fields to their render use; it is not another schema or registry:

| Owner | Data retained/authored | Runtime derivation |
|---|---|---|
| `ProjectileFrameLayer` / `ProjectileFramePart` | `appearanceEncoding`, `radianceScale`, `geometry`, paired `geometryFile` and discriminated `ownership`; existing rect/offset/pivot and layer order | Shader uniforms, decoded depth/normal and coupled resource leases |
| Existing drawable registration | Shared `ReceivingMaterial`: enabled, linear reflectance, emission preservation; existing palette/condition/item materials remain owners | One material/light function; no per-spell light renderer or second normal registry |
| `ProjectileFrameStorage.emitter` | `VisualEmitter` position/colour/intensity/range keys on the existing phase clock | Disclosed visual emitter sampled at displayed time; no rules-side light source invented |
| `EnvironmentBankSource` / existing depth registration | `surface_geometry_by_pose`, converted depth encoding and calibrated ray registration; existing masks, poses/pivots/sample times | Shared camera depth, normals, receiving light and light blockers from displayed geometry |

The accepted two-room wall-reach example now uses the same reconstructed `P` for
native-authorized continuous region and solid-interior tests before camera depth.
That is separate from `J`'s light-shadow calculation. The compact general-region
contract, audience evidence and stage scheduling remain owned by existing native
projection/presentation/world-geometry components; see
[occlusion §1.1](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md#11-native-reach-to-continuous-render-regions).
Do not translate its one-axis proof interval into a per-spell shader or infer a
blocked region from absent subjective hit cells.

Use an existing field wherever it already carries the role. Source/export types own
the data; `render/` consumes compiled records. No raw Godot manifest interpretation
inside an individual spell. Studio's existing material/environment/timeline
inspectors edit those same source values and show colour/depth/normal plus unlit,
receive-off and receive-on views. Diagnostic toggles do not change gameplay state.

**Wall lessons are part of the production design.** The real D1 wall has a calibrated
inner-quarter-cell main face (0.25 thickness, height 2), not the demo's initial
guessed centred box. Those numbers belong to that asset registration, not universal
wall constants. Adjacent collinear solid pieces share a receiving surface so tile
joins do not manufacture internal end-face normals. The arch retains its own frame
and aperture; joined receiving geometry never fills the opening's light blockers.
Retain source alpha and consistent face depth beneath irregular stone overhangs;
do not switch box misses to an unrelated vertical plane or crop the original art.
Invalidate this derived geometry on relevant displayed open/break/placement changes,
not camera pan or every frame. Different wall banks need their own calibration.

**Three separate operations:** camera depth ordering, light-ray shadowing, and
physical effect/wall contact. A shadow ray cannot be reused to delete the Fireball's
angular sector: that produced the rejected wedges and door cones. Camera-depth
probes now pass. The accepted two-room native-reach example covers one bounded
contact case; general topology, height and destruction contact require production
implementation and N1/N3/N5 acceptance
under [math §1.1](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md#11-native-reach-to-continuous-render-regions).
No affected-cell or visible-floor stencil may crop an admitted effect.

The same shared light functions serve walls and the effect. Receiving light adds
no texture or pass in the proof. The overall renderer still has solid composition,
ordered/peeled transparency and bloom passes; this is not a claim of one total pass.

## 5. Lighting that follows the map without square blocks

### 5.1 Facts we actually have

The protocol supplies five categorical light levels: magical darkness, darkness,
dim, bright and very bright. `SensesSnapshot.effective_light_levels` and its deltas
already incorporate observer senses. Party audience projection chooses an authorized
observation per visible cell. Seen-memory, visible support, entity contacts and
object contacts are separate facts.

It **does not** supply physical point lights with RGB, height, continuous intensity,
normal maps or shadow maps. Native light propagation is also categorical. A hidden
torch may illuminate an admitted floor without revealing its identity. Recreating
lights from visible torches would therefore be wrong.

Pygame maps the received levels through `world_bindings.json:treatments`, and applies
RGB gains to floor/water, walls, props, devices, items and deposits. Walls use their
incident admitted supports. Ordinary actor/VFX draws do not receive that general
world-light treatment. A consistent actor-light response is a **requested visual
improvement**, not already-implemented parity.

### 5.2 Required visual policy

Retain `world_bindings.json:treatments` as the sole level-colour table. Add
`WorldBindingsSource.lighting: WorldLightingPolicy` in the existing
`game/world_binding_types.py` owner, with these exact fields/defaults:

| Field | Type / default / meaning |
|---|---|
| `edgeHalfWidthCells` | Finite float in (0, 0.5], default 0.20; half-width of connected-support smoothing |
| `treatmentSpace` | Literal `"linear_gain"`; table RGB values are receiving-light gains in the linear working space |
| `baseResponse` | Finite float in [0, 1], default 1; `I_base = mix(vec3(1), smoothedTreatment, baseResponse)` for receiving materials |
| `directCeilingLinear` | Three nonnegative finite floats, default `(2, 2, 2)`; total receiving-illumination ceiling per channel |
| `directFalloff` | Literal `"quadratic_range"`; `max(0, 1-distance/range)^2` |

Receiving/emissive roles reuse `ReceivingMaterial.enabled`,
`diffuseReflectanceLinear` and `preserveEmission` from the owning drawable; no
per-body policy copy, emitter registry or extra normal schema. The defaults are
conservative finite visual authoring, not measured physical albedo. With bright
table gain 1 the direct headroom is 1; with very-bright red/green gain 1.08 it is
0.92. A gain already above its ceiling keeps that base and receives no added term.
Effective magical darkness and seen-memory permit no direct enhancement or
cross-boundary smoothing. Unknown supplies neither a light sample nor admission.
Do not add a light-source ECS or expose native unprojected sources. Studio edits
these same source values and provides the old sRGB-multiply reference view.

Build a compact GPU field for displayed admitted supports: treatment, validity,
memory/current classification, support height and known boundary/aperture continuity.
Update changed cells/edges only. It is derived render data, not another network
schema or independently simulated world. The shader samples **world/support
coordinates**, so light stays attached to the floor during rotation or pan.

For each fragment:

1. Determine its registered receiving support/face. Never use screen Y as a proxy.
2. Resolve the centre sample's categorical treatment first; never average enum IDs.
3. Near an edge, blend neighbouring authored RGB treatments using the following
   fixed smoothstep kernel, restricted to compatible currently admitted supports.
   At signed edge distance s in cells and half-width w, the neighbour weight is
   `smoothstep(-w, w, s)`; outside the strip it is exactly 0 or 1. At a corner,
   multiply the two axis weights for the four supports, remove inadmissible weights,
   then renormalize. Include a diagonal only when both intervening cardinal paths
   are disclosed and compatible, so a closed corner cannot be crossed. With
   `w=0.20`, a cell retains its exact centre treatment outside the edge strips.
4. Do not blend across a known closed wall, support discontinuity, magic-darkness
   boundary or memory/unknown boundary. Slopes/open doorways use actual admitted
   connectivity and receiving height; unknown does not imply open.
5. Keep visibility admission discrete and separate. Smoothing cannot grant visibility
   to a floor, occupant, object or upper volume. Do not sample objective/raw tile
   light when a current effective-light entry is absent.

This provides softer light boundaries close to the game's square regions without
round floodlights overruling those regions. It deliberately does not promise
physically correct continuous light falloff from data that does not exist.

Apply the same field to walls/doors using registered incident face/support ownership,
so a door and its matching wall receive consistent illumination. Apply a conservative
non-emissive body/equipment response using the actor's received support/contact; do
not sample whichever flat tile happens to lie behind the sprite's head. Retain
source sprite shading. Flight uses its disclosed contact/path and height policy,
not an invented airborne light simulation.

Keep palette/material albedo separate from illumination. Decode source sRGB colour
to linear before the receiving calculation and premultiply once. The new policy
interprets treatment RGB as linear gain; this is an explicit visual improvement
over Pygame's sRGB-channel multiplication, not pixel-parity with that treatment.
Preserve the exact old sRGB-multiply reference in Studio and review both on the
same recorded state. Existing normals
can retain their authored material use. Emissive spell parts remain legible without making all
characters self-lit; icons/markers/HUD remain exempt.

The existing bounded proof supplies warm/cool-light and Fireball-flash evidence.
Production acceptance exercises those functions with disclosed occurrences;
cosmetic direct light comes only from a disclosed visual
emitter and its existing authored position/intensity curve at displayed time.
Never reconstruct hidden emitters from categorical brightness. Use the shared
receiver position/normal and finite wall/aperture geometry for light-ray visibility.
No new GPU normal plane is required when geometry supplies the normal.

The native treatment is the base. Sum admitted, attenuated, geometry-visible
Lambert terms as J and calculate
`I_direct = diffuseReflectanceLinear * J`, then
`I = I_base + min(I_direct, max(0, I_ceiling - I_base))` component-wise in linear
light. Ordinary albedo uses this illumination while retaining source alpha/baked
shading. Combined radiance with `preserveEmission=true` retains C0 and adds only
`coverage * min(I_direct, max(0, I_ceiling-I_base))`, matching §4.1's received-light
approximation with production headroom. Disabled receiving leaves its authored
colour/emission unchanged. The ceiling belongs to this world visual policy, not
a new gameplay level.
This deliberate art approximation prevents unbounded double-brightening of the
already-lit native field; existing baked sprite shading remains conservative.
No enhancement crosses unknown/memory or effective magical-darkness boundaries.
It never changes disclosure, targeting, native illumination or rule outcomes.
Synthetic proof lights are labeled scene inputs; actual replay uses only admitted
emitters, with the categorical baseline preserved where no emitter is disclosed.

Optional cosmetic flicker may only modulate an already-admitted emissive source's
authored effect. It cannot change native illumination or reveal a source. The
bounded shared-geometry shadow test above is implemented/accepted at N1/N3; a client light
propagation engine, ambient-occlusion reconstruction or per-frame global convolution
is not required. This is one material/light path, not a second world simulation.

### 5.3 Historical changes

Light and visibility use the **displayed** state at the same authored commit as the
door/wall/cloud that caused the change. Latest packet light cannot leak through an
old closed-door frame. Continuous visual transitions may interpolate two admitted
appearance samples, but cannot show future occupants. Switching party inspection
does not replace the authorized party audience with an individual private view.

## 6. Selection, highlighting and transparency

Maintain a small CPU spatial index of the last successfully presented scene. Inverse
project the pointer to candidate support planes and source coordinates; evaluate
authored physical masks, aperture holes and depth cuts at that point. Store compact
source masks, not a new full viewport mask every frame. No synchronous `readPixels`
on every mouse move. Decorative VFX/auras are not physical blockers by default.

Outline only admitted/selectable visible coverage. Apply hover and Alt outlines to
the same silhouettes used by picking, after cutaway/occlusion decisions; faded
wall tops do not trap pointer hits intended for the admitted floor behind them.
Door apertures and wall bases remain selectable. Rotate through four cameras and
verify the same interactable set, not identical screen pixels.

Wall cutaway is automatic for walls covering received visible tiles, as requested.
It is distinct from dim remembered geometry. It changes render alpha and picking,
not native sight, projectile collision, propagation or pathfinding. End attack
selection highlighting when the command is committed; do not keep it flashing
through the complete attack animation. Keep an optional neutral selection state
separate from a spending/targeting gesture.

## 7. Production acceptance scenes at N1/N3/N5

These cases run in the one production renderer and Studio after the human resumes
work. They are implementation acceptance of the settled design, not a new
standalone proof phase or a reason to leave source fields undecided. N1 establishes
the shared rendering path, N3 covers every authored family, and N5 combines the
real-event cases with the master's full-scene frame/resource targets. The current
standalone receipt proves only its stated subset; none of the following is claimed
complete by this planning update.

| Scene | What must be visible/correct |
|---|---|
| Two elevations, stairs, doorway and tall prop | Correct support/picking, grid below geometry, wall face and door light agreement |
| Actor crossing near/far faces, prone and death | Stable ground contact, no rise in depth due to sprite crop, ordinary corpse ordering |
| Actor inside Fireball/Sunburst/Sleep/ring | Continuous admitted art; physical cuts only; correct front/back alpha and light |
| Two crossing translucent effects | Authored sibling/mix rules and the proven finite order policy; no unexplained zIndex fix |
| Blood inside a cloud, then landing and settled stains | Batched flight, shared landing clocks, retained native footprint, old/new response isolation and bounded working set |
| Ground/wall deposits, raised floor, cleanup and seek | Correct receiver, no double rendering, no future stain after rewind or full-history repaint |
| Projectile at oblique angle and different heights | Correct bank, residual policy, release socket and trajectory tangent; all four cameras |
| Palette + condition + owned coated weapon | One colour source; item state survives equip/drop/loot; body cache does not swallow item changes |
| Torch/opening/split party and historical seek | Smooth allowed light transitions, no hidden-room leak; latest light does not overwrite history |
| Black background and checkerboard alpha test | No premultiplied fringes, RGB under transparent pixels does not create additive boxes |
| Pan/zoom/rotation during the above | GPU transforms, unchanged texture ownership; no per-frame decode or CPU pixel processing |

Expose chosen geometry/depth, supports, ownership, light validity and material masks as
Studio diagnostic views. They must be optional views of the production inputs, not
alternative debug geometry that bypasses the production renderer.
Original XYZ may be an offline comparison view without being a production dependency.
