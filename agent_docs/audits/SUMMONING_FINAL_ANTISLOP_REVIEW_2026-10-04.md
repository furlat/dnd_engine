# Final summoning/Fly/Goblin anti-slop review — 2026-10-04

## Bounded verdict

**APPROVED for the agreed scope and the subsequent bounded visual corrections at the final 134-file snapshot.** The original suite/gallery reconciliation remains accepted; the terminal-death source/data and inspected correction footage are approved below. Wolf now uses the user-specified 2.00 scale, with its separate six-clip pixel review assigned to the ECS reviewer. No unresolved anti-slop source or inspected-pixel blocker remains. Historical pending statements below are superseded by the later dated addenda; passing reruns are not represented as one clean monolithic suite.

Independent review was read-only except for this audit. Existing completed MP4s were decoded with ffmpeg for inspection; no native scenario, test, or game renderer was run by this reviewer in this final pass. No production changes, artwork changes, new agents, or other-chat communication were made.

## Exact scope and source identity

- Reviewed base: `cd6d4ec363c0640595ec1f9b1b6ad9cda11baaef`.
- Final corrected source manifest: `.runtime/terminal-death-review-20261004/source-final-snapshot.json`, SHA256 `96605c30162fc3e2100d12d19d75a844a0083d94299d7d2b68185903aead49e6`. All **134** listed files matched at correction acceptance.
- Prior suite-reconciled source manifest: `.runtime/summoning-final-acceptance-20261004/source-final-acceptance-snapshot.json`, SHA256 `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3`. All **131** listed files matched again at final acceptance.
- Initial source manifest: `.runtime/summoning-final-acceptance-20261004/source-final-snapshot.json`, SHA256 `8059df6cbab94bafb519a18fc7faba0b6615a34d241a19fb6b6f9e08e83b4585`. All **119** listed source/test files matched their recorded hashes when this audit was written.
- Parent plan: `agent_docs/SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md`, SHA256 `16d93fcdd9f659867b562e454b6d6e80f3d34f3dc724d34bc82bfeff96b79a6d`.
- Required Goblin amendment: `agent_docs/GOBLIN_ROSTER_FINAL_PHASE_PLAN_2026-10-03.md`, SHA256 `f2a20d8984e88086bc32568964aa478ae8f64030a296aedd8919d7f7d4a6a03e`.

Scope remains the implemented 24 ordinary summon bodies and three summoning spells, the approved Fly presentation, injury/Prone/death corrections, accepted summoning media, and the exact 17 dedicated Goblins. The riders remain single native combatants; Pistol remains an ordinary authored weapon. This review does not authorize another spell, a mount system, additional artwork, or a general transformation framework.

## Architecture and source delta

The earlier combined source approval at manifest SHA256 `491e7f7968fa30cddb67432589951f39bdeb8f4cda8d7bc826f22b5dd72bbbb3` remains valid for its reviewed bytes. The current delta was checked against that scope:

- The four newly classified passive traits (`innate_flight`, `magic_resistance`, `attack_hit_save_rider`, `keen_perception`) have exact native binding identities and `state_only` recipes. They add no looping media, appearance change, timer, or native rule. `condition-recipes.json` SHA256: `c33fab4ac8ae45cfcb0c8aa21b5ed0902c1703faeca9957b39a5d21b9704d280`.
- Fly now has its exact binding through the existing draft loader. `support_conditions/fly-draft.json` uses the existing Special1 gesture, release frame 11, and empty cast effects/media; it does not duplicate the source-owned Fly wings/wind. Draft SHA256: `20355efae93f11ce200ce349d891f7176ec01bd97907c6748625291f37f2c940`; bindings SHA256: `2e052102c03b1daaf64f596e9dc881c5ea0a7a2e724ef9d2a26bb8718f776872`.
- The canonical Goblin fixtures now assert the actual dedicated profile, seven HP, scale 1.0, and Goblin03's actual bow/release binding. The combat demo uses an ordinary seeded first hit of four damage, leaving three HP; it does not edit HP to manufacture the intended scenario. The shared projectile endpoint assertion remains.
- The new creature spell capture helper materializes canonical entities with owned possessions, uses native encounters/controllers and legal available actions, and records actual Web/drop-concentration, Shield, and Counterspell consequences. The dispatcher and case data extend the existing capture tool. They introduce no gameplay or presentation executor. Source binding and native reaction assertions remain explicit.

The final source still uses passive data and the existing native/presentation owners. In particular:

