# Raycaster engine in Python

This is an attempt at a Python 3 implementation of a classic raycaster. Think original DOS Wolfenstein.

Run this with any recent Python 3 version::

    python -m pywolf
    
This implementation favors readability and simplicity over speed, because my main goal
is to learn how to build a raycaster engine, and not to create an actual playable game or something like that. 

*No 3d acceleration or third party graphics libraries are used.* 
The program uses just built-in Tkinter for the GUI and display, and Pillow to load the textures 
and provide a pixel image display.

Tip: try using Pypy3 to run this (instead of CPython). It will *greatly* improve
 the performance and can actually result in a very smooth frame rate.

## Todo

- draw texture mapped ceiling and floor (something DOS Wolfenstein didn't have)
- fix the wall texture X position by calculating the ray intersection point
- fix the rounding errors that result in uneven wall edges and texture jumps
- use a more efficient ray trace algorithm that 'steps over squares' instead of actually tracing the ray using tiny steps
- find a use for the Z-buffer :)
- add sprites?
- interpolated texture sampling?
- simple directional global lighting so not all walls appear the same brightness?
  (when imagining a cave and holding a torch however, this makes no sense...)


# World coordinate system

The world is an infinite 2d plane built from squares. Each square measures 1x1 and
can either be a wall (of a certain texture) or an empty space.
The engine uses the regular mathematical axis orientation so the positive X axis is to the right,
and the positive Y axis is up.  This usually means the (0, 0) word map coordinate
corresponds to the bottom left corner in the minimap display on the screen.
The Z coordinate is not used at all because we are only able to draw corridors
that all have the same floor level and height.


# Camera ('player') position and viewing angle

The camera is just a 2d vector, it's viewing direction another 2d vector.
The length of the viewing direction vector doesn't matter.
The 'height' of the camera is simulated in the column draw phase where it
determines the height and position of the walls. Currently, the height of the
camera is exactly in the middle between ceiling and floor.
It is not possible to look up or down: you can only rotate the camera horizontally.
FOV can be adjusted to tweak the (horizontal) perspective.

You can use W,S,A,D to walk, and rotating is done with the mouse (or Q,E).


# Textures

All textures (walls, ceiling, floors) are squares of 64x64 pixels.
Could be another power of 2, but I settled on 64x64 considering the display size and
the number of pixels the engine has to push.
