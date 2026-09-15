"""Valideer een campaign.yaml tegen de PMax asset requirements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .specs import (
    ALLOWED_IMAGE_FORMATS,
    ASPECT_TOLERANCE,
    BUSINESS_NAME_MAX_CHARS,
    IMAGE_SPECS,
    LOGO_SPEC,
    MAX_FILE_SIZE_KB,
    TEXT_SPECS,
    ImageSpec,
)

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    level: str
    group: str
    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper():7}] {self.group} / {self.field}: {self.message}"


def _check_text_field(group_name: str, spec, values: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    n = len(values)

    if n < spec.min_count:
        issues.append(
            Issue(ERROR, group_name, spec.field, f"{n} van minimaal {spec.min_count} — asset group kan niet serveren")
        )
    if n > spec.max_count:
        issues.append(
            Issue(ERROR, group_name, spec.field, f"{n} van maximaal {spec.max_count} — Google weigert de extra assets")
        )
    if spec.min_count <= n < spec.recommended_count:
        issues.append(
            Issue(WARNING, group_name, spec.field, f"{n} van {spec.max_count} slots gevuld — meer varianten verbeteren ad strength")
        )

    for i, text in enumerate(values, start=1):
        if not isinstance(text, str):
            # Klassieke YAML-val: een niet-gequote regel met ': ' erin wordt een
            # dict in plaats van een string. Dat glipt door een simpele
            # len()-check heen en levert stilzwijgend kapotte copy op.
            issues.append(
                Issue(
                    ERROR,
                    group_name,
                    spec.field,
                    f"[{i}] is geen tekst maar {type(text).__name__} — zet de regel tussen "
                    f'quotes als er ": " in staat: {text!r}',
                )
            )
            continue
        if not text.strip():
            issues.append(Issue(ERROR, group_name, spec.field, f"[{i}] is leeg"))
            continue
        if len(text) > spec.max_chars:
            issues.append(
                Issue(ERROR, group_name, spec.field, f"[{i}] {len(text)} tekens (max {spec.max_chars}): {text!r}")
            )

    seen: dict[str, int] = {}
    for i, text in enumerate(values, start=1):
        if not isinstance(text, str):
            continue
        key = text.strip().casefold()
        if key in seen:
            issues.append(
                Issue(WARNING, group_name, spec.field, f"[{i}] duplicaat van [{seen[key]}]: {text!r}")
            )
        else:
            seen[key] = i

    return issues


def _check_forbidden_terms(group_name: str, spec, values: list[str], terms: list[str]) -> list[Issue]:
    """Claims die deze klant niet mag maken, uit het klantprofiel."""
    issues: list[Issue] = []
    for i, text in enumerate(values, start=1):
        if not isinstance(text, str):
            continue
        lowered = text.casefold()
        for term in terms:
            if term.casefold() in lowered:
                issues.append(
                    Issue(ERROR, group_name, spec.field, f"[{i}] bevat verboden claim {term!r}: {text!r}")
                )
    return issues


def _check_final_url(group_name: str, url: str | None) -> list[Issue]:
    if not url:
        return [
            Issue(
                ERROR,
                group_name,
                "final_url",
                "ontbreekt — zet 'path: /pad' in de asset group (wordt opgelost tegen base_url "
                "uit het klantprofiel) of geef een volledige 'final_url'",
            )
        ]
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return [
            Issue(ERROR, group_name, "final_url", f"geen absolute URL: {url!r} (verwacht https://...)")
        ]
    return []


def _check_image(group_name: str, spec: ImageSpec, path: Path) -> list[Issue]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return [Issue(WARNING, group_name, spec.slot, "Pillow niet geinstalleerd, beeldcheck overgeslagen")]

    if not path.exists():
        return [Issue(ERROR, group_name, spec.slot, f"bestand bestaat niet: {path}")]

    issues: list[Issue] = []
    size_kb = path.stat().st_size / 1024
    if size_kb > MAX_FILE_SIZE_KB:
        issues.append(
            Issue(ERROR, group_name, spec.slot, f"{path.name} is {size_kb:.0f} KB (max {MAX_FILE_SIZE_KB} KB)")
        )

    try:
        with Image.open(path) as img:
            fmt, (w, h) = img.format, img.size
    except Exception as exc:
        return issues + [Issue(ERROR, group_name, spec.slot, f"{path.name} niet leesbaar: {exc}")]

    if fmt not in ALLOWED_IMAGE_FORMATS:
        issues.append(
            Issue(ERROR, group_name, spec.slot, f"{path.name} is {fmt}; toegestaan: PNG, JPEG, GIF")
        )

    ratio = w / h
    if abs(ratio - spec.ratio) / spec.ratio > ASPECT_TOLERANCE:
        issues.append(
            Issue(
                ERROR,
                group_name,
                spec.slot,
                f"{path.name} is {w}x{h} (ratio {ratio:.3f}), verwacht {spec.ratio:.3f} "
                f"— Google geeft ASPECT_RATIO_NOT_ALLOWED",
            )
        )

    min_w, min_h = spec.minimum
    if w < min_w or h < min_h:
        issues.append(
            Issue(ERROR, group_name, spec.slot, f"{path.name} is {w}x{h}, minimaal {min_w}x{min_h}")
        )

    return issues


def validate_campaign(data: dict, asset_root: Path | None = None) -> list[Issue]:
    """Valideer de hele campagne. asset_root=None slaat beeldchecks over."""
    issues: list[Issue] = []
    campaign = data.get("campaign", "campagne")

    business_name = data.get("business_name")
    if not business_name:
        issues.append(Issue(ERROR, campaign, "business_name", "ontbreekt — verplicht asset in PMax"))
    elif len(business_name) > BUSINESS_NAME_MAX_CHARS:
        issues.append(
            Issue(ERROR, campaign, "business_name", f"{len(business_name)} tekens (max {BUSINESS_NAME_MAX_CHARS})")
        )

    logo = data.get("logo")
    if not logo:
        issues.append(Issue(ERROR, campaign, "logo", "ontbreekt — 1:1 logo is verplicht in PMax"))
    elif asset_root is not None:
        issues.extend(_check_image(campaign, LOGO_SPEC, asset_root / logo))

    groups = data.get("asset_groups") or []
    if not groups:
        issues.append(Issue(ERROR, campaign, "asset_groups", "geen asset groups gevonden"))

    terms = list(((data.get("_client") or {}).get("copy") or {}).get("forbidden_terms") or [])

    for group in groups:
        name = group.get("name", "naamloos")
        issues.extend(_check_final_url(name, group.get("final_url")))

        for spec in TEXT_SPECS:
            values = group.get(spec.field) or []
            issues.extend(_check_text_field(name, spec, values))
            if terms:
                issues.extend(_check_forbidden_terms(name, spec, values, terms))

        if asset_root is None:
            continue

        images = group.get("images") or {}
        for spec in IMAGE_SPECS:
            paths = images.get(spec.slot) or []
            if isinstance(paths, str):
                paths = [paths]
            if spec.required and len(paths) < spec.min_count:
                issues.append(
                    Issue(ERROR, name, spec.slot, f"{len(paths)} beelden, minimaal {spec.min_count} vereist")
                )
            if not spec.required and not paths:
                issues.append(
                    Issue(WARNING, name, spec.slot, "geen portretbeeld — je mist mobile-first inventory")
                )
            if len(paths) > spec.max_count:
                issues.append(Issue(ERROR, name, spec.slot, f"{len(paths)} beelden, max {spec.max_count}"))
            for p in paths:
                issues.extend(_check_image(name, spec, asset_root / p))

    return issues


def has_errors(issues: list[Issue]) -> bool:
    return any(i.level == ERROR for i in issues)