- Summon defeat waits for the enclosing native damage consequence, preserving witnessed blood before retirement. Exact causing Death-event visibility permits terminal evidence without relaxing actor identity/current-position gates.
- Birth condition identity is copied explicitly as optional `ConditionState.behavior_id`; all snapshot overrides preserve it. Missing historical identity does not trigger a semantic-key guess.
- Observed creation, terminal removal and exact Fey control removal feed existing retained choreography. Passive lifecycle cues supply coverage and immutable terminal contact/pose; decorative tails use existing contact media. There is no second actor, event traversal, event bus, native lifetime, or playback queue.
- The stale placed-contact issue is resolved by retaining current witnessed actor state and copying only placement fields. The Prone terminal case captures appearance before the exact existence-owner ConditionRemoval cleanup, then carries the resolved retiring pose/appearance into the normal compositor. It does not restore native conditions after removal.
- Flight uses existing motion legs and admitted geometry, with held lift through reactions and measured pose registration. Fly appearance remains keyed to exact condition membership; native-wing rigs do not receive a second pair of wings. Native same-spell replacement rules remain unchanged.
- Goblin attacks/casts, original frame-registered layers, selected immutable item variants and ordinary loot stay on the existing common pipelines. No species-specific executor or manufactured source gesture was added.

No new anti-slop, ownership, duplication, or import-layering blocker was found in these reviewed boundaries.

## Lifecycle footage inspected

Run: `.runtime/summoning-final-acceptance-20261004/runs/20261003T231132Z-2970cd`.

All eight finished traces below have **zero failed recorder checks and zero reported gaps**. Recorder checks supplement the following actual pixel inspection; they are not treated as visual approval by themselves. Primary and opponent recordings were inspected through selected decoded frames, each containing all four camera panels.

- **Wolf defeat:** nonlethal blood and TakeDamage, Prone, recovery, lethal hit, retained Die pose, dissolve, and disappearance were visible in the correct order. Body and original shadow leave together; persistent native blood and the finite media tail can remain. No falling body was replaced with Idle during retirement. The observed native HP sequence is 15 → 10 → −6.
- **Fey control:** the same Jaguar UUID `32942490-f65d-4725-9c55-131b7c5dd257` remains at 13 HP through control removal. Its blue manifestation and neutral ground shadow persist. The brief bond effect occurs without despawning/recreating the body. The creature subsequently moves toward and attacks the former caster; the paired opponent frame shows the caster receiving three damage and Prone. The native attack contact retains `manifestation: fey_spirit` after control loss.
- **Fey defeat:** actual nonlethal blood, lethal feedback and the blue fallen body precede the blue-family departure. The retained body does not lose its manifestation when its native conditions are cleaned up. Body/shadow then disappear while the finite effect tail finishes. HP goes 13 → 8 → −8.
- **Mammoth:** the approved large visual scale remains consistent across arrival, movement, native tusk attack and dismissal. The original body/shadow pixels remain recognizable; no body stretching, added wings, duplicate body or residual shadow was seen. The arrival/departure media encompass the large body without changing native position. The attack deals 11 piercing damage and causes the recorded Prone result.

Inspected primary source-frame indices: Wolf 50, 110, 175, 221, 250, 280, 296, 307; Fey control 90, 140, 148, 158, 230, 245, 285; Fey defeat 105, 275, 292; Mammoth 50, 65, 99, 192, 210, 224. Opponent corroboration: Wolf 280; Fey control 245 and 305; Fey defeat 292; Mammoth 65 and 224. Frame indices refer to decoded MP4 frames; displayed presentation time can differ from video elapsed time because the recording contains successive retained heads.

Decoded inspection images are under `.runtime/summoning-final-acceptance-20261004/antislop-inspection/`, named for each case. These are extracts, not regenerated artwork.

| Finished case | Frames / checks | MP4 SHA256 | Trace SHA256 |
| --- | ---: | --- | --- |
| summon-wolf-defeat | 345 / 28 | `1efadcf8d7f904b9f6fedbb5fbe9b4d95319b1c8162173f4c562f8a7379869e6` | `fd0b2f0322449bffc9061f8a0f57bae2708f7a83fd36a00b6b8cf07d9065171b` |
| summon-wolf-defeat--opponent | 345 / 28 | `76c5230516deb81189a8557581196e89d654aa313a84be836ed617502926f042` | `fcabecd1b66e8bb888f447a8c252c42b8dd4a5bb62481e67e5e716d6b33e3e44` |
| summon-fey-control | 365 / 47 | `51cd17871a11ecbb4098a571daa7b39ded5ea2aa373674093ab5b153e9fd4b7f` | `8965b558c2911167757c73cbcbfc338ba39a99568d663fa37a42b74df900da41` |
| summon-fey-control--opponent | 365 / 47 | `08b0715f793222e4b272348a64871f0ea059879819f0013924424c3b6eb37dae` | `3aaed283a47a2bfdc3558d2ec04eccee1dc89e5ec77e79bcb16cc2422dac87c0` |
| summon-fey-defeat | 340 / 28 | `2704eae9fc766b583948cf81189350fbf5d94645289710f6fee378d281b83284` | `76dff543940aca389a413aebb767fd1d3c9533cccbb1926f9b021cd9825571bb` |
| summon-fey-defeat--opponent | 340 / 28 | `8ab38aeed36fcfb1a1d2afb7a8ca94009f25b6421b1dffd1043b1bfd899dba56` | `c3bb615c203dae0b998982017a4a46aa572d6a4ba819140e364e01eeacc04309` |
| summon-mammoth | 262 / 31 | `99d1fbd7bd678a4136bfec40b6cf4a650668c4d54c6b318a43511e4ee130e95d` | `99ccddfa711a24503e12e5b6468d92072cbc405c1d7ca2b238ab338761ce839e` |
| summon-mammoth--opponent | 262 / 31 | `00a434397d1083ca96387fbcd62224da8e4309aa6810d9cdc9d5b2706f6a8c62` | `195764e5163822ece2004846b7051c44d835858959e80f420bc8c3397a36bc81` |

