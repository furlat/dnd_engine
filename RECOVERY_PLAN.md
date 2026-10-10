# NDClient migration — current entry point

Updated 10 October 2026. This is a compact status/index, not another implementation specification. Keep it current; put historical detail in `agent_docs/history/`.

## Current scope

**10 October assembly-authoring completion:** the review's missing door/timber
connection is now implemented. Existing typed bank/door/library owners carry the
physical contacts, camera registration, effective mounts, compatible members and
fractional timber supports. The
[assembly-authoring pre-phase plan and result](agent_docs/NDCLIENT_ASSEMBLY_AUTHORING_PREPHASE_PLAN_2026-10-10.md)
records scope and verification. Asset/authoring preparation is complete; next is
client setup and the shared runtime. N0 remains partial. No artwork was recopied.
The client preparation is committed at `df5397e` (`first push - pre implementation`).
This checkpoint does not imply that the separate engine worktree is committed.
Test Fireball's authored light in the shared renderer first; author the remaining
spell light curves in a later phase, as agreed with the user.

- Fresh repository: `/home/tommaso/Dev/NDClient`, branch `codex/ndclient`. Repository, agreed asset copies and core tracked authoring preparation are complete. The Goblin/Demon leaf material and full sheet review are implemented; game renderer, UI and SDK integration have **not started** in this repository.
- Ordinary VFX and the completed Factory replacement delivery are prepared in separate spell, condition, area and action folders. The replacement delivery covers **28 spell families, 193 paired banks and all 38 formerly pending XYZ references**. Full authoring is preserved; retired XYZ remains excluded and renderer implementation remains outside this step.
- The delivered engine/server and Python/TypeScript SDKs remain the backend. The deleted client is not an implementation baseline.
- The asset-to-authoring preparation in master plan §5.1.1 is **implemented**. NDClient `authoring/` is the Git-tracked editable copy, seeded once through the existing exporter and updated to replacement storage/clocks and readable `/media/` paths. It contains all 149 drafts, 160 condition recipes and 193 paired banks. Pygame JSON was not overwritten. The client assembler reads this copy without engine imports or intake receipts; complete application-release integration remains part of N0.

## Next implementation work

Environment companion adoption is complete (10 October): 42,805 required files (1114.43 MiB) were copied into the existing readable family folders. Tracked authoring now includes all 324 selected banks (24,632 pose/frame associations), the selected static resources, device/hatch layers and 725 library families (67,272 explicit samples). All seven assembly closures are connected to typed authoring; source records remain inspection provenance.

Existing colour, source rectangles, pivots, scales, IDs and clocks remain unchanged.
Native sampling, normals, support/role masks, parent receivers and D6's arch mesh
are normalized at their current owners. Existing RG16LE depth remains intact.
Source art and supplier data are unchanged; new media stays Git-ignored and
authoring stays tracked. The normal assembler reads current authoring directly,
without a supplier receipt interpreter. Master §6.1 governs the next shared
renderer/light consumers; installation does not claim visual acceptance.

**Character authoring pre-phase is complete (9 October).** Current tracked client
JSON explicitly owns all 85 registered Goblin/Demon source effects (19 on, 66 off)
and all existing animal/dinosaur shadow companions (98 added links). Existing
layer types carry enabled/opacity/tint and the optional shared material record.
Consume master §7.4's settled contract; do not repeat this migration or start game
runtime work merely to finish this asset-preparation step.

Follow master plan §§1.2/5.4/10; do not repeat repository creation, asset copying
or the one-time authoring import. The selected EnvironmentDocument is now tracked
and assembled too: 324 banks, 11 doors, 12 traps, 113 props and 28 wrecks, retaining
existing registrations and their original 1,030 media references, now supplemented
by the adopted library and geometry channels. The whole authoring resolves 126,959
distinct media references. Environment files
are now organized by family under `authoring/environment/` and `.media/environment/`;
the 60 received source records are tracked and linked to existing relevant owners.
Water registrations and static companion reference support are repaired. Physical
assembly qualification and rendering consumption remain distinct from adoption.
The four existing item appearance/material/variant/source-palette sections are
now tracked and assembled too, with 325 missing equipment sheet references
connected to the installed modular library across existing authored actions.
UI authoring adoption is also complete: `authoring/ui/index.json` assembles the
existing five UI sections with 620 icon keys, 43 exact creature portrait assignments,
618 free portraits, five documented premade defaults and all 103 choice records.
The modular Skeleton Warrior portrait assignment and dedicated Unarmed icon remain
explicit, non-blocking artwork follow-ups. Rejected old skin art is excluded; Pygame JSON is unchanged.
The assembly-authoring amendment is complete. Next generate current
authored TS types once, extend the existing package with the application/current SDK
and serve the existing media tree. Then connect the shared production
reducer/compiler/renderer used by play and recorded-server Studio cases.
Native amendments block their affected features only. Fireball’s impact storage
now carries the accepted demo’s world-light curve, adopted at the user’s request
on 10 October. Other spell VFX world-light curves are deferred until Fireball has
been tested in the shared renderer; they will use the same optional emitter field.
No runtime placement or visual quality
is implied by files being installed and references resolving.

