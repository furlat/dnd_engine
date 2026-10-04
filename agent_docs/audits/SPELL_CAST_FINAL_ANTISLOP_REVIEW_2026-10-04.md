# Spell casting final anti-slop review — 2026-10-04

**Final verdict: accepted within the documented loaded-presentation scope.**
Production changes, executed gallery coverage, sampled visual combinations and
full client-suite reconciliation are approved. The integrity-receipt correction
is verified. No remaining anti-slop blocker was found.

## Scope and current production

The approved assignment covers 126 canonical recipes and 24 derived
presentations. It authors existing Studio data through the generic offline
`devtools/author_spell_casts.py`; it does not add a runtime assignment registry.
The only reviewed runtime changes preserve authored gamma/noise while resolving
automatic owning RGB and supply the existing noise texture to the existing
palette mapper. Explicit overrides, distinct variant palettes and the existing
cache separation remain intact.

The authoring tool and both runtime files still have the exact hashes from
`SPELL_CAST_IMPLEMENTATION_ANTISLOP_REVIEW_2026-10-04.md`. Independently compared
all 41 production data/code/authoring hashes in the preserved initial 48-file
snapshot with current files: no mismatch. The refreshed snapshot also includes
the existing measured pose-socket source. Later changes are reviewed test
expectations and documentation, not production fixes. The earlier independent
recursive data review therefore remains applicable: unrelated main delivery, outcome,
hit/death/condition tracks and owning `elementColors` are preserved. There is no
backend, gameplay, event, renderer-per-spell or new-artwork extension in this
scope. Fixed rigs retain their own source gestures; True Strike uses its actual
weapon attack rather than an added parent gesture. Buff assets are excluded.

## Final persistent gallery

Reviewed archive:
`/home/tommaso/Dev/neurodragon_art/reviews/spell-casting-20261004/acceptance/runs/20261004-all-spell-casts/`.

- Independently counted 298 unique passed recordings, 5,560 passing recorder
  checks, no failed checks and zero reported gaps. All 1,192 video/poster/input/
  trace files exist, are nonempty and match their declared origin file sizes.
  The three gallery HTML/CSS/JS files are byte-identical to the existing standard
  recorder templates. This is the native four-camera gallery at 32 fps,
  1280×960, with the existing timber-floor choice.
- `spell-coverage.json` is non-partial. Its 150 unique identities equal exactly
  the assignment's 126 canonical plus 24 derived rows. Independently reconciled
  all 335 claimed primitive proofs against 296 relevant raw traces: every
  primitive event and native owner UUID exists, the owner is not canceled,
  behavior/effect fields agree, and recorded causal chains agree. All 150
  identities are represented, with no mismatch. The two additional fixed-rig
  recordings are not counted as extra spell identities.
- Coverage preserves distinct effect variants and action/reaction aliases.
  True Strike proves the child attack's ancestry; Ice Knife's disabled burst is
  accounted for inside its real owner sequence. Neither is presented as an
  extra enabled standalone body cast. Declaration rows in the general coverage
  inventory are kept separate from this executed evidence.
- The four explicit replacements are Wolf and Fey Jaguar in two perspectives
  each. The manifest retains origin links and all eight gaps from their old
  inputs. The final recordings use the refreshed existing scenarios; failed
  originals remain preserved. This provenance is disclosed rather than folded
  into an unexplained clean-run claim. The manifest's `dirty: null` is not
  evidence of a clean Git checkout.

Reviewed manifest SHA-256:
`5503c81628e1bfea46c21aea2a7b957cf98887613eba7165ee08417c1f16f484`.
Executed coverage SHA-256:
`d05999e003b88a727717b1aa0306749eb32e949316443f678c0753102fa6f404`.

## Pixel evidence and limits

The independent smoke and full-pixel receipts in this directory remain the
visual evidence: 108 selected recorded frames across 25 recordings, inspected
as 432 camera crops, plus their documented uncropped views. They cover all 19
distinct assigned motion/layer combinations and alternate signature palettes.
The exact frame indices, timestamps and source video/trace hashes are recorded
there. No additional render or exhaustive frame review was performed here.

No sampled geometry drift, rectangular effect backing, gross actor recolor or
added competing projectile was observed. Godot remains the main delivery.
Compact and broader accents show the intended relative budgets; deliberate
skulls and invocation columns remain limited to the selected spells. Red
Bestow Curse on the red outfit has low contrast, and native wide framing limits
fine inspection of some casters. These disclosed limits prevent claims of a
strict brightness ordering by spell level. Lossy MP4 pixels do not establish
exact alpha/RGB; source-surface tests provide that evidence.

## Validation and closure

Read completed logs: 57 palette/body/True Strike checks, 41 current-selection/
delivery-contract checks, nine Hold/volley checks and 82 architecture checks
passed; scoped typing reports zero errors/warnings. The reviewed test changes
retain actual pixels/alpha, cache/seek isolation, real child-attack timing,
equipment/outcomes and delivery contracts while replacing obsolete selection
expectations. No tests were run by this reviewer.

The completed full client run records **3,524 passed and 34 failed, 3,558 total**.
Independently extracted all 34 exact failed node IDs from `game-suite.log` and
compared them with `test-reconciliation.json`: no missing, extra or duplicate
entry. Each maps to its complete current test-file rerun. The six rerun logs
record 57 + 41 + 9 + 3 + 37 + 14 = **161 passing cases**, with no failure entry.
Thus all 3,558 original client cases are accounted for after the reviewed test
corrections. This is full-run-plus-rerun reconciliation, not a claim that one
subsequent monolithic run passed. The original failed log remains preserved.

The six later test-file corrections are approved:

- Silence samples inside the selected 32 fps frame rather than exactly on a
  floating-point boundary. Expected application/sustain frames, looping pixels,
  removal fade/end, backward seeks and zero backend-event checks remain.
- Palette rebake uses a full 128px source cell and deterministic noise endpoints.
  Every output RGBA pixel, partial/zero alpha, dimensions, source/noise bytes,
  selected outputs and authored recipe bytes are still checked. The separate
  material tests retain nontrivial noise/palette checks.
- Summon preparation/release coordinates match all eight measured source hand
  paths at frames 6/11, independently compared here. Summon timing follows the
  approved frame 11; the separate dismiss action retains frame 8. Native
  visibility boundaries, effect placement, fixed-rig behavior and seeking stay
  asserted.
- Support expects the selected original Magic2 bank while retaining duration,
  ground registration and no-damage contracts. Teleport expects frame 11 while
  retaining before/at-release position, destination height and continuous-cast
  checks.

`artifact-integrity.json` now references the exact current manifest and coverage
hashes above. Its earlier stale manifest hash is closed; no recording changed
for this correction. The initial snapshot is preserved separately. The final
source/test/docs snapshot is being recopied after review receipts; this is
evidence packaging, not an outstanding implementation or test finding.

Reconciled full-run log SHA-256:
`5e952e8302769ed279c147f0b32153273c503591e59fe4baf59ea6844734f63e`.
Reconciliation JSON SHA-256:
`98be9678f09213425320a545ab8339aa64d8c3cf796b76413d25d5658d207bd4`.

The backend-only definitions `spell.necrotic_bless` and
`spell.prismatic_spray` still lack loaded presentation recipes. These are
pre-existing gaps outside the 126 reviewed canonical recipes, not successfully
rendered members of this gallery. “All loaded presentations” must retain that
scope qualification.

Only this receipt was written. No production changes, tests, renders or
external-chat communication occurred in this final review.