Previously inspected original run `20261003T225450Z-2af445` also supported bounded Huntsman/Fellwing arrival, winged motion and departure approval. Its old Fly cast binding gaps were real and are superseded by the corrected source above; that old footage does not prove the corrected Fly cast.

## Existing receipts and remaining completion gate

Observed receipts, without rerunning the suites:

| Evidence | Result and limit |
| --- | --- |
| `/tmp/final-phase-types-final.log` | Zero errors, zero warnings for dnd/game and changed tools. |
| `/tmp/final-phase-bindings-check.log` | 24 passed; exact passive trait/Fly binding correction. |
| `/tmp/lifecycle-retained-pose-check.log` | 52 passed; includes actual scene-contact Die retention and native Prone retirement. |
| Packet A native/presentation receipt | 121 passed; blood, hidden terminal cases, death saves and retirement ownership. |
| `/tmp/final-phase-native-suite.log` | 2,838 passed, two old Goblin expectation failures. |
| `/tmp/final-phase-native-reconciliation.log` | Both native expectation causes corrected; affected ten checks passed. |
| `/tmp/final-phase-client-reconciliation.log` | 76 passed after obsolete Goblin profile/bow/flight structure expectations were corrected. |
| `/tmp/final-phase-combat-marker-reconciliation.log` | Five passed after the demo's seeded hit was aligned with canonical seven HP. |
| `/tmp/final-phase-game-remainder.log` | Still running with additional failures visible. No complete client-suite approval is given. |

Named coverage also closes requirements that these visible clips do not claim to prove: `test_reacquisition_receives_current_fey_without_replaying_hidden_lifecycle`; `test_only_observed_terminal_removal_discloses_its_native_cause` (visible/hidden dismissed, defeated, instant death, expired, sustain lost and closed); `test_only_exact_fey_control_removal_marks_observed_faction_change`; reversible removal/redeployment; and lethal injury with ordinary death saves in `tests/game/test_summon_lifecycle_facts.py`. Native summoning tests cover replacement, expiry despite dismissal veto, required sustain loss, and immediate agency revocation before incoming birth publication.

Goblin tests cover ordinary Pistol attack budget and loot, retained robe variant after modular equip, guard Protection's exact reaction/shield dependency, and two owned weapon hits under one Multiattack action. These are native/projection tests, not claims of completed visual review of every Goblin.

**Still required for whole-phase completion:** reconcile every remaining client failure against the frozen source, record passing affected checks and the complete collected outcome accounting, and finish the required gallery inspection beyond this eight-clip lifecycle subset (including corrected Fly/geometry, ordinary injury, native-wing and Goblin/caster cases as assigned). Any later source correction needs a bounded review of its changed bytes. Deferred effects outside the accepted final-phase artwork remain deferred; this audit does not quietly expand that art scope.

## Fixture reconciliation delta — 2026-10-04

**Approved: the nine-file fixture/capture-catalog delta at acceptance manifest SHA256 `138f1f2106ec918be0738568cc21a27048e5f3080186719ebebe1d03c974e2cd` (128 files).** All manifest entries matched when checked. The existing 119 source hashes are unchanged. The added nine paths are eight game test files and the existing animation-review catalog; there are no new production mechanics.

The changed assertions preserve each tested boundary:

- Seed 27 gives the canonical handaxe a noncritical five-damage hit against four HP, raw HP −1. Both raw damage and normalized life are retained. With death saves enabled the tested state remains DYING; a critical/massive-damage DEAD case was not substituted. The downed-blood test additionally asserts the exact five-damage packet and noncritical release. The catalog changes only that native capture seed.
- The three close encounter layouts now explicitly assert round-one encounter closure, all native enemies dead, input closed, one ENCOUNTER_END, and the exact thirteen-damage opportunity hit taking the surviving Goblin to −11 HP. The diagonal layout still explicitly expects an active round-two player. This is a committed native outcome, not an early-return assertion bypass.
- The dead-mover history test accepts the real encounter-ending boundary while retaining its exact one undisclosed TURN_END, original observation metadata, dead actor state, absent sensory actor, and full replay equality assertions.
- The forced-movement test explicitly expects authored Goblin brace frame 5 and modular frame 3. It still asserts exact travel timing, a held identical body during movement, release at the next frame, contact/grid progression, and no latest-state leak. It does not derive the expected frame from the implementation under test.

Read receipts: `.runtime/final-client-fixture-review/receipt.json` accounts for 29 distinct cases after its last floating-number literal correction; `/tmp/final-phase-displacement-history-reconciliation.log` reports 16 passed in 28.20 seconds for the two remaining affected files. These bounded reconciliations do not declare the still-active whole client run clean.

