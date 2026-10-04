# Finger of Death presentation — 4 October 2026

Implemented the approved damage-only Finger of Death presentation, including the original normal hand, Darkness projectile and confirmed Counterspell cameo. Native spell rules are unchanged. Root independently approved this bounded implementation in `agent_docs/audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md` after 70 shared/native/DAG checks. This is not whole-plan acceptance.

The selected recipe is `game/data/finger_media/finger-draft.json`. Registration, exact source identities and installed hashes are beside it in `bindings.json`, `projectile-assets.json` and `source.json`.

## Source and installation

Pinned accepted source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/finger-of-death-approved-media.json`, SHA-256 `69b6eb2b875a57b5df596e5220ed124e3ef47a011b9b9df0031025d4252ee9f8`. The associated `production-handoff/HANDOFF.md`, `FINGER_OF_DEATH_NORMAL.md`, `COUNTERSPELL_CAMEO.md` and original models remain preserved. The sibling `directed-cast-completion/FingerDirectedCapture.gd.in` supplies the accepted arbitrary-target mesh and splinter equations.

Full originals and authoring commands are preserved under `/home/tommaso/Dev/neurodragon_art/sources/finger-of-death-20261004/`. Local/private production copies have matching SHA-256 values: **156 payloads, 34,101,016 bytes**. The private manifest retained its previous entries and its prior version is preserved with the selected source. No original sprite pixels were painted or modified.

| Accepted component | Selected content |
| --- | --- |
| `finger_ground_magic_v8` | Original `SkeletalArm.glb`, portal, bones, charge and withdrawal. Native scale 1.65; 104 samples at 32 FPS. |
| `finger_counterspell_v5` | Original `SkeletalCounterspellV5.glb`, fixed forearm and animated wrist. Same source canvas, clock and paired layers. |
| `finger_death_lance_v3` | Original three Darkness donor meshes and material parameters/textures; hidden MBall stays omitted. Thirty original triangular cylinder splinters retain their lag, orbit, dimensions and finite envelope. |
| `finger_death_impact_v2` | Original four-camera, paired 64-frame contact banks at 32 FPS. |
| `counterspell_stop_v1` | Original four-camera, 16-frame reaction bank. This is the accepted cameo-specific temporal source, not a claim that the existing ordinary Counterspell bank is byte-identical. |

`devtools/export_finger_media.py` captures the original full hand scenes at eight owner headings, four camera quarters and both physical sides for each branch: **128 banks / 13,312 full source cells**. Geometry rotates in Godot; sprites are never rotated in screen space. Camera capture slots ascend counterclockwise, so registration maps engine quarters to `[0,3,2,1]`. Native owner heading is `(3-worldFacingRow)%8`; each selected facing also accounts for the viewed camera quarter.

`devtools/export_finger_components.py` exports the three original mesh arrays, exact local transforms, material parameters, grayscale-adapted HDR gradients, decompressed original Noise531 and original splinter mesh. Its original GPU export includes texture mip levels; the runtime linear sampler reads the base level explicitly. `devtools/import_finger_media.py` uses the existing lossless atlas packer and verified private/local installer.

Evidence:

- `.runtime/finger-20261004/source-validation.json`: every one of the **13,312** installed cells reconstructs its complete original RGBA source exactly; all **156** selected local/private hashes agree.
- `.runtime/finger-20261004/original-camera-parity.json`: the recaptured unrotated camera-zero normal/cameo, front/back banks match **all 416 original accepted frames with zero changed pixels**.
- Original donor geometry, shader equations and sampling are ported into the existing CPU world compositor. These source/numerical checks do not claim whole-screen GPU pixel identity for procedural meshes.

## Shared consumer changes

`StudioMediaTrack.assetIdsByCamera` selects four independently captured camera resources while retaining existing facing fallback. The loader validates all four clocks, dimensions, pivots, row orders and storage; the existing preload and cast/stationary media samplers use the selected resource. The review recorder fits exact authored crop metadata, keeping the large transparent logical canvas from forcing an unreadable zoom. This changes offline framing only.

`StudioDirectedDelivery` is a closed discriminated union. The `darkness_mesh` branch in `game/directed_mesh_media.py` uses original local XYZ/UV triangles and shader inputs on the recorded owner/recipient geometry. `game/directed_surface.py` owns shared triangle rasterization and the ordinary `SurfaceVolume` draw command. Each mesh surface retains native XYZ for existing world occlusion. The original lower-right two-pixel palette pass is applied after the donor layers combine; each emitted fragment retains its own alpha and geometry. No recipient search, hit decision, damage rule or separate renderer is introduced.

The hand and contact RGBA banks retain their supplied paired billboard layers and pivots. No per-pixel XYZ is invented for those banks. The moving projectile is actual mesh geometry. The dark red/brown lance/contact palette is distinct from the original weathered bone hand palette.

## Timing and outcomes

- Ordinary Attack5 retains 12 FPS and release frame 7. Optional `StudioContact.launchDelayMs` defaults to zero; Finger delays the original hand discharge until 1.50 seconds. The hand starts at 0.40 seconds. Existing contact travel speed scales the fixture's 0.65-second four-cell flight to received target distance.
- The launch uses the evaluated native index socket `[0.2105243369936943, 2.062067713588476, 2.4470988512039185]`, transformed with the same world facing as the hand. Recipient endpoints use the existing body contact, including already-Prone placement. Impact media corrects its authored source pivot to that actual body contact.
- Optional `StudioCast.holdUntilContact` defaults to false. Finger keeps the existing clamped final Attack5 pose until contact; it adds no body clock or action cost. Both existing cast compilation paths honor this passive field.
- The application and ordinary damage/death response occur at the existing contact milestone. A successful CON save still plays the normal hit and half-damage response. Lethal damage uses existing health/life/corpse handling; no zombie is created.
- `StudioCancellationMedia` names the exact recorded outcome `spell.counterspell.interrupted` and reaction `reaction.spell.counterspell`. The existing interruption path selects the finite cameo only for that outcome. Failed Counterspell continues the normal cast.
- The original Special1 reaction is aligned to its frame-8 effect at 1.275 seconds. Its collapse is attached to the evaluated cancellation index socket. The cameo continues from native source frame 28 and withdraws/closes by 3.65 seconds. It uses existing `StationaryMediaCue` lists; no second timeline or queue is added.
- Canceled native effects remain canceled. The finite source cleanup extends visual completion only; it does not emit a projectile, target impact, damage, life change or condition, nor postpone native child facts to the end of the withdrawal.

## Validation

- `tests/game/test_finger_directed_delivery.py`: seven focused cases, each using native captured histories. Both observers and all four cameras cover save, survival, lethal damage, existing Prone, actual launch/contact, original final-pose hold, successful/failed Counterspell, original reaction gesture clock and finite cleanup.
- `/tmp/finger-combined.log`: **54 passed**, including focused Finger cases, shared interruption/replay/relocation regressions and architecture import boundaries.
- `/tmp/finger-clock-final2.log`: **7 passed** after adding exact reaction gesture/cleanup timing assertions.
- `/tmp/finger-types-final.log` and `/tmp/finger-framing-types.log`: scoped typing **0 errors / 0 warnings**.
- Standard saved-input gallery: `.runtime/finger-gallery-20261004/runs/20261004T083844Z-b3c196/index.html`: **12/12 recordings, 96 checks, zero gaps**. Six real experiments retain both public perspectives and four camera views. Native inputs were captured once; palette/framing corrections replayed those same inputs.
- Visually inspected `.runtime/finger-20261004/normal-travel-current.png`, `normal-contact-current.png`, `counterspell-cameo-current.png` and `prone-contact-current.png`: index-origin travel, body-centered contact, distinct cancellation gesture without target damage, and prone contact in all four views. This is representative frame inspection, not a claim that every recorded frame was manually viewed.

Initial failed receipts remain available: `/tmp/finger-outcomes.log` exposed donor mipmap reading and a test assertion using the standalone damage list instead of cast-owned damage; `/tmp/finger-clock-final.log` exposed an empty retained-state test assumption. The current code/tests correct those issues. Early recordings with the initial donor palette or full transparent-canvas framing are superseded by the gallery above.

No commit or external chat message was made. The accepted class-action batch remains a separate remaining lane. Root independently reviewed the shared launch/hold/cancellation and camera registration seams; its bounded approval is recorded above.
