# Final summoning / Fly ECS and event review

Reviewer: `summoning_events_items`. Date: 2026-10-04.

## Verdict and exact source

**APPROVED within the independent source scope below.** No remaining concrete ECS, import-DAG, event-ownership, or recorded-lifecycle blocker was found. The final completion and subsequent visual correction sections record the validation reconciliation and latest 134-file snapshot; they supersede earlier chronological pending notes. Pixel approval remains limited to the cases and samples explicitly recorded below.

The final source manifest is `.runtime/summoning-final-acceptance-20261004/source-final-snapshot.json`, SHA-256 `8059df6cbab94bafb519a18fc7faba0b6615a34d241a19fb6b6f9e08e83b4585`. Its base is `cd6d4ec363c0640595ec1f9b1b6ad9cda11baaef`. All 119 listed current file hashes matched the manifest when checked for this report.

This preserves the earlier combined source verdict on `source-review-snapshot.json`, SHA-256 `491e7f7968fa30cddb67432589951f39bdeb8f4cda8d7bc826f22b5dd72bbbb3`. The final manifest changes capture/test helpers, adds the reviewed Fly draft and passive trait rows, and includes the combat-demo seed correction. The reviewed renderer/native packet code is unchanged from that earlier frozen review. The 119-file hash check identifies the snapshot; it does not expand independent review to every test/helper in the manifest.

## Independence and scope

Independently reviewed:

- A: native lethal ordering, existing event phases and atomic retirement boundaries.
- B: shared flight trajectory, lift, pose registration, support elevation and reaction continuity.
- C: source-owned condition appearance, original wings/wind composition and import wiring.
- D: lifecycle presentation, retained departing pose, shared scheduling/drawing, palette replacement and phase/condition data; the separate S1 source-hand cast path.
- E: native Goblin/item/action ownership and shared body/cast integration, as reviewed in the preceding packet reviews.

**Authorship exclusions:** this report does not independently approve my own player-fact/projection completion (`game/player_facts.py`, `game/player_projection.py`, `game/presentation.py` portions), initial-condition `behavior_id` preservation (`dnd/types/actor.py`, `dnd/core/base_conditions.py`, `dnd/actor_projection.py` portions), or summoning original-media importer/registrations (`devtools/import_summoning_media.py` and its authored media data). Those portions require the other reviewer's verdict. This report also does not turn earlier authored scenario work into an independent scenario review.

Only this report was edited during the final review. No production edits, test runs, rendering jobs, or new art were performed. Video decoding and temporary frame extraction were used to inspect existing recordings.

## Event and ECS findings

The reviewed design keeps native gameplay in its existing owners and presentation in the existing client traversal. There is no species-specific event bus, simulation executor, anatomy registry, or separate rendering scheduler. Passive recipes and cues carry authored data. Imports remain through the existing low-level schemas, condition/body/media helpers and compositor.

Lethal summon retirement is triggered at the `TAKE_DAMAGE` pre-completion boundary, after native damage consequences can produce witnessed injury/blood. Existing `DEATH` and `INSTANT_DEATH` paths remain. Native retirement is still completed before a subsequent action can run. The presentation does not restore a removed gameplay actor merely to finish a death or departure image.

The D retained-pose blocker is resolved. `bind_lifecycle` selects state before the exact same-actor terminal `ConditionRemoval` parent, which owns cleanup. It does not infer the cause from a name or missing actor. The retiring cue keeps pre-cleanup condition membership; `retiring_pose` applies `condition_body_pose`; `ActorPose.appearance_override` prevents the cleaned current actor map from overriding that membership. The placed contact contributes geometry only, so it cannot restore older HP/life state. This preserves Prone during dismissal while allowing a genuinely committed death pose to finish.

