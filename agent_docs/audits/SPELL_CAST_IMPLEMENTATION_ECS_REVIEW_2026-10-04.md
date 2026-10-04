# Spell casting implementation ECS review — 2026-10-04

**Outcome: source and authored-data architecture approved within the assignment
plan. Final validation and the persistent native gallery remain open.**

Reviewed `devtools/author_spell_casts.py`, the shared palette resolver and cast-row
loader, current typed recipes and resource bindings, and the data delta against
`.runtime/spell-casting-20261004/before`. This reviewer made no production edits
and ran no gameplay tests or renders.

## Ownership and implementation

- The new command is an offline authoring operation. Its Pydantic selection
  records contain passive inputs; functions write existing Studio recipe data.
  No game/dnd module imports the command or assignment catalog. Canonical owner
  coverage and output Studio schemas are checked before writes. A dry run after
  application returned `applied: false, changed: []`.
- The runtime diff contains only two shared changes: `_layer_palette` copies the
  existing treatment while replacing its colors, and `load_cast_rows` supplies
  the selected resource through existing `palette_noise`. No late imports,
  reflection, spell dispatch, new registry, event/rule changes, or entity behavior
  were introduced by these changes.
- Existing automatic cache keys include the full resolved treatment and source;
  enclosing keys also identify rig, clip, and row. Gamma/noise and distinct spell
  palettes therefore remain separate. Explicit override bypass is retained.
- Existing fixed-rig adaptation still substitutes its own gesture and removes
  modular accents. Ordinary casts and actual child attacks resolve palettes
  through the same existing helper.

## Independent applied-data checks

- All 150 loaded identities are accounted for. All 148 enabled presentations
  match their approved clip, speed, release, layer categories, automatic palette,
  gamma `0.65`, noise resource, and standard sheet addresses. This covers 299
  enabled cast layers, including active variants and aliases.
- Every enabled cast's release and preparation sockets exactly equal the chosen
  original hand track. Every applicable projectile has the same sockets and an
  explicit preparation frame three frames before release. Source-hand media and
  projectile consumers retain their existing measured-track/fallback behavior.
- Six action/reaction aliases equal their canonical owners after loading. Active
  variants keep their own element colors and delivery. Disabled child-effect
  casts remain disabled.
- True Strike's parent remains disabled. Its eight existing exact/fallback pose
  rows retain their rig/weapon/clip identity and use matching original Magic2
  with parent material policy. Actual weapon timing and release remain owned by
  the child attack path.
- The snapshot comparison found changes in 38 JSON files, confined to existing
  cast presentation, projectile sockets/preparation frame, child overlay layers,
  and 21 resource bindings. No unrelated recipe field or delivery changed.
- All 21 selected runtime sheets match their original source bytes and recorded
  SHA256 hashes: 7,659,330 bytes total. Standard resource addresses are present in
  the modular rig clip metadata, including reused installed hand sheets.

## Remaining acceptance evidence

The first recorded test run has failures from old authored-art/timing assumptions;
it is not acceptance evidence. The follow-up palette/body run was still in
progress at review time. Scoped typing reports zero errors and warnings.
`test_true_strike_presentation.py` still had an expectation for the replaced
`/support-spells/true_strike/` charge sources at review time; update that expectation
to the approved matching Magic2 source while retaining substantive child timing,
equipment, palette and alpha checks.

Final approval must inspect completed relevant tests and the persistent native
gallery/coverage evidence. This receipt does not claim all spells were rendered
or all gallery frames visually inspected.
