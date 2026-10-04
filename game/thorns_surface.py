"""Original living Thorns material, driven by received owners and actual contacts."""

from dataclasses import replace
from functools import lru_cache
from math import ceil, cos, exp, pi, sin
from pathlib import Path

import numpy as np

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallRing, WallSegment
from game.animation import ActorContact, body_elevation_steps
from game.animation_types import AnimationData, AuthoredRecord, ThornsMaterial
from game.area_media import AreaMedia
from game.directed_surface import (DonorMesh, DonorTexture, donor_texture, rasterize_surface,
    repeated_texture, source_palette_rgba, surface_command)
from game.draw_commands import DrawCommand
from game.projection import Camera
from game.volume_media import ExcludedSphere


class VineMesh(DonorMesh):
    normals: tuple[tuple[float, float, float], ...]


class VineTextures(AuthoredRecord):
    VinesTexture: DonorTexture
    EnergyColor2DGradient: DonorTexture
    DetailsNoiseTexture: DonorTexture
    DisolverDetailsTexture: DonorTexture


class VineParameters(AuthoredRecord):
    VineTextureScale: tuple[float, float]
    NoiseScale: tuple[float, float]
    Intensity: float
    IsInvertFresnel: bool
    FresnelPower: float
    AlphaScissorThreshold: float
    DisolverDetailsScale: tuple[float, float]
    DisolverDetailsSpeed: tuple[float, float]
    DisolverDetails: float


class VineTransform(AuthoredRecord):
    origin: tuple[float, float, float]
    basis: tuple[tuple[float, float, float], ...]


class VineStart(AuthoredRecord):
    times: tuple[float, ...]
    scales: tuple[tuple[float, float, float], ...]
    steps: tuple[float, ...]


class VineComponents(AuthoredRecord):
    mesh: VineMesh
    textures: VineTextures
    params: VineParameters
    child_transform: VineTransform
    start: VineStart


@lru_cache(maxsize=2)
def vine_components(path: Path) -> VineComponents:
    return VineComponents.model_validate_json(path.read_bytes())


def _smooth(a: float, b: float, value):
    t = np.clip((value-a)/(b-a), 0, 1)
    return t*t*(3-2*t)


@lru_cache(maxsize=32)
def vine_mesh(resource: Path, count: int, length: float, cell: float, modules: tuple[int, ...],
              circular: bool = False):
    """Source interior variation leaves every module's two endpoints unchanged."""
    mesh = vine_components(resource).mesh
    original = np.asarray(mesh.vertices)
    u = np.clip((original[:, 0]-original[:, 0].min())/np.ptp(original[:, 0]), 0, 1)
    interior = np.sin(pi*u)**2
    vertices = []
    for index in modules:
        p = original.copy()
        p[:, 1] += np.sin(u*8+index*1.9)*interior*.65
        p[:, 2] += np.cos(u*6+index*2.1)*interior*.11
        vertices.append(p)
    return (np.concatenate(vertices), np.tile(mesh.normals, (len(modules), 1)),
        np.tile(mesh.uv, (len(modules), 1)),
        np.concatenate([np.asarray(mesh.indices).reshape(-1, 3)+index*len(original)
            for index in range(len(modules))]),
        np.repeat((np.asarray(modules)+.5-(0 if circular else count*.5))*(length/count)*cell, len(original)))