Lifecycle presentation consumes permitted player facts and contacts. The reviewed arrival/departure/bond route uses existing typed facts, with ordinary `CLOSED` cleanup silent. Terminal departure accepts the actual expired/dismissed/defeated/sustain-lost causes; loss of sight alone cannot become departure. No native entity lookup supplies undisclosed render identity. Original media tails remain on the existing retained media path: only the required body interval joins action timing, and the remaining media tail does not block the next action.

Flight uses disclosed committed movement edges and the existing movement clock. Rejected/unknown edges do not become successful travel. Lift is continuous across adjacent steps, support changes preserve clearance, paused reactions retain the airborne placement, and actual action/hurt/death bodies retain priority over an airborne idle replacement. Sparse measured registration is explicit rather than guessed.

Condition-owned modular wings do not occupy or remove the real backpack item, and native-wing rigs do not receive an extra modular pair. Condition removal retains source ownership. Wind is composed with the existing actor image and receives the same world clipping. Color treatment uses palette replacement and bounded glow while preserving source alpha, not legacy multiplicative recoloring.

S1 keeps the accepted original cast pages and the established release clock. Source-hand placement follows actual body facing; camera-facing media selection is separate. Fixed caster clip accents keep their existing shared override behavior. No second summoning cast event or duplicate source preparation track is introduced.

## Final data delta

| File | SHA-256 | Bounded result |
| --- | --- | --- |
| `game/data/condition-recipes.json` | `c33fab4ac8ae45cfcb0c8aa21b5ed0902c1703faeca9957b39a5d21b9704d280` | Four added passive traits are neutral state-only rows. |
| `game/data/support_conditions/bindings.json` | `2e052102c03b1daaf64f596e9dc881c5ea0a7a2e724ef9d2a26bb8718f776872` | Exact `spell.fly` reference, matching the draft. |
| `game/data/support_conditions/fly-draft.json` | `20355efae93f11ce200ce349d891f7176ec01bd97907c6748625291f37f2c940` | Existing Special1 gesture; no added hand/effect media. |

`trait.innate_flight` and `trait.magic_resistance` use the SRD trait pack; `trait.attack_hit_save_rider` and `trait.keen_perception` use `content.neurodragon`, matching `dnd/content_system/condition_definitions.py`. All four rows have alpha 1, no body/equipment/media/effect layers, disabled feedback and zero application/removal duration. They do not create a second aura or rule handler.

The existing bundle `*-draft.json` discovery loads the Fly program. Its Special1 release frame 11 follows the neighboring support-cast program, optional hand/aura/slash fields default to absent, media/effects are empty and recovery is disabled. The shared body-action route places native condition children at the authored effect anchor once. The Fly condition remains the sole wing/wind owner. The combat-demo change is only seed 17 to 58 for a first nonlethal hit against the current 7-HP Goblin; it does not alter native damage rules.

## Actual footage reviewed

Earlier completed run: `.runtime/summoning-final-acceptance-20261004/runs/20261003T225450Z-2af445`.

| Case | Actual MP4 samples (seconds) | Observation |
| --- | --- | --- |
| `fly-window-solid-neighbor` | 1.4375, 1.625, 1.8125, 1.875, 2.0, 2.1875 | Four camera views show body/wings hidden by solid panels and visible through the aperture. |
| `fly-window-solid-neighbor--recipient`, `--neighbor` | 1.625, 1.875 | Same clipping result with distinct subjective floor/contact views. |
| `innate-huntsman-wing-devil`, `innate-fellwing-devil` | 1.9375, 2.09375, 2.3125 | Raised native bodies remain registered above floor shadows; no added wing pair or planted running animation. |
| `fly-lifetime-modular-backpack` | 0, 1.0, 1.75, 2.3125, 3.0 | Temporary cyan wings appear and leave; the real backpack remains. |
| `fly-lifetime-wolf` | 1.0, 1.75, 3.0 | Held non-winged body and wind follow flight; wind is absent after removal. |
| `fly-lifetime-huntsman` | 1.0, 1.75, 3.0 | Native wings remain after Fly removal without a duplicate pair. |

