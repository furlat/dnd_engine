# NDClient — finish environment assembly authoring

10 October 2026. **Implemented: assembly authoring connected; runtime consumption remains.**
The bounded asset-authoring pre-phase is complete; §8 records implementation and
verification. This document supplies the concrete steps for the
remaining connection identified in the [master plan §6.1](NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md).
It does not restart the migration or authorize client/renderer development.

## 1. Outcome and boundary

The ordinary NDClient authoring document must expose the supplied physical mounts,
camera registrations and compatible parts for **six indoor door families**, and
the fractional tread/landing profile for **the timber staircase library family**.
A consumer must obtain them from the existing typed environment owners without
opening supplier receipts or inspection-only `source-records`.

The artwork and geometry companions are already copied. The missing work is to
connect delivered measurements to current authoring, preserving the original
image registrations and animation clocks. Completion means the assembled data is
correct and usable; it does not mean the unimplemented renderer has been accepted.

Outside this phase: artwork copying/repacking, new exports, shader or renderer
implementation, Studio or gameplay UI, SDK changes, native map/stair changes,
other spell light emitters, and general metadata-loading work. Preserve current
character, item, UI and spell authoring. Do not change Pygame's authoring JSON.

## 2. Evidence and exact affected set

Repositories:

- Engine/schema owner: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.
- Client authoring: `/home/tommaso/Dev/NDClient`.

The defect is visible in `NDClient/tools/environment_geometry_library.py`:
`adopt_assembly_closures` installs the measured closures in source records only.
`EnvironmentDoorSource.authoring_record` is explicitly inspection-only, and normal
`tools/build_authoring.py::read_authoring` does not resolve it. Active companions
therefore still contain earlier mounts; successful media-path resolution did not
prove the assembly was connected.

Use the existing tracked records as the measurement source:

- Doors: `authoring/environment/source-records/doors/generated-<stem>.json`,
  especially `/record/physical_mount`, `parts`, `compatible_pieces` and the
  measured camera crosswalk.
- Timber: `authoring/environment/source-records/interiors/generated-timber-stair-flight.json`,
  especially `/record/physical_mount` and `contact_by_pose`.
- Existing active banks, library samples and companion fields retain each actual
  frame's sampling grid and calibration. They are required inputs, not disposable
  intermediate data.

| Door stem | Existing door ID suffix | Frames per destruction bank | Compatible header / partition pairs, primary first | Library samples |
| --- | --- | ---: | --- | ---: |
| `indoor-door-shabby` | `indoor_door_shabby` | 37 | G10 / G1 | 1,132 |
| `indoor-door-elegant` | `indoor_door_elegant` | 28 | D5 / D8; F5 / F8 | 916 |
| `indoor-door-shabby-plain` | `indoor_door_shabby_plain` | 26 | G10 / G1; D5 / D8; F5 / F8 | 868 |
| `indoor-door-shabby-battens` | `indoor_door_shabby_battens` | 33 | G10 / G1 | 1,036 |
| `indoor-door-shabby-patched` | `indoor_door_shabby_patched` | 30 | G10 / G1 | 964 |
| `indoor-door-elegant-three-panel` | `indoor_door_elegant_three_panel` | 24 | D5 / D8; F5 / F8 | 820 |

Door IDs are `environment.door.<suffix>`. Each selects five existing banks:
`door.<stem>.inward`, `.outward`, `.destruction.closed.clear`,
`.destruction.open.inward.clear`, `.destruction.open.outward.clear`.
The two opening banks have 24 frames each. This is **30 banks and 3,288 pose/frame
associations**, plus **5,736 door library samples**. These are observed coverage
counts, not budgets. Preserve the library's additional component, endpoint and
debris variants; do not reduce it to the selected banks.

Timber is `environment.library["generated-timber-stair-flight"]`: **124 samples**,
four source views, with 12 supplied tread supports. It currently has no native
prop/stair assignment. That remains true after this phase.

## 3. Passive data at existing owners

Extend the existing models in `game/environment_art.py`; reuse vector and geometry
types from `game/asset_types.py`. Keep the import DAG and data-only composition.
There is no new asset registry, assembly service or parallel rendering model.

