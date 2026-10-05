# Produce Flame / Frightened — independent bounded review

Scope: `PRODUCE_FLAME_DIRECT_PLAN_2026-10-05.md`, the direct-damage Produce Flame implementation and retained-presentation removal, canonical Frightened outline data, and the newly recorded native examples. No production edits, tests, scene renders, artwork changes, or external-chat access by this reviewer.

## Source and scope

The damage-only Produce Flame implementation follows the explicit user decision: one 30-foot ranged spell attack, fire damage with shared cantrip scaling, ordinary validation/payment/defenses, and no maintained flame, light, condition or granted Hurl/Dismiss actions. It reuses the finite directed projectile and Attack5/Magic2 presentation. Current assignment JSON and `SPELL_CAST_ASSIGNMENTS_CURRENT_2026-10-05.md` describe the immediate throw honestly; the latter explicitly marks the October 4 Markdown table as archival.

Frightened uses the existing canonical `condition.frightened` persistent `ConditionBodyOutline` record: muted-violet color, pale-violet pulse, opacity 0.8, pulse opacity 1, period 900 ms, onset 180 ms, alpha threshold 100. The existing silhouette compositor owns the effect and the original wisps remain. No Fear-only renderer or new state owner is introduced.

## Actual pixels and provenance

Run: `.runtime/produce-flame-direct-20261005/runs/20261004T233223Z-50bf7d`, 32 fps, native 1280×960 four-view output. The manifest contains six passed recordings, 86 checks, and zero recorded gaps. These recorder results are distinct from the independent pixel sample below. Frightened uses `scene` framing with 128-pixel actor draw buffers; Produce Flame uses `actors` framing with 192-pixel buffers. The normal-zoom Frightened conclusion does not depend on enlarging a crop.

Exact extracted-image paths, source-video SHA-256 hashes, video and presentation timestamps, and flags distinguishing viewed from merely extracted frames are saved in `.runtime/produce-flame-direct-20261005/antislop-frames/samples.json`. Twenty-two original video frames were visually inspected across all six recordings; this is not a claim of watching every frame.

- Fear caster: n0, n96 (3.000 s), n160 (5.000 s), n176 (5.500 s), n224 (7.000 s). The affected Recipient has a visible violet silhouette in every camera at ordinary scene scale; successful-save Second and the outside bystander remain plain. The silhouette persists after the large cone has faded and is absent after native concentration/condition clear.
- Fear recipient observer: n188 (5.875 s), n224 (7.000 s) agree on sustain and clearance. This scenario moves Caster while Frightened is active and moves Recipient only after clearance. It does **not** independently demonstrate the affected actor moving while outlined, natural turn expiry, every rig, or every background.
- Produce Flame hit caster: n58,60,64,68,72,80,84,86,90,130; hit recipient: n60. The directed gesture releases an orange/gold projectile visible in all four camera directions. The recipient flashes on contact, and the final state is 116 HP from 120. The cast hands and projectile are finite; no retained flame remains in the settled frame.
- Produce Flame miss caster: n64,70,103; miss recipient: n103. The projectile is still visible in flight, the target does not get the hit flash/damage, and both actors settle without a retained flame or condition at 120 HP.

## Verdict and remaining timing finding

The normal-scene Frightened visibility correction passes this bounded pixel check. The Produce Flame simplification has no source/scope blocker, and its finite hit/miss delivery is visible. The new gallery is not a full spell-catalog rerender.

One existing Produce Flame presentation mismatch remains in this recording: contact/hit flash is 863.333 ms after cast start, but HP and the floating number are at 1446.667 ms, a 583.333 ms lag. The loaded recipe has `floatingNumber.frame = 7` interpreted at 12 fps. Actual n68/72 (2.125/2.250 s) show the hit flash; n84/86 (2.625/2.6875 s) show a plain target still at 120 HP; n90 (2.8125 s) finally shows 116 HP and “4 Fire”. No substantial later impact in these samples explains the delay. This is inherited authoring, not evidence of a backend damage failure. The lean correction is to align the existing number/vitals frame with the measured contact and review the inherited `death.frame = 12` against that contact; alternatively, retain this explicitly as an unresolved presentation limitation. No unconditional timing approval is given here.