These are decoded MP4 frames, not posters. Extracts are under that run's `review-events-pixels/`. Trace samples corroborate continuous 0→24→0 pixel lift over committed movement spans (wall scene 1375–2208.333 ms; Huntsman 1781.25–2406.25 ms; Fellwing 1781.25–2281.25 ms). There is no per-step lift reset in the sampled motion.

**Wind-wall evidence clarification:** the modular wall case does contain both Fly wind layers; modular compatibility does not filter them out. `resolve_condition_appearance` keeps the layers, and `compose_condition_layers` combines their registered media with the body before common world clipping. The actual footage shows the combined actor appearance at the wall without visible spill through solid panels. The pale wind is much less distinct than the cyan wings and partly overlaps labels; this is useful composite-occlusion evidence, not an isolated wind-mask measurement. The previous statement that no wind-wall case existed was too broad. No new capture is requested absent a demonstrated defect. The path runs along the wall, so these clips establish occlusion, not successful physical traversal through a window.

The older run records missing Fly cast-binding diagnostics and passive-trait recipe gaps. Its movement/drawing evidence carries forward only for the unchanged presentation paths; it is not evidence for the newly added casting gesture.

Final run: `.runtime/summoning-final-acceptance-20261004/runs/20261003T231132Z-2970cd`.

- `summon-wolf-defeat`, decoded at 7.8, 8.4 and 9.4 seconds: visible lethal blood and the dying/dead body precede terminal departure media; residue remains after the summon body disappears. All four camera views were inspected. Its completed trace reports no gaps.
- `summon-fey-control`, decoded at 8.9 seconds: the same blue Fey Jaguar remains after control loss and acts near its former caster. Material and identity remain consistent. Its completed trace reports no gaps. The frame alone is not used to infer native targeting authority.
- Updated `fly-window-solid-neighbor`, decoded at 0.875, 1.375, 2.55, 2.8, 3.1 and 4.1 seconds: the visible Special1 cast precedes Fly appearance, the shifted movement retains the reviewed solid-panel/aperture clipping, and the temporary wings are absent after removal. All four camera views were inspected. No duplicate hand/effect preparation is visible. Its completed trace reports no gaps; MP4 SHA-256 is `40efba95cb3e9ff804a1af7ef95ce1590b8797f49b980bfad8c2f928b30589ac`.
- Updated wall `--recipient` and `--neighbor` clips, both decoded at 2.8 seconds: the same intermediate clipping remains correct across all four camera quadrants and their distinct subjective views. Both completed traces report no gaps. MP4 SHA-256 values are respectively `2b4fa6acc961d0587a55926556105f22ada0979f71ee7164e579a9008813837e` and `2c7eced5346fd5524ce7207aa52072aa4b9c447ecbbb3291bd820c99884d74a9`.

The updated wall trace contains one `spell.fly` body cue with empty `cast_layers` and one recipient Fly condition application. The cast begins at video 375 ms, releases at local 916.667 ms (absolute 1291.667 ms), and joins the condition's existing 900 ms application interval. Flight then runs at video 2312.5–3145.833 ms; native concentration removal begins at 3375 ms and finishes its existing 700 ms visual removal interval. This verifies the new data route and timing rather than borrowing the older run's missing-gesture footage. Later final clips remain outside this bounded pixel approval until separately inspected.

## Verification boundaries

Read existing receipts, without rerunning them: `/tmp/lifecycle-retained-pose-check.log` records 52 passing checks in 27.11 seconds; `/tmp/final-phase-types.log` records zero errors and warnings. These corroborate the source review rather than substitute for it. Parent owns full-suite reconciliation, the remaining final gallery, final source acceptance and the independent reviews of the authorship exclusions.

## Final fixture and test delta — independent approval

