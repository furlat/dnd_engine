# Environment geometry — supplier response to intake

10 October 2026. **Client import remains paused.** This corrects supplier metadata;
it does not install artwork, amend NDClient types or accept renderer output.

Production correctly found inconsistent active associations. The earlier final
check verified file coverage but missed root/per-view agreement. The files existed,
but a consumer following the advertised per-view catalog fields could reach an
obsolete normal-only receipt. That was a supplier delivery defect.

## Corrected associations

- **816 active views across 207 families** now reference the completed family
  receipt and its exact `view_record` JSON pointer.
- The existing `source_view` and source colour identity are preserved. Fireplace,
  Torch East, Torch West and Torch2 remain actual `single` views.
- Each corrected `geometry_delivery.historical_provenance` preserves its earlier
  channel record and qualifications. A pending status inside that historical
  evidence is not an active delivery status.
- The merger now applies this correction when a complete receipt supplies native
  views but omits the optional `owner_updates.views` block. Final validation now
  rejects root/view pending conflicts and resolves the corrected view records.

[Corrected catalog](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/catalog.json),
[all 816 corrections](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/ROOT_INTAKE_VIEW_RECONCILIATION.json),
[current conflict scan: zero rows](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/catalog-status-conflicts-current.csv).
The original intake CSV remains unchanged as evidence of the reported defect.

## Which receipt supplies the active values

The existing [delivery index](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/DELIVERY_INDEX.json)
now includes `receipt_selection` for each existing ID:

| Field | Meaning |
| --- | --- |
| `effective` | Active reference/JSON pointer and its explicit frame, view or role scope. |
| `historical` | Superseded channel evidence; never an active override. |
| `supporting_evidence` | Source proofs or aggregate validation; not a competing selection. |
| Original `receipts` | Preserved provenance list; its ordering does not establish precedence. |

For `prop.crate.intact`, the selected-prop-closure `original-frame0-reuse.json`
record supplies the effective `frames_by_pose`; the older original-reuse result is
historical. For `prop.crate.break`, that closure supplies **frame 0 only**, while
the source animation receipt supplies **frames 1–25** in each actual pose. Replacing
the whole bank with the frame-zero receipt would lose valid animation geometry.
The index makes these scopes explicit, including exclusion of frame 0 from any
otherwise overlapping animation receipt.

The resource `RESULT.json` aggregate summary is historical, but its valid individual
resource crosswalks and non-solid/utility records remain useful. The index points
at the precise `#/resources/<index>` record where it is effective. Completed
replacement resources point at their own final receipt. Do not discard the entire
older file or interpret its summary as today's missing list.

Embedded `source_evidence.original_colour.geometry_delivery`,
`previous_normal_only_channel` and original normal-basis qualifications remain
immutable provenance snapshots. Final `reused_channels` supplies active geometry.
`CLOSURE_DELIVERY.json` aggregates validate members; they are not frame owners.

## Native grids, shadows and qualifications

The checked 128→256 darts and 192→384 bed packets require no correction. Their
native-to-colour mapping and colour-sized alternatives remain intact; other assets
have their own mapping, including 1:1. Library-original and selected-bank pivots,
canvases and calibrations are distinct even when artwork is reused.

No raster, source RGBA, pivot, scale, clock, calibration or shadow definition was
changed for this correction. Identified ground shadows remain excluded from
object geometry and retained on their receiving surface. Classify original source
pixels using the existing selector/mask/component roles; packet A is normal data.
Existing shadow verification and inferred-geometry qualifications are preserved.
Intake established no new shadow defect; this response does not claim exhaustive
new visual acceptance.

## Verification and remaining ownership

Final supplier gate **PASS**, 2026-10-09T22:51:24.596109+00:00. Revalidated
**15,102 referenced files**, **2,412 RGBA companions**,
all **324 original bank clocks/registrations** and **332 variant slots**.
Independent metadata review **PASS**.

The association check resolves all **816 corrected view records**, finds **zero
root/view pending conflicts**, and checks **24,632 view/frame pairs across all
324 selected banks**, with no missing or overlapping effective frame owners.
The existing index covers all **1,608 records** across the four overlapping lists.

The refreshed [final validation](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/FINAL_VALIDATION.json)
and [independent metadata review](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/ROOT_INTAKE_METADATA_PEER_REVIEW.json)
record the final gates. The [production handoff](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/environment-geometry-production-2026-10-09/PRODUCTION_HANDOFF.txt)
contains the corrected consumption instructions.

The [intake findings](ENVIRONMENT_GEOMETRY_INTAKE_FINDINGS_2026-10-10.md) remain the
record of client schema/import limitations: independent geometry sampling grids,
complete ray/normal conventions, per-frame/per-layer ownership, D6 aperture mesh
plus packet, and device/portal overlays. Those are production integration tasks.
No supplier re-export was requested for them, and this correction does not resume
the paused import or substitute file validation for visual acceptance.
