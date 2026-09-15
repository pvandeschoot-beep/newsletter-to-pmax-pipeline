"""Genereer handoff-mail en review-CSV uit campaign.yaml."""

from __future__ import annotations

import csv
from pathlib import Path

from .specs import TEXT_SPECS

DISCLAIMER = (
    "Dit zijn automatisch gegenereerde voorbeelden ter review, geen definitieve "
    "productie-assets. Copy en beeld komen uit de nieuwsbrief; het logo komt van "
    "de officiele merkbron."
)


def render_handoff(data: dict, drive_link: str | None = None) -> str:
    """Bouw de interne handoff-mail. Geen losse template met placeholders meer:
    de campagnedata is de enige bron, dus tekst en tabel kunnen niet uit de pas
    lopen met wat er daadwerkelijk is opgeleverd."""
    client = data.get("client", "de klant")
    campaign = data.get("campaign", "")
    subject_line = (data.get("source") or {}).get("subject", "")
    groups = data.get("asset_groups") or []

    lines = [
        f"**Onderwerp:** {client} PMax voorbeelden - {campaign} (gegenereerd uit nieuwsbrief)",
        "",
        "Hoi team,",
        "",
        f"Hierbij een set voorbeeld-PMax creatives voor {client}"
        + (f', gebaseerd op de nieuwsbrief "{subject_line}"' if subject_line else "")
        + ".",
        "",
        DISCLAIMER,
        "",
        f"**{len(groups)} asset groups:**",
        "",
        "| # | Asset group | Landingspagina | Headlines | Beelden |",
        "|---|---|---|---|---|",
    ]

    for i, g in enumerate(groups, start=1):
        images = g.get("images") or {}
        n_images = sum(len(v if isinstance(v, list) else [v]) for v in images.values())
        lines.append(
            f"| {i} | {g.get('name', '?')} | {g.get('final_url', '-')} "
            f"| {len(g.get('headlines') or [])} | {n_images} |"
        )

    lines += ["", f"Business name: {data.get('business_name', '-')}"]
    if drive_link:
        lines.append(f"Beelden en copy: {drive_link}")
    lines += [
        "",
        "Laat weten of dit door kan naar productie, of dat we eerst finetunen "
        "(copy, logo-positie, landingspagina's).",
    ]
    return "\n".join(lines)


def write_review_csv(data: dict, out: Path) -> Path:
    """Platte CSV met een regel per tekst-asset, voor review in Sheets.

    Dit is bewust geen Google Ads Editor-importbestand: verifieer dat format
    tegen een verse Ads Editor-export voor je op import vertrouwt.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["asset_group", "final_url", "asset_type", "index", "tekens", "tekst"])
        for group in data.get("asset_groups") or []:
            name = group.get("name", "")
            url = group.get("final_url", "")
            for spec in TEXT_SPECS:
                for i, text in enumerate(group.get(spec.field) or [], start=1):
                    writer.writerow([name, url, spec.asset_field_type, i, len(text), text])
    return out
