"""CLI: python -m pmax <command>

    clients    toon de bekende klantprofielen
    init       zet een nieuw klantprofiel en/of campagne op
    validate   campaign.yaml tegen de PMax-specs (de poort voor oplevering)
    images     bronbeelden -> alle PMax-ratio's, met en zonder logo
    handoff    handoff-mail als markdown
    export     review-CSV met alle tekst-assets
    bundle     zip per campagne

Paden naar beelden en logo's zijn relatief aan --root (standaard de huidige map),
zodat klantprofiel en campagne naar dezelfde assets kunnen wijzen.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import yaml

from .client import (
    ClientError,
    available_clients,
    brand_settings,
    clients_dir,
    load_client,
    resolve_campaign,
)
from .images import make_pmax_formats
from .render import render_handoff, write_review_csv
from .validate import ERROR, WARNING, has_errors, validate_campaign


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"bestand niet gevonden: {path}", file=sys.stderr)
        raise SystemExit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_resolved(args: argparse.Namespace) -> dict:
    """Laad de campagne en voeg het klantprofiel toe.

    De klant komt uit --client of uit het veld 'client_slug' in de campagne.
    Zonder klant werkt alles nog steeds, maar dan moet de campagne zelf
    business_name, logo en volledige final_urls bevatten.
    """
    campaign = _load_yaml(args.campaign)
    slug = getattr(args, "client", None) or campaign.get("client_slug")
    if not slug:
        return campaign
    try:
        return resolve_campaign(campaign, load_client(slug, args.root))
    except ClientError as exc:
        print(f"fout: {exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_clients(args: argparse.Namespace) -> int:
    names = available_clients(args.root)
    if not names:
        print(f"geen klantprofielen in {clients_dir(args.root)}")
        print("maak er een met: python -m pmax init --client <slug>")
        return 0
    for slug in names:
        client = load_client(slug, args.root)
        print(f"{slug:20} {client['name']:28} {client['base_url']}")
    return 0


def _campaign_skeleton(slug: str) -> str:
    return f"""# Campagne. business_name, logo en base_url komen uit clients/{slug}.yaml.
client_slug: {slug}
campaign: Naam van de campagne
source:
  type: newsletter
  subject: "Onderwerp van de nieuwsbrief"
  date: "JJJJ-MM-DD"

asset_groups:
  - name: Thema 1
    path: /pad/naar/landingspagina    # wordt opgelost tegen base_url
    headlines:                        # 3 tot 15, max 30 tekens
      - ""
    long_headlines:                   # 1 tot 5, max 90 tekens
      - ""
    descriptions:                     # 2 tot 5, max 90 tekens
      - ""
      - ""
    images:
      landscape: []                   # 1200x628, minimaal 1
      square: []                      # 1200x1200, minimaal 1
      portrait: []                    # 960x1200, optioneel maar aanbevolen
