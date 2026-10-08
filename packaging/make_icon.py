"""Generate packaging/md2doc.ico (rounded blue tile with 'md')."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / "src" / "md2doc" / "vendor" / "fonts" / "Inter-Bold.ttf"


def tile(size: int) -> Image.Image:
    s = 512
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, s - 16, s - 16), radius=96, fill=(9, 105, 218, 255))
    d.rounded_rectangle((16, 16, s - 16, s // 2), radius=96, fill=(31, 136, 255, 255))
    d.rectangle((16, 160, s - 16, s // 2), fill=(31, 136, 255, 255))
    d.rounded_rectangle((16, s // 2 - 8, s - 16, s - 16), radius=96, fill=(9, 105, 218, 255))
    d.rectangle((16, s // 2 - 8, s - 16, s // 2 + 120), fill=(9, 105, 218, 255))
    try:
        font = ImageFont.truetype(str(FONT), 250)
    except OSError:
        font = ImageFont.load_default()
    d.text((s / 2, s / 2 + 6), "md", font=font, fill=(255, 255, 255, 255), anchor="mm")
    return im.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big = tile(256)
    big.save(HERE / "md2doc.ico", format="ICO", sizes=[(n, n) for n in sizes])
    print("wrote", HERE / "md2doc.ico")
