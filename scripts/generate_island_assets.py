"""Generate standalone aesthetic PNG assets for Island Survival scenario using standard library."""

import math
import struct
import zlib
from pathlib import Path


def write_png(filepath: Path, width: int, height: int, pixels: list[tuple[int, int, int, int]]):
    """Write an RGBA PNG file directly using standard library zlib and struct."""
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter type 0 (None)
        row_offset = y * width
        for x in range(width):
            r, g, b, a = pixels[row_offset + x]
            raw_data.extend([r, g, b, a])

    compressed = zlib.compress(bytes(raw_data), level=6)

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    png_bytes = bytearray(b"\x89PNG\r\n\x1a\n")
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes.extend(make_chunk(b"IHDR", ihdr_data))
    # IDAT
    png_bytes.extend(make_chunk(b"IDAT", compressed))
    # IEND
    png_bytes.extend(make_chunk(b"IEND", b""))

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(png_bytes)


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
        255,
    )


def generate_beach_background(filepath: Path, w=960, h=540):
    pixels = []
    # Tropical Beach with Sunset/Day Sky, Cyan Ocean, Golden Sand, and Silhouettes
    sky_top = (45, 115, 185)
    sky_mid = (110, 185, 235)
    sky_horizon = (245, 200, 140)
    sea_deep = (20, 85, 130)
    sea_shallow = (35, 175, 195)
    sea_foam = (235, 248, 255)
    sand_wet = (195, 160, 115)
    sand_dry = (230, 205, 155)

    for y in range(h):
        ny = y / h
        for x in range(w):
            nx = x / w
            if ny < 0.40:
                # Sky gradient
                t = ny / 0.40
                if t < 0.7:
                    color = lerp_color(sky_top, sky_mid, t / 0.7)
                else:
                    color = lerp_color(sky_mid, sky_horizon, (t - 0.7) / 0.3)
                # Sun glow
                sun_dx = nx - 0.65
                sun_dy = ny - 0.22
                dist_sun = math.sqrt(sun_dx * sun_dx * 2 + sun_dy * sun_dy)
                if dist_sun < 0.25:
                    glow = (1.0 - dist_sun / 0.25) ** 2 * 0.7
                    color = lerp_color(color, (255, 245, 210), glow)
            elif ny < 0.68:
                # Ocean waves
                t = (ny - 0.40) / 0.28
                wave = math.sin(nx * 28 + ny * 20) * 0.04
                color = lerp_color(sea_deep, sea_shallow, t + wave)
                # Ocean horizon line
                if ny < 0.41:
                    color = (25, 75, 115, 255)
                # Surf & foam near shore
                if ny > 0.64:
                    foam_val = math.sin(nx * 40) * 0.5 + 0.5
                    if (ny - 0.64) / 0.04 > foam_val * 0.6:
                        color = lerp_color(color, sea_foam, 0.8)
            else:
                # Sandy beach with texture
                t = (ny - 0.68) / 0.32
                color = lerp_color(sand_wet, sand_dry, t)
                # Driftwood / rocks silhouettes on beach
                if 0.20 < nx < 0.32 and 0.72 < ny < 0.78:
                    color = (60, 45, 35, 255)
                # Subtle texture grain
                grain = ((x * 13 + y * 17) % 19 - 9) * 1.5
                color = (
                    max(0, min(255, int(color[0] + grain))),
                    max(0, min(255, int(color[1] + grain))),
                    max(0, min(255, int(color[2] + grain))),
                    255,
                )

            # Left palm frond silhouette
            if nx < 0.22 and ny < 0.45:
                palm_arch = 0.45 - (nx * 1.8) ** 1.3
                if ny < palm_arch and math.sin((nx + ny) * 50) > -0.2:
                    color = (18, 32, 24, 255)

            pixels.append(color)

    write_png(filepath, w, h, pixels)