## Final source snapshot and Goblin footage — 2026-10-04

**Approved source snapshot:** `.runtime/summoning-final-acceptance-20261004/source-completion-snapshot.json`, SHA256 `76528a429f0acae75f2870159c36dfca92219359441211e37843987857fcc4a3`. All 129 listed hashes matched. The previous 128 entries are unchanged; the additional file is `tests/game/test_movement_routes.py`, SHA256 `404deee398a9f6b754331921eb908bf0bf5e4d902ef1d2a716a9032328bed19c`. Its sole change accepts absolute grid rounding error up to 1e-9 with zero relative tolerance at a jump midpoint. Exact lift, landing, frame sampling, held-reaction pose and replay checks remain. This is appropriate for the measured 1.9999999999999998 versus 2.0 result. The entire file passed: 22 checks in 21.57 seconds, `/tmp/final-phase-movement-routes-reconciliation.log`.

**Approved Goblin footage:** selected actual action and final death frames for all 17 dedicated rigs, plus native Goblin02 Web and Goblin08 Fire Bolt/Shield/Counterspell recordings. The same final run contains 38 finished Goblin traces: 690 passing checks, zero failed checks, zero reported gaps. Every recorded canonical Goblin has visual scale 1.0. Pixel inspection was performed on decoded MP4 frames in all four camera panels, not inferred solely from trace checks.

- Goblin02 uses original Attack2 preparation and a measured-source Web release; the ground web exists during concentration and clears after actual concentration removal. Its physical attack remains the expressly reviewed PhysicalGesture binding, without a fabricated staff swing.
- Goblin08's Fire Bolt leaves the actual gesture, hits the opponent, and reduces native HP. Incoming bow fire invokes Shield with the same rig's casting gesture; the native result is a miss. The subsequent Fireball invokes Counterspell, with native cancellation represented in playback. The ordinary duel separately shows incoming nonlethal blood and final death for this caster.
- Goblin03/09 use original bow Attack1, release at body frame 11 (916.6667 ms), and retain the ranged delivery to the actual target. Trace frame 69 has no projectile; frame 70 introduces it at the authored source, then it advances toward contact. The very short adjacent shot in these duels is not presented as a new long-distance geometry test.
- Goblin07/15 each use distinct Attack1 and Attack2 for the two owned weapon children of native Multiattack. The sampled second attack misses and preserves the first hit's HP result; it does not repeat the first clip or invent a second hit.
- Goblin11/12 remain one actor UUID and one native damage/life result per rider. Their original composite death art visibly separates rider and animal silhouettes; this is one recorded body sheet, not a spawned second entity or mount system.
- Goblin17 uses original Attack5 firearm discharge and registered muzzle flash, with native projectile release at body frame 5 (416.6667 ms). The observed hit deals seven piercing damage. It does not use a bow gesture.
- Representative action and death frames for the remaining original rigs preserve their authored gear, shadows, scale and distinct silhouettes. Blood/flash and falling-body samples were additionally inspected for the longer caster and dual-weapon fights. No duplicate body, detached effect layer, missing gear, inappropriate species fallback, or new pixel blocker was found.

Priority paired-perspective corroboration was also viewed: Goblin02 Web frame 32; Goblin08 Shield/Counterspell frames 176/236; Goblin07/15 second weapon frame 111; Goblin11 terminal composite frame 185; Goblin17 discharge frame 55. Other paired traces were checked for failures/gaps, without claiming that every frame of both recordings was viewed. Native Protection and loot acceptance remains the named tests above; the two-person duels do not pretend to exercise ally Protection or a loot transfer.