| Owner | Addition / amendment | Meaning |
| --- | --- | --- |
| `EnvironmentBankSource` | `physical_source_contact_by_pose: dict[str, tuple[FiniteFloat, FiniteFloat]]`, default empty | Physical floor contact in the bank's untrimmed colour-cell coordinates. Distinct from its raw sprite pivot. |
| Same bank | `camera_quarter_by_pose: dict[str, int 0..3]`, default empty | Actual capture quarter for each stored row label. |
| `EnvironmentLibrarySampleSource` | Optional `physical_source_contact_px` | The same contact, in that sample's own colour-frame coordinates. |
| Same library sample | Populate existing `camera_quadrant` | Reuse its present field; do not add a second library camera mapping. |
| Existing `SurfaceCompanionSource.geometry` / `.normal` | Replace effective `sourceToLocal` / `normalToLocal` where affected | A single final mounted calibration, with existing per-frame ray/depth/sampling fields retained. |
| `EnvironmentDoorSource` | `assembly_variants`, default empty, keyed by existing opening-header family ID | Finite compatible part sets; a whole variant is selected together. |
| `EnvironmentLibraryFamilySource` | Optional typed `support_profile` | Timber's continuous local contacts, tread supports and separate landing requirement. |

For affected banks the two new maps are supplied together and cover exactly the
declared rows. Four-view camera registration is one-to-one. Other banks keep their
existing data and behavior. Do not rewrite `pivots_by_pose`, `ground_pivot`,
`ground_origins_by_pose`, row labels, scales, rectangles, clocks or marker frames.

### Door part sets

Each `assembly_variants[header_family_id]` contains `primary: bool` and a tuple of
passive members. A member has:

```text
role: supported_floor | opening_header | adjacent_partition
family_id: existing environment library family ID
offset_XHZ: (finite X cells, finite height steps, finite Z cells)
```

Offsets use **one canonical door-local physical orientation**, not a camera
orientation. Rotate this complete physical stencil once when placing an occurrence.
There must be exactly one primary variant. The key must match its opening-header
member. Each variant preserves the supplied floor, header and two adjacent
partition members; the table above defines the allowed header/partition pairs.
For example D5/D8 and F5/F8 are alternatives; D5/F8 is not a supported combination.

The full generated frame and leaf are already provided by the selected door bank.
Do not add that bank or its frame as another member. These recipes describe
compatible placements and offsets; they do not spawn native objects, infer hidden
map contents or blindly duplicate support/header objects already owned by a scene.

Use each member family's own capture registration when choosing its view. A door
source label must not select a same-named member image by assumption. Preserve
the distinction between camera-local and object-local geometry.

### Timber support profile

Use one passive `EnvironmentSupportProfileSource` on the existing library family:

```text
contacts_XHZ: typed lower_floor, entry_tread, exit_tread, upper_landing points
supports: ordered tuple of {
    center_XHZ: Vec3,
    polygon_XZ: tuple of finite (X,Z) pairs,
    contact_px_by_pose: source-view -> finite pixel pair
}
lane_width_cells: positive finite float
upper_landing_required: bool
```

The support's top height is `center_XHZ[1]`; do not serialize the same height and
rise under multiple competing fields. Tread thickness, original source coordinates
and historical layout remain in the existing source record if not consumed here.
Polygon vertices are relative to the same lower-floor mount as the centers.
Pixel contacts remain in their supplied 384×384 source frame, independent of the
world translation or height of a future occurrence.

Preserve all 12 supports in order and the delivered continuous numbers, including:

- lower floor: `(0, 0, 0)`;
- entry tread: `(0, 0.0857257846456693, -0.048360047716535425)`;
- exit tread: `(0, 0.9086933172440945, -0.9442935633070867)`;
- upper landing: `(0, 0.9086933172440945, -0.9926536110236222)`;
- lane width: approximately `0.432695` cells; retain the supplied precision.

The upper landing is required **separate support geometry**; it is not in the
stair sprite. This data does not implement traversal. Do not round the rise,
stretch the image to G17 or amend `TerrainStairSource`'s native integer grid rules.
Any later playable placement must supply compatible landing/enclosure geometry.

## 4. Coordinate and registration rules

### 4.1 Colour contact and elevation

Let `s` be a point in the untrimmed colour frame, `c` its physical floor contact,
`p` its unchanged raw pivot, `k` its existing render scale, and `A` the world floor
anchor, including its actual elevation. With the selected authored camera view:

