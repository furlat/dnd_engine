"""Folded original meshes choose their physical front/back independently of triangle order."""
import numpy as np
import pytest

from game.directed_surface import rasterize_surface
from game.projection import Camera


@pytest.mark.parametrize('quarter',range(4))
def test_overlapping_original_triangles_keep_camera_depth_when_export_order_changes(quarter):
    camera=Camera(quadrant=quarter,viewport=(300,250),zoom=1).with_focus((0,0))
    signs=((1,1),(1,-1),(-1,-1),(-1,1))[quarter]
    back=np.array([[-.5,0,-.5],[.5,0,-.5],[0,0,.5]])
    front=back+np.array([signs[0],1,signs[1]])
    vertices=np.concatenate((back,front))
    uv=np.array([[0,0]]*3+[[1,1]]*3)
    triangles=np.array([[0,1,2],[3,4,5]])
    for nearest,value in ((True,1),(False,0)):
        normal=rasterize_surface(vertices,uv,triangles,camera,nearest=nearest)
        reversed_order=rasterize_surface(vertices,uv,triangles[::-1],camera,nearest=nearest)
        assert normal is not None and reversed_order is not None
        assert np.array_equal(normal.owned,reversed_order.owned)
        assert np.allclose(normal.xyz[normal.owned],reversed_order.xyz[reversed_order.owned])
        assert np.allclose(normal.uv[normal.owned],value)


@pytest.mark.parametrize('quarter',range(4))
def test_source_vertex_normals_and_colors_follow_the_same_visible_surface(quarter):
    camera=Camera(quadrant=quarter,viewport=(300,250),zoom=1).with_focus((0,0))
    signs=((1,1),(1,-1),(-1,-1),(-1,1))[quarter]
    back=np.array([[-.5,0,-.5],[.5,0,-.5],[0,0,.5]])
    front=back+np.array([signs[0],1,signs[1]])
    vertices=np.concatenate((back,front));uv=vertices[:,(0,2)]
    triangles=np.array([[0,1,2],[3,4,5]])
    # Deliberately varying values expose interpolation errors, not only which
    # triangle won. Native affine data must follow its sampled world point.
    colors=np.column_stack((vertices+2,np.ones(6)))
    normals=vertices*.25
    for nearest in (False,True):
        surface=rasterize_surface(vertices,uv,triangles,camera,nearest=nearest,normals=normals,colors=colors)
        plain=rasterize_surface(vertices,uv,triangles,camera,nearest=nearest)
        assert surface is not None and plain is not None
        assert surface.colors is not None and surface.normals is not None
        assert np.array_equal(surface.xyz,plain.xyz) and np.array_equal(surface.uv,plain.uv)
        assert np.allclose(surface.colors[surface.owned,:3],surface.xyz[surface.owned]+2)
        assert np.allclose(surface.colors[surface.owned,3],1)
        assert np.allclose(surface.normals[surface.owned],surface.xyz[surface.owned]*.25)


@pytest.mark.parametrize('quarter',range(4))
def test_original_alpha_cutout_discards_before_surface_depth(quarter):
    camera=Camera(quadrant=quarter,viewport=(300,250),zoom=1).with_focus((0,0))
    signs=((1,1),(1,-1),(-1,-1),(-1,1))[quarter]
    back=np.array([[-.5,0,-.5],[.5,0,-.5],[0,0,.5]])
    front=back+np.array([signs[0],1,signs[1]])
    vertices=np.concatenate((back,front));uv=np.array([[0,0]]*3+[[1,1]]*3)
    triangles=np.array([[0,1,2],[3,4,5]])
    expected=rasterize_surface(vertices,uv,triangles,camera,nearest=False)
    plain=rasterize_surface(vertices,uv,triangles,camera)
    assert expected is not None and plain is not None
    assert np.allclose(plain.uv[plain.owned],1)
    for order in (triangles,triangles[::-1]):
        cutout=rasterize_surface(vertices,uv,order,camera,admit_uv=lambda sample:sample[:,0]<.5)
        assert cutout is not None
        assert np.array_equal(cutout.owned,expected.owned)
        assert np.allclose(cutout.xyz[cutout.owned],expected.xyz[expected.owned])
        assert np.allclose(cutout.uv[cutout.owned],0)
