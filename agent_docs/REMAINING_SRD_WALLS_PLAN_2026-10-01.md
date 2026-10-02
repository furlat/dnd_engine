# Remaining SRD walls

Status: October 2, 2026 shape revision approved by separate anti-slop and
anti-OOP/ECS reviewers, after acceptance of Fire's formation timing. This
document records the approved backend lane. Implementation and validation are
tracked in REMAINING_WALLS_IMPLEMENTATION_2026-10-02.md; no new artwork jobs are authorized here. The decisions below must be pinned before the
affected forms are admitted. General multi-Z remains deferred. Shape references
use the 2014/SRD 5.1 rules, not the revised edition.

## Foundation at planning time

- `dnd/spells/walls.py` implements Fire only. Other walls in the SRD coverage
  ledger are inventory entries, not playable spell registrations.
- Ordered point selection already reaches native discovery/execution, Pygame
  and AI. Preserve the one-point shorthand starting one cell from the caster;
  explicit points can intentionally include the caster's cell.
- `WallPresentationGeometry` retains a segment or ring, physical dimensions,
  support elevation and optional Fire side. It cannot yet represent a panel
  collection, polyline, dome or complete sphere.
- Globe already has a spherical presentation geometry, paired surface media and
  XYZ composition. Its native owner protects a filled area against selected
  outside spells; it does not obstruct physical movement. Reuse the spherical
  drawing path with the appropriate material, retaining a distinct hollow-shell
  collision contract for Ice/Force. No second spherical compositor is needed.
- Spatial conditions own appearance/entry/turn events, concentration cleanup,
  light/terrain contributions and subject-specific observations. Destructible
  environment items already have integrity/destruction profiles and native
  transitions. Unified attacks can target world items; no object-attack fork.
- Structural edges already separate movement, propagation and optical channels.
  Physical contact distinguishes hands, light weapons, weapons, natural/body
  contact and projectiles. It does not describe ammunition mass or gaseous bodies.
- Existing Disintegrate validates and resolves entity targets only. Existing
  Petrified is usable, but Prismatic's counters and transport are separate work.

These are code observations, not evidence that every required owner is complete.
Implementation begins by checking each existing public boundary against the
acceptance cases below, rather than rewriting all wall/attack infrastructure.

## Scope and delivery order

1. Thorns: maintained hazard, opacity and movement expenditure.
2. Wind: shaped field and selective passage/attack outcomes.
3. Ice: destructible flat panels, shared-HP dome and residual frigid air.
4. Stone: supported sections, enclosure reaction and permanent completion.
5. Force: transparent physical barrier and Disintegrate interaction.
6. Prismatic: separately gated until layer interactions and planar disposition
   can be implemented faithfully. Do not expose a misleading partial spell.

Each step ships independently with backend tests. Missing media does not block
mechanical tests, and missing media is reported as presentation coverage.
The accepted Fire formation fix is complete. Its partial-ring ownership and
directional admission follow-ups remain separate; this plan does not reopen
clouds, windows or that accepted formation timing.

## Placement and shared data

Keep geometry separate from rules and artwork. Extend the existing passive wall
data only for forms the next spell needs: ordered polyline for Wind, explicit
panels for Force/Ice/Stone, and a hemispherical shell for Ice/Force. Destructible
flat panels retain stable identities, dimensions and world positions so one
breach cannot erase the rest of the flat construction. The human-selected Ice
dome has one stable item identity and shared HP pool for its entire shell. A ring
is a vertical circular wall with an open roof; a dome has a curved roof; a sphere
also has a lower hemisphere. None is a filled hazard or protection volume.

The proposed release includes vertical walls on one existing support level and
ground-anchored Ice/Force domes. The human explicitly identified the existing
Globe rendering as reusable and requested the correct material. Complete spheres,
free-floating/tilted panels, horizontal bridges/ramps and stacked placements stay
declared unsupported until their native vertical placement and crossing queries
are implemented. These are implementation limits, not SRD prohibitions. Adding
domes does not authorize a general multi-Z simulation or a change to Globe rules.

### Shape rules and native authoring

The source distinction must survive content authoring, discovery, execution and
replay. Do not infer a spell's legal forms from the renderer's supported forms.