```text
pixel position = project(A) + k * (s - c)
sprite position using raw pivot p = project(A) + k * (p - c)
```

This separates floor height, physical attachment and raw image anchoring. Apply
the contact correction once. The image rectangle's atlas origin does not become
a world offset. Elevating an assembly translates all its mounted parts together;
it does not change their pixels, proportions or local relationships.

Example: Elegant opening e retains raw pivot `(100,198)` and scale `128/127`.
Its delivered floor contact is approximately `(128,208)`, so its raw-pivot sprite
position is shifted approximately `(-28.22,-10.08)` pixels relative to `project(A)`.
These numbers belong to this registration, not a global environment offset.

### 4.2 Preserve each frame's own calibration

Do not copy a 256-pixel opening calibration over a 384-pixel destruction/static
frame. The latter's contact is correspondingly near `(192,272)`, and its e raw
pivot is `(164,262)`. Preserve each packet's `pixelToRayOrigin`, `rayDirection`,
depth range, encoding, geometry rectangle and colour-to-native sampling.

Determine the physical contact on each retained capture by projecting the supplied
physical source anchor through that capture's actual calibration. Algebraically,
with ray-origin columns `a`, `b`, `o` and ray direction `d`, solve:

```text
[a b d] * (u,v,t) = source_floor_anchor - o
```

Convert the resulting native continuous `(u,v)` to the colour-frame coordinates
componentwise: `c = ((u,v) - sampling.offset) / sampling.scale`. For the affected
door/timber mappings the scale is `(0.5,0.5)` and offset `(0,0)`, giving `c=2*(u,v)`.
The existing pixel-centre convention is
part of the calibration: do not add another half-pixel. Do not round a continuous
contact through the discrete texture lookup. Where the delivered source gives the
contact for that exact canvas, retain it and independently check the projection.
The observed 64-pixel padding is a check, not a rule inferred from image dimensions.

Door packets and their delivered mounted calibrations share the source packet
basis `[Blender X, -Blender Y, Blender Z]`. Install the delivered physical mount
in that basis once; retain the actual capture's remaining fields. Derive normal
transport from the same effective linear transform, using its inverse transpose,
or retain the delivered matching `normalToLocal`. No second old-mount correction
may remain active alongside it.
The door physical source anchor is the supplied
`physical_mount.views[pose].calibration.mounting.physical_anchor_source_xyz`,
currently `(0,0,0)` for these six families.
Use that delivered mount for the corresponding pose across its existing frames.
The old 256px and 384px reconstructed metric scales differ by roughly `1e-7`;
that source precision is not a reason to fit new frame-specific mounts. Discard
the old pivot-derived geometry translation while preserving the raw sprite pivot.
Some library animation samples and static entries have different raw pivots even
at the same canvas size, so dimensions alone cannot select their placement.

Timber is different: its delivered `sourceToMountLocal` maps **raw Blender XYZ**,
whereas its packets use `[Blender X, -Blender Y, Blender Z]`. Therefore:

```text
timber packet sourceToLocal = sourceToMountLocal * diag(1,-1,1,1)
```

Use the upper 3×3 inverse transpose for matching normal transport. Its physical
source anchor is `(0,-0.995,0)` in raw Blender coordinates, hence **`(0,+0.995,0)`
in packet coordinates for the contact solve above**. The solve's anchor, ray
origin and direction must all use packet coordinates; the door anchor remains
`(0,0,0)` in either basis. Preserve the supplied
sample contacts and rebase support polygons into this same mount. Do not apply
this basis flip to the already normalized door mount.

Preserve shadow/dust/paint role selectors, support masks and receiver relationships.
If a role owns a separate surface calibration, normalize it only in its declared
coordinate frame; never replace a ground receiver with the solid-fragment mount.
Legacy `actor_depth` bytes/registration remain present as legacy data; the new
surface companion is the authoritative corrected ray/normal path for these assets.

### 4.3 Camera capture versus physical orientation

For the six doors and timber the corrected capture mapping is:
`e→0, s→3, w→2, n→1`. Preserve the original source labels and rows.

