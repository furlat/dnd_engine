# Terminal fixture reconciliation

Root assigned the failures from `/tmp/dnd-spell-game-preflight.log` in
`test_animation_rigs`, `test_animation_draw`, `test_combat_history` and
`test_combat_play`. No production behavior changed.

The actual accepted `game/data/rigs/goblin01.json` selects the original `Death`
clip for the death role (15 frames at 12 FPS). Its `Die` clip remains separately
available for recoverable Prone/downed poses. The old tests required the shared
`Die` name despite that accepted terminal binding.

Corrections preserve their original assertions:

- Rig comparisons allow the authored terminal clip name to differ while still
  requiring identical frame/facing, caster timing, contact feedback and vitals.
- The hypothetical nine-frame slow death fixture alters the selected `Death`
  metadata, proving that exact recipient duration and last frame drive playback.
- Combat history/map fixtures require actual Goblin `Death` and retain all HP,
  native ownership, state reduction, initial/final frame and seek assertions.
- The deleted-source-links preload fixture requests the clip actually sampled
  by its already-loaded lethal timeline. It still deletes every resource link
  and proves that all later frames come from retained session media.

All four complete files: **45 passed in 71.67 seconds**. Permanent log:
`directed-outcomes-20261004/terminal-fixtures.log`. This is fixture reconciliation,
not an independent implementation approval.

The root authorized explicit neutral-field migration of the three destruction
archives after confirming that today's same-owner native implementation cannot
regenerate their intentionally older replacement-owner semantics. The same two
inherited fields were also added to four legacy-completed-actions rows exposed
by the full affected run. No codec was relaxed.

Only new neutral facts were supplied: intact remains / zero-HP disposition, no
removed volume, no source condition, no suppression tokens, no propagation, no
retained spell origin or Antimagic exception. Every previous JSON value, list
order, event UUID and intentionally absent action receipt is preserved. The exact
per-family fields/counts and before/after SHA256 are recorded in
`directed-outcomes-20261004/legacy-fixture-migration.json`. Original compressed
archives were also copied to `/tmp/dnd-legacy-fixtures-original-20261004/`.

Strict passive decode passed before writes. Complete `test_device_destruction`
and `test_recorded_history`: **76 passed in 76.03 seconds**. Permanent log:
`directed-outcomes-20261004/legacy-fixtures-final.log`. Earlier 72-pass/4-failure
run identified exactly the additional completed-action fixture omissions.