**APPROVED.** The acceptance manifest `.runtime/summoning-final-acceptance-20261004/source-acceptance-snapshot.json` has SHA-256 `138f1f2106ec918be0738568cc21a27048e5f3080186719ebebe1d03c974e2cd` and lists 128 files. All 128 current hashes matched. Every one of the prior 119 entries is unchanged. The nine additional entries are eight test files and the review catalog fixture; this delta adds no production mechanism or rendering change.

Reviewed the complete current diffs for:

- `tests/game/test_damage_animation.py`
- `tests/game/test_downed_blood_playback.py`
- `tests/game/test_encounter_completion.py`
- `tests/game/test_encounter_layouts.py`
- `tests/game/test_forced_movement_playback.py`
- `tests/game/test_gameplay_history.py`
- `tests/game/test_lifecycle_history.py`
- `tests/game/test_lifecycle_playback.py`
- `devtools/animation_review/catalog.json` (parsed comparison: only `walk-downed` gains explicit seed 27).

The low-HP opportunity fixtures now select the canonical handaxe's noncritical 5-damage hit against 4 HP, retaining raw -1 HP and normalized 0 HP where death saves apply. Explicit packet/blood assertions were added. The tests still require `DYING` with death saves, `DEAD` without them, a noncritical blood release, an uncommitted interrupted Step and no `DeathEvent` in the DYING branch. A critical or massive-damage death was not substituted to obtain a passing test. The playback floating-number expectation now agrees with the asserted native 5 damage.

Encounter completion and three close layouts now require the actual round-1 ending. The tests additionally assert the movement-owned Fighter reaction's 13 damage and -11 resulting HP, one encounter-end fact, dead hostiles, no current actor and closed input. The diagonal layout still explicitly expects round 2 with an active player. The dead-mover history test changes the expected terminal boundary while retaining its one undisclosed turn, copied native disclosure metadata, dead actor absent from senses, no projection dispositions and full replay-equality assertions.

The forced-movement test now expects the original Goblin rig's explicit `TakeDamage` brace anchor at frame 5; modular cases retain frame 3. This was checked against `game/data/rigs/goblin01.json` and `game/data/neuroclient/forced-movement-profile.json`, not inferred from test output. The test continues to verify held body pixels during travel, release at the following authored frame, the committed location, timing, and absence of latest-state leakage.

Existing receipt `.runtime/final-client-fixture-review/receipt.json`, SHA-256 `9cc416b43793124587f9621ac3c9a46af769076dd49a87d68ed29dbb2826978f`, accounts for 29 distinct cases: its first complete six-file run had 28 passes and one stale number expectation; the final complete lifecycle file then passed all 10 cases after the explicit 6→5 correction. It reports zero typing errors/warnings and no production/helper/frozen-native-input edits. Separately, `/tmp/final-phase-displacement-history-reconciliation.log` records 16 passes in 28.20 seconds for the two entire forced-movement/history files. These are existing focused receipts, not a newly run suite. The full client suite and remaining gallery were still in progress; this addendum makes no full-suite-completion claim.

## Numerical midpoint assertion — independent approval

**APPROVED.** Completion manifest `.runtime/summoning-final-acceptance-20261004/source-completion-snapshot.json`, SHA-256 `76528a429f0acae75f2870159c36dfca92219359441211e37843987857fcc4a3`, lists 129 files. All hashes matched; all 128 prior entries are unchanged. Its sole added file is `tests/game/test_movement_routes.py`, SHA-256 `404deee398a9f6b754331921eb908bf0bf5e4d902ef1d2a716a9032328bed19c`.

The entire diff changes only the successful multi-cell jump's midpoint grid comparison to `pytest.approx(..., rel=0, abs=1e-9)`, separating but preserving the exact `midpoint.lift_px == arc` assertion. This admits floating-point arithmetic such as 2 versus 1.9999999999999998 after a fractional-duration reaction. It does not tolerate a meaningful grid displacement. Exact reaction hold/resume, arc height, final destination, zero final body lift and other timing/body assertions remain. There is no production or fixture change.

