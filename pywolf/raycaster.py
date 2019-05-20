import pkgutil
import io
from math import pi, tan, radians
from typing import Tuple, List, Optional, Union, BinaryIO
from PIL import Image
from .vector import Vec2

# Optimization ideas:
#
# - get rid of the Vector class and inline trig functions instead.
#   (but that results in code that is less easier to understand)


class Texture:
    SIZE = 64

    def __init__(self, image: Union[str, BinaryIO]) -> None:
        if isinstance(image, str):
            data = pkgutil.get_data(__name__, image)
            if not data:
                raise IOError("can't find texture "+image)
            image = io.BytesIO(data)
        with image, Image.open(image) as img:
            if img.size != (self.SIZE, self.SIZE):
                raise IOError(f"texture is not {self.SIZE}x{self.SIZE}")
            if img.mode != "RGB":
                raise IOError(f"texture is not RGB (must not have alpha-channel)")
            self.image = img.load()

    def sample(self, x: float, y: float) -> Tuple[int, int, int]:
        """Sample a texture color at the given coordinates, normalized 0.0 ... 0.999999999, wrapping around"""
        return self.image[int((x % 1.0)*self.SIZE), int((y % 1.0)*self.SIZE)]


class Raycaster:
    HVOF = radians(80)
    BLACK_DISTANCE = 4.0

    def __init__(self, pixwidth: int, pixheight: int) -> None:
        self.pixwidth = pixwidth
        self.pixheight = pixheight
        self.zbuffer = [[0.0] * pixheight for _ in range(pixwidth)]
        self.ceiling_sizes = [0] * pixwidth
        self.image = Image.new('RGB', (pixwidth, pixheight), color=0)
        self.textures = {
            "test": Texture("textures/test.png"),
            "floor": Texture("textures/floor.png"),
            "ceiling": Texture("textures/ceiling.png"),
            "wall-bricks": Texture("textures/wall-bricks.png"),
            "wall-stone": Texture("textures/wall-stone.png"),
        }
        self.wall_textures = [None, self.textures["wall-bricks"], self.textures["wall-stone"]]
        self.frame = 0
        self.player_position = Vec2(0, 0)
        self.player_direction = Vec2(0, 1)
        self.camera_plane = Vec2(tan(self.HVOF / 2), 0)
        self.map = self.load_map()      # rows, so map[y][x] to get a square

    def load_map(self) -> List[bytearray]:
        cmap = ["11111111111111111111",
                "1..................1",
                "1..111111222222.2221",
                "1.....1.....2......1",
                "1.....1.....2......1",
                "1...111.....2222...1",
                "1.....1222..2......1",
                "1......222..2.1.2.11",
                "1.........s........1",
                "11111111111111111111"]         # (0,0) is bottom left
        cmap.reverse()  # flip the Y axis so (0,0) is at bottom left

        def translate(c):
            if '0' <= c <= '9':
                return ord(c)-ord('0')
            return 0

        for y, line in enumerate(cmap):
            x = line.find('s')
            if x >= 0:
                self.player_position = Vec2(x + 0.5, y + 0.5)
                break
        m2 = []
        for mapline in cmap:
            m2.append(bytearray([translate(c) for c in mapline]))
        return m2

    def tick(self, walltime_msec: float) -> None:
        # self.clear_zbuffer()        # TODO actually use the z-buffer for something
        self.frame += 1
        # cast a ray per pixel column on the screen!
        # (we end up redrawing all pixels of the screen, so no explicit clear is needed)
        d_screen = 0.5/(tan(self.HVOF/2) * self.pixheight/self.pixwidth)
        for x in range(self.pixwidth):
            wall, distance, texture_x = self.cast_ray(x)
            if distance > 0:
                ceiling_size = int(self.pixheight * (1.0 - d_screen / distance) / 2.0)
                self.ceiling_sizes[x] = ceiling_size
                if wall > 0:
                    self.draw_column(x, ceiling_size, distance, self.wall_textures[wall], texture_x)   # type: ignore
                else:
                    self.draw_black_column(x, ceiling_size, distance)
        self.draw_floor_and_ceiling(self.ceiling_sizes, d_screen)

    def cast_ray(self, pixel_x: int) -> Tuple[int, float, float]:
        # TODO more efficient algorithm: use map square dx/dy steps to hop map squares,
        #      instead of 'tracing the ray' with small steps
        camera_plane_ray = (pixel_x / self.pixwidth - 0.5) * 2 * self.camera_plane
        cast_ray = self.player_direction + camera_plane_ray
        distance = 0.0
        step_size = 0.02   # lower this to increase ray resolution
        ray = self.player_position
        ray_step = cast_ray * step_size
        while distance <= self.BLACK_DISTANCE:
            distance += step_size
            ray += ray_step
            square = self.map_square(ray.x, ray.y)
            if square:
                tx, intersection = self.intersection_with_mapsquare(self.player_position, ray)
                return square, distance, tx
        return -1, distance, 0.0

    def intersection_with_mapsquare(self, camera: Vec2, cast_ray: Vec2) -> Tuple[float, Vec2]:
        """Returns (wall texture coordinate, Vec2(intersect x, intersect y))"""
        # TODO there has to be a more efficient way to calculate the intersection
        # first determine what quadrant of the square the camera is looking at,
        # and based on the relative angle with the vertex, what edge of the square.
        direction = cast_ray - camera
        square_center = Vec2(int(cast_ray.x) + 0.5, int(cast_ray.y) + 0.5)
        if camera.x < square_center.x:
            # left half of square
            if camera.y < square_center.y:
                vertex_angle = ((square_center + Vec2(-0.5, -0.5)) - camera).angle()
                intersects = "bottom" if direction.angle() < vertex_angle else "left"
            else:
                vertex_angle = ((square_center + Vec2(-0.5, 0.5)) - camera).angle()
                intersects = "left" if direction.angle() < vertex_angle else "top"
        else:
            # right half of square (need to flip some X's because of angle sign issue)
            if camera.y < square_center.y:
                vertex = ((square_center + Vec2(0.5, -0.5)) - camera)
                vertex.x = -vertex.x
                positive_dir = Vec2(-direction.x, direction.y)
                intersects = "bottom" if positive_dir.angle() < vertex.angle() else "right"
            else:
                vertex = ((square_center + Vec2(0.5, 0.5)) - camera)
                vertex.x = -vertex.x
                positive_dir = Vec2(-direction.x, direction.y)
                intersects = "right" if positive_dir.angle() < vertex.angle() else "top"
        # now calculate the exact x (and y) coordinates of the intersection with the square's edge
        if intersects == "top":
            iy = square_center.y + 0.5
            ix = 0.0 if direction.y == 0 else camera.x + (iy - camera.y) * direction.x / direction.y
            return square_center.x + 0.5 - ix, Vec2(ix, iy)
        elif intersects == "bottom":
            iy = square_center.y - 0.5
            ix = 0.0 if direction.y == 0 else camera.x + (iy - camera.y) * direction.x / direction.y
            return ix - square_center.x + 0.5, Vec2(ix, iy)
        elif intersects == "left":
            ix = square_center.x - 0.5
            iy = 0.0 if direction.x == 0 else camera.y + (ix - camera.x) * direction.y / direction.x
            return square_center.y + 0.5 - iy, Vec2(ix, iy)
        else:   # right edge
            ix = square_center.x + 0.5
            iy = 0.0 if direction.x == 0 else camera.y + (ix - camera.x) * direction.y / direction.x
            return iy - square_center.y + 0.5, Vec2(ix, iy)

    def map_square(self, x: float, y: float) -> int:
        mx = int(x)
        my = int(y)
        if mx < 0 or mx >= len(self.map[0]) or my < 0 or my >= len(self.map):
            return 255
        return self.map[my][mx]

    def brightness(self, distance: float) -> float:
        # TODO non-linear?
        return max(0.0, 1.0 - distance / self.BLACK_DISTANCE)

    def draw_column(self, x: int, ceiling: int, distance: float, texture: Texture, tx: float) -> None:
        start_y = max(0, ceiling)
        num_pixels = self.pixheight - 2*start_y
        wall_height = self.pixheight - 2*ceiling
        brightness = self.brightness(distance)      # the whole column has the same brightness value
        for y in range(start_y, start_y+num_pixels):
            self.set_pixel(x, y, distance, brightness, texture.sample(tx, (y-ceiling) / wall_height))

    def draw_black_column(self, x: int, ceiling: int, distance: float) -> None:
        start_y = max(0, ceiling)
        num_pixels = self.pixheight - 2*start_y
        for y in range(start_y, start_y+num_pixels):
            self.set_pixel(x, y, distance, 1.0, (0, 0, 0))

    def draw_floor_and_ceiling(self, ceiling_sizes: List[int], d_screen: float) -> None:
        mcs = max(ceiling_sizes)
        if mcs <= 0:
            return
        max_height_possible = int(self.pixheight*(1.0-d_screen/self.BLACK_DISTANCE)/2.0)
        ceiling_tex = self.textures["ceiling"]
        floor_tex = self.textures["floor"]
        for y in range(min(mcs, max_height_possible)):
            sy = 0.5 - y / self.pixheight
            d_ground = 0.5 * d_screen / sy          # how far, horizontally over the ground, is this away from us?
            brightness = self.brightness(d_ground)
            for x, h in enumerate(ceiling_sizes):
                if y < h:
                    camera_plane_ray = (x / self.pixwidth - 0.5) * 2 * self.camera_plane
                    ray = self.player_position + d_ground*(self.player_direction + camera_plane_ray)
                    # we use the fact that the ceiling and floor are mirrored
                    self.set_pixel(x, y, d_ground, brightness, ceiling_tex.sample(ray.x, -ray.y))
                    self.set_pixel(x, self.pixheight-y-1, d_ground, brightness, floor_tex.sample(ray.x, -ray.y))

    def clear_zbuffer(self) -> None:
        infinity = float("inf")
        for x in range(self.pixwidth):
            for y in range(self.pixheight):
                self.zbuffer[x][y] = infinity

    def set_pixel(self, x: int, y: int, z: float, brightness: float, rgb: Optional[Tuple[int, int, int]]) -> None:
        """Sets a pixel on the screen (if it is visible) and adjusts its z-buffer value.
        The pixel's brightness is adjusted as well.
        If rgb is None, the pixel is transparent instead of having a color."""
        # TODO use the z-buffer (for now we ignore it because there's nothing using it at the moment)
        # if z <= self.zbuffer[x][y]:
        #     if rgb:
        #         self.zbuffer[x][y] = z
        #         if z > 0:
        #             rgb = self.rgb_brightness(rgb, brightness)
        #         self.image.putpixel((x, y), rgb)
        if rgb:
            if z > 0.0 and brightness != 1.0:
                rgb = self.rgb_brightness(rgb, brightness)
            self.image.putpixel((x, y), rgb)

    def rgb_brightness(self, rgb: Tuple[int, int, int], brightness: float) -> Tuple[int, int, int]:
        """adjust brightness of the color. brightness 0=pitch black, 1=normal"""
        # while theoretically it's more accurate to adjust the luminosity (by doing rgb->hls->rgb),
        # it's almost as good and a lot faster to just scale the r,g,b values themselves.
        # from colorsys import rgb_to_hls, hls_to_rgb
        # h, l, s = rgb_to_hls(*rgb)
        # r, g, b = hls_to_rgb(h, l*scale, s)
        return int(rgb[0] * brightness), int(rgb[1] * brightness), int(rgb[2] * brightness)

    def move_player_forward_or_back(self, amount: float) -> None:
        new = self.player_position + amount * self.player_direction.normalized()
        self._move_player(new.x, new.y)

    def move_player_left_or_right(self, amount: float) -> None:
        dn = self.player_direction.normalized()
        new = self.player_position + amount * Vec2(dn.y, -dn.x)
        self._move_player(new.x, new.y)

    def _move_player(self, x: float, y: float) -> None:
        if self.map_square(x, y) == 0:
            # stay a certain minimum distance from the walls
            if self.map_square(x + 0.1, y):
                x = int(x) + 0.9
            if self.map_square(x - 0.1, y):
                x = int(x) + 0.1
            if self.map_square(x, y + 0.1):
                y = int(y) + 0.9
            if self.map_square(x, y - 0.1):
                y = int(y) + 0.1
            self.player_position = Vec2(x, y)

    def rotate_player(self, angle: float) -> None:
        new_angle = self.player_direction.angle() + angle
        self.rotate_player_to(new_angle)

    def rotate_player_to(self, angle: float) -> None:
        self.player_direction = Vec2.from_angle(angle)
        self.camera_plane = Vec2.from_angle(angle - pi / 2) * tan(self.HVOF / 2)

    def set_fov(self, fov: float) -> None:
        self.HVOF = fov
        self.rotate_player(0.0)
