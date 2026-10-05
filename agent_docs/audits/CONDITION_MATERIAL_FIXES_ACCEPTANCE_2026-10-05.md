# Condition and material fixes

Approved scope: Steps 1–2 of the cleanup plan only. General `/game` restructuring,
schema exports, AI and target-index validation remain unchanged and deferred.

## Production changes

| Owner | Change |
| --- | --- |
| Shield | Existing turn-start removal runs during suppression. |
| Guiding Bolt | Mark is magical; its deadline continues during suppression, while attack consumption remains gated. |
| Light | Light source references the condition owner through the existing contribution field. |
| Continual Flame | Existing item condition is classified magical. |
| Regenerate | Existing counter advances while suppressed; healing requires active contributions. Authored duration unchanged. |
| Command | Intended next-turn bookkeeping/cleanup continues; commanded behavior remains gated. |
| No Healing | Passive condition capability replaces writes to the health boolean. Health derives effective prevention from its owner's condition index and preserves its independent baseline flag. |
| Body materials | Current-frame composition retains item-owned modifiers before the body ramp. Only proven static mappings use row caching; full immutable ramp participates in its key. Dynamic mappings receive age, strength and texture inputs. |
| Material admission | Persistent normal textures must be registered, matching the existing finite-material resource requirement. |

No new event type, runtime registry, scheduler, action rule, asset or renderer
framework. No expiry-helper migration was needed for these bounded corrections.

## Validation and limits

Final focused checks: **130 passed** across three non-overlapping runs:

- Condition/material affected files: 67 passed (109.77s).
- Light-item lifecycle, silent condition removal, shared materials and dependency
  boundaries: 61 passed (42.97s).
- Actual Guiding Bolt casting/consumption/expiry cases: 2 passed (2.26s).
- Scoped production typing: zero errors/warnings. `git diff --check` clean.

The native material contact sheet was inspected: first four samples use the
retained Shillelagh modifier at 0/500/1000/1500ms during partial stone blending;
the fifth omits it as a diagnostic comparison. Original sprites are unchanged.

The affected-file test run and evidence receipts are recorded in
`condition-material-fixes-20261005/`. Existing independent overlapping-field checks
remain in the condition suite. Added cases cover suppressed deadlines, baseline
healing prevention, actual Light/Continual Flame casts and restoration, modifier
ownership at partial/full body-material strength and deterministic dynamic sampling.

The combined rendering case uses actual Stoneskin/Shillelagh casts and a real
equipped staff, then renders the resulting passive state at controlled transition
samples. It does not claim to validate transition scheduling end to end. A fully
opaque stone palette can quantize away small glint changes; partial blending
demonstrates that the item animation still progresses before the ramp. The
synthetic opacity regression independently verifies full-strength modifier retention.

Independent backend ECS/anti-OOP and client anti-slop reviewers approved the
scoped implementation. They reran the original defect probes and confirmed the
Shield/Guiding Bolt suppression and material-modifier failures were corrected.
Client final review also approved normal-texture admission and the added tests,
with the controlled-sampling evidence qualification above.

This is focused validation, not a full engine/client suite certification.