| Case | Inspected primary source frames | Primary MP4 SHA256 | Paired MP4 SHA256 |
| --- | --- | --- | --- |
| goblin-02-web | 22, 32, 61, 85 | `7d64201c2bdcd43084dd312c9d31a9cbde77a4397ac66a2e8ff9d1c77bab68be` | `653243f31e36121457ffb0b94294123b820397618bbca98e1c4ba786196e476a` |
| goblin-08-spell-reactions | 31, 62, 176, 236 | `22204c776f2a96272300811e54b30aded85a362b4a0456b198a9b053a68df4b2` | `891882c5a66571032795422c9ea413970ae6f45e454743365d9068433db51828` |
| goblin-01-duel | 58, 191 | `01604c9df0bff7576dc7a6af2d1943721f03d9d86951349fe494e51c410d576c` | `bf4c58d4ec9da5d582670b5d0f68fd696267b2f48d3f88d2c390de159917db53` |
| goblin-02-duel | 58, 129, 660 | `1012d9c6cf4da548dfca6f0a087be3afd16095163540eb3e5cf0f9f862d033ff` | `a7593384f86c7a026178ecf89ea21f10aa94a81016f98d842045a703f69e3ef8` |
| goblin-03-duel | 69, 70, 71, 209 | `eab25ae51f13428e347324a20c497fa69e803fc13c3359fd67074a5b3c6dd3a1` | `d7ef4ceb532ba182e193c4e26dcd892c462a34f15308ea2304dcfea9a1bc70c7` |
| goblin-04-duel | 58, 191 | `9ad1eca5660b4c3585ff1428d08f96dd103271b92b069705316bd118b441de08` | `05aa0bcc50f5f6cf02009ef83a914ca8f198985b97eb3aee17d37fa365082e4d` |
| goblin-05-duel | 58, 191 | `0734b28f14c9d11778b7971712fbe719ddc77166e3c2857ccaa2df1f16df6ce9` | `cbe15afe7d903531cd3389802fcd6bfa778c928a4d0c6192755490ccbf772d5b` |
| goblin-06-duel | 58, 191 | `20934fbea84892c06751d0823347201e1ebd87f1bcea1f112c1b7c7286cac596` | `2744d1e8330055854bcbba031c157d7119fb40831ecdb07f5022ee3e4c5f204a` |
| goblin-07-duel | 58, 111, 228 | `ec47c02e848770deb1442f4e2f946f9732e64fa0a753d0e6ff32fb48a64ca083` | `47d1bc2216009153dd6f96daf47503cbefdb3aa1e59a8a8e2924d96ab5d0b516` |
| goblin-08-duel | 58, 129, 649 | `3cd08ce5a01b8cd6d88b8cca47408b8eddd5a34e66e3bd1156f48462a11cdb71` | `013f42985809cc10daf75b5cea1d3c169923cd69cc36f3a6d324b4a693e10f57` |
| goblin-09-duel | 71, 209 | `ee545826bf874e8e5bef9de44d85814c9a347b082e2d386c1b9d95a2059a8d41` | `241055837adf69f9cad69b27deb1bcb6002ebc5fb0431935a7f1e4fc7d3c7cfe` |
| goblin-10-duel | 58, 191 | `610c210d1a5f1ef6107c113a393d3a51f7709ccc47acf1b0dd50174d048caef0` | `2cf79b8ec3e3df18fd03e614ebb4261f7f234731e992da1b65571c6fbbd7233c` |
| goblin-11-duel | 52, 123, 185 | `395d46ff69ea26c07c901888c0ff4379ca8262a573e58602bfa2707f662cd585` | `e7c1f49bdcbfaf16f77609d73bdd9b4736bd156564393d58735a323abbd7d468` |
| goblin-12-duel | 52, 185 | `77fbaef0aa35a1c5dbbdcdb650872147b41f77025d978a62c0d1056b2b622d7c` | `63ecbdf9210a741226cd906bf91eec76d9656ee35becbeb683a4e2a268840340` |
| goblin-13-duel | 58, 191 | `ee0e447a1ab8434f880852ab7030b4bbd234451dc629ebaf62fde6a260434278` | `4023af8bbfb91a1f31595ca2e3fa2633d24e728682c76876b917c6722be1123a` |
| goblin-14-duel | 58, 191 | `42c2ace8a6e0220fa758eb41760b3a480e627d89b36b756cce701fe04e64a5a7` | `2430ec2037c5fa2322a3c60d33dcc8b3cf82297c088bdcc543183feba433aea6` |
| goblin-15-duel | 58, 111, 166, 430 | `a7b2a84494dcac59a989afd6cf9a1fe892ea252b8d5c96738b453de2f4ce5690` | `cf007d679f3d700e357f84cb3b3a6baf3d59048d57c793429a676c20f299e9b0` |
| goblin-16-duel | 58, 191 | `5f6f5390678412fcf10368f9cc6261f4f58ae887c49a2ca7300eb858e7d61804` | `adaba18b99c4812ee00a0ef1eaab27f4f8632fce4084f15fad3aceafdd3f2e07` |
| goblin-17-duel | 55, 131, 193 | `0648c8973598306974e6057301053a90e01b6a8d3232514aa28d8518a21db4ab` | `15fbdc5366a8d20401f11e938d172e7e349459407c66227a2abfe0fd4e07b898` |

Trace identity aggregate: `0e896bafe9e3bc7febdd883571dacbc8450143e3433ae7e2bb0562161f9558df`. This is SHA256 of the sorted UTF-8 lines `case-name|trace.json-SHA256`, one trailing newline per line, for the 38 paired cases in the table. All source frames remain available as extracts under `antislop-inspection/`.

**Completion gate still open:** the active client run must finish and its complete outcome accounting must be reconciled. Separately, `/tmp/final-phase-gallery-final.log` reports `RuntimeError: unsupported or ambiguous three-support stair run at (5, 4)` for `fly-modular-rise-descent` at case 67/69. This is an observed missing gallery result, reported to the parent for bounded correction; no cause beyond that log evidence is asserted here. It does not invalidate the completed Goblin footage, but it prevents treating the whole gallery as complete. This reviewer did not regenerate the failed case or change its source.

## Height-recording provenance amendment — 2026-10-04

**Accepted as a bounded capture replacement; no source change.** The failed proving-ground stair arrangement remains archived. The replacement uses the existing `battlefield.visual_vertical_seam` route `(13,20) → (14,20) → (13,20)` and recorded native flying movement. Its two lineages contain ten public nodes. The bound motion has support heights **0 → 2 → 0**, with the normal flight phase edges and support riser. It is not a flat substitute for the required rise/descent case.

