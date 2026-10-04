# Casting-hand palette anti-slop review — 4 October 2026

**Implementation approved within the bounded plan; no source blocker found.**
The review compared current production files with the current-turn copies in
`.runtime/spell-hand-audit-20261004/before/`, avoiding unrelated checkout changes.

`resolve_cast_recipe` prepares the spell's tertiary/primary/secondary ramp for
automatic isolated layers. `load_cast_rows` performs exact palette replacement,
including on precolored source sheets. Automatic layers never enter the legacy
hue/tint branch. Frame selection, timing, source alpha and authored geometry are
preserved. The existing body-context adaptation continues removing modular hands
when a fixed rig supplies its own gesture and accents.

The row identity separates automatic treatment from explicit source pixels and
includes the source plus complete effective palette value. The same key serves
preloading and body drawing. Explicit layers retain their original pixel path;
their offline `palette` metadata does not cause a second runtime recoloring.
Acid Splash's accepted 22-color ramp is now explicitly retained as an override.

The inspected authoring has 18 automatic isolated hands: Beacon of Hope, Cone of
Cold, Continual Flame, Daylight, Divine Word, Fear, Flame Strike, Globe of
Invulnerability, Hold Monster, Hold Person, Hypnotic Pattern, Mass Healing Word,
Slow, Wall of Force, Wall of Ice, Wall of Stone, Wall of Thorns and Wind Wall.
The other 80 active isolated layers in the selected inventory remain explicit.
Aid/Haste originals, accepted electric/solar artwork and exact baked ramps are
preserved. Cone uses the existing Ray of Frost hand sheet; no artwork was
generated and no other previously absent hand representation was invented.

The new tests exercise actual visible RGB values and alpha, two automatic spell
palettes plus an explicit override sharing a source in both preload orders,
four camera rows, backward/forward sampling, the native actor-only cast route,
fixed Goblin02 adaptation and nonempty pre-release pixels for concrete affected
spells. The final stored `verification.log` reports **86 passed in 74.03s**.
Earlier failing test attempts remain preserved; the final tests correctly count
partially transparent visible pixels and select a rig with authored cast
adaptation. Existing exact-palette tests remain in the passing affected run.

Reviewed source SHA256 values:

- `game/animation.py`: `0a810f44ff56aba64f1ba2cc813b09087b471638edf0c24fd842dd7f396b796d`
- `game/animation_draw.py`: `b24303c199a881e3bb934dfc74dfb06f762f6c264724cba4a54bff10628a6111`
- `game/animation_types.py`: `412f322e05facfbc336af6fb470fdda58e1902bb0ef1846aa6f72b79103ba39b`
- `tests/game/test_spell_palettes.py`: `39e92635ff414edad91d0f363992ca9e0c8df43426abfb16affd9072ad468cad`

This is source and stored-test-evidence approval. It does not claim independent
test execution, typing verification or visual inspection of an in-engine
recording. The planned standard replay and its visual acceptance belong in the
delivery evidence. No production edits, tests, renders or external chat access
were performed by this reviewer; this receipt is the only file written.
