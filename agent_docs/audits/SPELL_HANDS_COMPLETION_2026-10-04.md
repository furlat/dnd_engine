# Missing modular spell hands — completion, 4 October 2026

The preceding palette correction recolored existing layers but left 27 active
canonical casts without hands. True Strike was counted as a 28th missing cast,
although its real child weapon attack owns the presentation; that route lacked
glow for weapons other than shortsword/shortbow. Both omissions are corrected.

## Exact changes

- Added automatic Magic2/Attack5 or Magic3/Special1 layers to 27 canonical spells
  and four independently authored Bestow Curse variants in 16 existing recipe
  files. Aliases inherit their owner's correction. Existing installed isolated
  Ray of Frost/Haste sheets provide geometry; the owning spell supplies the RGB
  replacements. No body pose, release frame, speed, socket, delivery or backend
  value changed.
- True Strike keeps its disabled parent and actual attack. Its two exact charge
  rows are unchanged. Six modular rig/clip fallbacks reuse original Magic2
  Attack1–6 sheets, preserving the weapon, attack profile, clock and results.
  Exact weapon matches take precedence; ambiguous rows remain errors. Automatic
  child layers resolve the parent spell palette through the same shared layer
  helper used by casting. Unmatched fixed rigs still report missing media.
- Six unchanged existing sheets (1,496,267 bytes) were copied to installed art
  and the private production release; public resources and both manifests were
  updated. Original/source/install/production hash evidence is in
  `.runtime/spell-hands-completion-20261004/asset-receipt.json`.
- Updated the presentation contract, recovery checkpoint, full palette inventory
  and the explorer's read-only spell mappings. No new events, gameplay rules,
  render subsystem, animation clock, artwork or external chat communication.

Current inventory: **126 canonical spells: 125 enabled ordinary modular casts
with Magic layers, plus True Strike's weapon-attack presentation**. Their current
hand categories are 44 Magic2 and 81 Magic3; this fixes missing layers without
claiming to finish the wider animation/effect selection pass. Fixed creature
gestures and explicit accepted artwork overrides remain intact.

## Verification

- The new completeness regression failed before the ordinary recipe correction.
- **79 tests passed** across spell palettes, native True Strike presentation,
  body action playback and animation drawing. The former missing-longsword test
  now checks the requested rendered behavior. Longsword/heavy-crossbow hit/miss
  retain real attack timing and equipment while producing exact spell-colored
  pixels with unchanged source alpha in four cameras. Existing exact charge
  on/off-frame tests remain unchanged and pass.
- Scoped Pyright: zero errors/warnings in the four changed runtime modules.
- [Standard engine gallery](http://127.0.0.1:8768/spell-hands-completion-20261004/review/runs/20261004T163327Z-ba16d8/index.html):
  six passing native observer clips, 94 recorder checks, zero presentation gaps.
  Longstrider, Power Word Stun and longsword True Strike cover both ordinary cast
  poses and the actual child attack. Actual four-camera frames were inspected.
- Browser mapping check: all 125 enabled canonical rows have hands; True Strike
  shows its two exact poses and six other-weapon poses; zero browser errors.
- [Anti-slop approval](SPELL_HANDS_COMPLETION_ANTISLOP_2026-10-04.md) and
  [ECS/import-DAG approval](SPELL_HANDS_COMPLETION_ECS_2026-10-04.md).

Logs, native inputs, exact changes and pre-edit snapshots are retained under
`.runtime/spell-hands-completion-20261004/`. Tests are scoped verification, not a
claim to have rerun the entire engine. No commit was requested.

## Human direction for the next authoring pass

Select the whole tuple **spell → actor animation → Magic1/2/3 and optional
Effect1–5 for that action → automatic owning palette**. Manual choices are
acceptable. Colors must be swapped, not multiplied. Godot exports stay the main
VFX; modular layers only complement the sprite. Buff assets are outside scope.
Keep selections in existing recipes rather than adding a procedural rule engine.
An animation choice includes checking its release frame/socket against delivery;
Effect2/Attack5 and Effect2/Special1 are different artwork, not equivalent IDs.

Condition reuse was inspected but not implemented. Effect4/5 have populated
Special1 and Attack1–6 sheets but empty Idle/Walk/TakeDamage/Die sheets. They could
accent attacks/casts while Rage/Frenzy, Fire Shield or another visually magical
condition is active, if selected to match the accepted effect and palette; they
cannot simply become permanent auras. Most conditions already have dedicated
Godot presentation. Their current condition-media path expects precolored media;
nonwhite condition color fields are not an existing palette-swap facility. Any
future condition-driven modular accent must use the action's registered sheet
and shared exact swap, without replacing sustained Godot media or adding backend
conditions. No condition recipes or renderers changed in this correction.