Read existing `/tmp/final-phase-movement-routes-reconciliation.log`: the whole file passed 22 tests in 21.57 seconds. No tests were run by this reviewer. The full client suite and final gallery were still progressing when this addendum was written; final aggregate receipts remain the parent's responsibility.

## Corrected height recording — bounded pixel approval

**APPROVED for the corrected recording.** Inspected actual decoded frames of `height-correction/runs/20261003T233842Z-2d43aa/cases/fly-modular-rise-descent/clip.mp4` under the final-acceptance directory. MP4 SHA-256: `da22b56f01ffb17a63f95d7975d48905c34f075369f6283f3766e381e8b882cb`. This is a separately captured native case on the existing `battlefield.visual_vertical_seam` terrace, not a rendering of the failed stair-scene input.

The public input SHA-256 `643d0a062eed3cb12c24d63f7b26132174733e0467f3b970e43f26458d218784` matches `height-correction/receipt.json` (receipt SHA-256 `8e3479bf91d6d2ef15f1527f6b64bbd745fe0ebf17d9277d452ea3d7db32a1c0`). The input explicitly discloses the replacement of the unsupported earlier stair arrangement. It records route `(13,20) → (14,20) → (13,20)` and the actual native support changes `0 → 2 → 0`, with two lineages and ten nodes. This preserves a visible audit trail instead of claiming the earlier scene passed.

Reviewed all four camera quadrants at MP4 seeks 0.4375, 0.5, 0.5625, 0.625, 0.6875, 0.75, 0.8125 and 0.875 seconds. The body and wings clear the terrace edge on ascent, settle on its raised surface, rise again for the descent, and return to the lower floor. The terrace correctly hides the grounded body from the far-side cameras while the near-side views retain it. No body/wing clipping through the raised solid face, misplaced landing, duplicate body or stuck elevated pose was observed.

The trace corroborates ascent at video 375–583.333 ms and descent at 625–833.333 ms, each with 208.333 ms native movement duration. Intermediate support heights interpolate between 0 and 2 while the clearance lift reaches 64 pixels; lift settles to zero at each committed endpoint. The completed clip has 67 encoded frames, all recorded checks passing and no binding gaps. Those checks support, rather than replace, the pixel inspection.

The 129-file completion source manifest was checked again and still has no hash mismatch. No renderer, map or other production edit is part of this correction. Approval permits this explicitly identified replacement clip to join the 68 original successful recordings; it does not change the original failed-input result or claim that the full client suite has finished.

## Composed standard gallery — provenance and export approval

**APPROVED for composition integrity and the standard export contract.** Final gallery directory: `.runtime/summoning-final-acceptance-20261004/runs/20261004-final-acceptance`.

| Artifact | SHA-256 |
| --- | --- |
| `composition-receipt.json` | `590bbdecfd2af3158bb7f8e760f5ad0f5ee13ba803f9442100dd91a3a073d34e` |
| `manifest.json` | `02a4ebd5ef06445893ddfd51fa63dda1cb43ba34a44643d72003511578b3fe92` |
| `gallery.js` | `c7b3123e6db090984f4effbde1136842ecb6e2b0792773dfa445b5d0fe78a330` |
| `index.html` | `774915d8ca8ff786df5dab78692b16c1fe529ca2a069ad43c5ef35ba4c7c23bc` |

Independently compared all 69 packaged cases against their actual source files, rather than relying on the composition script's assertions. Exactly 68 resolve to `20261003T231132Z-2970cd`; only `fly-modular-rise-descent` resolves to the separately reviewed `20261003T233842Z-2d43aa` height run.

For every case, all parsed trace values outside `run`, `source_run` and `source_trace` are identical to the original trace. This covers the complete events/lineages, heads, per-frame states/draws, observations, timings, checks, gaps, camera data and source metadata. `source_run` equals the original run envelope; `source_trace` resolves to the actual original file and its recorded SHA-256 matches. All packaged trace hashes match the composition receipt. Case metadata is unchanged apart from the declared source provenance and relative media/input links.

