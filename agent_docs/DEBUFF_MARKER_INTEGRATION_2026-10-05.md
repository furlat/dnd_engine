# Steady debuff markers: integration and gameplay review

User scope: integrate the delivered steady-markers-v2 handoff and record actual
application, sustain and removal triggers. No wiggle/bob, no replacement body
animations, no surfaces, no Grappled and no rejected Mark Target artwork.

Implementation:
1. Verify and preserve the thirteen original single-frame assets with the existing
   verified media installer; merge their existing media schemas.
2. Append overhead layers to authoritative condition recipes, preserving body,
   transition and relationship data. Resolve Reduce using its existing size fact;
   Ray of Frost must follow the actual target and tracker expiry. Verify Lethargy
   ownership from code rather than trusting conflicting handoff descriptions.
3. Reuse the existing marker selector and presentation clock. Stabilize overhead
   placement against idle frame jitter while preserving movement and held poses.
4. Extend existing native gameplay recordings with real spell/attack/save/turn or
   recovery triggers, including multiple simultaneous debuffs and different rigs.
   Replay saved events in all four cameras; inspect pixels and transitions.
5. Run relevant behavioral tests and independent anti-slop and anti-OOP/ECS
   reviews of plan and final changes. Record evidence and remaining limitations.

No new gameplay condition, rules expansion, parallel event system or artist chat.

Implementation findings:
- Both independent reviews corrected the handoff's Lethargy assumption: it owns
  incapacitation directly. Its own recipe reuses the accepted pause marker.
- Reduce uses the existing cold size_change fact via a narrow typed layer filter.
- Ray of Frost's affected target is absent from cold ConditionState. Do not bind
  a marker to its caster tracker. A proper recipient/disclosure/expiry connection
  remains necessary; this batch has not fabricated one from damage or live state.
- New overhead glyphs are stills. Stable clip envelope applies to head markers
  only; existing face-attached Zzz and body/ground VFX retain their registration.
- Exhaustion/Petrified recovery fixtures begin afflicted and use real Greater
  Restoration. No nonexistent affliction-producing spell is claimed.

Verification checkpoint:
- 51 targeted condition compositor, marker selector, media lifetime and transition
  tests pass. Tests preserve original body banks independently of added glyphs.
- Scoped production/importer typing: zero errors/warnings.
- Anti-slop comparison confirmed unchanged existing Bane/Charmed/Slow/Fear/
  Prone/Paralyzed/Petrified body and transition values.
- ECS source review approved after registration offsets and missing-frame socket
  handling were corrected. Existing face-attached sleep Zzz retains its old path.
- Explicit Unconscious membership is separate from native dying/stable life state.
  A fixture shows Unconscious while Prone and native turn expiry; it does not
  claim zero HP creates that condition. Automatic life-state markers are not added.
- New clips use real casts/save outcomes/native expiry/Greater Restoration except
  explicitly labeled condition fixtures. Supplied assets remain original pixels.

Final review receipts (October 5):
- Independent anti-slop reviewer approved the bounded source integration after
  checking registration, body-independent glyph sizing and the weak-key geometry
  cache. Compared five four-camera images: Bane, Charmed, Grovel, Exhaustion and
  explicit Unconscious. No source blocker; temporal claims rely on recorded clips
  and behavioral tests rather than still images.
- Independent ECS reviewer approved the existing cold-fact/compositor path and
  confirmed no new gameplay manager, event queue or parallel condition system.
- Final scoped typing remained clean after the geometry cache; the four compositor
  tests also passed after that final change (included in the 51-test scope).

Review guide:

| Condition / behavior | Recorded trigger or fixture |
| --- | --- |
| Frightened | Fear with failed and successful saves, movement, concentration clear |
| Poisoned | Native poison trap; Lesser Restoration recovery |
| Bane | Real Bane application and expiry/removal lifecycle |
| Charmed | Actual Charm cast and removal |
| Slow | Failed-save lifecycle plus resisted-cast negative case |
| Paralyzed | Hold Person; Hold Monster on a Reduced creature |
| Prone | Failed Grease save; Command Grovel |
| Commanded | Halt, Flee and Grovel before the commanded action resolves |
| Sickened | Eyebite with caster, recipient and second-observer recordings |
| Reduce | Actual Enlarge/Reduce; Enlarge is the negative marker case |
| Haste Lethargy | Actual Haste action sequence and loss of Haste |
| Harm / Spirit Guardians slowdown | Native spell application and lifecycle |
| Exhaustion / Petrified recovery | Clearly labeled initial-affliction fixtures, paid Greater Restoration |
| Unconscious | Clearly labeled initially-Prone fixture, explicit finite Unconscious, native turn expiry |

Only overhead marker layers participate in the cycle. Existing body/ground
animations, including chains, hearts and runes, keep their own playback. Marker
cycling does not rotate the artwork. New glyphs use steady source pixels with
short application/removal opacity fades.