The door's existing `pose_offset` describes its relation to a physical wall edge.
It is not this capture mapping. For the six doors it remains zero. With the
existing physical edge index E/N/W/S = 0/1/2/3, occurrence quarter
`r = edgeIndex - pose_offset`, and camera quarter `q`, the required capture quarter
is `(q+r) mod 4`. Invert the authored mapping to select the stored source view.
Here X/Z are native map coordinates: **+X is East, +Z is North** (the second
native map coordinate in `game/connector_motion.py`), not browser screen-down Y.
Colour, depth and normal use that same sample. Object-local geometry is rotated
by the physical occurrence and camera exactly once; camera-local geometry follows
its existing camera-local contract, without an extra occurrence rotation.

External frame selection stays keyed by the physical edge. Member artwork uses
its own capture crosswalk, not the corrected door's same-label convention. The
settled registrations to write into existing library samples' `camera_quadrant`
are:

| Source families | e | s | w | n |
| --- | ---: | ---: | ---: | ---: |
| Six generated doors and generated timber | 0 | 3 | 2 | 1 |
| Headers `fantasy.wall.d5`, `.f5`, `.g10` | 0 | 1 | 2 | 3 |
| Partitions `fantasy.wall.d8`, `.f8`, `.g1` | 0 | 1 | 2 | 3 |
| Floor `fantasy.ground.f1` | 0 | 1 | 2 | 3 |

The header mapping follows their object-local ray calibrations. The partition
mapping is explicit in supplier
`environment-geometry-production-2026-10-09/source-recovery/remaining-original-geometry/<family>/delivery.json`,
at `views/e/fine_normal_view/basis/view_to_host_world_by_source_view`; their identical
camera-local ray matrices alone would not establish it. F1 retains the actual
terrain selector in `game/app.py` (`camera_pose('east', camera.quadrant)`) and
`game/projection.py`: e, s, w, n. Its library companions reference those same
`terrain.wood.<pose>` resources. These are confirmed source-view registrations,
not a new claim about hidden vendor geometry. The bounded normalization writes
these known values; it does not defer finding them to implementation or add a
supplier dependency to ordinary assembly.

### 4.4 Compatible member offsets

For each finite variant, normalize the canonical e-view stencil from `parts`.
Support/header offsets start at zero; partitions start at `(0,0,-1)` and `(0,0,1)`.
Apply the delivered `adjacent_origin_relative_to_door_floor_XHZ` to each of those
origins once. For the measured door closure it is approximately:

```text
(-0.4409448566929133, -0.06299272440944884, 0)
```

Read each family's actual supplied value. It moves the recovered neighboring
members into the physical door-floor frame; it is not a second shift of the door.
At placement, use `A + Q(r)*offset_XHZ`. `Q` rotates X/Z while preserving height.
The supplied per-pose legacy stencils are cross-check evidence: do not rotate their
already rotated offsets again. Opposite-side member ordering may permute; the
physical set must agree. Camera rotation alone never changes world member positions.

## 5. Implementation sequence and files

1. **Add passive fields at the current engine owner.** Amend
   `game/environment_art.py` with the fields in §3 and only the associated semantic
   checks: coherent bank pose maps, finite data, complete variant members and
   resolvable library references. Reuse existing vector/matrix types. Defaults
   keep existing documents valid. No renderer methods, engine entities or new
   hierarchy; do not thread unused fields through Pygame drawing code.
2. **Normalize the seven closures into the client copy.** Extend the existing
   environment authoring tooling with a narrow assembly-only operation, reading
   current tracked source records and owners. Put the pure normalization with the
   existing assembly helper in `tools/environment_geometry_library.py`; expose it
   through `tools/adopt_environment_geometry.py --assembly-only`, branching before
   constructing `Intake` or entering bulk intake.
   Do not rerun `prepare()` or `import_environment_authoring.py`: they are completed
   one-time imports and intentionally refuse overwrite. No supplier receipt walk,
   media copy, hashes, general migration framework or new registry is needed.
3. **Write only affected authored owners.** Update the 30 door banks, six door
   definitions, six door library families and timber library family. Populate the
   needed camera metadata of their seven existing member families (F1 ground;
   D5/D8, F5/F8, G10/G1) using the settled table in §4.3. Keep their geometry
   and pixels intact. Preserve existing IDs, file organization and index entries.
   Update active qualifications that still incorrectly say these mounts are
   unresolved, while preserving honest inferred-geometry limits and original
   historical evidence in source records.