| Spell | 2014/SRD shape wording and budget | Forms in this lane |
| --- | --- | --- |
| Fire | Wall up to 60 feet long, 20 high, 1 thick, or ring up to 20 feet diameter. The text does not explicitly say straight or grant Wind's arbitrary-path clause. | Preserve the accepted single straight segment and fixed 10-foot nominal-radius ring, with their existing heat-side choices. No new Fire shape rule. |
| Thorns | Wall up to 60 feet long, 10 high, 5 thick, or circle up to 20 feet diameter, 20 high, 5 thick. No explicit arbitrary-path clause. | Straight segment and circular wall. Straight-only noncircular authoring is a bounded implementation policy, not quoted SRD wording. No invented L-path or dome. |
| Wind | Any shape forming one continuous path along the ground; at most 50 feet of path, 15 high, 1 thick. | Ordered connected segments can bend, zigzag or close into a loop. Total length includes the closing segment. No separated pieces or roof. |
| Ice | A flat surface of ten contiguous 10-foot-square panels, or a hemispherical dome/sphere with radius up to 10 feet; 1 foot thick. | Coplanar vertical panels and a ground-anchored dome. Full sphere is a recorded rule option outside this bounded release. |
| Stone | Ten contiguous 10-by-10-foot panels, 6 inches thick, alternatively 10-by-20-foot panels, 3 inches thick; any shape, supported by existing stone. | Connected vertical panel runs may turn corners or enclose an area. Both panel sizes need explicit native dimensions and their actual support requirements. |
| Force | A flat surface of ten contiguous 10-by-10-foot panels, or a hemispherical dome/sphere with radius up to 10 feet; quarter-inch thick. Arbitrary orientation and free-floating placement are also allowed by the rules. | Coplanar vertical panels and a ground-anchored dome. Other orientations, floating placements and full spheres remain explicit coverage gaps. |
| Prismatic | A vertical plane up to 90 feet long and 30 high, 1 inch thick, or a sphere up to 30 feet diameter. | No arbitrary panel chain or dome inferred. Both actual forms stay gated with the spell's layer rules. |