Verified evidence under `.runtime/summoning-final-acceptance-20261004/height-correction/`:

- `receipt.json` SHA256 `8e3479bf91d6d2ef15f1527f6b64bbd745fe0ebf17d9277d452ea3d7db32a1c0`.
- `review.json` SHA256 `5673036ae2355f892ca6db27c436eb7b181b2099065af132966cbe66e7c8249d`.
- Public input SHA256 `643d0a062eed3cb12c24d63f7b26132174733e0467f3b970e43f26458d218784`; the captured input and the rendered run's archived input are byte-identical.
- Rendered case in `runs/20261003T233842Z-2d43aa/cases/fly-modular-rise-descent/`: 67 frames, all 15 checks passed, zero gaps. MP4 SHA256 `da22b56f01ffb17a63f95d7975d48905c34f075369f6283f3766e381e8b882cb`; trace SHA256 `713acb91728c67c465ff70e221027048347ae0f17e61d4738a4c18e3836f391b`.

The original top-level review input still hashes to `660ad30a753ec56a1e9ee3d6b0c6e6075893431421ddba2f1f8cb74761a49e7c`. All 129 entries in source-completion snapshot `76528a429f0acae75f2870159c36dfca92219359441211e37843987857fcc4a3` still match. No map, renderer, or gameplay changes were needed. Combining the 68 original passing recordings with this one replacement is honest provided the combined gallery retains these distinct input/run origins and does not relabel the failed original case as passing.

This closes the failed-capture provenance issue within this review. The assigned events reviewer owns the replacement's pixel verdict; this amendment does not claim an additional visual inspection by the anti-slop reviewer. Whole-suite completion and its final outcome reconciliation remain open.

## Final two-fixture reconciliation — 2026-10-04

**Approved:** `.runtime/summoning-final-acceptance-20261004/source-final-acceptance-snapshot.json`, SHA256 `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3`, contains 131 files. All entries matched; all previous 129 hashes are unchanged. The only additions are the two bounded fixture corrections below.

- `tests/game/test_resolution_contract.py`, SHA256 `b6a71476b4ddc93bf37d8dccdb05122fb940a497a8506bd7cc2a005d1245671d`: the synthetic multiple-damage-result ownership test now starts from seed 10's noncritical one-damage result, HP 7 → 6, and explicitly asserts that premise. Its extra one-damage result consistently ends at 5 HP. It retains result ordering, exactly one bound action, no extra injury group, exact displayed HP and deterministic seeking checks. The former seed 17 killed the canonical seven-HP Goblin and retained a conflicting terminal life/HP commit; changing this fixture does not weaken a death test, because this test's subject is multiple results owned by one attack. Other lethal/legacy resolution cases remain unchanged.
- `tests/game/test_rig_body_contexts.py`, SHA256 `6ed7893586bba602e20991de9dced73e76f2fa17e71592c3084bf234a1c2ae1b`: the root-only high-precedence override is checked against Goblin01's actual preexisting `goblin01-physical` profile, with an explicit identity assertion. It no longer expects the historical modular fallback. Exact source-item/source-kind exclusion, outcome parameterization, contact timing, frame selection and unchanged reduced native state assertions remain.

The reviewer read `.runtime/final-resolution-rig-review/receipt.json` (SHA256 `d7f70484b2c8729f1021d0d46b537f3b02edc55cf6e1617641f410204030726e`) and its complete-file `tests.log`: **50 passed in 34.63 seconds**. Its typing comparison reports zero new diagnostics; the resolution test file has ten matching preexisting diagnostics, and the rig file has none. This is not misreported as a clean typing result for every test file. Production dnd/game typing remains covered separately by the earlier zero-error receipt.

No production changes or new architectural scope are involved. Whole-run final acceptance remains pending the durable per-failure reconciliation receipt and complete outcome accounting; the reported 2,344-case remainder result is not yet substituted for that independent evidence check.


## Final independent acceptance — 2026-10-04

**APPROVED.** The approved plan scope is complete at the final 131-file source manifest `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3`. This final evidence check found no remaining blocker and preserves the earlier bounded source, architecture, fixture and pixel verdicts. It introduces no implementation or scope change.

Durable reconciliation: `.runtime/summoning-final-acceptance-20261004/validation/reconciliation.json`, SHA256 **`d13b9f089b36deb54902cd95e77970bc7c0f7a1e0a3ea49906cf89cbb10dc17f`**. Independently recomputed its hash and all **23** indexed evidence-file hashes: no mismatch. Rechecked all **131** source hashes and both plan hashes: no mismatch.

The collected outcomes and original failures are preserved rather than replaced with inflated rerun totals:

| Original run | Distinct cases counted | Original outcome | Final reconciliation |
| --- | ---: | --- | --- |
| Native engine/AI/architecture/progression/package | 2,840 | 2,838 passed, 2 failed | Both obsolete Goblin expectations are covered by the passing complete affected files: 10 passed. |
| Client interrupted prefix | 884 | 875 passed, 9 failed | Seven profile/bow/movement-data expectations are covered by the 76-pass affected-file run; two seeded demo cases by the five-pass whole-file run. |
| Client remainder | 2,344 | 2,326 passed, 18 failed; zero errors/skips | Every failure is mapped to the previously reviewed fixture corrections and passing complete affected files. |