@lru_cache(maxsize=32)
def vine_surface(resource: Path, center: tuple[float, float],
        tangent: tuple[float, float] | None, length: float,
        cell: float, vertical_scale: float, base_height: float, age_ms: float,
        applied: bool, removal: float, occupants: tuple[tuple[float, float, float, float], ...],
        modules: tuple[int, ...], camera: Camera):
    """Literal ThornsModules vertex law and ss_vines material; no gameplay state."""
    circular = tangent is None
    count = max(1, ceil(length))
    vertices, normals, uv, triangles, shifts = vine_mesh(resource, count, length, cell, modules, circular)
    age = max(0., age_ms/1000)
    clock = age % 2
    source = vine_components(resource)
    timeline = source.start
    sampled = age if applied else timeline.times[-1]
    growth = np.array([np.interp(sampled, timeline.times, np.asarray(timeline.scales)[:, axis]) for axis in range(3)])
    root_scale = np.array((.3539, .4362, 1.004))
    model_scale = root_scale*growth
    p = (vertices @ np.asarray(source.child_transform.basis))*model_scale
    p += np.asarray(source.child_transform.origin)*root_scale+np.array((0, .7538, 0))
    p[:, 0] += shifts
    anchor = np.clip(p[:, 1]/4.242640688, 0, 1)**1.45
    phase = clock*pi
    broad = np.sin(p[:, 0]/33.941125504*2*pi*3+p[:, 2]*1.1-phase)
    tips = np.sin(p[:, 0]/33.941125504*2*pi*7+p[:, 1]*1.6+phase*2)
    p[:, 2] += anchor*(.23*broad+.075*tips)
    p[:, 0] += anchor*.08*np.sin(p[:, 0]/33.941125504*2*pi*4+p[:, 1]*.7+phase)
    p[:, 1] -= anchor*.065*(.5+.5*np.sin(p[:, 0]/33.941125504*2*pi*5-phase*2))
    p[:, 2] = 1.060660172*np.tanh(p[:, 2]/1.060660172)
    normals = normals/model_scale
    if circular:
        theta = p[:, 0]/33.941125504*2*pi
        radius = 4.242640688+p[:, 2]
        sn, cs = np.sin(theta), np.cos(theta)
        p[:, 0], p[:, 2] = sn*radius, cs*radius
        # The source circular branch curves MODEL_NORMAL_MATRIX*NORMAL before
        # returning it to the model frame. Carry that same world normal here.
        nx, nz = normals[:, 0].copy(), normals[:, 2].copy()
        normals[:, 0], normals[:, 2] = cs*nx+sn*nz, -sn*nx+cs*nz
    else:
        assert tangent is not None
        tx, tz = tangent
        # Straight source heading modifies vertices, not MODEL_NORMAL_MATRIX.
        p[:, (0, 2)] = p[:, (0, 2)] @ np.array(((tx, tz), (-tz, tx)))
    p[:, 1] *= 1-removal
    for x, z, presence, pulse in occupants[:16]:
        offset = p[:, (0, 2)]-(np.array((x, z))-center)*cell
        distance = np.linalg.norm(offset, axis=1)
        influence = (1-_smooth(.25, 1.45, distance))*presence
        body = (1-_smooth(2., 2.9, p[:, 1]))*_smooth(0., .45, p[:, 1])
        p[:, (0, 2)] += offset/np.maximum(distance, .12)[:, None]*(influence*body*(.32-pulse*.58))[:, None]
        p[:, 1] -= influence*body*(.05+.035*np.sin(phase*2+p[:, 0]))
    scale = np.array((1., vertical_scale, 1.))/cell
    base = np.array((center[0], base_height, center[1]))
    textures, params = source.textures, source.params
    dissolve = np.interp(sampled, timeline.times, timeline.steps)
    fade = 1-_smooth(.65, 1., removal)
    noise_texture = donor_texture(resource.parent, textures.DisolverDetailsTexture)
    def admitted(mapped: np.ndarray) -> np.ndarray:
        noise = repeated_texture(noise_texture,
            mapped[:, 0]*params.DisolverDetailsScale[0]+params.DisolverDetailsSpeed[0]*clock,
            mapped[:, 1]*params.DisolverDetailsScale[1]+params.DisolverDetailsSpeed[1]*clock)[:, 0]
        return ((mapped[:, 1]*(1-params.DisolverDetails)+noise*params.DisolverDetails >= dissolve)
            & (fade >= params.AlphaScissorThreshold))
    surface = rasterize_surface(base+p*scale, uv, triangles, camera,
        normals=normals, admit_uv=admitted)
    if surface is None:
        return None
    assert surface.normals is not None
    n = surface.normals/np.maximum(np.linalg.norm(surface.normals, axis=2)[..., None], 1e-9)
    view = np.array(((1., .816496580927726, 1.), (1., .816496580927726, -1.),
        (-1., .816496580927726, -1.), (-1., .816496580927726, 1.))[camera.quadrant])
    view /= np.linalg.norm(view)
    u, v = surface.uv[..., 0], surface.uv[..., 1]
    bark = repeated_texture(donor_texture(resource.parent, textures.VinesTexture),
        u*params.VineTextureScale[0], v*params.VineTextureScale[1])[..., :3]
    energy = (repeated_texture(donor_texture(resource.parent, textures.EnergyColor2DGradient), u, v)[..., :3]
        *repeated_texture(donor_texture(resource.parent, textures.DetailsNoiseTexture),
            u*params.NoiseScale[0], v*params.NoiseScale[1])[..., :3]*params.Intensity)
    dot = np.clip(n@view, 0, 1)
    fresnel = (dot if params.IsInvertFresnel else 1-dot)**params.FresnelPower
    color = bark*(1-fresnel[..., None])+energy*fresnel[..., None]
    light = np.array((sin(-pi/6)*cos(-50*pi/180), -sin(-50*pi/180), cos(-pi/6)*cos(-50*pi/180)))
    color *= np.array((.6, .65, .6))*.9 + np.array((.97, .93, .83))*1.6*np.maximum(n@light, 0)[..., None]
    alpha = surface.owned*fade
    return surface, color, alpha