Sources: [Fire](https://www.dndbeyond.com/spells/2291-wall-of-fire),
[Thorns](https://www.dndbeyond.com/spells/2295-wall-of-thorns),
[Wind](https://www.dndbeyond.com/spells/2302-wind-wall),
[Ice](https://www.dndbeyond.com/spells/2293-wall-of-ice),
[Stone](https://www.dndbeyond.com/spells/2294-wall-of-stone),
[Force](https://www.dndbeyond.com/spells/2292-wall-of-force),
[Prismatic](https://www.dndbeyond.com/spells/2215-prismatic-wall).

For Ice/Force, coplanarity is the literal reading of the singular flat surface,
not a separately quoted official clarification. Contiguous panels alone do not
grant Stone's unrestricted shape clause. Standing panels can vary their outline
within their common plane; the first vertical layout need not implement stacking.
Reject an L/U path for this form before costs. Stone may use those paths, subject
to panel and support limits. Each delivered form is a mutually exclusive cast
variant; a dome plus attached panels is not another allowed form.

Use the existing ordered-position contract for paths. A single target retains
the first-cell-from-caster shorthand; explicit endpoints may include the caster.
Wind and Stone accept additional admitted vertices; Fire/Thorns and the initial
Ice/Force straight layout accept only their required endpoints. Ring/dome casts
select their center independently of the caster. Shape and dimensions/radius
are typed native variant data; no frontend-only geometry or implicit resizing.

Wind length is the sum of native Euclidean segment lengths in feet, already used
by ordered selection, not the end-to-end chord or number of painted tiles. A
closing point equal to the first point is valid when the final segment has
positive length; duplicate consecutive vertices are invalid. Corner joins and
self-overlap do not apply formation damage twice or multiply footprint contributions.
Configure the existing segment-count bound to cover all representable paths
within 50 feet; its Fire default of one must not constrain Wind accidentally.
Validate support and crossing along every segment, not just each selected vertex.

Panel budgets count real rules-sized panels, not raster cells or clicked points.
Retain each panel's full rectangle, thickness, plane and stable rules-section
identity. Subdivide a selected run only into admitted native panels; reject
unrepresentable lengths instead of silently truncating or granting extra panels.
Stone turns spend the same shared panel budget and form one connected assembly.
Do not shorten a 10-by-20-foot panel visually while retaining its full HP/area.

Retain the existing nominal centerline-radius convention for circular walls;
record physical thickness separately. A dome likewise needs an explicit nominal
radius, thickness and support-relative center/vertical extent. This convention
is the game's geometric discretization, not an SRD statement about inner versus
outer measurement. Native footprint, crossing queries and artwork transforms
must use the same convention. Ice/Force's radius limit is 10 feet; Fire's accepted
fixed ring size must not silently become a new restriction on those spells.

### Dome ownership and renderer reuse

Sight rules are independent of physical passage. The source links in the shape
matrix establish the following; material inferences are labeled explicitly.

| Wall/material | Sight behavior and basis |
| --- | --- |
| Fire | The spell explicitly makes the wall opaque. |
| Thorns | The spell explicitly blocks line of sight. |
| Wind | No sight-obscuring rule. Keep the wind transparent to sight; its gas/ordinary-projectile interactions are separate mechanics. |
| Ice | Human decision, October 2: see-through ice. Sight and light pass through intact sections; movement and physical delivery remain blocked. The SRD does not prescribe opacity; this is the accepted material policy. |
| Stone | Solid stone blocks sight by its ordinary material properties; the spell does not add a separate opacity clause. |
| Force | Explicitly invisible; physical obstruction does not imply optical obstruction or observer knowledge of its presence. |
| Prismatic | Explicitly opaque; emitted light and its harmful nearby-sight trigger are separate rules. |
| Residual frigid air | No sight-obscuring rule. The default preserves sight through the breached space; cold damage does not imply fog/heavy obscuration. |

Author sight, light and physical access through their existing independent native
channels. Do not derive them from the asset alpha, damage type or the generic word
wall. Opaque Fire/Prismatic media must not invent emission distances beyond
accepted native light facts. Rendering a translucent cue does not itself grant
physical attack passage through intact Ice/Force.

Represent a dome as a hollow hemisphere whose equator is on the admitted support
plane. The interior remains available to existing creatures; crossing the shell
is blocked. Queries with both endpoints inside must not fail merely because the
positions belong to the dome's projected disk. Outside-to-inside and reverse
crossings use the existing requester-relative movement/contact/projectile and
propagation routes. Force stays optically transparent/invisible without granting
observer knowledge. The human selected see-through Ice for every admitted form.
Its existing native sight/light channels transmit while intact sections keep
their physical obstruction. No invented light-level penalty is part of this
choice. Ice's visible material remains translucent, with identifiable edges and
thickness; it is not made visually absent like Force. Neither optical policy
follows automatically from the dome shape.

Keep the curved roof and height in retained geometry even when the first native
queries only support ground-level actors. Reject unsupported elevated placement
and height-sensitive traversal explicitly; never substitute a roofless ring or
claim full sphere coverage. Force follows its own physical barrier, dispel and
Disintegrate rules; Globe retains its current selective spell protection.

For Ice domes, the human explicitly chooses one shared HP pool and complete
destruction at zero HP. This is a deliberate game simplification of the SRD's
per-10-foot-section destruction; flat Ice panels retain their original section
rules. Own the dome through one ordinary attackable world-item identity under
the spell condition. Every supported hit anywhere on its shell damages that
same health/integrity component, including native fire vulnerability and AC12.
The human selected **120 shared HP**, AC12 and fire vulnerability. This is
explicit native content data, independent of rendered pixels or curved partitions.

At zero HP, one cancelable ordinary destruction transition removes the complete
solid hemisphere and creates one residual frigid-air condition over the former
hollow shell. Do not fill its interior or project the roof hazard onto the floor.
Supported shell crossings remain passable and trigger the residual's existing
once-per-turn cold rule; standing/moving solely inside is not a crossing. The
whole dome retires visually at its authored destruction marker, once, even if
several damage packets arrive in the same lineage. Ordinary expiry removes it
without creating a destruction hazard. Keep native events authoritative and the
shared retained presentation timing faithful to that single transition.

No curved damage-section partition, local hole state or per-section dome item
IDs are required. The current world-item placement API still needs its bounded
shell-registration check: cardinal boundary registration cannot be mistaken for
a complete hemisphere, and the interior must stay usable. Ground-only targeting
must not invent elevated roof hit locations from the artwork; unsupported
height-sensitive traversal/targeting stays unavailable explicitly.

Reuse the existing Globe spherical sampling/XYZ and rear/front composition with
per-spell material registrations. Add hemisphere clipping and whole-dome owner
identity as passive surface data consumed by that shared drawing path. A material
change alone does not provide Ice break/residual artwork. Preserve exact XYZ
dimensions, radius transforms, pivots and heights; source coordinate channels
must not be dropped. Cold replay draws only disclosed live surface samples;
seeing a center tile or one section cannot disclose the complete dome. No global
cloud-mask, wall-ordering or observer-visibility rewrite belongs to this step.

Validate native length/panel budgets, continuity, range, support and overlap.
Do not copy Fire's placement validator: Force need not rest on solid ground in
the SRD, Stone requires stone support, and several walls displace creatures.
Keep subjective discovery and authoritative execution consistent without
revealing unseen blockers. Ordinary invalid input rejects before costs;
Prismatic's documented creature-overlap failure happens after action/slot spend.

Stone and flat Ice use only the four native grid directions (±X/±Z) in this
lane. Placement directions are separate from camera viewpoints. Their section
dimensions, joins, intact/local-break and exposed-neighbour faces must be
reusable for ordinary environmental walls. Stone retains supported turns and
panel budgets; flat Ice stays coplanar. Its dome keeps the separate whole-shell
shatter/frigid-air contract. Wind remains the artist's active lane. The Thorns
handoff is unsent and is not authorized for installation by this update.

Ground height and wall height remain explicit facts. Current adjacent-edge
identities are cardinal: diagonal panels need a conservative native coverage
decision and crossing tests, not nearest sprite-heading collision. Audit current
height queries: nonmovement edge queries currently return blocked without
testing vertical intersection. Do not advertise over-wall shots until the native
trajectory/height query supports them. No invented multi-Z support.

## Rule matrix and implementation boundaries

### Thorns

Level 6, range 120 feet, concentration ten minutes. Wall up to 60×10×5
feet, or 20-foot diameter ring up to 20 feet high and 5 feet thick. Opaque but
permeable. Formation: DEX save, 7d8 piercing, half on success. First entry on a
turn and turn end inside: DEX save, 7d8 slashing, half. Both increase by 1d8 per
slot above sixth. Movement through it spends four feet per foot travelled.
[2014 rules](https://www.dndbeyond.com/spells/2295-wall-of-thorns).

Compose an AreaCondition with distinct formation/contact damage facts. Extend
the shared native movement-cost query only enough to represent a named owned
fourfold expenditure; pathfinding, discovery, movement and remaining budget must
agree. Establish stacking with ordinary difficult terrain and immunity before
coding: do not implement this as two overlapping difficult-terrain tags. Test
entry plus turn end separately, walking in/out, forced movement and retirement.
No invented HP, fire destruction or ignition rule for living magical thorns.

### Wind

Level 3, range 120 feet, concentration one minute. Arbitrarily shaped continuous
ground path up to 50×15×1 feet, with 50 feet measured along that path. Formation
only: STR save, 3d8 bludgeoning, half. Ordinary arrows,
bolts and similar missiles crossing it automatically miss; giant/siege-sized
missiles pass. Small-or-smaller flying creatures/objects and gaseous creatures cannot cross; fog,
smoke and gases are kept back. Ordinary ground creatures can pass without a
recurring damage trigger. [2014 rules](https://www.dndbeyond.com/spells/2302-wind-wall).

Add native delivery facts only for distinctions the rules need: ordinary physical
missile versus large missile; do not derive these from a projectile VFX string,
or grant magical arrows a blanket exemption. Query the existing crossing route
with actor size/movement/form context. Apply deflection as a resolved attack miss
after legitimate costs, retaining its reason and contact location for replay.
Do not prefilter it out as an illegal attack or refund extra/bonus/reaction attacks.

Use typed gas interactions and actual footprint-change events. Verify existing
cloud wind-dispersal behavior per spell before choosing local exclusion versus
whole-field dispersal. Do not globally recompute cast clouds from current doors,
or add Wind to the ordinary vision-blocker channel. Loose material lifting is
an explicit content/capability gap if no loose-object motion owner exists.

### Ice

Level 6, range 120 feet, concentration ten minutes. One flat surface of ten
contiguous 10-foot-square panels or dome/sphere of radius up to 10 feet;
thickness one foot. Formation displaces intersected creatures and deals 10d6
cold (DEX half). Each 10-foot
section has AC12, HP30 and fire vulnerability. Destroyed sections leave frigid
air: first movement through per turn gives CON save, 5d6 cold, half. Upcasting
adds 2d6 formation and 1d6 residual damage per level.
[2014 rules](https://www.dndbeyond.com/spells/2293-wall-of-ice).

For flat walls, use ordinary attackable world items per rules section, sharing
HP across every cell of that section. For the dome, use the human's one-item,
shared-HP/full-shatter simplification above. A retained spatial owner records the
actual item IDs, geometry and spell origin. On completed destruction, remove
the damaged flat section or entire dome and create residual air at exactly that
removed surface. Ordinary expiry/concentration loss
retires solids and air without generating a destruction hazard. Preserve
destruction-to-footprint causality and distinguish break versus spell removal.
Do not import the 2024 edition's additional immunity text.

The human explicitly requires residual frigid air. It is mandatory registered
native spatial-condition content for flat-section breaks and complete dome shatters,
using the existing area-trigger, save/damage and concentration-owned cleanup
machinery. Retain its exact physical section, spell origin, save DC and upcast
damage. Creation, damage and removal produce ordinary retained events for
subjective presentation; no cosmetic-only substitute or ground tile underneath
a roof breach satisfies this requirement. Artwork delivery remains a separate
presentation-coverage requirement.

### Stone

Level 5, range 120 feet, concentration ten minutes. Ten contiguous 10×10-foot,
six-inch panels, alternatively 10×20-foot three-inch panels. Any shape is allowed;
existing stone must support it. Intersected creatures are displaced to the chosen
side; creatures enclosed can DEX save and spend a reaction to escape up to their
speed. Panels have AC15 and HP30 per inch. Full-duration concentration makes surviving stone
permanent; early termination removes it. Long unsupported spans have additional
support requirements. [2014 rules](https://www.dndbeyond.com/spells/2294-wall-of-stone).

Reuse Ice's concrete section ownership/lifecycle after it proves useful; keep
Stone's support, enclosure and permanence rules in its composer. Plan displacement
and enclosure from proposed final geometry before committing placement. Resolve
escape through native reaction/movement ownership, preserving opportunity-attack
semantics; do not teleport enclosed creatures or consume a missing reaction.
Permanent completion detaches surviving sections from spell ownership before
concentration teardown. No invented automatic connected-panel collapse: the SRD
leaves that to the GM. Bridges/ramps remain outside the first proposed release.

### Force

Level 5, range 120 feet, concentration ten minutes. Invisible, quarter-inch
barrier; one flat surface of ten contiguous 10×10-foot panels or a
radius-up-to-10-foot dome/sphere.
Intersected creatures are pushed to the chosen side. Physical passage is blocked,
all damage is ineffective, Dispel Magic cannot remove it, and Disintegrate
destroys it instantly. Ethereal passage is also blocked.
[2014 rules](https://www.dndbeyond.com/spells/2292-wall-of-force).

Represent physical obstruction independently of optical visibility; seeing the
target is insufficient for an attack or spell requiring a clear physical path.
Reuse shared contact/propagation queries for ordinary attacks, opportunities,
spell targeting and area propagation. Teleport destination legality is distinct
from traversing a physical path; do not block every teleport automatically.
Extend Disintegrate's native target contract to force constructions and ordinary
objects as required by its rules, preserving creature resolution. No arbitrary
HP pool. Disintegrate retires the complete Force wall, not one targeted panel;
Ice/Stone destruction remains section-local. Ethereal travel is presently a declared capability gap, not new plane
simulation in this lane. Invisible artwork must not grant observer knowledge.

### Prismatic

Level 9, range 60 feet, ten minutes without concentration. Opaque 90×30-foot wall
or 30-foot-diameter sphere; occupied-creature placement wastes action and slot.
Caster/designated creatures are exempt. It emits light and can blind nearby
seeing creatures. Crossing/reaching resolves seven ordered layers separately.
Five damage layers use DEX saves and fire/acid/lightning/poison/cold. Their
removal mechanisms differ; Indigo restrains and tracks saves toward petrification;
Violet blinds then tests WIS at the caster's next turn for planar transport.
Antimagic is ineffective; Dispel Magic affects Violet only.
[2014 rules](https://www.dndbeyond.com/spells/2215-prismatic-wall).

Keep a passive ordered surviving-layer state owned by one spell condition.
Layer removal uses typed native interaction facts: cold, strong wind, force,
surface-opening magic, fire, magical bright light and dispel. Red/orange distinguish
nonmagical/magical ranged attacks; Indigo independently blocks spells. Reaching
through must also enter this resolver: cell entry alone is inadequate. Exemptions
remain stable entity IDs, not a live faction lookup. Indigo save counters belong
to each affected creature; existing Petrified provides the final condition.

Gate implementation on explicit semantics for planar disposition, eligible
interaction sources, threshold accounting, and movement interruption during a
multi-layer crossing. Existing temporary Banishment cannot substitute for Violet.
Do not request seven-layer production artwork before this retained state contract
is accepted. A separate layer-rule table will pin every save, threshold, clock
and effect before coding; the spell is not reducible to seven recolored damage cues.

## Native lifecycle and presentation handoff

Create solid sections through ordinary placement APIs. Their spell owner stores
explicit ownership links; never repurpose inventory/support links or manually
delete registry rows. Retire through existing item/spatial lifecycle APIs. Ensure
each committed transition invalidates relevant movement, propagation, optics,
light and action discovery, and is represented by retained native events.

Concentration links one wall condition. That condition retains separate typed
section-item IDs; existing `linked_conditions` contains condition IDs and cannot
hold raw items. Preflight the complete proposed multi-position placement and
creature displacement before publishing any section. Current single-item grid
placement commits immediately; its support assembly is not a panel-chain
transaction and must not be borrowed for this purpose. Add bounded wall-cast
admission/cleanup at the composition boundary, not a general transaction framework.
If a later native placement is canceled, retire already-created cast sections
through their owners and leave no orphan contributions. Do not rewind consumed
reaction/action costs or already-published damage. Pin the externally observable
failure outcome before coding; canceled removals also cannot silently discard
ownership while a section remains live. Test failure after an earlier section
commit and retirement after one section refuses removal.

Cold replay consumes disclosed geometry/section/layer state, not live entities.
Creation, destruction, residual-air replacement, permanence and retirement have
different meanings. Reuse existing item transition timing so new gaps/debris do
not appear on animation frame zero. Simultaneous formation damage shares one
formation cue; individual creatures' later turn triggers remain separate.

Artist requirements after backend acceptance: supported forms and four camera
rows unless measured covariance proves reusable. Stone and flat Ice admit only
four native grid headings; other forms retain their approved directional contract.
Exports must retain exact dimensions,
support origin, pivots, frame clocks and crop offsets. Stone and flat Ice require
section break/removal/residual banks. Ice domes need whole-shell shatter/removal
and hollow residual-air banks. Domes
reuse the spherical rendering contract with their actual materials; they do not
require an independent presentation implementation. Prismatic requires
individually removable layers.
Request genuine matching XYZ where clipping needs it. Keep 32 FPS selected packed
production pages and short maintained loops, preserve full sources privately.
Do not rotate upright complete wall images or infer collision from sprite alpha.

### Visual delivery for the wall batch

The visual work is part of this plan for every admitted form. Existing Fire and
Globe remain regression references. Reuse the current spatial compositor,
ordinary item transitions and retained contact cues; do not add one spell-named
rendering branch per material or derive rules from the images. All registrations
are passive data suitable for the existing cold replay and a future client.

| Content | Required visual lifecycle and native facts |
| --- | --- |
| Thorns | Straight/circular shell formation, short maintained loop and retirement; local formation-around, enter/push-through, idle occupancy, event-driven damage and exit/recovery cues. Occupancy is not Restrained and does not manufacture damage. |
| Wind | Continuous shaped path with joined corners and loops, translucent formation/hold/removal; formation contact and resolved projectile deflection at the recorded crossing point. Art must not suggest opaque fog, a solid barrier to ordinary walking, or recurring entry damage. |
| Ice | Translucent panel/dome formation and hold; flat panels crack/break locally, while the shared-HP dome shatters completely. Mandatory frigid air matches the removed section or complete shell. Ordinary expiry retires ice and air without a break hazard. Formation/cold cues follow native packets. |
| Stone | Supported panel formation, intact hold, local destruction and gaps, ordinary spell retirement, and surviving permanent sections. Permanence is a lifecycle change, not another formation animation or regeneration of broken panels. |
| Force | Known/disclosed construction cues and contact/Disintegrate/retirement responses using the shared segment/dome geometry. The invisible barrier cannot become opaque or disclose unseen geometry simply because a visual cue exists. |
| Prismatic | Deferred with its mechanics: opaque admitted plane/sphere, emitted light and individually surviving/removed layers. No seven-color placeholder is presented as completed production coverage. |

See-through Ice applies to all visual phases and both panels and domes. People,
objects and terrain behind intact ice remain discernible through its translucent
material; use shared depth/XYZ and alpha composition rather than an opaque
silhouette cutout. The near and far dome surfaces retain correct ordering and
surface thickness without double-darkening the interior into an opaque shell.
Flat-wall section destruction removes only that section. A zero-HP dome has one
complete-shell shatter; it never shows a local persistent hole or surviving ice.
Frigid air may have a thin visible cold cue, but does not create a new optical
blocker. Do not remove XYZ channels, turn hidden samples into black masks, or
borrow cloud visibility rules to implement transparent ice.

Each source handoff must identify its actual media phases and certified native
dimensions, panel or whole-dome owner IDs, pivots/crops, loop interval, formation/break contact
markers, camera/headings, original coordinate/validity channels and shadow layers.
Use source-provided shadows with their correct ground/support registration;
translucent ice must not gain a fabricated opaque floor shadow. Preserve original
layers when available. Select only needed frames at up to 32 FPS and bake packed
production pages at the agreed draw scale, retaining all originals privately
under the existing asset contract. Short loops must remain continuous at wrap.

Geometry and shadow transforms must match native length, thickness, height,
radius and actual construction ownership. Ring centerline versus outer-diameter measurements
must be reconciled before accepting exports; nominal diameter plus thickness
cannot silently be interpreted as a different shell by the artist and backend.
Every accepted directional bank must compose into a full wall at the requested
length, including views where its path projects vertically on screen. A whole
spherical drawing path is reused for domes with the correct Ice/Force material;
Ice destruction/residual media need local-panel or whole-dome delivery as authored.

Presentation clocks follow retained native causes. Formation and local contact
must visibly reach the affected creature before HP/reaction/damage accents;
simultaneous formation recipients remain simultaneous. Solid-to-air/gap change
uses the actual break marker, not animation frame zero. Crossing, later damage,
permanence and ordinary spell expiry keep their own causes. No invented turns or
new damage packets may be inserted to manufacture a clip.

Visual acceptance uses actual discovered native casts and saved-event replay,
both observers, all four camera corners and real legible floor tiles. Include
maximum-length walls, Wind corners/loops, perpendicular views, Ice seen from
both sides and inside/outside its dome, intact flat panels beside a breach,
whole-dome shattering, frigid air crossing/removal and Stone permanence. A switchable native-coverage
overlay can explain occupancy; it does not replace actual in-game recordings.
Compare accepted Fire formation and Globe overlap/movement recordings to catch
shared-renderer regressions. Report missing media explicitly until delivered.

## Acceptance and review

For each wall, test native discovered action -> allocation -> cost -> committed
state/events -> cold subjective replay. Include diagonal boundary crossings,
elevation rejection, privacy, valid/invalid placement, interrupted concentration,
owner death, load/serialization and cleanup without orphan sections/modifiers.

Shape acceptance must cover:

- Wind straight, L/U path and closed loop: the full sum respects 50 feet; an
  over-budget closing edge and an obstructed segment reject before costs;
  duplicate consecutive vertices reject, repeating the first vertex to close
  the path is valid, and overlapping joins affect each creature once.
- Ice/Force flat panels: valid collinear placement, count/dimension limits, no
  L-shaped layout, no mixed panel/dome cast, and explicit unsupported orientation.
- Stone: supported straight and turning layouts, both panel sizes, enclosure
  escape, panel-count exhaustion, and rejection of unsupported stone/overlap.
- Ice/Force dome: inside movement remains legal; actual shell crossings block
  ordinary movement, contact attacks, opportunities and physical spell delivery;
  optical behavior stays spell-specific. Existing Globe remains passable.
- See-through Ice: native sight/light and received observations reach through
  an intact panel/dome while movement, attacks and physical spell delivery still
  encounter its shell. Saved-event views from both sides show behind-ice creatures
  through the actual material; no opaque cutout, hidden-surface disclosure or
  extra light attenuation is introduced. Flat breaches preserve other panels.
- Shared-HP Ice dome: hits from different sides/cameras affect the same native
  pool. Damage below zero does not replay destruction; exactly one accepted
  zero-HP transition clears the whole physical shell and creates one hollow
  residual-air owner. No surviving patches/HP pools or curved partition exist.
  All admitted paths cross the same residual shell; its roof is not floor damage.
  Test ordinary attacks/AoE, fire vulnerability, cancellation, serialization,
  pre-zero intact hold, synchronized whole-shatter media and parent cleanup.
- Required frigid-air condition: actual flat-section or whole-dome destruction creates the native
  hazard and its retained creation fact; the first crossing on a turn applies
  5d6 cold with CON half, repeat crossing that turn respects the same trigger
  fence, and the next turn can trigger again. Test the 1d6-per-slot residual
  upcast, passable cleared shell, unchanged unrelated flat sections, cold replay and
  parent-expiry/concentration cleanup. Frigid air adds no invented recurring
  turn-end damage, slowing, sight blocker or floor hazard beneath a roof breach.
- Geometry serialization and old Fire/Globe recordings: no live registry queries
  in replay, no complete-shell disclosure from a partial observation, unchanged
  Fire ring and heat-side behavior, and roof/radius/thickness match native data.

Attack filtering must preserve normal/extra, Haste, Slow, Action Surge, off-hand,
Frenzy and opportunity attack availability/costs. Solid sections must accept the
same ordinary item-targeting route, and AoE damage must follow its existing item
admission rules. Breaching a section must alter subsequent physical queries;
whether the same cast propagates beyond a newly breached blocker is a separate
existing propagation policy, not an accidental side effect of event order.

Focused spell tests precede the complete engine suite and affected active client
tests. Document failures with observable behavior; do not weaken tests to green.
Visual acceptance follows actual accepted artwork using saved native events,
real legible floor tiles, all camera corners and no fabricated mechanics.

Independent anti-slop and anti-OOP/ECS reviewers must validate this plan before
implementation, then inspect the implemented ownership, DAG imports, shared
queries and replay contract. No new wall behavior superclass hierarchy, parallel
attack resolver, universal elemental framework or UI-only collision rule.

## Decisions to settle at the implementation boundary

- Keep all unimplemented SRD forms explicit in coverage; the requested dual
  shape-plan review is complete, not approval to invent unreviewed rule choices.
- Ice's see-through material and single shared dome HP pool/full-shatter policy
  are accepted, with the human-selected 120 HP total. Verify its one-item hollow
  shell representation before admission; no curved damage partition is needed.
- Define Thorns plus other movement-cost stacking using current native semantics.
- Pin stone-support authoring and safe creature displacement/enclosure failure.
- Pin Wind gas interaction and missing projectile/form facts at their native owners.
- Hold Prismatic until plane disposition and all layer interaction sources are
  supported; missing spells must not be silently invented to make it look complete.

## Review record

October 1: independent anti-slop review checked the linked legacy rules and found
no rule correction blocker. Its Wind flying-object and complete Force destruction
clarifications are incorporated. Independent ECS review found no hierarchy/DAG
issue; its multi-position admission/cleanup and typed section-ownership findings
are incorporated above. The ECS reviewer verified those amendments and approved
the bounded plan with no remaining planning blocker. Proposed forms and listed
gameplay decisions still require acceptance before implementation.

October 2: the human requested a careful shape update and two independent
reviews. The shape matrix, source/interpretation distinction, Wind ordered-path
budget, planar versus shaped panels, ground-anchored domes, spherical renderer
reuse and shape-specific acceptance cases are added above.

Independent anti-slop/rules review verified the primary legacy spell wording and
caught a closed-loop test contradiction. The acceptance case now rejects only
duplicate consecutive vertices; repeating the first endpoint to close the path
is valid. Ice opacity is explicitly a material/content policy rather than quoted
SRD behavior. The reviewer verified these amendments and gave final approval
with no remaining blocker to this revision.

Independent anti-OOP/ECS review approved the passive geometry, shared spherical
XYZ rendering, hollow barrier ownership and retained section/disclosure contract.
Its boundaries are recorded: measure Ice's curved rules sections and pin their
ordinary-item representation before admission; roof breaches only affect paths
that intersect that actual removed surface. The reviewer verified the amendments
and gave final approval with no remaining ECS planning blocker.

This is approval of the bounded plan, not evidence of implemented domes. The
human's later Ice choices below supersede the earlier unresolved optical policy
and proposed curved damage partition. Other listed gameplay decisions remain open.
No production code, artwork or accepted Fire/cloud/window behavior changed in
this revision.

The subsequent human clarification makes frigid-air content an explicit Ice
acceptance requirement. The sight table records exact spell clauses versus
ordinary material inferences. These clarify the reviewed residual-hazard and independent-optics
contracts rather than introduce another wall rules system. Both reviewers
subsequently checked these exact additions and confirmed approval with no rules
or ECS planning blocker. The later dome simplification supersedes the partition requirement.

The human subsequently selected see-through Ice and requested the visual work
in the plan. The current sight table, dome contract, wall-batch visual lifecycle,
packed delivery and native/replay acceptance above now reflect that choice.
Both reviewers approved that material/visual amendment with no remaining rules
or ECS planning blocker.

The human then simplified the Ice dome to one shared HP pool and complete
shattering at zero HP. The current ownership, destruction/frigid-air, visual and
acceptance contracts above remove the curved damage partition entirely while
retaining flat-panel SRD behavior. Both independent reviewers verified and
approved this exact ownership/visual simplification with no planning blocker.
The human subsequently selected 120 HP as the explicit dome content parameter.
The authorized Godot thread has received the see-through material and complete
dome-shatter contracts. The artist also confirmed the Thorns shell calibration
will match the native centerline convention before any final registration.
