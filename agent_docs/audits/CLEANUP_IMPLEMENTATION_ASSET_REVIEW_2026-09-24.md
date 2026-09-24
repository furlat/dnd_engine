# Asset/setup implementation review — 2026-09-24

Reviewed the asset portions of
`agent_docs/RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md`, especially
A1–A4, against the completed inventory, prepared private-setup commit
`59aa7262fdb`, and the current readers. No production code, media, installation,
Git index or archive was changed. This is an implementation-plan review, not
pixel-equivalence approval of a package that has not been built.

## Decision

**Approved after final revalidation.** The sequence and scope are sound. The two
precise additions below are now incorporated in A2/A3a; neither required another
framework or broader gameplay work. No asset/setup plan blocker remains.

1. **Keep paired color/raw-XY rectangles aligned during compaction.** A3a permits
   selected-cell compaction and A3b permits coordinate-page sharing. The existing
   `PackedFootpoint` has only `file` and `bounds`
   (`game/animation_types.py:544`); `projectile_frame_layers` passes the color
   `part.rect` to `_raw_part` for its footpoint page
   (`game/projectile_media.py:243`). Consequently, a color crop and its paired
   raw-XY crop must occupy the same rectangle in their respective pages. Preserve
   a common packing layout for this unit. Do not independently compact those
   pages and assume the existing metadata can describe both. Exact whole-page
   aliases remain valid and need no new field. Add the paired raw-value case to
   the existing small compaction/reader checks.
2. **State which generated output is public.** The normalized resource/storage
   bindings in `game/data` remain versioned with public code; packing produces a
   reviewable patch to those addresses alongside the separate private media
   release. The private payload carries the media and its asset-local index and
   installation manifest. The setup tool's `contained()` deliberately permits
   only `game/assets` paths (`devtools/art.py:28` in the prepared checkout).
   Installation must continue to copy private payloads without overwriting
   public bindings or running importers. The code/art release pair associates
   the coordinated outputs. This makes A1's ownership statement explicit at
   A2's build/install boundary.

## Confirmed implementation choices

- Forward `git rm --cached` after preserving the installed archive avoids the
  checkout-deletion hazard of blindly applying the prepared migration. Historical
  removal and remote publication remain separate. The native JSON fixtures under
  `output/fireball-propagation` stay public.
- The installer currently performs a full source checksum pass, full-content
  comparisons of existing files, and a destination scan. The plan correctly
  removes unconditional content verification from normal install/reinstall and
  keeps explicit integrity checking separate. This is installer overhead, not
  evidence of a game-startup hash pass. Existing tiny CLI tests should be revised
  around that explicit distinction, including the same-size-corruption case.
- The 20,700,948,428 selected bytes and 14,919,399,724 unique-payload bytes match
  the final inventory arithmetic. They are candidates before new indexes,
  encoding and layout decisions, not a promised installed size. Of the
  5,781,548,704 duplicate bytes, 5,711,626,726 are in persistent media; starting
  with its explicit page/part references is proportionate to the measured saving.
- Sharing physical bytes does not merge resource identity, clock, palette,
  material, crop, pivot or geometry interpretation. Most large PNG sharing can
  use existing `file` references. No global filename discovery or runtime
  content-addressed asset service is necessary.
- The eight loose color phases can use the existing page/part reader. Environment
  sheets need the stated passive frame-address adapter; color and encoded depth
  can have different source dimensions. Existing character layers remain sheets
  and remain composable.
- `ZIP_STORED` containing unchanged gzip packets is an appropriate first XYZ
  container: it supplies a standard index without a custom compression format.
  Read only the selected member, feed the existing packet decoder, preserve
  `frameIndices` and ordered component registrations, and bound open handles.
  Container/member identity must distinguish cached samples. The plan correctly
  avoids whole-effect decompression.
- The packet interpretation hazard is real. A temporary 1×1 packet read first
  with bounds `(-16,16)`, vertical scale `1.2247` and position scale `1`, then
  requested with `(-8,8)`, `2` and `.5`, returned the first cached interpretation.
  `_surface_packet` stores those values but its current key omits them
  (`game/projectile_media.py:153`). Fixing the key or separating raw samples from
  their interpretation is required before cross-owner packet aliases. This
  reproduction does not establish that distinct current packet paths misrender.
- Native image sizes and exact Ashen intermediate semantics are preserved.
  Fractional VFX downsampling stays optional and requires a measured comparison;
  the plan does not assume that two nearest-neighbor resizes equal the current
  single resize. Numeric coordinates and ownership remain unfiltered data.
- Final reachability must use an empty asset destination. The current full
  installation would conceal omitted dependencies. Existing phase, registration,
  ordered-blend, raw-geometry, eviction/seek, environment and portal tests are the
  right validation boundaries; no new golden-video framework is needed.

## Review limits and revalidation

Inspected the prepared installer and its filesystem tests, current VFX/cache
readers, source storage types, environment/depth/image/portal readers, and the
final inventories. Reused existing source-manifest arithmetic; no corpus hash,
full art scan, pack build, upload or broad game test run was performed. The only
packet experiment used a tiny synthetic temporary file.

Final revalidation checked the revised A1–A4 sections. A2 explicitly keeps
normalized resource/storage changes in public `game/data`, associates them with
the matching code/art release, and restricts installation to private asset
paths. A3a explicitly preserves identical color/raw-XY rectangle layouts without
introducing another schema. The packet-cache correction, independent indexed
reads, source preservation and empty-destination installation remain required.
The plan also distinguishes baseline missing modular content from accidentally
omitting a selected dependency; this cleanup does not claim to supply missing
outfits.

This closes the asset/setup plan review. Package equivalence and measured
install/render costs remain implementation gates; no package, production fix or
remote publication is approved as already completed by this review.
