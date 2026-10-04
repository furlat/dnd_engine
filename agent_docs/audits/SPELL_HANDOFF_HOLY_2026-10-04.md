# Holy artwork intake audit — 4 October 2026

Source inspection at commit `95a47cd5ca5`; no imports, implementation, native
execution or new visual acceptance. Source root:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/`.
This report covers the three entries in `holy-guardians-study/HANDOFF.md`.

## Findings

| Spell | Accepted source | Current production | Asset decision | Integration work / rank |
| --- | --- | --- | --- | --- |
| Spirit Guardians | `SPIRIT_GUARDIANS_HANDOFF.md`, `manifest.json`, `review.js`; `relaxed-flow-v5` | Backend caster-anchored zone exists; no spell binding or guardian spatial-media selection | No additional artwork required. Four component atlases hash-match: 2,312,482 bytes. Ground haze, orbit, trails and body contact include authored procedural composition, not a pre-rendered whole aura. | Medium/high presentation work: translate the supplied composition into shared, typed presentation data/operators; owner-local movement and trails, actual recipients, radiant/necrotic variant, removal and depth. Do not call this a JSON-only import. |
| Guardian of Faith | `guardian-of-faith/HANDOFF.md`, `manifest.json`, blade metadata and `review.js`; `lean-horned-v3` | Backend anchored object/zone exists; no selected guardian spell/object presentation | No additional artwork required. Eight native heading banks hash-match: 7,106,586 bytes. Reuse Spirit Guardians' radiant recipient contact; retain blade metadata. | Medium/high: object creation/idle, admitted target-facing strike, contact at strike frame 13, recovery/retirement. Same accepted component family as Spirit Guardians, distinct owner and rules. |
| Heroes' Feast | `heroes-feast/HANDOFF.md`, `manifest.json`, `review.js`; `spectral-material-v2` | Backend object/use/buff exists; no feast object media or spell binding. Eat action recipe explicitly disables actor animation. | Feast and blessing artwork are accepted and available. Four feast atlases hash-match: 1,870,514 bytes; four empty compatibility images add 2,224 bytes and need not ship. Actual eating gesture remains unfinished, but no missing new bitmap is established. | Later: verify/resolve the retained backend gaps, bind the prop and each eater, and author a reusable eating interaction from existing rig poses where suitable. Do not commission a new creature sheet from this finding. |

## Code evidence and boundaries

- `game/animation_data.py:263–411`: default selected bundles and spell recipes.
  No binding for these three identities exists in those bundles. Catalog text,
  condition relationship rows and an inert action recipe are not installed VFX.
- `game/data/world_bindings.json` / `game/data/environment_art.json`: no selected
  Spirit Guardians, Guardian of Faith or Heroes' Feast artwork.
- `dnd/spells/conjuration.py:2205`, `:2413`: Spirit Guardians owns zone slowing,
  admitted damage and concentration. The spell passes its `damage_type` to the
  zone; default is Radiant. Two approved art variants do not prove player-facing
  variant discovery. The visual orbit must not perform hit tests.
- `dnd/spells/conjuration.py:4352–4530`: Guardian of Faith is an anchored zone,
  ENTER-triggered, with 4,800-round duration and a 60 actual-HP-loss budget. The
  currently computed footprint is a 5×5 set, including corners. Draw received
  facts; do not turn the preview's radius or sword overlap into authoritative
  targeting. Any mechanics discrepancy is a separate backend decision.
- `dnd/spells/conjuration.py:4532–4736`: Heroes' Feast currently removes/prevents
  Poisoned and Frightened, adds Wisdom-save advantage and a per-eater 2d10 max-HP
  modifier. No explicit current-HP heal or disease-cleanse operation is present
  in this path. Buff creation omits a duration; `dnd/core/base_conditions.py:53`
  defaults to permanent. Object use keeps a consumed-user set but has no serving
  cap or feast-specific expiry. These dated handoff findings still match the
  inspected source. This audit does not authorize rule changes or implement a
  full rules review.
- `game/data/neuroclient/source/src/render/data/animation/contentActionPresentationRecipes.json:1771`
  contains `action.environment.heroes_feast.eat`: actor disabled, Idle, all
  milestones at frame zero. The existing potion-use recipe uses `Taunt` with
  hidden weapons and a frame-eight application. That is an available donor to
  inspect during implementation, not proof of an acceptable eating animation.

## Source completeness checked

All 20 listed holy manifest files were present and SHA-256 matched on this
inspection (including the four optional empty Feast placeholders). Contracts,
source composition and Guardian blade metadata are present. No game recordings
were regenerated or evaluated. Existing source approval does not certify
arbitrary actor sizes, terrain occlusion or in-engine timing.

The root holy handoff contains the current approvals. Historical candidate
paragraphs at the bottom of `guardian-of-faith/BACKEND_CONTRACT.md` describe its
earlier study and do not revoke `lean-horned-v3`.
