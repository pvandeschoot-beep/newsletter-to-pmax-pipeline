# Newsletter → PMax Creative Pipeline

Van de **laatste nieuwsbrief van een klant** naar reviewbaar Performance Max-
materiaal: copy per thema, beelden in alle PMax-formaten, logo-overlay en een
handoff naar het team. **Bronbeelden komen standaard uit die nieuwsbrief**
(bijlagen / inline / HTML CDN). Te lage resolutie → AI-upscale van het
mailbeeld (compositie behouden). Volledig nieuwe AI-beelden alleen als er geen
bruikbare mailbeelden zijn, en dan pas na akkoord.

Er zit geen vaste klant of voorbeeldcampagne in deze repo. Elke run begint met:

> Voor welke klant wil je PMax-assets op basis van de laatste nieuwsbrief?

Zie [`AGENT.md`](AGENT.md) voor de agent-stappen (Gmail → beelden/upscale → yaml →
validate → handoff) en [`docs/pipeline-flowchart.md`](docs/pipeline-flowchart.md)
voor het overzicht.

## Wat de agent doet en wat de scripts doen

| | Agent (Claude + MCP) | Scripts (`pmax`) |
|---|---|---|
| Klant vragen / profiel kiezen | ✅ | |
| Nieuwsbrief ophalen en lezen | ✅ | |
| Thema's kiezen, copy schrijven | ✅ | |
| Beelden uit de mail extraheren | ✅ | |
| AI-upscale bij te lage resolutie | ✅ | |
| Landingspagina's controleren | ✅ | |
| Tekenlimieten en assetcounts | | ✅ |
| Aspect ratio's, bestandsgrootte | | ✅ |
| Ratio's renderen, logo-overlay | | ✅ |
| Bundelen, handoff-mail, review-CSV | | ✅ |

Alles wat verifieerbaar is zit in code. Alles wat oordeel vraagt doet de agent.
Ze praten via één bestand per run: `campagnes/{slug}/{datum}.yaml`.

## Klanten

Een klantprofiel in `clients/{slug}.yaml` beschrijft wat voor die klant altijd
geldt: merknaam, domein, logo, Gmail-label, tone, verboden claims.

```bash
python -m pmax clients                      # wie kennen we
python -m pmax init --client nieuwe-klant \
  --campaign campagnes/nieuwe-klant/concept.yaml
```

Vul daarna `clients/nieuwe-klant.yaml` in (template staat in
`clients/_template.yaml`). Campagne-yaml's blijven leeg tot een nieuwsbrief-run
ze vult.

```yaml
client_slug: nieuwe-klant
asset_groups:
  - name: Thema
    path: /pad/naar-pagina        # -> {base_url}/pad/naar-pagina
```

`business_name`, `logo`, `final_url` en standaard-CTA komen uit het profiel.
Zet je ze toch in de campagne, dan winnen die.

## Installatie

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Gebruik (na een gevulde campagne-yaml)

```bash
# Beelden: nieuwsbrief-bronbeelden (evt. na AI-upscale) -> alle PMax-ratio's
python -m pmax images --client <slug> \
  --input-dir assets/<slug>/base \
  --output-dir runs/<slug>/2026-09-15

# Valideren — poort naar oplevering
python -m pmax validate campagnes/<slug>/2026-09-15.yaml

# Opleveren
python -m pmax export  campagnes/<slug>/2026-09-15.yaml --out review.csv
python -m pmax bundle  --source-dir runs/<slug>/2026-09-15 --output-zip out.zip
python -m pmax handoff campagnes/<slug>/2026-09-15.yaml --drive-link <link>
```

`validate` geeft exitcode 1 bij errors (bruikbaar in CI / pre-commit).

## Wat de validator controleert

Getallen komen uit de [Google Ads API asset requirements][spec] en staan in
`pmax/specs.py`.

| | Limiet | Min | Max |
|---|---|---|---|
| Headlines | 30 tekens | 3 | 15 |
| Long headlines | 90 tekens | 1 | 5 |
| Descriptions | 90 tekens | 2 | 5 |
| Business name | 25 tekens | 1 | 1 |
| Landscape 1.91:1 (1200×628) | 5 MB | 1 | 20 |
| Square 1:1 (1200×1200) | 5 MB | 1 | 20 |
| Portrait 4:5 (960×1200) | 5 MB | 0 | 20 |
| Logo 1:1 (≥128×128) | 5 MB | 1 | 5 |

Daarnaast: absolute `final_url`, leesbare PNG/JPEG/GIF, duplicaten, YAML die
geen string meer is, en `forbidden_terms` uit het klantprofiel.

[spec]: https://developers.google.com/google-ads/api/performance-max/asset-requirements

## Structuur

```
clients/
├── _template.yaml      # startpunt voor een nieuwe klant
└── {slug}.yaml         # merk, domein, logo, gmail-label, tone, verboden claims
campagnes/
└── {slug}/{datum}.yaml # per run, gevuld vanuit de nieuwsbrief
assets/{slug}/          # logo + bronbeelden (uit de nieuwsbrief)
runs/{slug}/{datum}/    # gegenereerde PMax-ratio's
pmax/
├── specs.py            # Google's getallen
├── client.py           # klantprofiel laden en mengen
├── validate.py
├── images.py
├── render.py
└── cli.py
tests/
AGENT.md                # agent-instructies (start met klantvraag)
```

## Tests

```bash
pytest
```
