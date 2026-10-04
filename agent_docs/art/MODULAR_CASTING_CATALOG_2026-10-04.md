# Modular casting motions and effects — 2026-10-04

An authoring reference for choosing **motion → Magic hand style → optional Effect → spell palette**. Godot exports remain the main spell VFX. Buffs are excluded. This catalog does not change production spell assignments, runtime code or artwork.

[Interactive catalog](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/index.html) · [Layered contact sheet](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/layered-studies.png) · [JSON](MODULAR_CASTING_CATALOG_2026-10-04.json)

## Evidence and interpretation

- 30 body motions and 240 motion/layer combinations: Magic1–3 and Effect1–5. The JSON records source SHA256, availability and nonempty frames for all eight facings.
- Direct inspection: body atlases across all motions; five SW phases for each core cast/attack and running/riding attack; opposite NE samples for core motions; two SW phases for remaining Magic combinations. The animated catalog exposes all frames/facings. This is not an exhaustive animation-quality certification.
- Source facts, original handwritten labels, our visual observations, your observations and proposed uses are separate fields. Suggested spell meanings are interpretations, not mechanics.
- Approximate gesture phases are descriptive. They must not overwrite production release frames or pose sockets.
- Contact sheets keep source registration and use nearest-neighbor enlargement for inspection. The shared frost palette enables comparison; layered studies use seven actual current spell palettes. Palette replacement preserves source alpha, rather than multiplying/tinting source RGB.
- Magic source pixels exist on all 30 motions, but some rest/locomotion samples are almost invisible. Nonempty is not the same as a useful aura.

## Main motion choices

| Motion | Observed gesture | Proposed use | Caution |
|---|---|---|---|
| Special1 | Raises/gathers the hands, dips through the knees with arms forward, then rises and opens the arms upward/outward before settling. | Invocation, self-centered magic, power called from above. | Sky origin is a design interpretation; the pose itself does not specify where the spell lands. |
| Attack1 | Winds an arm overhead, brings the upper body and hand down through a chopping stroke, then recovers. | Weapon-bound magic and forceful close strikes. | Reads as melee unless equipment and delivery deliberately explain it. |
| Attack2 | Drops into a low, wide stance and sweeps through a lateral body turn, then returns upright. | Sweeping enchanted attacks or a directional release with a low stance. | Large body displacement and melee language can compete with a quiet cast. |
| Attack3 | Sets one arm toward the target, draws the other toward the head/shoulder, releases and lowers/repositions the arms. | Magical arrow casts or an explicitly spectral bow. | The gesture implies a bow; colored hands alone do not depict an imaginary bow. |
| Attack4 | Holds an arm high, sinks into a deep knee bend, and drives the hand/body down toward the ground. | Earth-driven effects, ground invocation, an impact sent into the floor. | Ground-centered extras must not imply additional affected cells or an extra mechanical hit. |
| Attack5 | Keeps a mostly upright stance, brings a hand forward and extends it toward the target, then retracts. | Bolts, rays and economical directed casts. | Use its actual hand/release socket; the optional skull or orbits are not projectiles. |
| Attack6 | Leans into a low forward lunge with a punching/thrusting arm motion, then straightens and recovers. | Forceful bolts, beam-like releases, piercing spell-attacks. | Beam-cast interpretation is plausible; the source is a thrust, not a literal two-handed beam charge. |

Your gesture descriptions are broadly supported. Two qualifications: Special1 does not itself establish a sky origin; Attack6 is a low one-arm thrust, although it can plausibly accompany a beam. Attack3 implies a bow, so a spectral-bow cast needs an intentional visual explanation beyond glowing hands.

## What the Magic layers contribute

| Layer | Observed hand style |
|---|---|
| Magic1 | Fine, sparse, flickering particles. |
| Magic2 | Broader wisps/ribbons and trailing hand energy. |
| Magic3 | Compact bright glows with shorter flecks. |

These descriptions come from the core casting/attack observations. They are style choices, not fixed weak/medium/strong tiers. Each uses its own action-matched sheet and follows that action’s hands. For non-core Magic combinations the JSON marks footprint, competition and suitability unverified; sparse locomotion/rest frames must be inspected before any assignment.

## Effects 1–3: different geometry for each action

| Motion | Effect1 | Effect2 | Effect3 |
|---|---|---|---|
| Special1 | A small ring forms at the feet, then becomes a broad multi-line ground circle and upward radial flare as the arms open. **High competition.** | Loose concentric particle spirals surround preparation; a field of upward energy spikes appears around the arm-open phase. **High competition.** | A wide ring of small particles builds, followed by a relatively narrow vertical cage/column around the rising body. **Medium competition.** |
| Attack4 | Fine particles precede a foot-centered circle that expands into a broad flashing ring after the downward motion. **High competition.** | Several radii of tall upward spikes surround the figure through the overhead-to-ground motion. **High competition.** | Energy descends toward the body, then a segmented radial burst spreads from the feet. **High competition.** |
| Attack5 | Small directional flare/ring at the forward/off-hand region; it follows the pointing sequence and disappears. **Low competition.** | Two large bright bodies orbit around the caster with long curved trails, then fade. **High competition.** | A large directional skull grows in front of/over the figure and dissolves. **High competition.** |
| Attack6 | Brief narrow directional flare at the thrusting hand during the low lunge. **Low competition.** | A narrower group of tall spikes is strong during preparation, then mostly fades to scattered sparks around the thrust/recovery. **Medium competition.** | Descending energy in preparation leads to a segmented foot-centered radial burst after the thrust. **High competition.** |