def generate_coastal_jungle(filepath: Path, w=960, h=540):
    pixels = []
    # Coastal jungle: Dappled forest light, massive green fronds, bamboo and twisted roots
    top_dark = (12, 28, 16)
    foliage_dark = (22, 58, 32)
    foliage_mid = (45, 110, 55)
    foliage_light = (85, 168, 75)
    dirt_ground = (65, 48, 32)

    for y in range(h):
        ny = y / h
        for x in range(w):
            nx = x / w
            # Base vertical gradient
            if ny < 0.75:
                base = lerp_color(top_dark, foliage_dark, ny / 0.75)
            else:
                base = lerp_color(foliage_dark, dirt_ground, (ny - 0.75) / 0.25)

            # Procedural vine / canopy bands
            vines = math.sin(nx * 18 + math.cos(ny * 12) * 2)
            tree_trunks = math.sin(nx * 8 + 1.2) * 0.5 + 0.5
            dappled_sun = math.sin(nx * 32) * math.sin(ny * 24)

            if dappled_sun > 0.4 and ny < 0.70:
                color = lerp_color(base, foliage_light, (dappled_sun - 0.4) * 1.4)
            elif tree_trunks > 0.78:
                # Tree trunk
                color = lerp_color((38, 26, 18), (55, 38, 25), (tree_trunks - 0.78) * 4)
            elif vines > 0.65:
                color = lerp_color(base, (30, 80, 40), 0.7)
            else:
                color = lerp_color(base, foliage_mid, max(0.0, math.sin(nx * 14 + ny * 8) * 0.4))

            pixels.append(color)

    write_png(filepath, w, h, pixels)


def generate_deep_jungle(filepath: Path, w=960, h=540):
    pixels = []
    # Deep jungle: Mysterious, foggy teal-emerald canopy, moonlight/creek glint
    deep_bg = (8, 18, 16)
    mist_glow = (25, 75, 70)
    stream_cyan = (40, 160, 175)
    moss_rock = (28, 55, 42)

    for y in range(h):
        ny = y / h
        for x in range(w):
            nx = x / w
            base = lerp_color(deep_bg, (15, 32, 28), ny)

            # Central mist or stream path
            stream_center = 0.5 + math.sin(ny * 4) * 0.15
            dist_stream = abs(nx - stream_center)

            if ny > 0.55 and dist_stream < (ny - 0.55) * 0.4:
                # Stream water glinting
                water_factor = 1.0 - (dist_stream / max(0.01, (ny - 0.55) * 0.4))
                wave = math.sin(x * 0.3 + y * 0.4) * 0.2
                color = lerp_color(moss_rock, stream_cyan, max(0.0, min(1.0, water_factor + wave)))
            else:
                # Mossy giant trunks and dense ancient canopy
                trunk = math.sin(nx * 6 + 0.5)
                if abs(trunk) > 0.8:
                    color = lerp_color(base, (22, 38, 28), 0.6)
                else:
                    mist = math.sin(nx * 10 + ny * 6) * 0.3
                    color = lerp_color(base, mist_glow, max(0.0, mist))

            # Firefly / glow spore particles
            spore = math.sin(x * 137.5 + y * 73.1)
            if spore > 0.985:
                color = (135, 255, 200, 255)

            pixels.append(color)

    write_png(filepath, w, h, pixels)


