# Player UI plan — independent anti-slop review, 2026-10-05

Status: **approved as a planning contract; no unresolved anti-slop blocker**.
This is a fresh review of the rewritten `PLAYER_UI_PLAN_2026-10-05.md`, all four
linked studies, and relevant source owners. It does not inherit the first plan's
approval. The three findings from the initial receipt were corrected and
rechecked in the final files listed below. This review does not authorize
production work or claim implementation or visual acceptance. No production or
test source changed; no tests were run. The log study's history limit was aligned
to the integrated plan's explicit 10,000-row decision.

## Resolved findings

1. **Registered presentation has one owner.** Main plan §9 now keeps registered
   creature/item fields, including a missing `portrait_key`, in their existing
   descriptor/ledger. The UI document accepts only direct semantic IDs with no
   descriptor, authored portrait choices and UI keys; duplicated ContentRef
   rows are forbidden. Resolver kinds select an exact authority without runtime
   name probing or fallback-ledger searches. An explicit controlled-player
   portrait preference overrides only the default portrait. This closes the
   earlier duplicate-authority ambiguity without retired class factories or
   fabricated ContentRef hashes.

2. **Space has one live-input contract.** Main plan §3 and targeting study §4
   and its acceptance matrix now agree: Space ends a turn only in neutral,
   active-human, settled live play; it does nothing during targeting, modals,
   AI turns or history. Enter/Confirm commits selections. Pause is review-only.

3. **Log absence remains absence.** Main plan §7 now permits a cancellation or
   interruption row only when a native entry exists. The acceptance paragraph
   explicitly checks intentional absence for all listed cases, including
   state-only destruction, transfer and summon outcomes: `combat_log is None`
   never becomes a row. Counterspell's actual reaction entry remains visible.
   This closes the route back to the removed fallback narrator.

## Findings corrected during this review

The updated main plan now removes speculative minimum/exact-count allocation
machinery and uses `selected_only | fill_primary`; preserves Aid/Longstrider/Fly
repeat permission; specifies exactly one form and one destination per summon;
and replaces the misleading multi-summon acceptance phrasing with successive
ordinary casts. These match the targeting study's actual native behavior.

Section 6 now names one complete-selection preview, its result and purity
requirements, typed variant facets, depleted-rank exposure, the actual existing
unexposed ability/mode variants, and the two explicitly identified count-hook
defects. It no longer treats all of these as cosmetic widget choices. The plan
requires approval for these bounded source repairs and makes no implemented
claim.

The plan expressly defers full gameplay persistence and rejects a character-only
substitute. The character study's §§3/7 now replace its earlier conditional
format proposals with the same definitive boundary. Creation, in-session
inventory and passive recording remain distinct; no misleading Save/Continue
control or new mechanics restoration framework is included.

The log parser now supports its documented simple tags and bold syntax with
literal fallback for malformed/unsupported nesting. Its earlier unnecessary
“preserve nested colour text” requirement is removed.

## Accepted boundaries

- **One log:** ordinary canonical rows come from existing projected PlayerNodes;
  embedded `sub_entries` and `per_target_logs` are not additional row streams.
  Equal strings never identify an event. The standalone immunity append repair
  is necessary because that real producer bypasses EventQueue registration.
  The existing encounter listener captures only its explicit standalone marker,
  retains generation/index identity and adds an optional field to existing
  recordings. It does not justify a transcript, formatter or synthetic event.
- **Existing timing:** presentation groups, result identities, state commits
  and bound clocks gate text. Missing precise anchors use group completion.
  Decorative tails do not become invented rule times, and no fresh result prose
  is derived from graphics facts.
- **One selection geometry path:** carrying explicit pick coverage through the
  existing renderer cuts and painter order is a justified renderer integration.
  Hover, target selection and Alt use the same regions. The plan excludes a
  second depth resolver, secret live-world queries, shadow/VFX hitboxes and
  unlimited per-entity full-screen buffers. Actual occlusion and aperture tests
  remain required; a region type alone does not prove this behavior. The final
  window rule distinguishes foreground frame/insert pixels, a visible actor
  through a hole, and an empty admitted traversal aperture; Alt/context retains
  access to traversal when an actor occupies the aperture.
- **World actions:** source-item SELF actions and object-target actions both
  reach world context interaction. Remote operation descriptors remain
  non-executable; approach filters existing exact movement targets through
  native contact, then rediscovery admits final use. This is one pending intent,
  not a second action executor or pathfinder.
- **Stale commands:** generation plus exact row/target identity and Session's
  active-human gate are appropriate. Final admission stays native; widget
  caches and hotbar preferences confer no authority.
- **Character/resources:** source-authored build/choice/loadout records and
  native transactional commands remain owners. Sheet/resource/initiative
  extensions are detached observer-authorized values; historical playback must
  not be overwritten with a current live snapshot. No invented XP/rest policy
  or unconditional human reaction dialog is included.
- **Verification:** named native cases, record-once replay, real Pygame input,
  bounded history/cache tests and inspected gameplay imagery are appropriate.
  Source inspection, tests and visual acceptance remain separate claims. Both
  anti-slop and anti-OOP/ECS review gates are retained.

## Final reviewed versions

SHA256 identifies the reviewed content, not an implementation check:

| Document | SHA256 |
|---|---|
| `PLAYER_UI_PLAN_2026-10-05.md` | `fc290f593e6eb152614208572d453f27189b3e98b452952f4c69f386d3c43e09` |
| `UI_TARGETING_CONTRACT_2026-10-05.md` | `cbbcae33a29fb4c2c4b29605b734aaa53f18c7dee64072f454473f821bd484c0` |
| `UI_CHARACTER_FLOW_CONTRACT_2026-10-05.md` | `b088fc08112c8139c04138613a3492372a1cc806ea219de7151aab061c045d9e` |
| `UI_ICON_COVERAGE_2026-10-05.md` | `cf1561dd6054b89ad2fa8abb93b6b5eb5a981f922fc06a95e0806a0f71abeb66` |
| `UI_COMBAT_LOG_CONTRACT_2026-10-05.md` | `69b9c6dec9ee5bd293652540cccde23797eab5bc8495165c1fd9fbfc49e2a4b5` |

The reviewed proposal is bounded and source-grounded. All requested anti-slop
corrections are resolved; implementation must still satisfy its native,
recording, input, bounded-resource and inspected-visual acceptance gates.