Your Effect1/Attack5 and Attack6 observations hold: they are comparatively restrained hand accents. Effect2/Attack6 is quieter at release but has strong tall preparation spikes; it is not delicate throughout. Effect3/Special1 becomes more contained late, but its initial particle orbit is broad. The Effect3/Attack5 skull is a deliberate necrotic signature, not a generic aura.

## Effects 4–5: frequent candidates

- **Effect4:** broader and brighter body contour/afterimage, with more spread from the limbs.
- **Effect5:** finer, tighter patterned contour, less surrounding spread.
- Both depend on the pose. Attack5 reads more subtly than wide/low Attack2 or Attack6. Their source sequences fade outside active poses; they are finite cast/attack accents.
- They are good frequent candidates alongside one Magic layer. Choose one body accent first; stacking both must earn its extra visual density.
- They are present for Special1, Attack1–6, AttackRun/AttackRun2 and the two mounted attacks. Their Idle, ordinary locomotion, damage and death sheets are blank. They cannot become persistent condition auras simply by binding those sheets.

## Other motions and availability

| Motion group | Magic1–3 | Effect1–3 | Effect4–5 |
|---|---|---|---|
| Special1, Attack4–6 | Available | Available; per-motion geometry above | Available |
| Attack1–3 | Available | Blank | Available |
| AttackRun, AttackRun2 | Available | Blank | Available |
| RideIdleAttack1, RideRunAttack1 | Available | Available; mounted variants | Available |
| Remaining 19 motions | Nonzero source pixels; often faint in rest/locomotion | Blank | Blank |

On running attacks, Effect4 gives stronger body/arm energy and Effect5 a finer patchier contour; sampled final frames fade. Mounted Effect1 is a small side ring, Effect2 has early vertical streaks, and Effect3 ends in a broad floor burst. The mount is omitted from these study composites; no standing-cast or mounted-footprint equivalence is inferred.

### All body motions

| Motion | Description |
|---|---|
| Special1 | Raises/gathers the hands, dips through the knees with arms forward, then rises and opens the arms upward/outward before settling. |
| Attack1 | Winds an arm overhead, brings the upper body and hand down through a chopping stroke, then recovers. |
| Attack2 | Drops into a low, wide stance and sweeps through a lateral body turn, then returns upright. |
| Attack3 | Sets one arm toward the target, draws the other toward the head/shoulder, releases and lowers/repositions the arms. |
| Attack4 | Holds an arm high, sinks into a deep knee bend, and drives the hand/body down toward the ground. |
| Attack5 | Keeps a mostly upright stance, brings a hand forward and extends it toward the target, then retracts. |
| Attack6 | Leans into a low forward lunge with a punching/thrusting arm motion, then straightens and recovers. |
| Idle | Small standing weight and arm changes. |
| Idle2 | Bent knees and a guarded arm position with slight shifts. |
| Idle3 | Upright narrow stance with minimal movement. |
| Idle4 | Bent-arm ready stance and small weight shifts. |
| Walk | Alternating leg stride with arm swing. |
| Run | Forward-leaning long stride and stronger arm motion. |
| RunBackwards | Guarded upright torso with retreating footwork. |
| StrafeLeft | Sideways stepping gait with stable upper-body facing. |
| StrafeRight | Opposite sideways stepping gait. |
| AttackRun | Running stride combined with a raised-arm chopping attack. |
| AttackRun2 | Running stride combined with a more forward-reaching arm strike. |
| Kick | Lifts a knee, extends the foot and returns to stance. |
| CrouchIdle | Low stationary stance. |
| CrouchRun | Low stepping motion with bent knees. |
| Rolling | Drops and rotates the body through a low horizontal roll, then rises. |
| Slide | Drops into a low extended-leg sliding posture then recovers. |
| TakeDamage | Brief backward upper-body recoil then recovery. |
| Die | Loses upright posture and falls back to a sprawled terminal pose. |
| Taunt | Raises an arm and gestures while standing. |
| RideIdle | Bent seated leg posture and upright arms. |
| RideRun | Seated pose with riding bounce. |
| RideIdleAttack1 | Seated stance with raised-arm and follow-through attack. |
| RideRunAttack1 | Mounted attack layered into riding motion. |

## Layered combinations and progression

