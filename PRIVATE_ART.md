# Private art setup

Public code, schemas and authored `game/data` bindings stay in the engine
repository. Images, spritesheets, raw coordinate images and XYZ packets under
`game/assets` come from the private art release. Installation never runs gameplay,
media importers or source audits; it never overwrites public bindings.

The preserved installed-art archive is `/home/tommaso/Dev/neurodragon_art`.
It is a source snapshot. The selected, packed production release is separate at
`/home/tommaso/Dev/neurodragon_art-production`, a local Git LFS repository. Current
remote publication is pending; install the local production release that matches
the checked-out public bindings:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
```

The installer copies listed payloads into their `game/assets` paths and records
the supplied manifest in `.runtime/art-manifest.json`. Repeating installation
reuses that receipt and skips unchanged entries whose installed files still have
the declared size. Changed release entries and missing files are copied. Source
and destination files are not compared or hashed during normal installation.
Unlisted local files and caches are preserved.

Manifest and receipt parsing is metadata-only. File access checks happen at the
copy/check boundary: parent-directory checks are reused only within that pass,
and every leaf is checked for redirection. A later install starts fresh checks;
normal installation does not hash the library.

The receipt does not detect manual edits of the same size. These are explicit
setup commands, never startup work:

```bash
# Check listed paths, sizes and LFS hydration.
uv run --no-sync python devtools/art.py check
# Also read and compare every payload with its published checksum.
uv run --no-sync python devtools/art.py check --hashes
# Restore every listed file from the selected release, ignoring the receipt.
uv run --no-sync python devtools/art.py install --source /path/to/release --reinstall
```

Before changing installed media, copy intentional authoring edits to the private
authoring location. Installation replaces changed release entries; it does not
merge pixel edits. A fresh empty asset destination is needed to check a trimmed
release's completeness, because an existing installation retains unlisted files.

Once the private remote is published, `install` without `--source` uses Git/LFS
and existing Git authentication. `--update` explicitly fetches the latest remote
release; `--ref` chooses a specific private revision/tag. Record the matching
public-code and art-release identifiers together. Tokens do not belong in URLs
or manifests. Normal gameplay has no network or installation dependency.

`export --destination /new/private/directory` preserves an installed tree in a
new directory and performs explicit offline checksum verification. The current
archive already exists; do not re-export it during ordinary setup. Neither the
exporter nor installer deletes source archives or rewrites Git history.

The implementation and packaging scope is in
[the cleanup plan](agent_docs/RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md).

Setup tests use tiny local bundles:

```bash
uv run --no-sync python -m pytest -q tests/test_private_art_setup.py
```

## Rebaking isolated casting palettes

Production keeps selected colored casting sheets. Uncolored authoring inputs
that no active renderer reads can remain only in the preserved archive. The
offline baker accepts that source root explicitly; it does not install those
originals or rewrite recipes/bindings:

```bash
uv run --no-sync python -m devtools.bake_spell_palettes \
  --source-root /path/to/preserved-art \
  --output-root /new/path/to/palette-review
```

Both roots use the existing `game/assets/...` layout. `--draft-file` selects a
particular bundle; its default is the current CodexFX, recovery and ice bundles.
Without `--output-root`, the command replaces the declared local colored sheets;
use a separate output directory to compare first. Without `--source-root`, it
uses the checkout's existing sources for compatibility with an authoring install.
Normal gameplay and the production test lane do not require those originals.
Palette tests use small explicit source images to check exact declared colors,
alpha and geometry; production checks read the selected sheets.

## Building a selected local release

`python -m devtools.pack_art plan` reads the source manifest and completed
inventory without opening payloads. `bindings` proposes exact file-address
changes in existing VFX page/part/resource bindings; it emits a patch and candidate
alias list into a separate directory. Neither changes current public bindings.

```bash
uv run --no-sync python -m devtools.pack_art plan \
  --archive /path/to/preserved-art --inventory /path/to/inventory.jsonl \
  --code-release MATCHING_CODE_REVISION --output /path/to/selection-plan.json
uv run --no-sync python -m devtools.pack_art bindings \
  --plan /path/to/selection-plan.json --candidate-aliases /path/to/shared-content.jsonl \
  --bindings-root game/data --output /new/path/to/binding-proposal
```

Review and apply the public-binding patch with the matching code release. Confirm
that every consumer of each proposed alias uses its canonical address; pattern
and packet consumers may require the separate packing adapters first. Only then
pass the reviewed map as `plan --applied-aliases /path/to/applied.jsonl`. Without
that argument, all selected duplicate paths remain present. Source identities
come from existing manifest metadata; planning computes no new checksums.

```bash
uv run --no-sync python -m devtools.pack_art stage \
  --archive /path/to/preserved-art --plan /path/to/selection-plan.json \
  --destination /new/path/to/production-art
```

Staging requires a new directory outside the archive. It copies selected payloads
and writes their installation manifest, preserving originals and unlisted source
material. It creates a selected base release; the commands below add packed
outputs. A successful metadata plan alone does not establish rendering equivalence.

## Packing and finalizing the release

`pack_media` writes standard ZIP_STORED archives containing the original gzipped
XYZ packets, and lossless color pages addressed by existing phase/page metadata.
`pack_environment` pages oversized color/depth strips, keeps only the selected
static doorway cells, and packs loose mechanism images. It retains independent
color/depth cell sizes and reads loose PNG dimensions before planning. Neither
resizes pictures, changes authored timing or overwrites public data.

```bash
uv run --no-sync python -m devtools.pack_media plan \
  --selection /path/to/selection-plan.json --phases /path/to/asset-phase-scales.json \
  --bindings-root game/data --output /path/to/media-plan.json
uv run --no-sync python -m devtools.pack_media build \
  --plan /path/to/media-plan.json --archive /path/to/preserved-art \
  --bindings-root game/data --output /new/path/to/packed-media
uv run --no-sync python -m devtools.pack_environment plan \
  --selection /path/to/selection-plan.json --archive /path/to/preserved-art \
  --data game/data --output /path/to/environment-plan.json
uv run --no-sync python -m devtools.pack_environment build \
  --plan /path/to/environment-plan.json --archive /path/to/preserved-art \
  --data game/data --output /new/path/to/packed-environment
```

Review and apply the generated **guarded binding records** to current public
data, checking their `before` values. Mirrored binding documents are review aids;
do not copy them over newer authoring. Verify that replaced input files have no
other current consumers. A retained shared consumer can be named explicitly with
`finish --retain-source game/assets/...`; this keeps the original alongside the
new pack. `finish` checks every selected current binding against the generated
`after` value before creating its destination.

```bash
uv run --no-sync python -m devtools.pack_art finish \
  --base /path/to/selected-base \
  --pack /path/to/packed-media/packed-media.json \
  --pack /path/to/packed-environment/packed-environment.json \
  --bindings-root game/data --code-release MATCHING_CODE_REVISION \
  --destination /new/path/to/production-art
```

Finalization copies only retained base files and generated outputs into a fresh
directory; every source directory remains intact. It reuses published identities
for unchanged base files and computes identities for newly generated files once,
while copying them. This is explicit offline release creation, never a runtime
check or a normal installer checksum pass. No remote publication occurs.

Install the final release into an empty destination (`art.py install --root
/new/path/to/game-checkout --source /path/to/production-art`) and run the focused
replay checks using that installation. This proves missing files are not being
supplied by a previous local install.
