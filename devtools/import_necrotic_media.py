"""Install explicitly selected accepted necrotic banks without altering recipes."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from devtools.import_registered_media import register_billboard_bank, validate_billboard_bank
from devtools.media_delivery import install_verified_payloads, contained_media_path

ROOT = Path(__file__).resolve().parents[1]


def import_necrotic_media(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT,
                          programs: tuple[str, ...] = ("kill", "stun", "stunned")) -> dict:
    manifest = json.loads((source / "media.json").read_text())
    revisions = {"kill": "native-family-v2", "stun": "native-family-v2",
        "stunned": "native-family-v1", "harm": "native-family-v3", "circle": "native-fissure-smoke-v9"}
    if not programs or len(set(programs)) != len(programs) or any(name not in revisions for name in programs):
        raise ValueError("Select distinct known necrotic banks")
    selections = tuple((name, revisions[name]) for name in programs)
    banks = {}
    payloads = {}
    for name, revision in selections:
        row = manifest[name]
        if row["revision"] != revision or row["fps"] != 32:
            raise ValueError(f"Unexpected accepted necrotic revision: {name}")
        layers = row["layers"]
        # The area capture is one whole layer, deliberately kept unsplit.
        bank = dict(row, layers={"front": layers["whole"]}) if name == "circle" and set(layers) == {"whole"} else row
        validate_billboard_bank(bank, paired=name != "circle")
        banks[name] = bank
        for layer in row["layers"].values():
            for path in layer["pages"]:
                payloads[path] = (path, f"game/assets/necrotic_media/{path}", row["sha256"][path])
    metadata = [(source / name, contained_media_path(preserved, name)) for name in
        ("HANDOFF.md", "APPROVED_HANDOFF.md", "NOTES.md", "media.json", "delivery-receipt.json")]
    for origin, target in metadata:
        content = origin.read_bytes()
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Archived necrotic metadata differs: {origin.name}")
    files = install_verified_payloads(source, tuple(payloads.values()), preserved=preserved, production=production, repo=repo)
    for origin, target in metadata:
        shutil.copyfile(origin, target)
    identities = []
    for name, _ in selections:
        identities.extend(register_billboard_bank(banks[name], f"necrotic.{name}",
            media_root="game/assets/necrotic_media", bundle=repo / "game/data/necrotic_media", loop=name == "stunned", paired=name != "circle"))
    receipt = {"source": str(source), "preserved": str(preserved), "identities": identities, "files": files,
        "manifest_sha256": hashlib.sha256((source / "media.json").read_bytes()).hexdigest()}
    for target in (preserved / "install-receipt.json", repo / "game/data/necrotic_media/necrotic-source.json"):
        target.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def import_blight_media(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    """Preserve the accepted body contact and its unchanged donor texture."""
    bank = json.loads((source / "contact.json").read_text())
    if bank["revision"] != "native-colored-aim-v4":
        raise ValueError("Unexpected accepted Blight revision")
    validate_billboard_bank(bank)
    metadata = [(source / name, contained_media_path(preserved, name)) for name in
        ("contact.json", "NOTES.md", "review.js", "delivery-receipt.json", "cast-sockets.json")]
    for origin, target in metadata:
        if target.exists() and target.read_bytes() != origin.read_bytes():
            raise ValueError(f"Archived Blight metadata differs: {origin.name}")
    payloads = [(path, "game/assets/necrotic_media/blight/" + path, digest)
        for path, digest in bank["sha256"].items()]
    texture = "assets/donor-noise.png"
    payloads.append((texture, "game/assets/necrotic_media/blight/" + texture,
        hashlib.sha256((source / texture).read_bytes()).hexdigest()))
    files = install_verified_payloads(source, tuple(payloads), preserved=preserved,
        production=production, repo=repo)
    for origin, target in metadata:
        shutil.copyfile(origin, target)
    bundle = repo / "game/data/necrotic_media"
    identities = register_billboard_bank(bank, "necrotic.blight",
        media_root="game/assets/necrotic_media/blight", bundle=bundle)
    path = bundle / "bindings.json"
    bindings = json.loads(path.read_text())
    bindings["resources"]["/necrotic/blight-noise.png"] = "game/assets/necrotic_media/blight/" + texture
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "preserved": str(preserved), "files": files,
        "identities": identities, "operator_source_sha256": hashlib.sha256((source / "review.js").read_bytes()).hexdigest()}
    (bundle / "blight-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--program", action="append", choices=("kill", "stun", "stunned", "harm", "circle"))
    args = parser.parse_args()
    result = import_necrotic_media(args.source, preserved=args.preserved, production=args.production,
        programs=tuple(args.program or ("kill", "stun", "stunned")))
    print(f"Installed {len(result['identities'])} records / {len(result['files'])} original pages")


def import_dust_source(source: Path, *, preserved: Path, repo: Path = ROOT) -> dict:
    """Preserve the accepted source operator; authored runtime values stay separate."""
    files = []
    for name in ('HANDOFF.md', 'DustOutcome.js', 'DisintegrateBody.gdshader', 'DustOutline.gd'):
        origin = contained_media_path(source, name)
        destination = contained_media_path(preserved, name)
        content = origin.read_bytes()
        if destination.exists() and destination.read_bytes() != content:
            raise ValueError(f'Archived dust source differs: {name}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        files.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    receipt = {'source':str(source),'preserved':str(preserved),'files':files,
               'operator':'game/body_effects.py:silhouette_dust','recipe':'game/data/silhouette-dust.json'}
    (repo/'game/data/necrotic_media/dust-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def import_plasma_components(project: Path, samples: Path, handoff: Path, *,
                             preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    """Preserve exact source materials and RNG samples; never author a recipe."""
    files = {
        'trail.jpg': project/'codexfx_exporter/DisintegrateTrailTexture.jpg',
        'noise.png': project/'VFX/textures/T_VFX_Noise_10.PNG',
        'plasma-particles.json': samples/'plasma-particles.json',
        'sphere.json': samples/'sphere.json',
        'ExportPlasmaParticles.gd': samples/'ExportPlasmaParticles.gd',
        'command.json': samples/'command.json',
        'capture.log': samples/'capture.log',
        'ForceCapture.gd': handoff/'authoring/ForceCapture.gd',
        'DisintegrateTrail.gdshader': handoff/'authoring/DisintegrateTrail.gdshader',
        'HANDOFF.md': handoff/'production-handoff/HANDOFF.md',
    }
    preserved.mkdir(parents=True,exist_ok=True)
    for name,source in files.items():
        target=preserved/name
        if target.exists() and target.read_bytes()!=source.read_bytes():
            raise ValueError(f'Original plasma source differs: {name}')
        shutil.copyfile(source,target)
    selected=('trail.jpg','noise.png','plasma-particles.json','sphere.json')
    payloads=tuple((name,'game/assets/necrotic_media/plasma/'+name,
        hashlib.sha256((preserved/name).read_bytes()).hexdigest()) for name in selected)
    installed=install_verified_payloads(preserved,payloads,preserved=preserved,production=production,repo=repo)
    bundle=repo/'game/data/necrotic_media'
    path=bundle/'bindings.json';bindings=json.loads(path.read_text())
    bindings['resources'].update({'/necrotic/plasma/'+name:'game/assets/necrotic_media/plasma/'+name for name in selected})
    path.write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    receipt={'project':str(project),'handoff':str(handoff),'preserved':str(preserved),'files':installed,
        'sources':{name:hashlib.sha256((preserved/name).read_bytes()).hexdigest() for name in files}}
    (bundle/'plasma-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
