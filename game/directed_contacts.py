"""Numeric authored release sockets and admitted object-surface contacts."""

import numpy as np

from dnd.core.presentation_geometry import WallDome, WallRing, WallSegment, WallPolyline
from game.animation import CastTimeline, CastSample, ObjectContact, actor_point_offset, body_elevation_steps, body_rig, view_facing, sample_cast
from game.animation_types import StudioNoiseRibbonDelivery, StudioPlasmaTrailDelivery
from game.projection import Camera, TILE_WIDTH


def directed_socket(timeline: CastTimeline, sample: CastSample, camera: Camera,
                     spec: StudioNoiseRibbonDelivery | StudioPlasmaTrailDelivery) -> np.ndarray | None:
    """Place the selected authored socket on its explicitly authored XYZ plane."""
    contact = timeline.source.caster
    if spec.sourceSocket == "owner":
        return np.array((contact.grid[0],body_elevation_steps(contact,timeline.data)+spec.sourcePlaneHeightCells,contact.grid[1]))
    rig = body_rig(timeline.data,contact)
    selected = next((body for body in sample.bodies if body.actor_uuid==contact.actor_uuid),None)
    clip = selected.clip if selected is not None else timeline.recipe.cast.actionClip
    frame = selected.frame if selected is not None else int(timeline.recipe.cast.releaseFrame)
    facing = view_facing(selected.facing if selected is not None else timeline.facing,camera.quadrant,timeline.data)
    socket = rig.pose_sockets.get(spec.sourceSocket,{}).get(clip)
    if socket is None:
        raise ValueError(f"Directed source requires authored {spec.sourceSocket}/{clip} sockets")
    point = socket[facing][frame]
    if point is None:
        return None  # The original pose has no visible source surface in this frame.
    dx,dy = actor_point_offset(timeline.data,contact,(point.x,point.y))
    factor = TILE_WIDTH/timeline.data.rig.TILE_W
    # The attachment plane is authored data; screen height does not select it.
    lift = spec.sourcePlaneHeightCells
    sx,sy = dx*factor/64,(dy*factor+lift*64)/32
    x,z = (sx+sy)/2,(sy-sx)/2
    x,z = ((x,z),(z,-x),(-x,-z),(-z,x))[camera.quadrant]
    return np.array((contact.grid[0]+x,body_elevation_steps(contact,timeline.data)+lift,contact.grid[1]+z))



def recorded_surface_contact(contact: ObjectContact,source: np.ndarray,target: np.ndarray) -> np.ndarray:
    """First forward surface of the received, already-admitted construction owner."""
    geometry=contact.geometry
    if geometry is None:
        return target
    path=geometry.path
    # A native footprint cell may end before its curved physical shell.
    # Keep that admitted direction and intersect the received owner ray.
    delta=target-source
    candidates=[]
    base=geometry.base_height_steps
    top=base+geometry.height_feet/5
    if isinstance(path,(WallDome,WallRing)):
        center=np.array((path.center[0],base,path.center[1]),dtype=float)
        scale=np.array((1.,1.,1.)) if isinstance(path,WallDome) else np.array((1.,0.,1.))
        offset=(source-center)*scale
        radius=path.radius_feet/5+geometry.width_feet/10
        for attempt in range(2):
            direction=delta*scale
            a=float(np.dot(direction,direction));b=2*float(np.dot(offset,direction));c=float(np.dot(offset,offset))-radius*radius
            disc=b*b-4*a*c
            if a and disc>=0:
                candidates.extend(t for t in ((-b-np.sqrt(disc))/(2*a),(-b+np.sqrt(disc))/(2*a)) if t>=0)
            if candidates or attempt:
                break
            # Coarse admitted cells can graze outside the continuous shell.
            # Only this miss uses nearest-shell registration; a genuine ray
            # intersection above retains its exact source direction.
            radial=(target-center)*scale
            distance=float(np.linalg.norm(radial))
            if distance<1e-9:
                break
            shell=center+radial*(radius/distance)+(target-center)*(1-scale)
            delta=shell-source
    else:
        points=(path.start,path.end) if isinstance(path,WallSegment) else path.points if isinstance(path,WallPolyline) else ()
        for a,b in zip(points,points[1:]):
            axis=np.array((b[0]-a[0],0.,b[1]-a[1]));length=float(np.linalg.norm(axis));axis/=length
            normal=np.array((-axis[2],0.,axis[0]));den=float(np.dot(delta,normal))
            if abs(den)<1e-9:continue
            origin=np.array((a[0],base,a[1]),dtype=float)
            for side in (-1,1):
                t=(float(np.dot(origin-source,normal))+side*geometry.width_feet/10)/den
                p=source+t*delta
                if t>=0 and 0<=float(np.dot(p-origin,axis))<=length:candidates.append(t)
    for t in sorted(candidates):
        p=source+t*delta
        if base<=p[1]<=top and not any(section.contains_point((float(p[0]),float(p[2])))
            and section.base_height_steps<=p[1]<=section.base_height_steps+2 for section in geometry.removed_sections):
            return p
    return target



def ordinary_object_contact(contact: ObjectContact, source: tuple[float,float]) -> tuple[float,float,float]:
    """Admitted actor-to-band geometry; ordinary weapon XYZ was not delivered."""
    point=recorded_surface_contact(contact,np.array((source[0],contact.elevation_steps,source[1])),
        np.array((contact.grid[0],contact.elevation_steps,contact.grid[1])))
    return float(point[0]),float(point[1]),float(point[2])


def directed_object_contacts(timeline: CastTimeline, object_uuid: str) -> tuple[tuple[float,float,float], ...]:
    """Store only the four measured contact points, never a cast/render lifetime."""
    spec=timeline.recipe.directed
    if spec is None or spec.material!='plasma_trail':
        return ()
    target=next((row.source.target for row in timeline.applications if isinstance(row.source.target,ObjectContact)
        and row.source.target.object_uuid==object_uuid),None)
    if target is None:
        return ()
    endpoint=np.array((target.grid[0],target.elevation_steps,target.grid[1]))
    points=[]
    sample=sample_cast(timeline,timeline.release_ms)
    for quadrant in range(4):
        source=directed_socket(timeline,sample,Camera(quadrant=quadrant,zoom=1),spec)
        if source is None:
            return ()
        point=recorded_surface_contact(target,source,endpoint)
        points.append((float(point[0]),float(point[1]),float(point[2])))
    return tuple(points)
