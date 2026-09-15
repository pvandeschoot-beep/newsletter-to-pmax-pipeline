"""Klantprofielen laden en in een campagne mengen."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import yaml


class ClientError(Exception):
    """Klantprofiel ontbreekt of is ongeldig."""


def clients_dir(root: Path) -> Path:
    return root / "clients"


def available_clients(root: Path) -> list[str]:
    folder = clients_dir(root)
    if not folder.is_dir():
        return []
    return sorted(
        p.stem
        for p in folder.glob("*.yaml")
        if p.name != "_template.yaml" and not p.name.startswith(".")
    )


def load_client(slug: str, root: Path) -> dict:
    path = clients_dir(root) / f"{slug}.yaml"
    if not path.exists():
        known = ", ".join(available_clients(root)) or "(geen)"
        raise ClientError(
            f"klant '{slug}' niet gevonden in {clients_dir(root)} "
            f"(bekend: {known}). Maak eerst: python -m pmax init --client {slug}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["slug"] = slug
    for required in ("name", "base_url", "logo"):
        if not data.get(required):
            raise ClientError(f"clients/{slug}.yaml mist verplicht veld '{required}'")
    return data


def brand_settings(client: dict) -> dict:
    brand = client.get("brand") or {}
    return {
        "logo_width_ratio": float(brand.get("logo_width_ratio", 0.28)),
        "logo_position": brand.get("logo_position", "bottom-left"),
    }


def resolve_campaign(campaign: dict, client: dict) -> dict:
    """Meng klantprofiel in de campagne. Campagnevelden winnen bij conflict."""
    out = dict(campaign)
    out["_client"] = client
    out.setdefault("client", client.get("name"))
    out.setdefault("client_slug", client.get("slug"))
    out.setdefault("business_name", client.get("business_name") or client.get("name"))
    out.setdefault("logo", client.get("logo"))
    if client.get("cta") and "cta" not in out:
        out["cta"] = client["cta"]

    base = client["base_url"].rstrip("/") + "/"
    groups = []
    for group in out.get("asset_groups") or []:
        g = dict(group)
        if not g.get("final_url") and g.get("path"):
            g["final_url"] = urljoin(base, g["path"].lstrip("/"))
        groups.append(g)
    out["asset_groups"] = groups
    return out