These eight study presets can be played in the catalog, with individual layers toggled. Names/palettes illustrate composition; they do not assign the named spell to that motion. Full Godot effects are not included, so compatibility with each final spell remains a composition check.

| Study | Motion | Layers | Palette | Why / limit |
|---|---|---|---|---|
| Quiet directed cast | Attack5 | Magic3 + Effect1 | ray_of_frost | Compact hand accent; leaves the projectile silhouette clear. |
| Empowered directed cast | Attack5 | Magic2 + Effect4 | fire_bolt | A fuller hand trail plus body accent; no decorative floor ring. |
| Forceful thrust cast | Attack6 | Magic2 + Effect1 + Effect5 | eldritch_blast | Short hand release plus tight body contour. |
| Broad invocation | Special1 | Magic3 + Effect3 + Effect5 | guiding_bolt | Body opening and rising energy; inspect the early orbit for competing geometry. |
| Ground invocation | Attack4 | Magic2 + Effect1 + Effect4 | hold_person | Intentional large ground signature; not a default addition to all casts. |
| Necrotic signature | Attack5 | Magic1 + Effect3 + Effect5 | chill_touch | Skull is the chosen signature; its size must be judged beside the Godot effect. |
| Magical arrow gesture | Attack3 | Magic3 + Effect5 | ray_of_frost | Pose study only: does not supply artwork for a spectral bow. |
| Intentional congestion comparison | Special1 | Magic2 + Effect1 + Effect2 + Effect3 + Effect4 + Effect5 | fire_bolt | Not recommended: shows why simply stacking effects is not spell progression. |

- Select pose by delivery direction and gesture, not level alone.
- Use Magic1–3 for the hand style; Effect5 is a tighter accent and Effect4 a broader/brighter one.
- For stronger presentation, use one intentional signature or a fuller body accent, not every available layer.
- Keep Effect1–3 wide floor/orbit/skull shapes deliberate; a shared palette cannot remove their geometry.
- Repeated, multi-target and rapid casts need restraint even at high levels.
- A larger casting flourish must not communicate a false mechanical area or extra impact.

For level progression: quiet casts can use a compact hand layer; more forceful casts can add one body accent; major invocations can earn a distinct ring, column or skull when the main effect leaves room. Spell role and repeat frequency matter as much as level. Floor effects remain deliberate because they can conflict with future rune art or suggest a false affected area.

## Material inside the alpha mask

[Three-way material contact sheet](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/material-comparison.png) · [exact receipt](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/material-study.json)

The preview compares the same Attack5 + Magic2 + Effect3 + Effect5 composition, SW, using:
1. Three exact current Chill Touch palette colors.
2. The same colors with the already-delivered hand-noise treatment inside each original alpha mask.
3. The existing accepted Chill Touch necrotic material ramp plus that noise, as an explicit alternative to three-color inheritance.

**Observed:** the noise version introduces mottled variation; the accepted necrotic ramp makes the skull markedly darker. Both retain its large shape and motion. This demonstrates a feasible material treatment through the mask, not a universal improvement.

**Recommendation:** exact palette replacement first, especially for Magic and Effect4/5. Use an existing material treatment selectively when its texture helps a chosen spell. A shared palette/material cannot fix clashing geometry. Full Godot lighting, bloom, normals, XYZ, distortion and simulation are not transferred by this mask study. No new shader or production binding was introduced.

## Visual files and source receipts

- [Seven core action matrices and all other contact sheets](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/index.html#contacts)
- [Original NeuroClient notes](http://127.0.0.1:8768/modular-effects-preview-20261004/catalog/../original-notes.json)
- Original source: `/home/tommaso/Dev/NeuroClient/app/public/spritesheets/`.
- Source cells: 128×128; 15 frames per strip; 12 fps; eight facings.
- JSON contains all 240 per-motion records, exact source hashes, frame availability, original notes and material provenance.
- Private reproduction scripts and pixels: `.runtime/modular-effects-preview-20261004/catalog/`.
- Runtime code, events, game rules, accepted art and production spell bindings were not modified for this study.

## Validation and independent reviews

- Browser checks passed: nine representative motions, all eight facings, pause/frame scrubbing, palette replacement, layer toggles and 25 links, with no browser/HTTP errors. Final checks also confirm preset text resets and faint non-core entries are described honestly.
- Data checks cover 30 motions, 240 unique combinations, 1,920 facing records, matching public/private JSON, source hashes and valid contact links. Material generation asserts identical original alpha per source layer.
- Independent anti-slop review: closed after correcting overly confident descriptions of faint non-core Magic and stale preset text. Layered and material contact sheets support the bounded conclusions.
- Independent ECS/data review: closed after saving every exact palette treatment and applied-noise setting. The catalog remains passive authoring data with no gameplay coupling.
- Validation receipt: `.runtime/modular-effects-preview-20261004/catalog/validation.json`. No outstanding findings within this study scope.
