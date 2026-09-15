# AGENT.md — instructies voor de AI-agent

Dit bestand is voor de agent die de pipeline draait. De mens leest `README.md`.

## Startpunt (altijd zo beginnen)

Er staan **geen** vooringevulde campagnes of klantcopy in deze repo. Elke run
begint met een vraag aan de gebruiker:

> Voor welke klant wil je PMax-assets op basis van de laatste nieuwsbrief?

Wacht op het antwoord (slug of naam). Doe **niets** vóór die klant bekend is:
geen mail zoeken, geen copy verzinnen, geen beelden genereren.

Daarna:

1. Zoek het klantprofiel (`python -m pmax clients`).
2. Ontbreekt het → `python -m pmax init --client <slug>` en vraag de gebruiker
   de lege `clients/<slug>.yaml` in te vullen (base_url, logo, gmail_label,
   forbidden_terms). Stop tot dat klaar is.
3. Haal de **laatste** nieuwsbrief op via Gmail (label uit het profiel).
4. Bouw `campagnes/<slug>/<datum>.yaml` vanuit die mail — leeg starten, niets
   hergebruiken van eerdere klanten.
5. Valideer, bundle, draft-handoff. Verstuur nooit zelf.

## Het contract

De agent en de scripts praten via precies één bestand per run:
**`campagnes/{slug}/{datum}.yaml`**.

- De **agent** doet alles wat oordeel vraagt: nieuwsbrief lezen, thema's kiezen,
  copy schrijven, beelden prompten, landingspagina's controleren.
- De **scripts** doen alles wat verifieerbaar is: tekenlimieten, assetcounts,
  aspect ratio's, bestandsgrootte, formaten renderen, bundelen, mail opstellen.

Verzin nooit zelf een validatieregel en sla `pmax validate` nooit over. Als de
validator faalt, pas de campagne-yaml aan en draai opnieuw. De validator is de
enige poort naar oplevering.

## Stappen

### 0. Klant bepalen (verplicht, interactief)

Vraag: *"Voor welke klant PMax-assets op basis van de laatste nieuwsbrief?"*

```
python -m pmax clients
```

Staat de klant er niet bij:

```
python -m pmax init --client <slug> \
  --campaign campagnes/<slug>/concept.yaml
```

Vul samen met de gebruiker `clients/<slug>.yaml` in. Zonder profiel geen run.

Alles wat klantspecifiek is (Gmail-label, base_url, logo, team-mailadres,
verboden claims) hoort in `clients/{slug}.yaml`, niet in dit bestand en niet
hardcoded in copy van een andere klant.

### 1. Bron ophalen — Gmail MCP (`user-google-workspace`)

Gebruik het label uit `clients/{slug}.yaml` → `sources.gmail_label`. Geen
subject-search: die breekt bij emoji's en spelfouten.

Pak de **nieuwste** mail (niet een willekeurige unread):

```
gmail_search   query: "label:{sources.gmail_label} newer_than:30d"
               maxResults: 5
gmail_get      messageId uit het nieuwste resultaat, format: full
```

Web-URL message-ID's (`FMfcgzQg...`) werken niet; gebruik het `id` uit
`gmail_search`.

Toon de gebruiker kort: onderwerp, datum, en de thema's die je eruit haalt.
Vraag bevestiging als er twijfel is welke mail de juiste is.

Haal uit de mail: thema's, USP's, tone of voice, genoemde prijzen.

### 2. Landingspagina's controleren

Per thema één URL onder `base_url` van de klant. Controleer:

- De pagina bestaat en gaat echt over dit thema.
- Staan er actuele prijzen? **Alleen dan** mag een prijs in de copy.

Zet in de yaml `path: /...` (wordt opgelost tegen `base_url`) of een volledige
`final_url`. PMax accepteert geen relatief pad zonder client-resolve.

### 3. Merkassets

Logo komt uit `clients/{slug}.yaml` → `logo` (lokaal pad onder `assets/`).
Download niet elke run opnieuw van het CMS. Mist het bestand: vraag de
gebruiker om een 1:1 logo (min 128×128, aanbevolen 1200×1200) op dat pad.

Liggend logo (4:1) is optioneel en een apart assettype — niet hetzelfde veld.

### 4. Copy schrijven

Schrijf een **nieuwe** `campagnes/{slug}/{YYYY-MM-DD}.yaml` op basis van déze
nieuwsbrief. Geen teksten van andere klanten of oude campagnes kopiëren.

Harde grenzen per asset group: 3–15 headlines (30 tekens), 1–5 long headlines
(90), 2–5 descriptions (90), één business name (25 tekens, uit het profiel).
Mik op de bovenkant van die ranges.

Respecteer `copy.forbidden_terms` en de tone uit het klantprofiel.

YAML-val: zet een regel met `: ` erin **tussen quotes**.

### 5. Beelden

Genereer per thema één bronbeeld op hoge resolutie met het onderwerp in het
midden — de pipeline snijdt center-crop naar drie ratio's.

```
python -m pmax images --client {slug} \
  --input-dir assets/{slug}/base --output-dir runs/{slug}/{datum}
```

Lever per ratio een versie met én zonder logo. Zet de paden in de campagne-yaml.

### 6. Valideren — de poort

```
python -m pmax validate campagnes/{slug}/{datum}.yaml
```

Errors blokkeren oplevering. Warnings toelichten in de handoff.

### 7. Opleveren

Gmail MCP kan geen bijlagen versturen. Zip lokaal, zet in Drive, deel de link.
Maak een **draft**, verstuur niet zelf.

```
python -m pmax bundle --source-dir runs/{slug}/{datum} --output-zip out.zip
python -m pmax export campagnes/{slug}/{datum}.yaml --out review.csv
python -m pmax handoff campagnes/{slug}/{datum}.yaml --drive-link <link>
```

Daarna: `gmail_createDraft` met de handoff-body (HTML volgens workspace-
emailregels als die van toepassing zijn).

### 8. Review (optioneel)

Eén Asana-taak per asset group met Drive-link en copy, of een Chat-bericht
naar het team — alleen als de gebruiker dat vraagt.

## Vaste regels

- Start altijd met de klantvraag; geen aannames over welke klant.
- Label output altijd als voorbeeld ter review, nooit als productie.
- Logo alleen van de officiële merkbron van déze klant.
- Prijsclaim alleen als die prijs op de landingspagina staat.
- Respecteer `forbidden_terms`; de validator dwingt dit af.
- Copy, beeld en thema 1-op-1; geen hergebruik tussen asset groups of klanten.
- Verstuur nooit zelf een mail en publiceer nooit zelf een campagne.
- `pmax validate` moet groen zijn voor je iets deelt.