All video, poster and input links resolve directly to the correct original files. Video/input hashes match the receipt; source manifest hashes also match. No re-encoding, input rewrite, check deletion or event/frame modification is hidden in the composition. The copied stylesheet matches its source byte-for-byte. Gallery JavaScript matches both the original run and `devtools/animation_review/gallery.js` byte-for-byte. HTML changes are exactly the two advertised heading/explanation replacements.

The standard export checks were independently verified for every packaged case: derived trace run ID equals the composed manifest run ID; trace/case/input IDs agree; the input remains schema-version 1 `dnd-animation-input`; and its original `captured_at` equals the trace's input capture timestamp. All capture timestamps parse as timezone-aware instants and precede composition creation. The retained input capture range is `2026-10-03T22:31:37.485423+00:00` through `2026-10-03T23:38:23.793158+00:00`; composition creation is `2026-10-03T23:47:04.353834+00:00`. Existing export frame selection still reads the unmodified frame timestamps. This is source/data validation of the existing export path, not a claim of a browser button-click test.

Independently recomputed totals match the receipt: **69 cases, 35 experiments, 1,563 passing checks, zero gaps, 17,945 frames and 560,781.25 ms**. Every case is passed and every listed check is true. These counts establish recording/composition completeness; they do not imply that this reviewer manually inspected all 17,945 frames. Actual pixel coverage remains the explicitly listed samples above. The full client-suite reconciliation was still pending when this composition approval was added.

## Final completion evidence and independent verdict

**APPROVED within the stated independent scope, with no unresolved review blocker.** This closes the previously pending validation reconciliation and preserves the authorship exclusions above. It does not convert the original failing runs into an uninterrupted passing suite, expand the bounded pixel sample, or independently approve this reviewer's authored implementation portions.

| Final artifact | SHA-256 |
| --- | --- |
| `.runtime/summoning-final-acceptance-20261004/source-final-acceptance-snapshot.json` | `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3` |
| `.runtime/summoning-final-acceptance-20261004/validation/reconciliation.json` | `d13b9f089b36deb54902cd95e77970bc7c0f7a1e0a3ea49906cf89cbb10dc17f` |
| `validation/final-resolution-rig-review/receipt.json` under that directory | `d7f70484b2c8729f1021d0d46b537f3b02edc55cf6e1617641f410204030726e` |

All 131 current file hashes match the final source manifest. All prior 129 entries remain unchanged. Its only two additional entries are `tests/game/test_resolution_contract.py` (`b6a71476b4ddc93bf37d8dccdb05122fb940a497a8506bd7cc2a005d1245671d`) and `tests/game/test_rig_body_contexts.py` (`6ed7893586bba602e20991de9dced73e76f2fa17e71592c3084bf234a1c2ae1b`). Their complete diffs were independently read:

- The multi-result playback fixture now starts from native seed 10's nonlethal one-damage longsword hit against the current 7-HP Goblin. It explicitly checks the first result ends at 6 HP before adding its existing synthetic second result ending at 5 HP. The previous seed 17 hit already killed that actor and carried a terminal life fact, making the synthetic continuation inconsistent. The test retains exact result ordering, one attack/body ownership, injury timing and repeated-seek state equivalence.
- The rig selector fixture records and asserts the Goblin's existing `goblin01-physical` profile before inserting its root-rig-only override. It then requires the Goblin to retain that actual profile. Exact rig/item/source/outcome checks, the negative selectors, authored contact timing and native after-state equivalence remain. It no longer incorrectly expects the modular root profile on the explicitly bound fixed Goblin rig.

The preserved native-contract probe supports these fixture corrections. The existing complete two-file rerun passed **50 tests in 34.63 seconds**. No production mechanism or rendering change appears in this final delta.