The saved collection contains **3,228 unique client node IDs**. Parsing the interrupted log yields 887 result markers, including three successful combat-play cases repeated at the start of the remainder. The first 884 markers contain exactly 875 passes and nine failures. Those 884 IDs are disjoint from the remainder, whose JUnit IDs match the final 2,344 collection entries in order. The three repeated cases and every focused rerun are excluded from the distinct total. Thus the accepted accounting is **2,840 native and 3,228 client cases**, not a sum of repeated suite executions.

The JUnit contains exactly 18 failed remainder nodes. Their union with the nine prefix failures equals the receipt's 27 unique mapped client failures, with no missing or extra entry. The passing evidence includes the complete movement-route file (22), forced-movement/history files (16), final resolution/rig files (50), and the fixture receipt's 29 distinct cases. That fixture receipt honestly retains its initial 28-pass/one-failure result and the subsequent complete lifecycle file's ten passes. This reviewer read the durable logs/receipts; no test was rerun for this closure. Production dnd/game and changed-tool typing remains zero errors and warnings. The explicitly documented ten preexisting resolution-test typing diagnostics are unchanged and are not represented as clean test-code typing.

The composed gallery is `.runtime/summoning-final-acceptance-20261004/runs/20261004-final-acceptance`. Its composition receipt SHA256 is `590bbdecfd2af3158bb7f8e760f5ad0f5ee13ba803f9442100dd91a3a073d34e`; its manifest SHA256 is `02a4ebd5ef06445893ddfd51fa63dda1cb43ba34a44643d72003511578b3fe92`. Both hashes, the standard gallery JavaScript and the index match the independently approved ECS/events audit. Its **69 cases / 35 experiments / 1,563 passing checks / zero gaps** retain 68 original recordings and the separately identified native terrace replacement. The replacement's actual pixel and composition/export review is recorded in `SUMMONING_FINAL_ECS_EVENT_REVIEW_2026-10-04.md`; this report's own lifecycle and all-17-Goblin pixel samples remain documented above. These combined reviews close the remaining gallery gate without pretending every frame was manually inspected or the original failed stair input passed.

No additional spell, mount system, general renderer/executor, native rule framework, or unapproved artwork is included in this acceptance. Effects outside the accepted final-phase media remain deferred. Only this audit was edited during final acceptance; no production changes, tests, renders, new agents or other-chat operations were performed.


## Subsequent user correction — Wolf scale pending

After the preceding reconciliation was independently accepted, the user judged Wolf scale 1.30 insufficient in the completed gallery. The parent reports a bounded canonical Wolf appearance change to **1.80**, with native stats/footprint and other species unchanged, and plans replacement captures for the three Wolf scenarios (six observer clips).

The preceding approval remains bound to the frozen 131-file manifest and its original gallery. It does **not** approve this subsequent source delta or its not-yet-reviewed pixels. Current completion awaits the exact changed-file/source receipt and replacement footage/provenance review. No broad suite rerun or additional architectural scope is implied by this pending visual adjustment.


## Wolf 2.00 and terminal-death correction — 2026-10-04

**APPROVED for the bounded source/data correction and the terminal-death pixels inspected here.** The user's final Wolf request is **2.00**, superseding the intermediate 1.80 proposal. The revised terminal rule also supersedes the earlier suggestion that a distinct death clip should always play from its first frame while downed: fallen creatures must not stand up just to die.

Final source manifest: `.runtime/terminal-death-review-20261004/source-final-snapshot.json`, SHA256 **`96605c30162fc3e2100d12d19d75a844a0083d94299d7d2b68185903aead49e6`**. All **134** current files match. This replaces the 132-file manifest `77f9a184b6361dc2a869d2af63e11d984832af940d52fa3f298e5a07526c2964`: the final inventory additionally includes the already changed `game/play.py` and `dnd/monsters/srd_roster.py`; that inventory correction introduced no further source change. The amended final-phase plan hashes to `ad77bac8644236b3c6c203100331dfaa2a873ea29be4b38b3aebe418fc720d05`.

The shared implementation preserves the approved ownership boundaries:

- `death_body_context` selects the exact rig default through existing passive body-context data. Duration, damage/standalone-life sampling, retained corpse pose and media loading use this selection. Schema admission requires enabled, finite forward source playback; no new event, native effect, species branch or executor is introduced.
- Upright deaths play the original alternate clip. A resting Prone/DYING/STABLE contact goes directly to its selected terminal final frame. If the same fall is still active, sampling continues its original `life_start_ms` clock and existing completion; an alternate terminal clip instead settles at the actual death boundary. Already-dead targets retain their final frame. Reverse recovery remains on intact Die, and native life state is unchanged.
- The two earlier review findings are resolved. Terminal sampling handles the death boundary before an obsolete downing transition can mask it; the user's later no-stand-up rule determines whether to continue a shared fall or settle alternate remains. Lifecycle preload resolves the actual retained condition/life pose, so a fresh-cache Prone dismissal loads Die even when terminal death is Death. The native animals/fiend dismissal regression now draws that retained pose from an empty media cache.
- Wolf's canonical appearance assignment is exactly 2.0. Native statistics, footprint and other species' scales are not changed by that assignment.

