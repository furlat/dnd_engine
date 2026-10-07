# Full BG3-inspired icon replacement — 2026-10-07

The old icon bank was rejected. This delivery replaces all 620 exact icon keys with 594 newly generated original glyph images, preserving only the existing explicit shared-image bindings. All 103 delivered native choice bindings are covered. There are no old-image fallbacks.

**Status:** full generation, recolouring and file-contract validation complete. The user's latest preference is **smooth UI icons alongside the pixelated game world**. Smooth144 is the recommended runtime format and is the default in the preview and exact bindings. Final in-game sizing and visual validation remain for production; runtime installation has not been performed. CIE28 is retained for comparison/archive after the user rejected its aliased appearance. Do not describe file validation as art approval.

## Files and preview

- [Searchable comparison gallery](http://127.0.0.1:8784/ui-icons-bg3-glyphs-2026-10-07/): 24 entries per page, family/search filters, exact keys, smooth144 and CIE28 side by side. The touching strip uses smooth artwork at 28/40/48/56 screen pixels; 48px is the preview default, not a locked production size.
- [Two-format delivery ZIP](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/ui-icons-bg3-glyphs-2026-10-07.zip)
- [Complete manifest](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/manifest.json): per-file dimensions, byte sizes and SHA-256 hashes, original provenance, target keys and choices.
- [Exact replacement bindings](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/replacement-bindings.json)
- [Choice bindings](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/choice-bindings.json)
- [Validation result](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/validation.json)
- [Generation inventory](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/generation-plan.json)
- [Colour decisions and reasons for every icon](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/COLOUR_DECISIONS.md)
- [Machine-readable colour bindings](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/colour-bindings.json)
- [Before/after colour trial](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/review/colour-trial.png)
- [Complete coloured bank contact sheet](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/review/complete-colour-bank.png)
- [Interactive pixelation comparison](http://127.0.0.1:8784/ui-icons-bg3-glyphs-2026-10-07/pixelation.html)
- [Pixelation research and actual results](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/PIXELATION_RESEARCH.md)
- Full selected imagegen originals are preserved privately in `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/authoring/originals/`. They are authoring sources; the portable runtime delivery contains the two requested final resolutions.
- Full-resolution recoloured masters are preserved privately in `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-bg3-glyphs-2026-10-07/authoring/colour-masters/`. Original generated PNGs remain immutable. Neither master directory is included in the compact runtime ZIP.

## Style and formats

Built-in imagegen drew each icon separately as smooth antialiased fantasy contour artwork, informed by the local BG3 Wiki reference study. BG3 files are reference material only and are not shipped as our artwork. The earlier rejected bank and pixel-art study were not used as final pixels.

Every distinct image has an **unpixelated 144×144 RGBA** PNG and a **native CIE28 28×28 RGBA** PNG. Smooth artwork is preserved before pixelation. The 28px image is derived from smooth144 using premultiplied-alpha resampling and one pass through the existing CIE palette pipeline. Neither variant contains a baked UI border. Transparent alpha is retained; no opaque black tile backing is required.

**Use smooth144 for the UI.** Normal texture filtering resizes these assets to the chosen screen slot without enlarging a coarse 28px grid. The pixelated world rendering and any separate pixel-art border overlay are independent. High-quality UI artwork does not require changing world sprites or terrain. The ZIP retains both formats for comparison; production only needs to load the selected smooth bank.

## Colour correction and why

The generated bank initially left 393 entries with an ivory default. The user requested a deliberate colour taxonomy before export. Every one of the 594 image subjects now has an explicit function/effect family and reason in `colour-bindings.json`, including its native key aliases, measured BG3 reference colour where available, and backend catalogue metadata for identified spells. This is not a universal spell-school rule: Burning Hands, Healing Word and Hold Person demonstrate different functional families. BG3 relationships are observations from the actual reference images, not invented gameplay rules.

The main families are orange fire, cyan cold, cobalt lightning, steel-blue thunder, lime acid/poison, jade necrotic harm, turquoise healing/vitality, amber protective buffs, pale-yellow radiant, blood-rose control/curse, scarlet force damage, slate/cyan utility, vermilion martial attacks and bronze/steel physical materials. There is no purple/violet/magenta family. Necrotic damage is distinct from healing; defensive force walls are distinct from force-damage projectiles. Class and UI resource colours are recorded as categorical visual conventions, not new mechanical effects.

Important explicit exceptions: Chill Touch is necrotic despite its name; Death Ward is protective; False Life grants temporary vitality despite its school; Stinking Cloud is action-denial control rather than poison damage. The custom Necrotic Bless denotes undead magic and does not acquire damage from its colour. Fire Shield Warm/Chill, elemental protection and Spirit Guardians Radiant/Necrotic use the chosen effect's colour. Color Spray and Prismatic Spray retain separate authored ray accent regions instead of losing their deliberately multicoloured meaning.

The approved geometry is retained through a deterministic **full-resolution OKLab ink-ramp transform**. It changes RGB only, retains original alpha pixel-for-pixel, and uses narrow tinted highlights rather than white body strokes. The two delivered resolutions are rebuilt from the recoloured master. CIE76 and the native 28px grid remain the existing method; the shared palette is extended with these semantic colour ramps so CIE export does not quantize teal/rose/cobalt back to ivory. The original game palette and profile are included for provenance; `ui-semantic-palette.json` and `ui-semantic-cie28.json` are the profiles used for this delivery. No runtime colour inference or tinting is required.

The file validator independently compares full-resolution master alpha with the immutable generated source, then reconstructs source alpha at both final sizes and compares it exactly. Receipts retain source hashes, colour-master hashes, the selected family/ramp/reason and measured final colour statistics. Preserve these as evidence; do not treat a colour transform as a new imagegen source.

The final 144px bank occupies 13.63 MiB and the 28px bank 0.87 MiB before ZIP compression. Keep high-resolution authoring originals outside the runtime asset payload.

Broad glyphs whose tips would reach the CIE28 canvas boundary receive a one-pixel transparent inset in that derivative. The original and smooth144 images stay unchanged; `pixelEdgePadding` records the adjustment in their receipts.

The full Slow spell uses a rose/crimson hourglass. Reduced movement from Ray of Frost or Spirit Guardians uses a blue boot cue; those effects do not inherit the full Slow spell icon. Targeted review revisions also distinguish Fire Shield Warm from Chill, elemental protection choices, radiant from necrotic Spirit Guardians, and holy Death Ward from necrotic damage. Thunder protection shows sound waves rather than a lightning bolt. Revision evidence and the previous selected originals remain in `authoring/revisions/`; only the selected versions are delivered in the two bank formats.

| Family | New images |
| --- | ---: |
| spell | 129 |
| action | 80 |
| reaction | 5 |
| choice | 48 |
| condition | 170 |
| class_feature | 1 |
| trait | 34 |
| ui | 16 |
| item | 97 |
| object | 14 |

## Integration contract

1. Bind through `replacement-bindings.json` by exact native key. Each binding has `preferredFormat: smooth144` and a `file` pointing to that smooth PNG; both explicit format paths remain available. Preserve the existing intentional shared bindings; do not invent new mechanical aliases or use runtime substring matching.
2. Use the 144px smooth assets for action bars, choices, conditions and other UI icons. Use normal linear texture filtering (CSS `image-rendering: auto` for the web UI), and choose the final screen slot size in production. Do not apply the world's nearest-neighbour texture policy globally to these UI icons. The preview tests 28/40/48/56px; its 48px default is not a required game size. CIE28 remains comparison/archive and is not the selected production treatment.
3. Borders, cooldowns, disabled state, selection, resource costs and targeting highlights belong to the UI overlay. The artwork does not encode those states. Keep action slots touching (`gap: 0`) as requested, without building spacing or golden frames into the image.
4. `choice-bindings.json` retains the existing native spell/action/choice identifiers, including conjure and summon subjects, elemental protection, Fire Shield variants and shared wall shape/side choices. This is artwork mapping, not a gameplay change.
5. Seven additional declared active subjects are included: Traverse Connector, Aegis Training, Hit Save Rider, Keen Perception, Multiattack, Innate Flight and Magic Resistance. Owners and previous installed paths are recorded in the manifest. The Test Bless fixture, portraits, world sprites and rejected HUD skin are outside this delivery.
6. The ZIP has relative paths and can be relocated as a unit. Source/reference paths inside authoring evidence describe generation provenance and are not runtime loading dependencies.

## Verification and limits

The validator checks full inventory coverage, exactly one asset binding per native key, choice coverage, PNG dimensions/mode, actual alpha, transparent corners, preserved selected originals, exact alpha preservation through recolour/export and SHA-256 integrity. Review sheets and the browser gallery compare real generated files at both sizes. Any canvas-edge observations are recorded in `validation.json` as review flags; they are not hidden or substituted with older pixels.

Native human-readable names and descriptions informed each individual prompt. Prompts and actual reference paths are saved per asset in `authoring/prompts`; immediate generation receipts are in `authoring/receipts`. This preserves a resumable and auditable batch after the previous desktop crashes.

Generation input provenance: 11 final item/object originals were generated from the detailed style/subject prompt without an image reference. Their requests and receipts explicitly record an empty reference list and `prompt-only` mode; no reference image is falsely claimed for those calls. The actual selected originals were visually inspected with the final recolour.

Pixelation review: 18 actual icons were tested with direct linear-light resampling, a restricted ink ramp, soft alpha coverage and mild stroke expansion. Filter-only changes were modest; strong stroke expansion can close holes. Native 56px retains more contour detail in a 56px slot. After this comparison, the user preferred the unpixelated artwork. The production recommendation is now smooth144 with normal filtering; no further pixelation pass or image generation is required. Research trials remain separate, and final in-game size and readability still need visual review.

Review: one subject per icon, no image-sheet cutting, no old rejected-master fallback, explicit colour reasons, smooth-first pixelation and separate UI framing. This is an offline data/art delivery, with no runtime architecture or spell mechanics changed. No messages were sent to other threads.
