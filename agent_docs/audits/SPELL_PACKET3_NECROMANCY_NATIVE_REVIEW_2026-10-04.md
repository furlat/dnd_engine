# Packet 3 necromancy native checkpoint — 2026-10-04

**Reviewed change; root review of the correction is required.** The independent review found two Eyebite issues, then the root delegated their bounded implementation to this reviewer. This receipt therefore does not independently approve its own Eyebite correction. No other concrete blocker was found in the examined native changes for Blight, Circle of Death, Harm and the damage-only Finger of Death adaptation. Lightning Bolt, Chain Lightning, Disintegrate and all artwork/presentation acceptance are outside this checkpoint.

## Findings and authorized correction

1. Initial Eyebite omitted harmful intent, and the repeat used an ordinary `ActionEvent`. Both bypassed Sanctuary. The repeat also applied Sickened inside Antimagic. Three in-memory native probes reproduced those results; the four protection/provenance regressions failed before the correction. Initial Eyebite now declares harmful intent. The repeat emits the existing nonverbal, non-cast `SpellEvent` shape with the exact casting marker's retained origin, original slot level, target, Wisdom DC and ordinary action cost. Existing Sanctuary/Antimagic/Globe guards consume that data. The unused `_create_event` method was removed.

   The first gaze resolves on the paid cast's already-admitted event. It does not issue a second action declaration or ask for a second Sanctuary save. A successful Sanctuary-admission test pins exactly one such save. Subsequent gazes remain paid uses of the exact granted action and cannot adopt a replacement cast's marker. Applying Sickened still carries the exact original spell origin. Throwing no new spell event means Silence and Counterspell remain casting rules, while the caster's own Sanctuary correctly ends on the harmful effect.

2. Eyebite's repeat and Sickened turn-end saves omitted the existing `SavingThrowContext`; native Magic Resistance consequently provided no advantage. Both variants were reproduced and then failed dedicated regressions. The two save producers now explicitly identify the Eyebite magical save using the existing context type. No new condition, event class or saving-throw system was introduced.

Only `dnd/spells/necromancy.py` and focused cases in `tests/engine/test_spell_handoff_necromancy.py` were changed for these corrections.

## Other reviewed behavior

- Blight retains native range, undead/construct exclusion, plant save disadvantage, maximum plant damage with successful-save halving, ordinary resistance/HP handling and slot scaling. The temporary plant modifier is removed in `finally`.
- Circle of Death retains its native admitted footprint, 150-foot placement, 60-foot radius, 8d6 plus 2d6 per extra slot, Constitution half damage and native damage provenance. Its effect cancellation guard prevents damage after rejection; no persistent damage zone was added.
- Harm uses the native normal-HP cap after ordinary damage defenses and includes absorbed temporary HP in committed accepted damage. Its maximum-HP modifier preserves current normal HP instead of damaging/healing again. Independently timed `HarmSource` owners retain one public reduction, choose the strongest live source, reveal a weaker surviving source on expiry, and retire through disease/restoration cleanup. The existing modifier/parent ownership machinery is reused.
- Finger of Death retains seven d8 plus 30 at higher slots and ordinary save/damage/death handling. The approved damage-only adaptation creates no zombie or extra actor.
- Eyebite's three choices retain their actual conditions: damage/assistance wakes Asleep; Sickened penalizes attacks and ability checks without penalizing saving throws; Panicked uses paid Dash/movement and source-specific Frightened contributions. Shared Frightened membership preserves independent source visibility, movement directions and cleanup. The casting marker's ten intervals own the repeat action and linked victims.
- New passive save/check data remains below spell owners in the import graph. No late import, reflective fallback, separate spell executor or new framework was added in the reviewed changes. Existing unrelated code elsewhere in the modules is not certified by this statement.

## Verification

After the final correction, independently ran:

- `uv run --no-sync python -m pytest -q tests/engine/test_spell_handoff_necromancy.py tests/engine/test_telekinesis_landing.py` — **90 passed in 16.21s**.
- `uv run --no-sync pyright dnd/spells/necromancy.py` — **0 errors, 0 warnings**.

Two intervening attempts could not collect because the concurrently edited `HeroesFeastBuff` temporarily lacked its required authored description. The successful final run occurred after that independent edit was coherent. These transient import failures were not hidden or solved by modifying the other packet.

Final correction pins: `dnd/spells/necromancy.py` SHA256 `46b7f39a33018d6e88c8775708ce257ae85cc8a1cea315dfd47fc5dd57a42bf3`; test file `7003b1e3cb60a11274e69073a6ed1700e99815040d3e60f3923730b2dff1b69d`. Shared reviewed source pins: `dnd/conditions.py` `9191a7494d1487dbfd506d0dcd3a3fde93944d54e327cbf024f5913203db3556`; `dnd/blocks/abilities.py` `79e321da6519a61cbe473afaa2f7839a0532f3faff7095c1d212445b316304ad`; `dnd/blocks/health.py` `9a8e88e9a4fa248b06c134d48200738448000572948826b935270bc16f2f9430`; `dnd/entity.py` `4fb39336f316d6e6b16aa14d25cf77f5e1cf30cee7e47adb48548f0ffb6cc066`.

No imports of artwork, rendering jobs or external chats occurred. Root review remains the only required review action for the authored correction in this checkpoint.

## Root verification of delegated correction

Root independently read the declaration/protection/save paths and the regression
cases, then ran the complete necromancy file plus importer checks:62 passed,
`/tmp/dnd-root-necromancy-review.log`. The Eyebite correction is approved within
this native checkpoint. Presentation and remaining packet3 spells are pending.
