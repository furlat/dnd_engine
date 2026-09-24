# Asset setup and offline packing implementation

This implements the reviewed cleanup plan's A1–A3 tooling. It does not change
game rules, rendering authoring, live bindings, source artwork or Git history.
The primary task owns applying reviewed public address changes, assembling the
final release and proving a fresh installation. `PRIVATE_ART.md` contains the
repeatable commands.

## Implemented boundaries

- `devtools/art.py`: explicit installation with a receipt. Repeated installation
  skips matching published entries with the expected installed size; changed
  release entries are copied even when the old file had the same size. Normal
  installation does not compute payload checksums or compare all file contents.
  `check --hashes` and `--reinstall` remain explicit recovery operations.
- `devtools/pack_art.py`: inventory selection, explicit address-alias proposals,
  selected staging, and final clean release assembly. Planning uses existing
  manifest identities. Alias proposals never remove a source until the reviewed
  alias map is supplied. Finalization requires the matching generated `after`
  bindings, preserves input trees and computes new payload identities only once
  during their required copy. Base identities are reused.
- `devtools/pack_media.py`: existing color-page addresses and standard ZIP_STORED
  collections of unchanged gzip XYZ packets. Sparse frame indices, per-view
  component order, pivots, bounds, coordinate scales and timing stay authored.
  Identical whole packet banks can share physical archives while their different
  owner registrations remain separate. Existing raw XY/color part pairs are not
  repacked independently.
- `devtools/pack_environment.py`: full-size color cells, separately sized depth
  cells, the selected structural doorway frame cells, and loose mechanism
  resources. It emits the small agreed `{path, rect}` address records. It does
  not bake scale, trim transparent pixels, thin animation samples or introduce
  new state selectors.

All generated binding changes are guarded records. Mirrored full documents are
review aids and must not overwrite newer authoring. The finishing command checks
that selected generated records were applied; it is not a replacement for
checking other consumers of a proposed retired input. `--retain-source` preserves
such a shared original if required. No runtime importer, audit, checksum scan,
filesystem discovery or packaging registry was added.

## Generated outputs

The immutable source is `/home/tommaso/Dev/neurodragon_art`. Generation wrote only
the following separate directories:

| Pack | Selected input | Output | Effect |
| --- | ---: | ---: | --- |
| `neurodragon_art-packed-media-20260924` | 28,272 files / 2,399,975,900 bytes | 53 XYZ archives + 104 color pages / 2,398,102,578 bytes | Large file-count reduction; packets remain gzip-compressed unchanged inside standard uncompressed ZIP indexes. |
| `neurodragon_art-packed-environment-20260924` | 805 files / 63,341,591 bytes | 650 pages / 63,815,960 bytes | Individual page decode is at most 16,777,216 bytes instead of the largest 245,366,784-byte strip. Encoded size increases slightly; this is a decode/packing improvement. |

The environment output retains all frames and four views of 177 color banks and
136 paired depth banks, 48 selected cells from 12 static doorway frame atlases,
and 480 loose images. The earlier 482-image inventory count included two
3072×1024 blade/crusher depth strips. Those existing 12 MiB decoded strips remain
unchanged because they already have a correct frame sampler; forcing them through
whole-image pages would require unrelated addressing work.

Environment color and depth need not share a pixel rectangle: they retain their
own native cell dimensions and share logical frame/pose indexing. This differs
from VFX raw XY footpoint parts, whose existing protocol shares the color part's
rectangle and therefore requires identical layout if later repacked.

No portal/hatch micro-optimization, speculative resizing, sprite trimming,
authoring retiming or source regeneration was added. The four fixed Ashen motif
bakes belong to the separate A4 unit, not this tooling claim.

## Verification and limits

The initial combined focused suite passed **23 tests**; after shared-resource
and installer-path regressions, the final combined suite passes **30 tests**:

```text
tests/test_private_art_setup.py
tests/test_art_packaging.py
tests/test_media_packaging.py
tests/test_environment_packaging.py
```