"""


def cmd_init(args: argparse.Namespace) -> int:
    template = clients_dir(args.root) / "_template.yaml"
    if not template.exists():
        print(f"template ontbreekt: {template}", file=sys.stderr)
        return 1

    target = clients_dir(args.root) / f"{args.client}.yaml"
    if target.exists():
        print(f"{target} bestaat al; laat ongemoeid")
    else:
        target.write_text(
            template.read_text(encoding="utf-8").replace("klant-slug", args.client),
            encoding="utf-8",
        )
        print(f"klantprofiel aangemaakt: {target}  <- vul dit eerst in")

    if args.campaign:
        if args.campaign.exists():
            print(f"{args.campaign} bestaat al; laat ongemoeid", file=sys.stderr)
            return 1
        args.campaign.parent.mkdir(parents=True, exist_ok=True)
        args.campaign.write_text(_campaign_skeleton(args.client), encoding="utf-8")
        print(f"campagne aangemaakt: {args.campaign}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = _load_resolved(args)
    root = None if args.skip_images else args.root
    issues = validate_campaign(data, asset_root=root)

    for issue in sorted(issues, key=lambda i: (i.level != ERROR, i.group)):
        print(issue, file=sys.stderr if issue.level == ERROR else sys.stdout)

    n_err = sum(1 for i in issues if i.level == ERROR)
    n_warn = sum(1 for i in issues if i.level == WARNING)
    label = data.get("client", "campagne")
    print(
        f"\n{label}: {len(data.get('asset_groups') or [])} asset group(s), "
        f"{n_err} error(s), {n_warn} warning(s)"
    )

    if has_errors(issues):
        return 1
    return 1 if (n_warn and args.strict) else 0


def cmd_images(args: argparse.Namespace) -> int:
    logo = args.logo
    ratio, position = 0.28, "bottom-left"

    if args.client:
        try:
            client = load_client(args.client, args.root)
        except ClientError as exc:
            print(f"fout: {exc}", file=sys.stderr)
            return 2
        brand = brand_settings(client)
        ratio, position = brand["logo_width_ratio"], brand["logo_position"]
        if logo is None:
            logo = args.root / client["logo"]

    if logo is not None and not logo.exists():
        print(f"logo niet gevonden: {logo}", file=sys.stderr)
        return 2

    sources = sorted(p for p in args.input_dir.glob(args.glob) if p.is_file())
    if not sources:
        print(f"geen bronbeelden in {args.input_dir} (glob {args.glob})", file=sys.stderr)
        return 1

    for src in sources:
        out_dir = args.output_dir / src.stem
        made = make_pmax_formats(
            src, out_dir, src.stem, logo=logo, logo_width_ratio=ratio, logo_position=position
        )
        print(f"{src.name} -> {sum(len(v) for v in made.values())} bestanden in {out_dir}")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    data = _load_resolved(args)
    issues = validate_campaign(data, asset_root=None)
    if has_errors(issues) and not args.force:
        print("Validatie faalt; los dat eerst op of gebruik --force.", file=sys.stderr)
        for issue in issues:
            if issue.level == ERROR:
                print(issue, file=sys.stderr)
        return 1

    text = render_handoff(data, drive_link=args.drive_link)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"geschreven naar {args.out}")
    else:
        print(text)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    print(f"geschreven naar {write_review_csv(_load_resolved(args), args.out)}")
    return 0


def cmd_bundle(args: argparse.Namespace) -> int:
    if not args.source_dir.is_dir():
        print(f"map niet gevonden: {args.source_dir}", file=sys.stderr)
        return 2
    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(args.output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(args.source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(args.source_dir))
                n += 1
    print(f"{args.output_zip}: {n} bestanden, {args.output_zip.stat().st_size // 1024} KB")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pmax", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(),
        help="projectmap met clients/ en assets (standaard: huidige map)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("clients", help="toon bekende klantprofielen")
    p.set_defaults(func=cmd_clients)

    p = sub.add_parser("init", help="zet een klantprofiel en/of campagne op")
    p.add_argument("--client", required=True, help="slug, bijv. 'nieuwe-klant'")
    p.add_argument("--campaign", type=Path, default=None, help="pad voor een lege campaign.yaml")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", help="controleer een campagne tegen de PMax-specs")
    p.add_argument("campaign", type=Path)
    p.add_argument("--client", default=None, help="overschrijft client_slug uit de campagne")
    p.add_argument("--skip-images", action="store_true")
    p.add_argument("--strict", action="store_true", help="laat ook warnings falen")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("images", help="genereer alle PMax-ratio's uit bronbeelden")
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--client", default=None, help="gebruikt logo en brand-instellingen van deze klant")
    p.add_argument("--logo", type=Path, default=None, help="overschrijft het logo uit het klantprofiel")
    p.add_argument("--glob", default="*.png")
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("handoff", help="genereer de handoff-mail")
    p.add_argument("campaign", type=Path)
    p.add_argument("--client", default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--drive-link", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("export", help="review-CSV met alle tekst-assets")
    p.add_argument("campaign", type=Path)
    p.add_argument("--client", default=None)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("bundle", help="zip een map met assets")
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--output-zip", type=Path, required=True)
    p.set_defaults(func=cmd_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
