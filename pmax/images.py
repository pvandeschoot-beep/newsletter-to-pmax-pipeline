"""Beeldbewerking: crop/resize naar PMax-ratio's en logo-overlay.

Vervangt de macOS-only `sips`-stap uit de oude workflow door Pillow, zodat
dezelfde code op een laptop en in CI draait.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .specs import IMAGE_SPECS, MAX_FILE_SIZE_KB


def fit_to_ratio(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop naar de doelratio en schaal naar exacte afmetingen.

    Center-crop omdat Google elk formaat anders bijsnijdt; het onderwerp hoort
    in het midden te blijven.
    """
    target_ratio = target_w / target_h
    w, h = img.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        new_w = round(h * target_ratio)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        new_h = round(w / target_ratio)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)

    return img.crop(box).resize((target_w, target_h), Image.Resampling.LANCZOS)


def overlay_logo(
    img: Image.Image,
    logo: Image.Image,
    logo_width_ratio: float = 0.28,
    position: str = "bottom-left",
) -> Image.Image:
    """Plak het logo op een witte badge. Geeft een RGB-afbeelding terug."""
    base = img.convert("RGBA")
    w, h = base.size

    target_logo_w = max(1, int(w * logo_width_ratio))
    scale = target_logo_w / logo.width
    target_logo_h = max(1, int(logo.height * scale))
    logo_resized = logo.convert("RGBA").resize(
        (target_logo_w, target_logo_h), Image.Resampling.LANCZOS
    )

    pad_x, pad_y = int(w * 0.04), int(h * 0.04)
    badge_pad_x = int(target_logo_w * 0.12)
    badge_pad_y = int(target_logo_h * 0.22)
    badge_w = target_logo_w + badge_pad_x * 2
    badge_h = target_logo_h + badge_pad_y * 2
    radius = max(1, int(badge_h * 0.22))

    badge_x = pad_x if "left" in position else w - badge_w - pad_x
    badge_y = h - badge_h - pad_y if "bottom" in position else pad_y

    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (badge_x + 4, badge_y + 6, badge_x + badge_w + 4, badge_y + badge_h + 6),
        radius=radius,
        fill=(0, 0, 0, 70),
    )
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(6)))

    badge = Image.new("RGBA", (badge_w, badge_h), (255, 255, 255, 0))
    ImageDraw.Draw(badge).rounded_rectangle(
        (0, 0, badge_w, badge_h), radius=radius, fill=(255, 255, 255, 230)
    )
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(badge, (badge_x, badge_y), badge)
    base = Image.alpha_composite(base, layer)

    base.paste(logo_resized, (badge_x + badge_pad_x, badge_y + badge_pad_y), logo_resized)
    return base.convert("RGB")


def _save_within_limit(img: Image.Image, out: Path) -> Path:
    """Sla op als PNG; val terug op JPEG wanneer PNG boven de 5 MB uitkomt."""
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    if out.stat().st_size / 1024 <= MAX_FILE_SIZE_KB:
        return out

    jpg = out.with_suffix(".jpg")
    img.save(jpg, "JPEG", quality=88, optimize=True, progressive=True)
    out.unlink()
    return jpg


def make_pmax_formats(
    source: Path,
    out_dir: Path,
    stem: str,
    logo: Path | None = None,
    logo_width_ratio: float = 0.28,
    logo_position: str = "bottom-left",
) -> dict[str, list[Path]]:
    """Genereer alle PMax-formaten uit een bronbeeld.

    Levert per ratio een versie zonder logo en, als er een logo is meegegeven,
    ook een variant met logo. Beide bewaren is bewust: Google raadt aan per
    ratio minstens een beeld zonder overlay aan te leveren, omdat Google er op
    Display-plaatsingen zelf tekst overheen legt.
    """
    result: dict[str, list[Path]] = {}
    logo_img = Image.open(logo) if logo else None

    with Image.open(source) as src:
        src = src.convert("RGB")
        for spec in IMAGE_SPECS:
            w, h = spec.recommended
            sized = fit_to_ratio(src, w, h)
            paths = [_save_within_limit(sized, out_dir / f"{stem}-{w}x{h}.png")]
            if logo_img is not None:
                branded = overlay_logo(
                    sized, logo_img, logo_width_ratio=logo_width_ratio, position=logo_position
                )
                paths.append(_save_within_limit(branded, out_dir / f"{stem}-{w}x{h}-logo.png"))
            result[spec.slot] = paths

    if logo_img is not None:
        logo_img.close()
    return result
