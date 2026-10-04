# Packet 6 Telekinesis and landing native review — 2026-10-04

**Approved within this native scope after one correction.** This is an independent read-only review of Telekinesis and the shared landing/fall implementation against the approved packet 6 plan. The reviewer did not implement these production changes. Banishment, Dimension Door, other unfinished packet 6 spells and renderer/replay acceptance are excluded.

## Corrected finding

`resolve_fall_damage` originally used `Entity.receive_damage`'s normal-HP-loss return value to decide ordinary fall Prone. A native 10-foot Shove fall with ten temporary HP rolled two damage, consumed temporary HP to eight, and incorrectly left the victim standing. Temporary HP absorption is committed damage, not immunity.

The root corrected the resolver to inspect the direct committed `DamageAppliedEvent` records under this fall request, including temporary absorption and excluding nested secondary damage. The same independent probe now ends at the actual lower support with temporary HP eight and Prone applied. Zero committed damage still avoids ordinary fall Prone. No additional HP computation or damage application was added.

## Reviewed behavior

- Initial Telekinesis admits exactly one supported Huge-or-smaller creature and visible legal destination before payment. Both endpoints respect the caster's 60-foot support-height range; displacement is at most 30 feet. A failed initial Strength resistance still leaves the paid-repeat permission. There is no retained held victim, Restrain mode or free repeat.
- One actor-owned concentration marker lasts 100 native intervals and owns the exact repeat action UUID. Recast/removal/expiry cannot authorize an old action copy. Repeat uses one action without another slot and retains the original DC and spell origin. The initial and repeat events expose hostile intent while safe allied movement does not trigger hostile Sanctuary handling.
- Allied placement is controlled, with no spell impact or forced Prone. Hostile landing uses 4d8 force plus 2d6 bludgeoning, additional actual lower-support fall dice, and a Dexterity save solely for Prone. Zero-distance, resisted and canceled movement does not apply impact. Cosmetic height is not counted as a fall.
- Spatial admission reuses existing support, world-edge and occupancy queries. It distinguishes ordinary pushes from downward ledge contact without making cliffs walkable. Missing tiles, walls, occupied support and unsupported clearance are rejected; no sideways landing search is introduced. An independent shortened-transfer probe through an occupied intermediate cell was rejected with both creatures remaining in their original positions.
- `commit_forced_movement` commits the admitted leg, records actual path/support/drop/kind and resolves one contact. Airborne transfer does not enter each intervening ground cell. Shove, Thunderwave and Gust reuse the same forced landing path. Actual downward Jump settlement uses the shared fall resolver; controlled teleport remains safe.
- Fall damage is 1d6 per full ten feet, capped at twenty dice, through the existing damage, concentration, life/death and Prone owners. Telekinesis uses its approved spell-specific Prone save; ordinary falls have no added save. No physics engine, persistent airborne ownership or second health system was added.
- `LandingKind` is passive data; spatial query code does not import spell/action/entity owners upward. The bounded landing callback supplies Telekinesis's existing native effect composition rather than a per-spell movement engine.

## Verification and limits

Independently reran `uv run --no-sync python -m pytest -q tests/engine/test_spell_handoff_necromancy.py tests/engine/test_telekinesis_landing.py` after the fall correction: **90 passed in 16.21s**. Also read the root's `/tmp/dnd-nature-fall-corrections.log`: **65 passed in 17.71s**. The temporary-HP failure and corrected result were independently reproduced through native Shove; the reviewer wrote no packet 6 production code or tests.

Native event extensions are reviewed here. This receipt does not claim the corresponding passive client fields, disclosure, saved replay, visual landing timing or all requested recording cases are complete.

Reviewed SHA256 pins:

| File | SHA256 |
| --- | --- |
| `dnd/actions.py` | `ec315dac7a3966b741e6011e500da59332d28e3421fbef02e7f6476151518841` |
| `dnd/spells/transmutation.py` | `9fcb741f49d0a7b11e3383230d2f8b58cbe2c79959f295c129404595f08ea9dd` |
| `dnd/core/gridmap.py` | `d9d0f630183998073caa3d80d27d8ef2758f64520bf632231aac1bd71a6510f5` |
| `dnd/core/events.py` | `1de52035d4a53307cee21fc704e14577918b10e6a29d168334c4a63f702b8347` |
| `dnd/types/event_facts.py` | `f00bb72fb9262a4d22a5c9aedf51c7bac453f98e029eb261cd0700d45c63b886` |
| `tests/engine/test_telekinesis_landing.py` | `b0dc51419b04db8cba25de5fb1edc00149a376c347a3ab74f66fbcd955c04609` |

Whole-file hashes include other agents' concurrent, excluded changes. This verdict applies to the native portions described above, not every spell in those files.
