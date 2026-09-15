"""Google Ads Performance Max asset specs.

Single source of truth. Bron:
https://developers.google.com/google-ads/api/performance-max/asset-requirements
Laatst geverifieerd: 2026-09-15. Controleer periodiek; Google wijzigt deze tabel.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_FILE_SIZE_KB = 5120
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "GIF"}
# Relatieve tolerantie op aspect ratio. Google geeft ASPECT_RATIO_NOT_ALLOWED
# terug bij afwijking, dus we zijn hier strikt.
ASPECT_TOLERANCE = 0.01

# Richtlijn voor nieuwsbrief-bronbeelden vóór `pmax images` (agent-stap, geen
# harde validator). Kortste zijde onder deze waarde (of onder IMAGE_SPECS
# minimum na crop) → AI-upscale van het mailbeeld; compositie behouden, geen
# nieuwe scene. Zie AGENT.md §5b en docs/pipeline-flowchart.md.
NEWSLETTER_SOURCE_MIN_SHORT_SIDE_PX = 600


@dataclass(frozen=True)
class TextSpec:
    field: str
    asset_field_type: str
    max_chars: int
    min_count: int
    max_count: int
    recommended_count: int


TEXT_SPECS: tuple[TextSpec, ...] = (
    TextSpec("headlines", "HEADLINE", 30, 3, 15, 11),
    TextSpec("long_headlines", "LONG_HEADLINE", 90, 1, 5, 5),
    TextSpec("descriptions", "DESCRIPTION", 90, 2, 5, 5),
)

# BUSINESS_NAME hoort bij de asset group als brand guidelines uit staan,
# anders bij de campagne. Wij valideren hem altijd: hij is hoe dan ook nodig.
BUSINESS_NAME_MAX_CHARS = 25


@dataclass(frozen=True)
class ImageSpec:
    slot: str
    asset_field_type: str
    ratio: float
    recommended: tuple[int, int]
    minimum: tuple[int, int]
    min_count: int
    max_count: int
    required: bool


IMAGE_SPECS: tuple[ImageSpec, ...] = (
    ImageSpec("landscape", "MARKETING_IMAGE", 1200 / 628, (1200, 628), (600, 314), 1, 20, True),
    ImageSpec("square", "SQUARE_MARKETING_IMAGE", 1.0, (1200, 1200), (300, 300), 1, 20, True),
    ImageSpec("portrait", "PORTRAIT_MARKETING_IMAGE", 960 / 1200, (960, 1200), (480, 600), 0, 20, False),
)

LOGO_SPEC = ImageSpec("logo", "LOGO", 1.0, (1200, 1200), (128, 128), 1, 5, True)
LANDSCAPE_LOGO_SPEC = ImageSpec(
    "landscape_logo", "LANDSCAPE_LOGO", 4.0, (1200, 300), (512, 128), 0, 20, False
)

SPEC_BY_SLOT = {s.slot: s for s in IMAGE_SPECS} | {
    LOGO_SPEC.slot: LOGO_SPEC,
    LANDSCAPE_LOGO_SPEC.slot: LANDSCAPE_LOGO_SPEC,
}
