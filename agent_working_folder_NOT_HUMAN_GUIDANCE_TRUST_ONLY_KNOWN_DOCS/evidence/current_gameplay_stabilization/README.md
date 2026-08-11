# Current Gameplay Stabilization Evidence

These files preserve exact server-produced evidence needed by the current
gameplay stabilization manifest. They are data inputs, not a testing-surface
runner and not an implementation acceptance.

## Historical pre-fix sequence

| File | SHA-256 | Scope |
|---|---|---|
| `fireball-haste-fatal-subjective-pre-fix.json` | `103e109a205c4b216f0cdc42b4d2bf823b630443b7618312e80dc2639ffc04d1` | Exact 111-delivery subjective archive formerly retained only as `/tmp/neuro-current-subjective-replay.json`. It contains the first Fireball and Haste presentation, while the fatal subjective delivery omits the second Fireball root. |
| `fireball-haste-fatal-objective-pre-fix.json` | `0c6f1051867a876d93942b14e89955a3b8927b7512c6ce74aecf094b6e234f39` | Exact objective events 1..1105 formerly retained only as `/tmp/neuro-objective-events.json`. Events 1058..1100 contain the complete fatal second Fireball lifecycle. |
| `fireball-haste-fatal-combat-log-pre-fix.json` | `234f5be0398190b90452b26bd3ee0f652d1d49c57a70383f787915524f7aae22` | Exact paired combat-log bytes formerly retained only as `/tmp/neuro-current-combat-log.json`. |

## Nearest current production archive

| File | SHA-256 | Scope |
|---|---|---|
| `fireball-haste-fatal-objective-current-nearest.json` | `cdf0de449f30390a9f23d3d15366ed93be8c7d051d4527412d818098e400fb19` | Immutable objective artifact for game `0dbb4bb4-095a-4003-9438-eee942a6a96c`, source `8f1a39cf-7d03-433d-9459-d786d03b29fe`, generation `b1926256-6d75-4356-85b9-9cbe9e01982f`. |
| `fireball-haste-fatal-subjective-current-nearest.json` | `05dfa3c729b602b5f76ad853ed512855a6db251966575f006249b552e4fe4205` | Exact paired player archive. It contains first Fireball/deaths, Drink Haste Potion/Haste, second Fireball/death/Turn End. |

The current pair is deliberately labeled `nearest`: it does **not** contain an
Invisibility removal, so it cannot qualify the complete named
Fireball -> Haste -> Fireball -> Invisibility removal -> death -> Turn End
representative. A later complete current product artifact must be added as a
new immutable pair; these bytes must not be rewritten or promoted by prose.

## Fast-terminal reconnect fixture

`gateway-fast-terminal-reconnect-pre-fix/` preserves the exact terminal spool
from the gateway fixture that attempted reconnect after its AI companion had
already ended combat in 0.762668 seconds. Production correctly returned typed
`game_not_live`; the escaped defect was a live-reconnect test fixture that did
not remain live.

The terminal manifest is `ready.json`, SHA-256
`3f37151c6ac4b7c700a8f34aff8896ea97a28dc67dfeefdbd123fc5fe5f15128`.
Its four component filenames embed and exactly match their content digests:

- objective replay `64cf5e19f12c45aa23265fa2943ce9c4ecfdfed2eaed59b657ee78a9c357337a`;
- subjective replay `d833e6a8aa00bf98787b1c06c8616b0e98d500952538979d477d1d1409a65e14`;
- summary `d11a6a5a1f9f4871870ec7831197df61e349fee57d26e3b9f667ff36c65d037f`;
- holdings `e1e9f2403e84513932947b6c6372b571ec862518b0d5c3d7b208e327c8ed741d`.

This artifact remains a terminal/lifecycle negative. It must not be used to
weaken the rule that only live games accept reconnect/observer attachment.