def thorns_commands(geometry: WallAssemblyPresentationGeometry, spec: ThornsMaterial,
        data: AnimationData, age_ms: float, applied: bool, removal: float,
        camera: Camera, area: AreaMedia | None, modules: tuple[int, ...],
        exclusions: tuple[ExcludedSphere, ...], contacts: tuple[ActorContact, ...],
        contact_ages: tuple[tuple[str, float], ...], owner: str, phase: str) -> tuple[DrawCommand, ...]:
    """Current contacts bend quietly; only dated native damage can pull a vine."""
    path = geometry.path
    if not isinstance(path, (WallSegment, WallRing)) or removal >= 1 or not modules:
        return ()
    pulse_by_actor: dict[str, float] = {}
    for actor, elapsed_ms in contact_ages:
        if abs(elapsed_ms) < 600:
            pulse_by_actor[actor] = max(pulse_by_actor.get(actor, 0.), exp(-(elapsed_ms/130)**2))
    def distance(contact: ActorContact) -> float:
        if isinstance(path, WallRing):
            return abs(float(np.linalg.norm(np.subtract(contact.grid, path.center)))-path.radius_feet/5)
        delta = np.subtract(path.end, path.start)
        offset = np.subtract(contact.grid, path.start)
        along = np.clip(offset@delta/(delta@delta), 0., 1.)
        return float(np.linalg.norm(offset-along*delta))
    nearby = sorted((c for c in contacts if abs(body_elevation_steps(c, data)-geometry.base_height_steps) < .5
        and distance(c) <= .5+1.45/spec.nativeUnitsPerCell), key=lambda c: (distance(c), c.actor_uuid))
    occupants = tuple((c.grid[0], c.grid[1], 1., pulse_by_actor.get(c.actor_uuid, 0.))
        for c in nearby[:16])
    # The accepted source cycles every two seconds after its finite growth.
    age_ms = age_ms if applied and age_ms < 2000 else 2000+round(age_ms % 2000, 6)
    if isinstance(path, WallRing):
        # Sixteen original five-foot modules wrap onto the accepted ten-foot
        # radius. Keep their source slots rather than resampling circumference.
        center, tangent, length = path.center, None, 16.
    else:
        delta = np.subtract(path.end, path.start)
        length = float(np.linalg.norm(delta))
        tangent = float(delta[0]/length), float(delta[1]/length)
        midpoint = (np.asarray(path.start)+path.end)/2
        center = float(midpoint[0]), float(midpoint[1])
    result = vine_surface(data.resources[spec.components], center, tangent, length,
        spec.nativeUnitsPerCell, spec.verticalScale, geometry.base_height_steps, age_ms,
        applied, removal, occupants, modules, camera)
    if result is None:
        return ()
    surface, rgb, alpha = result
    # Permission was resolved for each physical section's observed shell before
    # sampling. Opaque Thorns can hide its own centre ground cells.
    rgba = source_palette_rgba(rgb, alpha, spec.palette, sample_pixels=2*camera.zoom,
        space='cie76', boost=1.12, alpha_energy_ceiling=.1)
    command = surface_command(surface, rgba, camera, center, area, owner)
    if command is None:
        return ()
    assert command.volume is not None
    return (command._replace(owner=owner, world_depth_group=(owner, 'thorns'),
        volume=replace(command.volume, exclusions=exclusions),
        evidence=(owner, path.center if isinstance(path, WallRing) else path.start,
                  f'thorns.{phase}.native', *command.evidence)),)
