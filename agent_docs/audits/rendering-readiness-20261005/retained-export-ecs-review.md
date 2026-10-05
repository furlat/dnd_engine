# Retained composition, interruption and export — ECS review

2026-10-05. Current-source checkpoint review, no production edits.

## Approved boundaries

Interrupted ActionNode milestones now omit target contact, scalar anchors beyond cutoff and interrupted application/ground-delivery result anchors. Reached release may remain. Canceled full gesture descriptions are omitted. This resolves the identified false future-contact/missing-cancellation problem structurally; runtime Counterspell checks remain with the implementation agent.

RetainedPresentation groups the existing six typed maps and retain_presentation calls their original registration functions with the original inputs/order. It is composition, not a replacement lifetime policy. Retained milestones omit unknown application dates rather than treating None as zero. Per-cell retirement preserves positions and exact spatial owner. No private ECS query, new condition mechanics or schedule evaluation is introduced here.

## Export changes required

1. **Relocate only actual typed path positions.** export_catalog currently collects Path values, converts to JSON, then replaces every string whose value equals any collected path. This can alter a legitimate authored string/description/resource ID that happens to equal a path. Retain typed-location information or explicitly replace Path-bearing fields (`media_root`, `resources`, Device/Portal path fields) before encoding. Do not use global string equality as a substitute for field typing.
2. **Preserve the media-root base.** Always replacing media_root with `.` is valid only if package_root equals the original media_root. Storage patterns are resolved relative to media_root. For a containing package root, preserve the relocated relative media_root or reject that packaging arrangement explicitly. Otherwise a JSON round trip succeeds but file addresses have changed meaning.
3. **Strictness must reach catalog records.** Inspected generated schema: outer PresentationCatalogExport has additionalProperties=false; AnimationData's schema does not. A strict outer model does not make plain nested dataclasses reject unknown fields. Apply a deliberate strict-extra policy to exported dataclass records, including Device/Portal data as needed, and test injected unknown catalog fields. Do not claim strict portable roundtrip validation solely from the outer wrapper.

Existing typed catalog reuse is preferable to a duplicate authoring model. WrapSerializer retaining value schema is appropriate for map encoding. Large output size is not itself a correctness defect. A local absence of `/home` and `/mnt` proves this exported sample lacks those prefixes; it does not prove the path semantics or field strictness above.

Review disposition: approve retained composition and interruption fixes; portable export needs the three corrections before acceptance. No full portability or TS execution claim is made.

## Corrected export re-review — approved

The current implementation tracks typed Path locations through encoding, so equal-valued descriptive strings remain untouched. Original media_root is relocated relative to package_root, preserving storage-pattern resolution. AnimationData and nested exported device/portal dataclasses now explicitly forbid extra fields.

Independent adversarial probe executed on the real catalog: replaced one motion description with text exactly equal to an actual resource's absolute path, exported the catalog, verified the prose remained unchanged while media_root became the correct package-relative path, then injected an unknown catalog field and verified validation rejected it. Output was 65,900,921 bytes for this modified-description fixture. Generated AnimationData schema reports additionalProperties=false.

All three prior export findings are resolved. Approve this portable boundary and unchanged six-map retained composition. This validates the exercised format/path/strictness behavior, not a TypeScript renderer or complete visual acceptance.
