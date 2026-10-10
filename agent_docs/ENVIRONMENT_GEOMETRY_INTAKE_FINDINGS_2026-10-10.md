# Environment geometry delivery — intake findings and exporter handback

10 October 2026. **Import paused at the user's request.**

## Follow-up: supplier metadata corrections verified, 10 October

The [supplier response](ENVIRONMENT_GEOMETRY_INTAKE_RESPONSE_2026-10-10.md)
resolves the exporter issues in sections 3–4 below. Those sections and the original
CSV remain the record of the earlier findings, not a current missing-assets list.

Direct follow-up checks resolved all **816 corrected view pointers across 207
families**, preserved their original source-view identities and earlier status/path
evidence, and found **zero current root/view pending conflicts**. The 813 corrected
records exposing `source_colour.path` also match their original catalog colour
paths after resolving relative paths. Four actual `single` views remain `single`.
All 1,608 existing index records now have explicit `receipt_selection` records.

The crate intact and destruction examples have respectively 4 and 104 expected
pose/frame pairs, without overlap or omission: corrected frame 0 is distinct from
destruction frames 1–25. The lever resource's effective JSON pointer resolves to
its own resource ID. [Follow-up results](audits/environment-geometry-review-20261010/response-check.json)
record these checks. The supplier additionally reports complete 24,632-pair bank
coverage; we did not repeat that full check or the raster validation.

**Assessment:** the supplier handback issues are resolved for intake. No re-export
is requested. Sections 1–2 still explain the valid resolution/shadow distinction;
section 5 still records our integration work. This is metadata acceptance, not
renderer/visual acceptance. Import has not resumed and no new artwork was installed.

## Original intake findings

No new environment artwork or geometry authoring records have been installed in
NDClient. Integration drafting started before the pause, but the importer was
run without its apply option and stopped. It is unfinished and must not be treated
as an accepted importer. Existing source artwork and delivery files are untouched.

The resolution differences checked below are legitimate. **This review has not
established a corrupt raster export.** It has established inconsistent current
versus historical metadata and limitations in our client schema. These are
different problems, with different owners.

## Sources and review limits