Delivered gallery:
- `.runtime/debuff-markers-20261005-review/index.html` — 48 four-camera clips,
  existing engine gallery format, with saved input histories and frame traces.
- `.runtime/debuff-markers-20261005-review/feed.html` — wheel/arrow-key playback.
- All 48 selected recordings passed their capture/replay checks. All linked
  videos, posters, inputs and traces exist; gallery/feed/media manifest return
  HTTP 200 from the local review server.
- Size-change clips use the final renderer that keeps overhead glyph size
  independent of creature scaling. Source recordings are retained separately.
- Sampled final Fear and Hold Monster/Reduce frames show the marker with the
  original spell/chain VFX continuing. Earlier sampled Bane, Charm, Grovel,
  Exhaustion and Unconscious frames are recorded in the review receipt above.

Outstanding: Ray of Frost still requires a correct recipient fact in the existing
condition disclosure path. This gallery does not claim that missing binding is
complete. Native dying/stable life state also remains distinct from explicit
Unconscious condition membership; no new zero-HP rule was introduced.

## User correction: overhead glyph sizes

Measured original visible alpha bounds (alpha ≥32), rather than transparent
canvas dimensions. Blindness is about 15×11 and Deafness about 12×11 at media
reference scale. New glyphs now fit within 15×13, keeping their aspect ratio,
through existing per-media scale values. Original art, marker timing and body
VFX are unchanged. The initial 48-clip gallery predates this size correction.

| Marker | Previous pixels | Corrected pixels | Media scale |
| --- | --- | --- | --- |
| frightened | [26, 20] | [15, 11] | 0.28302 |
| exhaustion | [24, 22] | [14, 13] | 0.30233 |
| poisoned | [26, 18] | [15, 11] | 0.29412 |
| paralyzed | [24, 22] | [15, 13] | 0.30233 |
| petrified | [24, 23] | [13, 13] | 0.28261 |
| prone | [24, 20] | [15, 12] | 0.30612 |
| unconscious | [24, 24] | [13, 13] | 0.27083 |
| commanded | [24, 20] | [15, 13] | 0.30612 |
| slow | [24, 20] | [15, 13] | 0.31707 |
| sickened | [28, 20] | [15, 11] | 0.27273 |
| reduce | [24, 22] | [15, 13] | 0.30233 |
| bane | [11, 18] | [8, 13] | 0.54167 |
| charmed | [13, 16] | [11, 13] | 0.8125 |

All thirteen glyphs inspected together against the two references. Nine
existing compositor/marker-cycle tests pass after the data correction.

Size-correction review: `.runtime/debuff-markers-20261005/runs/20261005T013650Z-4bf253/`
contains refreshed Petrified, Fear and Hold Monster/Reduce recordings.
All-thirteen comparison and measurements: `.runtime/debuff-marker-size-audit/`.
The fresh Petrified four-camera frame was inspected at its actual gallery scale.

## Distinct Slow and reduced-movement symbols

Integrated accepted `distinct-slow-v3`: Slow retains its crimson hourglass and
original body film; Spirit Guardians' movement penalty now uses the gold boot
with a downward arrow. Their marker groups are `slow` and `movement_slowed`, so
coexisting effects occupy separate cycle slots. Multiple movement-only owners
share one boot slot, and removing one retains the surviving owner's cue. No boot
is synthesized from Slow's own speed reduction. The new bank fits the same 15×13
reference footprint. Earlier recordings predate this icon replacement.

Ray of Frost remains unbound pending its existing recipient-fact gap; no cue was
attached to its caster tracker. This change adds no gameplay conditions or rules.

## Ray of Frost recipient gap resolved

RayOfFrostEffect now lives on its affected victim, so ordinary condition facts,
initial snapshots, disclosure and removal all identify the correct actor. It
reuses the existing source-turn expiry handler used by Sunbeam: target turns do
not expire it; the caster's next turn does. Dead/departed sources use that helper's
existing next-round cleanup. Removed the redundant affected_target_uuid field;
there is no new renderer bridge, event type or duplicate marker condition.

The recipe uses the movement_slowed boot and preserves Ray's own source-authored
relationship/classification metadata. Native cast tests cover hit/miss, correct
application/removal event recipient, target-turn survival and source-turn speed
restoration. Freedom of Movement and the existing legacy deadline assertions now
check the victim-owned condition. The fresh two-observer recording includes real
encounter advancement to expiry. Earlier notes describing the unbound gap are
superseded by this correction.

Ray correction verification: 80 focused engine/weather/spell-family/marker tests
passed, plus the existing manual Ray deadline regression (1 passed). Scoped
`evocation.py` typing reports zero errors/warnings. Both native hit recordings
passed replay checks in `.runtime/ray-frost-marker-20261005/runs/20261005T015102Z-846ec5/`.
The sampled four-camera impact frame shows the boot above the victim, not caster.