## Delivery contract

The **[complete NDClient implementation plan](agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md)** is the maintained specification. Its [NDClient repository copy](/home/tommaso/Dev/NDClient/agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md) carries the same requirements; refresh it when the master changes. The linked assembly pre-phase plan records the completed data amendment, not another pending phase. Resume at §1.2 / N0 for application loading, source-derived authored types and current SDK integration. Consult the relevant sections and source owners; older repair plans cannot override this plan or current user instructions.

- Deliver the playable Fighter/Sorcerer dungeon and all selected authored content. Studio consumes recorded **real server events**, using the same production reduction, timed tracks, renderer and resource ownership as play; its timeline exposes those tracks and layers.
- Preserve complete authored lifecycles and existing types/bindings. Keep server progress, stream consumption and displayed animation time independent.
- Consume authored layers, elevation, contacts, pivots, compatible assemblies and camera views. Preserve sprite proportions. Depth, normals and lighting supplement this geometry; they do not replace it.
- No guessed offsets, duplicate simulation, preview-only renderer, arbitrary budgets or validation loops. Retain accumulated corrections in the detailed plan.

## Asset state

Read **[ASSETS.md](ASSETS.md)** before artwork work; it owns selections and source locations.

- Prepared: `.media/smallscale/modular/` holds the **complete unified Fantasy V1.3** library; `.media/smallscale/authored/` holds **all owned** fixed-creature sheets, using combined/with-shadow sources and the now-authorized 1,368 original Goblin/Demon clean-body components for independent layer controls; agreed Fantasy environments/metadata; **smooth48 icons and 192×256 portraits only**. Preserve original sources and existing bindings; copies remain Git-ignored in readable family folders with meaningful source filenames. No hashed storage, checksums or deduplication machinery.

- Character layer controls are prepared for all 65 Goblin/Orc and Demon characters,
  all 1,368 combined sheets, with original body/shadow/effect references. The asset
  review at `http://127.0.0.1:8798/` uses the reusable Pixi material; it is not Studio
  or an event renderer. Client `authoring/characters/README.md` owns its equations,
  tested controls and limits, plus the Pygame integration scan. Existing 44 rigs,
  452 semantic clips and 767 body contexts are preserved. Source composition is
  ready; the pure sampler/layer resolver, full palette/material consumers and
  support-shadow/physical coverage consumers remain runtime work. The source links
  and typed authored controls are complete; other fixed packs retain initial
  partition annotations.

- Environment geometry companions and door/timber assembly authoring are connected; shared runtime consumption remains. Earlier missing-export entries in the [environment handoff](agent_docs/audits/ndclient-environment-assets-20261009/README.md) do not justify regenerating those closures.
- [VFX intake](agent_docs/audits/NDCLIENT_VFX_ASSET_INTAKE_2026-10-09.md) now includes the 23 replacements plus Sleep, Burning Hands, Thunderwave, Color Spray, Ice Knife's burst and shared ground-fire/Web aliases. **No retired VFX XYZ copying, conversion or fallback.** Preserve new depth/normal data, existing recipes and unaffected flat/procedural effects. Ice Knife's burst is enabled in client authoring; rendering still awaits the shared runtime. Desert remains deferred; copy completion is not renderer acceptance.

## Historical evidence — on demand only

The former recovery plan is preserved verbatim in the **[recovery diary](agent_docs/history/RECOVERY_DIARY_2026-10-09.md)**. Do not routinely load it. Its relative paths refer to the repository root; its old status and execution instructions are historical, not current authorization.

The former ASSETS.md is preserved verbatim in the **[asset diary](agent_docs/history/ASSETS_DIARY_2026-10-09.md)**. The compact current ASSETS.md locates the selected library, Godot Factory and Blender destruction sources; do not routinely load the diary.
