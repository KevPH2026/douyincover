from PIL import Image, ImageDraw, ImageFilter


def _scale(points, size):
    return [(int(x * size / 1000), int(y * size / 1000)) for x, y in points]


def paste_cut_k(img, xy, size, accent=(178, 255, 82), opacity=0.28):
    """Paste a custom cut-mark K onto an RGBA image."""
    mark = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    md = ImageDraw.Draw(mark)

    width = max(8, int(size * 0.105))
    shadow_width = max(10, int(size * 0.13))
    main = (255, 255, 255, int(255 * opacity))
    accent_alpha = int(210 * min(1, opacity * 1.8))
    blue_alpha = int(150 * min(1, opacity * 1.6))

    strokes = [
        [(240, 100), (240, 900)],
        [(300, 520), (785, 105)],
        [(305, 520), (820, 900)],
    ]

    for pts in strokes:
        gd.line(_scale([(x + 22, y + 0) for x, y in pts], size), fill=accent + (accent_alpha,), width=shadow_width)
        gd.line(_scale([(x - 18, y + 8) for x, y in pts], size), fill=(80, 214, 255, blue_alpha), width=shadow_width)
    glow = glow.filter(ImageFilter.GaussianBlur(max(2, int(size * 0.018))))
    mark.alpha_composite(glow)

    for pts in strokes:
        md.line(_scale(pts, size), fill=main, width=width, joint="curve")

    # Angled cuts give the mark a sharper, more constructed feel.
    cut = (5, 7, 10, int(210 * min(1, opacity * 2.2)))
    md.line(_scale([(120, 330), (378, 230)], size), fill=cut, width=max(5, int(size * 0.035)))
    md.line(_scale([(475, 708), (665, 610)], size), fill=cut, width=max(5, int(size * 0.034)))
    md.line(_scale([(718, 120), (900, 120)], size), fill=accent + (accent_alpha,), width=max(4, int(size * 0.025)))
    md.line(_scale([(760, 890), (900, 890)], size), fill=(80, 214, 255, blue_alpha), width=max(4, int(size * 0.021)))

    img.alpha_composite(mark, xy)