4. **Refresh the one environment schema.** Write
   `authoring/schemas/environment.schema.json` from
   `EnvironmentDocument.model_json_schema(mode='serialization')`, with the existing
   JSON Schema declaration. Do not hand-maintain duplicate TS types or regenerate
   wire SDKs/unrelated schemas. Current TS authoring type generation remains in
   client setup after this phase.
5. **Assemble and check the resulting contract.** Use ordinary
   `tools/build_authoring.py::read_authoring`. It already preserves fields from
   these indexed documents; do not add a source-record interpreter. Run the focused
   checks in §6 on the assembled output. Missing inputs produce an error naming the
   owner, sample/pose/frame and field; no guessed mount or nearest asset fallback.
6. **Update status precisely.** Record completion in the master §6.1/§12,
   `RECOVERY_PLAN.md`, current asset status and client authoring README. State
   “assembly authoring connected; runtime consumption remains” after the checks
   pass. Keep the current plan and its implementation result together here.

The operation assigns effective values derived from source data, rather than
accumulating corrections on already corrected output. This prevents double mounts
on a later deliberate rerun; it does not require a migration ledger or checksum.
Use the existing Git diff to review authored changes without staging unrelated work.

## 6. Focused verification and completion

Follow [HOW_TO_TEST.MD](../HOW_TO_TEST.MD). The observable boundary is the normal
assembled authoring document and its schema. Tests should survive replacement of
the normalization helper; do not assert helper calls or incidental file formatting.

Extend the existing engine `tests/game/test_environment_surface_authoring.py` and
client `tests/test_environment_geometry.py`, sharing their existing setup. Check:

| Case | Observable expectation |
| --- | --- |
| All six door families, five banks, four poses, every frame | Effective contacts, capture mapping and geometry/normal transforms are available without following `authoring_record`; no omitted destruction or opening path. |
| Door library static, animation, endpoint and component samples | Same physical mount and matching capture choice on their own canvases; extra variants remain present. |
| 256px opening versus 384px destruction/static | Correct distinct colour contacts; retained ray reconstruction puts the physical source floor at local zero. Raw pivots/rectangles are unchanged. |
| Translated anchors, all four camera quarters, floor heights 0 and 2 | Independently projected source contact equals `project(A)`; elevation is applied once; no 2× scale/pivot correction. These heights are test inputs, not supported-height limits. |
| Camera-only rotation versus occurrence rotation | Camera-only changes source selection, not world member placement; physical rotation transforms the whole compatible stencil once. |
| Member compatibility | Exact allowed variant pairs resolve to existing families; no D5/F8 hybrid, duplicate frame/leaf, or invented part. |
| Normal basis | A supplied source normal transforms consistently with the effective geometry; timber's Y reflection is applied once, door's not twice. |
| Timber | All 12 fractional treads, pixel contacts, support polygons, lane and upper landing survive assembly; no native/G17 assignment is introduced. |
| Role surfaces | Existing shadow/paint/dust coverage and receiver relationships survive; solid geometry does not replace a role's separate receiver. |
| Preservation | Original paths, colour/geometry rectangles, row labels, raw pivots, scales, clocks, marker frames and unaffected owners are unchanged. |
| Typed serialization | New fields survive source-model JSON round-trip; missing pose coverage and unresolved member references yield useful errors. Ordinary client assembly uses tracked client JSON alone. |

Use independent delivered contacts and known geometric points as expectations;
do not just compute both expected and actual values with the migration helper.
Compare a representative opening, destruction and timber reconstruction numerically
as well as covering all installed records structurally. Respect source numeric
precision when comparing independently recovered projections; no fabricated
performance or byte-size threshold is a completion condition.

Run the focused engine test file with the documented uv environment, and the
client environment-authoring unittest file from the client repository. The latter
already calls `read_authoring`; use that result for installed coverage checks.
Validate the affected assembled owners against the passive models/schema in the
engine environment once. Broaden or repeat only for a changed field or actual
failure. No browser run, video, screenshot export or full gameplay benchmark is
required to finish a data-only phase.

Done means all seven closures are connected, the ordinary assembled output carries
the exact usable contract, preservation checks pass, and status is corrected.
The next phase can consume those values without inventing offsets or parsing
provenance. The later shared-renderer tests still owe visual placement, layered
occlusion and lighting acceptance; this phase makes no claim to have performed them.