These cover clean and repeated installation, same-size release updates,
selected-only staging, source preservation, incomplete inputs, guarded current
bindings, clean final manifests, exact gzip member bytes, exact color/transparent
RGBA and depth cells, all four poses, static frame selection, independent depth
dimensions and unchanged authored registration. Scoped typing for these four
tools and four test files reports zero errors. Tests use tiny local inputs; they
do not re-run the whole asset corpus or assert internal helper call order.

The runtime adapter owner separately reported real door color/depth/static-frame
equivalence across four views and small fixtures across five supported zooms.
The primary task's final fresh installation, runtime checks and release manifest
counts remain separate acceptance evidence. Packing output existing on disk is
not by itself proof that every live consumer has migrated.

## Final release corrections

The initial generated-media counts above are historical. The fresh release
exposed an omitted Gust hold window in four camera banks; its exact selected
frame/ZIP/base-manifest correction and focused validation are recorded in
[the Gust release repair](GUST_RELEASE_SELECTION_REPAIR_2026-09-24.md). The complete
source archive and pre-correction output remain preserved.

## Measured installer path overhead and correction

The first main checkout installation on the Windows mount was still running
after more than 26 minutes, while the separate fresh Linux installation had
completed in roughly a minute. The parent later interrupted that original
installation at about 37 minutes. That interrupted elapsed time is **not** a
completed-install benchmark and cannot be attributed entirely to one helper.

The bounded diagnostic used the same Python 3.13.12 interpreter and 160 uniformly
selected paths across the 24,783-file production manifest. It performed path and
metadata reads, not a second installation or payload checksum scan.

| Measured operation | Before | After |
| --- | ---: | ---: |
| Validate 160 destination addresses on NTFS | 2.338 s | 0.662 s |
| Validate the same 160 addresses on Linux | 0.0370 s | 0.0188 s |
| Filesystem stat/lstat calls for the NTFS sample | 4,638 | 326 |
| Full 24,783-row manifest parse from Linux | not timed before | 0.0648 s |
| Full 24,783-row manifest parse from NTFS metadata fixture | not timed before | 0.0938 s |
| Explicit source verification of 160 files, sizes and LFS headers, without hashes | not timed before | 0.0073 s |

The old `contained` checked every ancestor with `is_symlink`, then resolved the
whole path and root again for every row. More than 96% of the NTFS sample's
self time was stat/lstat work. `read_manifest` called the same filesystem helper
even for receipt addresses, which would inspect the unrelated
`.runtime/game/assets/...` tree. The main first installation did not yet have a
receipt, so that extra receipt pass was **not** part of its observed delay;
removing it matters for repeated installations.

`devtools/art.py` now separates pure lexical path admission from file-boundary
checks. Explicit operation roots are resolved once; a pass-local set reuses
validated parent directories, while every leaf is still checked for symlinks or
junctions. Source verification still checks existence, ordinary file type, size
and LFS hydration before any copies. Copy passes start fresh parent checks.
There is no global path cache and no new runtime work. Ordinary installs still
reuse the receipt instead of hashing or comparing all content.

The combined installer/staging/packing lane passes **30 tests**. Added cases
exercise a receipt with an unrelated `.runtime/game` symlink, parent and leaf
replacement on source and destination between two install calls in the same
process, and an unhydrated source rejected before replacing existing files.
Existing tests retain missing-companion preflight, path-escape rejection,
same-size release changes, repeated installation and explicit deep checking.
Scoped typing for the installer and its tests reports zero errors.

Evidence is under `.runtime/cleanup-implementation-20260924/installer-profile/`:
`results.json` contains the original Python 3.13 sample, `updated-results.json`
contains the post-fix sample/full metadata parsing, and `tests.txt` / `typing.txt`
contain final validation output. The independent Python 3.12 initial sample is
retained as `results-system312.json` but is not used for the table.

The parent owns resuming and completing the actual main installation. Commands
remain explicit:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
uv run --no-sync python devtools/art.py check
```

The second command checks installed paths, sizes and hydration; `--hashes` stays
an optional separate deep check. This measurement does not claim that copying
15 GB to NTFS now takes the same time as copying it to Linux storage.
