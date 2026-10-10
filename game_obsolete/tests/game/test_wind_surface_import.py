"""Original color survives native coordinates and sparse surface ZIP framing."""

import gzip
import struct

import numpy as np
import pytest

from devtools.import_wind_surface import surface_packet


@pytest.mark.parametrize('quadrant',range(4))
def test_sparse_surface_packet_preserves_color_validity_and_registered_pivot(quadrant):
    color=np.zeros((512,512,4),dtype=np.uint8);color[290:294,240:245]=(71,141,199,88)
    axes=[]
    for value in (32890,16384,32900):
        axis=np.zeros_like(color);axis[290:293,240:245]=(value//256,value%256,0,255);axes.append(axis)
    packet,count,error=surface_packet(color,tuple(axes),quadrant,(-40,-.5,-40),(80,8,80),(256,311.425625842))
    raw=gzip.decompress(packet);w,h,ox,oy=struct.unpack_from('<HHhh',raw)
    assert (w,h,ox,oy)==(5,4,-16,-21)
    rgba=np.frombuffer(raw,dtype=np.uint8,count=w*h*4,offset=8).reshape(h,w,4)
    assert np.array_equal(rgba,color[290:294,240:245])
    ownership=np.frombuffer(raw,dtype=np.uint8,count=w*h,offset=8+w*h*10).reshape(h,w)
    assert count==15 and ownership.sum()==15 and not ownership[-1].any()
    assert error<.1
    coordinates=np.frombuffer(raw,dtype='>u2',count=w*h*3,offset=8+w*h*4).reshape(h,w,3).astype(float)*(80/65535)-40
    x=-40+32890*(80/65535);z=-40+32900*(80/65535)
    expected=((x,z),(-z,x),(-x,-z),(z,-x))[quadrant]
    assert np.allclose(coordinates[0,0,[0,2]],expected,atol=.001)