Independently verified every SHA-256 entry in `reconciliation.json.evidence_files`, then checked the saved collection, prefix log, complete remainder JUnit and logs, affected-file receipts and passing rerun summaries:

| Coverage | Preserved original outcome | Reconciliation |
| --- | --- | --- |
| Native: 2,840 cases | 2,838 passed; 2 failed | Both affected native files passed all 10 cases. |
| Client prefix: 884 distinct cases | 875 passed; 9 failed | All nine failure IDs map to passing complete-file reruns. |
| Client remainder: 2,344 distinct cases | 2,326 passed; 18 failed; zero errors/skips | All 18 failure IDs map to passing complete-file reruns. |

The collection contains 3,228 unique client node IDs. The JUnit contains 2,344 unique IDs from that collection; its complement is exactly the contiguous first 884 collected cases. Independently parsed prefix outcome markers yield 875 passes and nine failures for those 884 cases. The three subsequent passing combat-play cases in the interrupted prefix log also occur in the complete remainder and are correctly excluded from the prefix total. The ordinary diagnostic text `E=42 R=42 D=42` is not treated as test outcomes. The derived prefix failure IDs and JUnit failure IDs together exactly equal the 27 mapped client failures, with no missing or extra map entry.

The original native log retains its two named failures, and the complete remainder log retains its **18 failed, 2,326 passed in 2,593.55 seconds** summary. Passing affected-file logs record 10 native cases and client groups of 76, 5, 16, 22 and 50 cases. The separate fixture receipt accounts for 29 distinct cases through its initial 28-pass/one-failure run and the final whole lifecycle-file rerun of 10 passes. Reruns are not added to the unique collected totals. This establishes **2,840 native plus 3,228 client cases accounted for after documented corrections**, rather than claiming a fresh single run of all 6,068 cases passed without failures.

The final typing log reports zero errors/warnings for `dnd`, `game` and the changed animation-review/import tools. Separately compared the final two-file typing logs against the exact pre-edit copy: after removing only paths and line/column positions, all diagnostic messages are identical. `test_resolution_contract.py` retains ten pre-existing diagnostics; `test_rig_body_contexts.py` has none. No new diagnostic was introduced, and no repository-wide test-code typing-cleanliness claim is made.

The previously approved 69-case composed gallery remains supported by its original video/input links, identical event/frame/check payloads, explicit height-case replacement provenance and standard export identities. Its recording completeness and the actual pixel samples remain separate evidence. No additional test, renderer invocation, production edit or art generation was performed for this final review; only this report was updated. The parent retains responsibility for final task acceptance and combining the independent verdicts for the excluded authored portions.

Subsequent user-directed delta: after this reconciliation review, the parent reported a requested Wolf appearance-scale increase from 1.30 to 1.80 and planned replacement of three Wolf scenarios/six observer clips. The approval above is bound to the recorded 131-file snapshot and existing gallery. The new scalar change, replacement pixels and revised gallery provenance remain pending their own bounded review; they are not covered by this verdict.

## Final Wolf and terminal-death correction — bounded completion

**APPROVED within the independent scope stated above; no remaining concrete blocker.** This closes the preceding pending visual correction. The final user-directed Wolf appearance scale is **2.00**, superseding the intermediate 1.80 proposal. Current source is bound to `.runtime/terminal-death-review-20261004/source-final-snapshot.json`, SHA-256 `96605c30162fc3e2100d12d19d75a844a0083d94299d7d2b68185903aead49e6`. All 134 listed file hashes matched. The initially omitted `game/play.py` and `dnd/monsters/srd_roster.py` were added to the inventory without further code changes.