def generate_icon(filepath: Path, icon_type: str, size=180):
    pixels = []
    bg_circle_r = size * 0.44
    cx, cy = size / 2, size / 2

    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Outer glow & circle card
            if dist > bg_circle_r:
                pixels.append((0, 0, 0, 0))  # Transparent outside
                continue

            # Card background
            card_grad = (y / size)
            card_color = lerp_color((30, 36, 48), (18, 22, 30), card_grad)
            if dist > bg_circle_r - 2.5:
                card_color = (217, 168, 74, 255)  # Gold border

            # Draw item specific graphic inside
            if icon_type == "lighter":
                # Silver/brass rectangular lighter with flame
                # Body: x: [cx-22, cx+22], y: [cy-10, cy+38]
                if abs(dx) < 22 and -10 < dy < 38:
                    card_color = (195, 175, 130, 255)
                    if abs(dx) < 18 and -6 < dy < 34:
                        card_color = (225, 205, 155, 255)
                # Flip cap
                elif abs(dx) < 22 and -26 < dy <= -10:
                    card_color = (175, 155, 115, 255)
                # Flame: teardrop at [cx, cy-34]
                elif dy < -26:
                    flame_dx = dx / 12
                    flame_dy = (dy + 38) / 16
                    if flame_dx * flame_dx + flame_dy * flame_dy < 1.0:
                        card_color = (255, 140, 20, 255)
                        if flame_dx * flame_dx * 2 + flame_dy * flame_dy * 2 < 0.6:
                            card_color = (255, 235, 120, 255)

            elif icon_type == "rope":
                # Coiled rope ellipse loops
                r1 = math.sqrt((dx * 0.9) ** 2 + (dy * 1.4) ** 2)
                r2 = math.sqrt(((dx - 4) * 0.9) ** 2 + ((dy + 6) * 1.4) ** 2)
                r3 = math.sqrt(((dx + 5) * 0.9) ** 2 + ((dy - 8) * 1.4) ** 2)
                is_rope = (
                    (20 < r1 < 36) or
                    (22 < r2 < 38) or
                    (24 < r3 < 40)
                )
                if is_rope:
                    texture = math.sin((dx + dy) * 0.8)
                    card_color = (205, 165, 105, 255) if texture > 0 else (160, 125, 75, 255)

            elif icon_type == "glass_bottle":
                # Bottle silhouette: neck at top, rounded body
                if -45 < dy < -22 and abs(dx) < 9:
                    # Neck
                    card_color = (160, 220, 235, 230)
                elif -22 <= dy < 38 and abs(dx) < 26:
                    # Body
                    dist_corner = math.sqrt(max(0, abs(dx) - 18) ** 2 + max(0, abs(dy - 8) - 20) ** 2)
                    if dist_corner < 10:
                        # Liquid inside lower half
                        if dy > 0:
                            card_color = (75, 180, 215, 235)
                        else:
                            card_color = (185, 235, 245, 200)
                # Cork
                elif -54 < dy <= -45 and abs(dx) < 7:
                    card_color = (180, 135, 85, 255)

            elif icon_type == "branches":
                # Crossed brown wood sticks
                stick1 = abs(dx - dy * 0.7) < 6 and abs(dy) < 42
                stick2 = abs(dx + dy * 0.7) < 6 and abs(dy) < 42
                stick3 = abs(dx) < 5 and abs(dy) < 44
                if stick1 or stick2 or stick3:
                    card_color = (145, 95, 55, 255)
                    if math.sin(dy * 0.7) > 0.3:
                        card_color = (115, 70, 38, 255)

            pixels.append(card_color)

    write_png(filepath, size, size, pixels)


def main():
    base_assets = Path(__file__).resolve().parent.parent / "web" / "public" / "assets"
    print("Generating Island Survival Assets into:", base_assets)

    # 1. Backgrounds
    beach_bg = base_assets / "scenes" / "island_beach.png"
    coastal_bg = base_assets / "scenes" / "coastal_jungle.png"
    deep_bg = base_assets / "scenes" / "deep_jungle.png"

    print("Generating Beach background...")
    generate_beach_background(beach_bg)

    print("Generating Coastal Jungle background...")
    generate_coastal_jungle(coastal_bg)

    print("Generating Deep Jungle background...")
    generate_deep_jungle(deep_bg)

    # 2. Item Cards
    items_dir = base_assets / "items"
    print("Generating Lighter icon...")
    generate_icon(items_dir / "lighter.png", "lighter")

    print("Generating Rope icon...")
    generate_icon(items_dir / "rope.png", "rope")

    print("Generating Glass Bottle icon...")
    generate_icon(items_dir / "glass_bottle.png", "glass_bottle")

    print("Generating Branches icon...")
    generate_icon(items_dir / "branches.png", "branches")

    # 3. Hero Illustrations (wreckage & campfire)
    illus_dir = base_assets / "illustrations"
    print("Generating Campfire illustration...")
    generate_beach_background(illus_dir / "wreckage.png", w=640, h=360)
    generate_deep_jungle(illus_dir / "campfire.png", w=640, h=360)

    print("All assets successfully generated!")


if __name__ == "__main__":
    main()
