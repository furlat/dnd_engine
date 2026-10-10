"""Register D1/D6 receiving faces from the accepted October 8 Fireball proof.

Run ``python -m devtools.author_stone_wall_geometry --write`` to update only the
eight existing image geometry fields; omit --write to check the saved values.
The pinned proof's scene.js:wallBox and shaders.js:wallFragment are the source.
Its D1 uses padded original pixels. D6 already uses the legacy registration.

These are the three camera-visible receiving faces, not collision volumes.
Source alpha retains D6's aperture and the irregular stone silhouette. Source
polygons record the proof's face continuation over that silhouette. Joined D1
runs must not expose internal end faces; run composition remains a consumer
obligation. D2 corners, window apertures and destruction are outside this data.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

from game.asset_types import ImageResourceSource


ROOT = Path(__file__).resolve().parents[1]
PROOF_HASHES = {
    "scene.js": "01c373cd83a9109b392231cd0894465434134fd5a540d2c5f638295dcfaaf9d4",
    "shaders.js": "934580bf46901cded51686bd5756c96abfae8600fe032e01c1a1d361b53f1e2f",
    "environment-selection.json": "e0e3d9064917f0b13db18d8d5cf5602336687962c9d9f80613e36eb01131c7a4",
}


def project(point: tuple[float, float, float]) -> tuple[float, float]:
    x, height, z = point
    return 64 * (x - z), 32 * (x + z) - 64 * height


def clip(polygon: list[tuple[float, float]], a: float, b: float,
         c: float) -> list[tuple[float, float]]:
    """Intersect a source-cell polygon with a calibrated face half-plane."""
    result = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        first, last = a * start[0] + b * start[1] + c, a * end[0] + b * end[1] + c
        if first <= 0:
            result.append(start)
        if (first <= 0) != (last <= 0):
            t = first / (first - last)
            result.append((start[0] + t * (end[0] - start[0]),
                           start[1] + t * (end[1] - start[1])))
    return result


def geometry(pose: str, image: ImageResourceSource, *, padded_d1: bool) -> dict:
    # Exactly scene.js:wallBox at owner (0,0,0), in camera-local x,height,z.
    lower, upper = [-.5, 0., -.5], [.5, 2., .5]
    axis = 0 if pose in ("e", "w") else 2
    lower[axis] = .25 if pose in ("e", "s") else -.5
    upper[axis] = lower[axis] + .25
    x0, h0, z0 = lower
    x1, h1, z1 = upper
    faces = {
        "x_max": [(x1, h0, z0), (x1, h1, z0), (x1, h1, z1), (x1, h0, z1)],
        "top": [(x0, h1, z0), (x0, h1, z1), (x1, h1, z1), (x1, h1, z0)],
        "z_max": [(x0, h0, z1), (x1, h0, z1), (x1, h1, z1), (x0, h1, z1)],
    }
    # D1 proof source u+32, pivot160,240, scale1 -> legacy u,pivot128,207.36.
    # P(local) = image.scale * (P(proof) + (0,208-image.pivot.y)).
    factor = image.scale if padded_d1 else 1.
    height_shift = -(208 - image.pivot[1]) * image.scale / 64 if padded_d1 else 0.
    transform = [[factor, 0., 0., 0.], [0., factor, 0., height_shift], [0., 0., factor, 0.]]

    def local(point: tuple[float, float, float]) -> tuple[float, float, float]:
        return factor * point[0], factor * point[1] + height_shift, factor * point[2]

    vertices, triangles, uvs, face_ids = [], [], [], []
    for name, points in faces.items():
        offset = len(vertices)
        vertices.extend(points)
        for point in points:
            px, py = project(local(point))
            uvs.append([(px / image.scale + image.pivot[0]) / image.native_size[0],
                        (py / image.scale + image.pivot[1]) / image.native_size[1]])
        triangles.extend([[offset, offset + 1, offset + 2], [offset, offset + 2, offset + 3]])
        face_ids.extend([name, name])

    # The proof selects min(t_x,t_height,t_z), even beyond the ideal box's
    # projected silhouette. Partition full-source pixels by those exact planes.
    sx, sy = image.scale, image.scale
    ox, oy = -image.pivot[0] * sx, -image.pivot[1] * sy
    max_x, max_h, max_z = local((x1, h1, z1))
    exits = {
        "x_max": (-sx / 128, -sy / 64, max_x - ox / 128 - oy / 64),
        "top": (0., 0., max_h),
        "z_max": (sx / 128, -sy / 64, max_z + ox / 128 - oy / 64),
    }
    polygons = {}
    width, height = image.native_size
    for name, plane in exits.items():
        polygon = [(0., 0.), (float(width), 0.), (float(width), float(height)), (0., float(height))]
        for other_name, other in exits.items():
            if other_name != name:
                polygon = clip(polygon, *(plane[i] - other[i] for i in range(3)))
        polygons[name] = polygon
    return {"kind": "mesh", "basis": "camera_local", "sourceToLocal": transform,
            "vertices": vertices, "triangles": triangles, "uvs": uvs,
            "faceIds": face_ids, "sourcePolygons": polygons}


def author(proof: Path, *, write: bool) -> None:
    for filename, expected in PROOF_HASHES.items():
        if sha256((proof / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Accepted calibration changed: {proof / filename}")
    selection = json.loads((proof / "environment-selection.json").read_text())["sprites"]
    path = ROOT / "game/data/assets.json"
    document = json.loads(path.read_text())
    resources = document["resources"]
    maximum_error = 0.
    identities = []
    for family, prefix in (("wall", "stone.wall.straight"), ("door", "stone.door.frame")):
        for pose in ("e", "s", "w", "n"):
            identity = f"{prefix}.{pose}"
            image = ImageResourceSource.model_validate(resources[identity])
            if image.native_size != (256, 256) or image.pivot != (128, 207.36) or image.scale != 128 / 127:
                raise ValueError(f"Legacy source registration changed: {identity}")
            source = selection[family][pose]
            if family == "wall":
                if source["pivot"] != [160, 240] or source["scale"] != 1 or source["rect"][2:] != [320, 320]:
                    raise ValueError(f"Proof D1 registration changed: {pose}")
                x, y, _, _ = source["rect"]
                with Image.open(ROOT / "game/assets" / source["path"]) as atlas:
                    padded = atlas.convert("RGBA").crop((x + 32, y + 32, x + 288, y + 288))
                with Image.open(ROOT / "game/assets" / image.path) as original:
                    if padded.tobytes() != original.convert("RGBA").tobytes():
                        raise ValueError(f"Proof and legacy D1 source pixels differ: {pose}")
            elif (source["path"] != image.path or source["pivot"] != list(image.pivot)
                  or source["scale"] != image.scale or source["rect"] != [0, 0, 256, 256]):
                raise ValueError(f"Proof and legacy D6 registration differ: {pose}")
            value = geometry(pose, image, padded_d1=family == "wall")
            ImageResourceSource.model_validate({**resources[identity], "geometry": value})
            matrix = value["sourceToLocal"]
            for point, uv in zip(value["vertices"], value["uvs"]):
                local = tuple(sum(row[i] * point[i] for i in range(3)) + row[3] for row in matrix)
                screen = project(local)
                mounted = tuple((uv[i] * image.native_size[i] - image.pivot[i]) * image.scale for i in range(2))
                maximum_error = max(maximum_error, *(abs(a - b) for a, b in zip(screen, mounted)))
            if maximum_error > 1e-10:
                raise ValueError(f"UV/source mount mismatch: {identity}: {maximum_error}")
            if not write and resources[identity].get("geometry") != json.loads(json.dumps(value)):
                raise ValueError(f"Saved geometry differs: {identity}; run with --write to author")
            resources[identity]["geometry"] = value
            identities.append(identity)
    if write:
        path.write_text(json.dumps(document, indent=2) + "\n")
    print(json.dumps({"resources": identities, "maximum_projection_error_px": maximum_error,
                      "d1_source_pixels_equal": True, "written": write}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, default=ROOT / ".runtime/ndclient-fireball-proof")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    author(args.proof, write=args.write)