The shared terminal `death` body role consistently selects the original clip for duration, sampling, resting bodies and media loading. Ordinary Prone, DYING, STABLE and recovery retain their existing `Die` behavior. The latest explicit human direction governs already-down actors: Prone/DYING/STABLE terminal transitions settle at the selected dead rest frame without standing up to die. An ongoing fall using the same clip retains its original clock and completion; a distinct terminal clip settles at the death boundary. Upright terminal transitions play the full selected clip. The earlier review finding that repeated projectile death could restart an existing fall is resolved by the current sampling guard and retained action join. Condition-resolved departing/resting poses are also loaded correctly. These changes reuse the existing event traversal, passive body context, clip layers and compositor; no native explosion damage, new event authority or additional scheduler was introduced. Wolf scale changes no native size, footprint, stats or other species.

Original-art evidence was independently checked: all 21 binding hashes and all **48 installed PNGs (9,505,401 bytes)** match the installation receipt and the exact original ZIP member bytes. Six demon terminal banks retain their original body/shadow/Effects layers; 15 Goblin banks use original Die2 body/shadow. Riders 11/12 retain their available original bank. Nonterminal banks remain intact. Installation receipt SHA-256: `27fd50942cc9643bd19bb9c9ed44ee78e6de8e0509bbc430c315bc4fe780d6f1`; validation receipt: `b139e7e3e9218a221e5e2df8348296fe66d71b3d1879c40c192b67b7c8de625f`. Known source cell-edge contacts remain source limitations, not newly generated pixels.

Reviewed focused receipts include **75 passed** in `prone-death-no-refall.log`, **87 passed** in `terminal-death-regressions.log`, and zero production typing errors/warnings. The earlier 107-pass receipt and original failure logs remain preserved. These overlapping groups are not summed, and the previous full-suite reconciliation is not represented as a fresh full-suite run of this correction. Native lifecycle regressions cover current-Prone defeat/instant-death without a new fall; existing projectile regressions cover continuation of the same fall. Receipt index SHA-256: `5852706fe252c2002d3a87560a6beee7ae80102a09bb4213f00a9a1a37b4b673`.

Actual decoded Wolf footage from `wolf-original-200-percent/runs/20261004T001450Z-be467c` was inspected for incoming injury, Prone, standing, ordinary death/corpse, summon defeat/departure, and Fly application/removal, including paired observer views. Enlarged body/shadow registration remains sound; witnessed blood precedes departure, an ordinary corpse persists, and Fly removal grounds the body cleanly. Independently inspected terminal footage includes Dretch, Corrosive Dretch and Dread Dretch downing/death/rest samples from `terminal-death-review-20261004/runs/20261004T002155Z-c5ee42`; the intact nonterminal pose, full upright terminal animation, persistent original terminal effect and separate special wound profiles are consistent. The other reviewer separately completed the remaining demon/Goblin pixel coverage; this report does not claim their observations as its own. The current-Prone no-standing transition is supported here by source and native regressions, rather than claimed visible in these sampled upright-death recordings.

Composition/export verification is complete for `.runtime/summoning-visual-corrections-20261004/runs/20261004-wolf-and-death`. All 24 parsed traces preserve the complete original payload outside the declared run/provenance envelope. Original video/input links and hashes, source trace hashes, case identities and capture timestamps agree; gallery JavaScript is byte-identical to the standard implementation. No event, frame, check or native input was rewritten. Independently recomputed totals are **24 cases, 934 passing checks, zero gaps, 8,684 frames and 271,375 ms**. This verifies recording integrity and the standard export data contract, not a browser button-click test or manual inspection of every frame.

| Final correction artifact | SHA-256 |
| --- | --- |
| Combined `composition-receipt.json` | `a0671451b72c7b34662751d3dd1419064a927a137b0ed7f90d13159ffa002004` |
| Combined `manifest.json` | `51d2cec790a5079bd1848a4f403ee3045ab9b3c12759c76fbebabcb9d1572f01` |
| Combined `gallery.js` | `c7b3123e6db090984f4effbde1136842ecb6e2b0792773dfa445b5d0fe78a330` |

All authorship exclusions remain. Only this report was changed for this final review; no additional test, render, production or artwork work was performed. The parent retains combined acceptance responsibility.