- [Supplier's delivery summary](ENVIRONMENT_GEOMETRY_DELIVERY_2026-10-10.md).
- Catalog: `/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/catalog.json`.
- Delivery root, abbreviated `DELIVERY/` below:
  `/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/`.
- `DELIVERY/PRODUCTION_HANDOFF.txt`, `DELIVERY_INDEX.json`,
  `FINAL_VALIDATION.json` and `DELIVERY_FILES.csv`.
- Existing consumers: engine `game/asset_types.py`, `game/environment_art.py`,
  `game/device_art.py`, `game/portal_art.py`, and NDClient's tracked authoring.

The supplier reports a passing delivery covering 324 banks, 556 resources, 725
non-Desert families and three devices. These lists overlap. Its resource and family
lists include respectively 20 and 33 intentional non-solid/layer-only entries.
Its validation reports 15,100 referenced files, 2,412 RGBA companions, all 324 bank
clock/registration owners and 332 variant references. Those are **supplier results**,
not a claim that this intake independently rerendered every frame.

This review inspected delivery conventions, representative receipts and existing
types; scanned root/per-view catalog status contradictions; and compared native
and colour-sized packet bytes for the three examples below. No new renderer or
full visual acceptance was performed. Correct file references do not prove correct
depth, lighting, physical assembly or shadow classification for every asset.

## 1. Smaller packets: verified valid in the checked examples

| Delivery receipt | Native geometry cell | Colour cell | Result |
| --- | --- | --- | --- |
| `source-recovery/resources/darts/delivery.json` | 128×128 | 256×256 | Full-size geometry is exactly 2× repeated native pixels. First selected colour frame is also exact 2× repetition. |
| `source-recovery/props/prop.bed.intact/delivery.json` | 192×192 | 384×384 | Same byte-exact relationship. |
| `source-recovery/props/prop.bed.break/delivery.json` | 192×192 | 384×384 | Same byte-exact relationship. |

These are **depth AND normal packets**, not shadow maps. Their supplied mapping is
`floor(colour_xy / 2) + 0.5` into native pixel-centre coordinates. The exporter
also supplies colour-sized geometry copies. In these checks, the smaller packet
does not discard detail present in the source colour frame.

The bed intact sheets are 192×768 for native geometry and 384×1536 for the
colour-sized representation. The comparison checked the geometry sheets' raw
RGBA bytes, not a visually similar resized preview. The colour repetition check
covered the first selected frame; it is not an all-colour-frames claim.

Other receipts illustrate why a global scale assumption would be wrong:

- `source-recovery/door.indoor-door-elegant.inward/delivery.json` explicitly
  declares native 128×128 and colour 256×256, with both native and colour-sized
  geometry regions and the colour-to-native mapping. This receipt was inspected;
  it was not part of the three byte comparisons above.
- `source-recovery/props/prop.chest-a1.intact/delivery.json` declares both native
  geometry and colour as 384×384. Do not halve every prop's geometry.

**Exporter action:** no re-export requested for these size differences. Retain the
explicit mapping, source rectangle and calibration. Do not expand or shrink files
merely to satisfy a limitation in our current type.

## 2. Shadow exclusion is a separate question

The delivery explicitly excludes identified painted ground-shadow pixels from
object depth/normals and retains their colour on the receiving surface. This can
make the **valid geometry silhouette** smaller than the colour silhouette. That
is expected where the excluded pixels really are ground shadow. It does not
explain a 128×128 versus 256×256 sampling grid.

The supplied rules require classification against original source RGBA, before
recolouring, lighting, premultiplication or resampling. Some assets have per-asset
colour/alpha selectors; ambiguous materials use masks/component roles. A global
"black or translucent means shadow" rule would remove real stone, metal and
recesses. Intact-frame classification cannot silently stand in for destruction
frames with different components.

The packed channel A contains a normal coordinate, **not transparency**. Colour
alpha plus the declared support and component roles determine visible coverage.
Testing packet alpha as opacity would produce a client bug.

No new shadow-exclusion defect was established here. Exhaustive per-frame shadow
correctness remains outside this limited intake check; supplier evidence must
retain its original qualification rather than being upgraded by the importer.

## 3. Confirmed catalog status contradictions — exporter metadata correction

The read-only catalog scan found **816 view records across 207 families** whose
root `geometry_delivery.status` contains `complete`, while
`views.<view>.geometry_delivery.status` still contains `pending`.

The complete affected list, with both current paths and statuses, is saved in
[catalog-status-conflicts.csv](audits/environment-geometry-review-20261010/catalog-status-conflicts.csv).

| Per-view status | View records |
| --- | ---: |
| `normal_delivered_depth_pending` | 432 |
| `partial_normal_source_material_gaps_depth_pending` | 252 |
| `channels_delivered_physical_calibration_pending` | 104 |
| `partial_normal_components_depth_pending` | 24 |
| `channels_partial_normal_physical_calibration_pending` | 4 |

Concrete example: catalog family `fantasy.chest.a1`.

- Root status: `delivered_library_geometry_complete`.
- Root receipt:
  `DELIVERY/source-recovery/remaining-original-geometry/fantasy.chest.a1/delivery.json`.
- All four view records: `normal_delivered_depth_pending`.
- Their receipt:
  `DELIVERY/model-derived/fantasy.chest.a1/NORMAL_RESULT.json`.
- The complete receipt actually supplies per-view geometry/calibration and packed
  depth/normal references; the old fine-normal provenance is still useful.

**Requested correction:** make the existing active per-view records unambiguously
reference their final geometry, preserving source-view identity and the earlier
fine-normal evidence as historical provenance. Alternatively, explicitly document
and encode that these view records are historical and point consumers to the
final per-view record. Do not merely change the word `pending` to `complete` while
leaving an old normal-only receipt looking like the complete source.

This is **not evidence that 207 families lack geometry**. It is evidence that a
consumer following the advertised catalog per-view association can read a
contradictory or obsolete state. The supplied handoff explicitly asks consumers
to preserve those per-view associations, so this ambiguity matters.

## 4. Intermediate receipts remain reachable — clarify precedence

These examples explain why searching for the word `pending` alone is not a valid
missing-assets audit:

- `DELIVERY/source-recovery/resources/RESULT.json` still reports 59
  `source_geometry_unavailable` entries and 24
  `surface_overlay_parent_geometry_pending` entries in its intermediate summary,
  despite the final delivery's completed scope. This summary is historical; it
  cannot be used as the final missing list.
- `DELIVERY/source-recovery/props/prop.crate.intact/original-reuse/RESULT.json`
  has `frames_by_pose.e.reused_channels.status = normal_only_reused_depth_pending`.
- The newer
  `DELIVERY/source-recovery/selected-prop-closure/prop.crate.intact/original-frame0-reuse.json`
  has `reused_inferred_registered_geometry`, references `geometry-e.json` and its
  final geometry delivery, and preserves the previous normal-only channel as
  provenance. The closure exists; the crate is not demonstrated to be missing depth.

**Requested clarification:** state which referenced receipts are historical and
which supply the effective frame/view values when the index lists more than one.
Keep useful evidence, but do not require the importer to guess precedence from
directory names or select whichever status sounds most complete. Existing final
references/closure records are enough; a new binding registry is unnecessary.

## 5. Client integration gaps — our responsibility, not exporter defects

| Existing owner | Gap found | Consequence to avoid |
| --- | --- | --- |
| `ImageResourceSource.geometry_region` | Validator requires geometry rectangle dimensions equal to colour `native_size`; no explicit independent sampling-grid mapping. | Rejecting valid native packets or resampling encoded bytes to appease the type. |
| `RayDepthGeometry` | Current fields do not explicitly carry all delivered pixel-coordinate conventions, normal basis/transport and pose qualifications. | Double pivot subtraction, incorrect normal rotation, or discarded calibration. |
| `EnvironmentBankSource` | Existing per-pose surface geometry and frame regions help, but a single bank-level depth calibration cannot be assumed to describe every new frame/view/role. | Flattening distinct registrations or relabelling old depth. |
| Static geometry owner | A single geometry union does not by itself preserve both the D6 ray packet and its separate aperture-preserving receiving mesh. | Filling an arch opening or silently dropping a supplied representation. |
| Image/layer companions | Support, shadow/component masks, separate normals and inherited receiver roles need preserved typed associations. | Treating shadows, smoke, cloth, blood overlays or darkness as solid surfaces. |
| Device and portal owners | Existing pitch/pose/frame and front/overlay records do not yet expose all newly delivered companion associations. | Attaching one geometry packet to every moving part or losing hatch layers. |

The draft intake also assumed a `bindings` wrapper in the client portal document
that is not present. That is our unfinished importer's mistake, not bad delivery
data. It has not been used to install this delivery.

No schema repair or asset import continues during this pause. Any later repair
must extend the existing owners with the actual delivered information, rather
than inventing offsets, a parallel identity system or a second source of truth.

## 6. Valid representation differences that must survive eventual adoption

These are documented integration constraints, not newly discovered export errors:

- New packets encode `code = 256*R + G`; zero means no surface sample. Nonzero
  depth is `lo + (code-1)*(hi-lo)/65534`. B/A encode octahedral normals. Use raw
  bytes, not colour/gamma conversion, premultiplication or interpolated depth bytes.
- Preserve `pixelToRayOrigin`, `rayDirection`, `sourceToLocal`, `depthRange` and
  each receipt's pixel convention. The supplied ray direction is a parameterized
  vector; do not normalize it independently of its depth calibration.
- Preserve the declared normal basis and inverse-transpose transport. Apply the
  existing instance pose once. Source pose and physical assembly mappings cannot
  be conflated into a guessed pack-wide camera quarter.
- The 88 legacy `rg16le_contact` banks keep their byte order/calibration. Valid
  old depth plus new normals is not equivalent to relabelling old bytes as RG16BE.
- `spikes.blood.e.1` is surface paint inheriting `spikes.e.1` geometry, not a new
  solid object. D6 has aperture-preserving receiving meshes. B44/B45 distinguish
  their solid supports, cloth and shadows.
- The handoff supplies six generated-door physical mount closures and the
  timber-flight closure under `source-recovery/assembly-mount-closure/`.
  Timber's measured rise is 0.908693 height steps over 12 treads. These supplement
  existing adjacency/placement data; they do not authorize arbitrary door/wall
  combinations or rounding/stretching stairs to a different rise.
- Preserve duplicate-name variants by their actual existing slot and
  `variant_index`, selected source colour, source rectangle and pivot. Preserve
  clocks and phase/frame alignment; do not introduce an FPS conversion.
- Some geometry is source-derived and some is explicitly inferred. The chest
  root itself says `source_exact: false`. Completeness does not turn an inferred
  visible receiving surface into vendor-exact hidden geometry or a gameplay collider.

## 7. Package size is not evidence of wrong artwork

`DELIVERY_FILES.csv` lists 1,831,558,463 referenced bytes. It includes source and
validation records, raw arrays and alternative representations, not just the
eventual installed runtime images:

| Extension | Files | Listed bytes |
| --- | ---: | ---: |
| PNG | 8,275 | 71,580,174 |
| JSON | 4,791 | 1,095,840,482 |
| NPY | 732 | 575,761,920 |
| NPZ | 678 | 54,091,278 |
| zlib | 624 | 34,284,609 |

Do not blindly copy this entire package into `.media`, and do not discard real
geometry or normal/support data merely because a file is large. Runtime files and
their authoring references must be selected from actual usage after the metadata
questions are resolved. There is no new size budget or repacking requirement here.

## Handback request

1. Reconcile the 816 catalog view statuses/references listed in the CSV with
   their completed root receipts; keep earlier normal provenance clearly separate.
2. Clarify final-versus-intermediate receipt precedence for existing owners,
   including the resource summary and original-frame reuse examples above.
3. Preserve and confirm each asset's native geometry-to-colour mapping and
   per-layer shadow exclusions. The checked smaller packets require no correction.
4. If a case genuinely excludes material rather than shadow, identify the exact
   asset, view, frame and mask/selector; repair that case. This review has not yet
   established such a case and does not request a blanket re-export.

The client-side limitations remain ours to fix. Asset acceptance remains paused;
this report is ready for the user to send back and has not been sent externally.