Original-art intake is bounded to **21 terminal bindings and 48 PNGs / 9,505,401 bytes**: six demon explosion banks with original separated effects/shadows and fifteen Goblin Die2 banks. Riders11/12 remain unchanged. Installation receipt SHA256: `27fd50942cc9643bd19bb9c9ed44ee78e6de8e0509bbc430c315bc4fe780d6f1`; data validation receipt: `b139e7e3e9218a221e5e2df8348296fe66d71b3d1879c40c192b67b7c8de625f`, both under `.runtime/death-art-study-20261004/`. Independently hashed all 48 installed files, compared them with their named original archive members, and checked all 21 binding hashes: no mismatch. Existing `BodyClip.layers` carries the registered effects. The inspected original explosion sheet ends in ground splatter/remains; its nonempty final frame is not a perpetually replayed fireball.

Read and hash-verified every entry in `.runtime/terminal-death-review-20261004/validation/receipts.json`. The final focused evidence is **75 passed** in `prone-death-no-refall.log`, **87 passed** in `terminal-death-regressions.log`, and zero errors/warnings in the corrected typing log. The earlier correction run has **107 passed**. The original 17-failure and four-failure logs remain archived explicitly. These overlapping focused runs are not added to the prior distinct-case full-suite totals or claimed to be a new full run. Reviewed coverage includes retained native Prone dismissal, normal/instant fiend defeat before dissolution, downed life/revival, alternate death after overlapping volley downing, already-dead replay, exact profile timings and deterministic seeking. The volley boundary test uses passive cast inputs; native lifecycle tests provide separate integration evidence.

Actual terminal footage reviewed: `.runtime/terminal-death-review-20261004/runs/20261004T002155Z-c5ee42`. All **18 paired cases / 774 checks** pass and every trace has zero gaps. Manifest SHA256: `c225aa4ff42296a0de54da5c818994db65db923cafffd6f00279bc6fc52c394c`. Source MP4/trace identity aggregate: `cc63ea3149c57d4296a08f6e0c8b032301eff148104fa90a503032fb0ad1e69b`, computed from sorted `case-id|trace-SHA256|MP4-SHA256` lines, each with a trailing newline.

Inspected decoded frames include all four camera panels:

| Native case | Inspected source-frame indices |
| --- | --- |
| Dretch | 168 Prone, 199 recovered, 305 burst, 334 remains |
| Corrosive Demon | 305 burst, 334 remains |
| Dread Demon | 305 burst, 334 remains |
| Huntsman Wing Devil | 563 burst, 592 remains |
| Fellwing Devil | 767 burst, 796 remains |
| Claw Mote Devil | 159 Prone, 192 recovered, 228 burst, 257 remains |
| Goblin01 | 127 terminal fall, 156 corpse |
| Goblin03 | 145 terminal fall, 174 corpse |
| Goblin17 | 129 terminal fall, 158 corpse |

The demons visibly retain intact nonterminal bodies and distinct original terminal bursts/remains; the Goblins use their second original fall and settled corpses. Body, separated accents and shadows stay registered, with no duplicate actor, detached effect, stuck bright explosion or unexpected scale change seen in these samples. The displayed ordinary demon deaths happen after a genuine recovery; these clips are not misrepresented as direct proof of already-Prone lethal transitions, which are separately covered by the source and native regression above. This is representative pixel inspection, not a claim that every frame of both observers was watched. The exact extraction index is `.runtime/terminal-death-review-20261004/still-receipt.json`, SHA256 `aaec88bd00d9e17e99dace66132359abd69662fbb2ba45960c5aec0feb304734`.

Wolf's six recaptured clips are separately preserved in `.runtime/summoning-final-acceptance-20261004/wolf-original-200-percent/runs/20261004T001450Z-be467c`; all six report passed. The parent reports the assigned ECS reviewer has approved their four-view pixels. This anti-slop addendum approves the exact scalar source and preserves that independent pixel-review attribution rather than claiming an additional Wolf frame inspection.

The new combined correction gallery is `.runtime/summoning-visual-corrections-20261004/runs/20261004-wolf-and-death`: 24 cases, 934 passing checks, zero gaps. Its composition receipt hashes to `a0671451b72c7b34662751d3dd1419064a927a137b0ed7f90d13159ffa002004` and manifest to `51d2cec790a5079bd1848a4f403ee3045ab9b3c12759c76fbebabcb9d1572f01`. These explicit replacement origins preserve the original gallery history; final packaging integrity remains the parent's/assigned ECS reviewer's responsibility. No unrelated audit, new rule, art generation, test execution or game rendering was performed by this reviewer. Only this report was edited.
