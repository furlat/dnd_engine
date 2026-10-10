"""Render an existing Studio area through the unchanged Pygame world painter."""
import argparse
from pathlib import Path
import pygame
from dnd.player.reduction import decode_player_sequence
from game.app import draw_frame
from game.assets import load_catalog, SurfaceCache
from game.projection import Camera


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    pygame.init()
    screen=pygame.display.set_mode((1280,900))
    state,_=decode_player_sequence(args.recording.read_bytes())
    catalog=load_catalog()
    cache=SurfaceCache(catalog)
    args.output.mkdir(parents=True,exist_ok=True)
    for q in range(4):
        camera=Camera(quadrant=q,zoom=.5,viewport=(1280,900)).with_focus((7.5,7.5),elevation_steps=1)
        draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,mouse_position=None,show_debug=False)
        pygame.image.save(screen,args.output/f'pygame-{q}.png')
        print(f'Pygame camera {q} saved',flush=True)
    pygame.quit()


if __name__=='__main__':
    main()