## 7. Review record

Three independent same-thread reviewers inspected the actual source records,
current typed owners/tooling and this draft. This is a plan review; implementation
tests and renderer checks have not been run in this planning turn.

| Reviewer | Findings incorporated | Disposition |
| --- | --- | --- |
| Anti-slop | Keep completion at assembled data; no renderer, copying, SDK or metadata-loader detour. Remove conflicting duplicate field names from master §6.1. | Ready for this bounded phase; master now points here instead of declaring a second field contract. |
| ECS / type ownership | Keep finite compatibility variants whole; normalize one physical stencil; reuse sample camera field; preserve fractional library-only timber support; no Pygame runtime plumbing. Require exact source-backed member camera mapping. | Approved after the complete camera table, physical anchor and native-axis convention were added. No remaining ownership/duplication issue identified. |
| Rendering / geometry | Preserve 256px/384px frame calibration; distinguish raw pivot/contact; normalize timber's different packet basis, including its reflected source anchor; separate corrected door camera order from wall/floor camera order; rebase members once. | No other substantive defect identified; final requested contact-solve and sampling equations are incorporated. Ready for this scoped data implementation. |

Review corrections are part of the contract above, not a second list of future
discovery tasks. The master and compact entry point link here. The implementation
and focused checks in §§5–6 are now complete, as recorded below.

## 8. Implementation result — 10 October

**Assembly authoring connected; runtime consumption remains.**

- Existing `game/environment_art.py` source models now carry the reviewed contact,
  capture, finite assembly and continuous support fields. Defaults preserve the
  original engine/Pygame documents. No Pygame drawing path was changed.
- `tools/adopt_environment_geometry.py --assembly-only` reads current tracked
  authoring and the seven delivered source records. Its normalization lives beside
  the existing assembly helper in `tools/environment_geometry_library.py`.
  The ordinary client assembler remains unchanged and reads the resulting values
  directly; it does not read those source records.
- Updated **30 banks, six door definitions and 14 library families**: the six door
  libraries, timber and seven wall/floor member families. This covers **3,288 bank
  pose/frame associations, 5,736 door library samples and 124 timber samples**.
  The existing environment schema was refreshed once. These were **50 existing
  authored owners plus one schema**; no artwork was moved, copied or rewritten.
- Effective mounted transforms preserve each frame's own rays and sampling.
  Source contacts remain distinct from raw sprite pivots. Compatible header/wall
  variants stay whole, and timber retains all 12 fractional tread supports and its
  required separate landing. No native staircase assignment was introduced.
- An in-memory before/after comparison of the complete assembled environment
  removed only the explicitly amended fields/matrices/active qualification text,
  then compared everything else. All remaining fields, source paths, rectangles,
  pivots, scales, animation clocks, masks, receiver relationships and unaffected
  owners matched. No checksum or extra asset snapshot was produced.

Verification performed:

| Check | Result |
| --- | --- |
| `uv run --no-sync python -m pytest tests/game/test_environment_surface_authoring.py -q` in engine | **12 passed**. Passive source serialization, optional-field compatibility, missing pose coverage, assembly references/member validity, fractional support. |
| `python3 -m unittest tests.test_environment_geometry` in NDClient | **11 passed**. Normal assembled authoring, complete affected sample coverage, independent contact/ray/normal arithmetic, translated/elevated/rotated projection, compatible members and timber support. Existing companion/device checks also remain green. |
| Ordinary assembled environment against `EnvironmentDocument` during amendment | **Passed** before authored files were written. |
| Deliberate dry rerun of `--assembly-only` | **0 changed files**. Effective transforms and schema are stable; no compounded correction. |
| Targeted diff whitespace check | **Passed**. |

The plan-adherence/anti-slop sub-agent reviewed the actual changed source/tooling
and tests and reported **no blocking implementation findings**, no duplicated
registry/runtime parser, and no renderer/SDK/artwork detour. Current status was
updated in master §6.1/§12, `RECOVERY_PLAN.md`, `ASSETS.md` and both client authoring
READMEs. Source records and their historical evidence remain intact.

This result completes the authorized data pre-phase. Shared renderer placement,
lighting, depth composition and Studio/playback still require their planned
runtime implementations; no new app or visual acceptance is claimed here.
