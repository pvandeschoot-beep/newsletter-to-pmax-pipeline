# AGENT.md — instructies voor de AI-agent

Dit bestand is voor de agent die de pipeline draait. De mens leest `README.md`.

## Startpunt (altijd zo beginnen)

Er staan **geen** vooringevulde campagnes of klantcopy in deze repo. Elke run
begint met een vraag aan de gebruiker:

> Voor welke klant wil je PMax-assets op basis van de laatste nieuwsbrief?

Wacht op het antwoord (slug of naam). Doe **niets** vóór die klant bekend is:
geen mail zoeken, geen copy verzinnen, geen AI-beelden genereren.

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
  copy schrijven, beelden uit de mail halen (en zo nodig AI-upscalen),
  landingspagina's controleren.
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

Haal uit de mail: thema's, USP's, tone of voice, genoemde prijzen. Bewaar het
`messageId` — bij stap 5 download je de beelden uit dezelfde mail.

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

### 5. Beelden — uit de nieuwsbrief (standaard)

**Bronbeelden komen uit de nieuwsbrief-mail** (bijlagen / inline / HTML CDN)
die je in stap 1 al ophaalde. Volgorde:

1. Mailbeelden extracten.
2. Resolutie checken → zo nodig **AI-upscale van het mailbeeld** (zelfde
   compositie/onderwerp; geen nieuwe scene).
3. `pmax images` (ratio’s + logo).
4. Pas daarna validate → export/bundle/handoff.

Volledig nieuwe AI-beelden alleen als er géén bruikbare mailbeelden zijn, en
dan pas na akkoord van de gebruiker.

#### 5a. Beelden uit de mail halen (Gmail MCP)

Je hebt al `gmail_get` (`format: full`) gedaan. In het antwoord zoek je
afbeeldingen op twee plekken:

**1. Bijlagen en inline parts (voorkeur)**

In `payload` (en geneste `parts`) staan MIME-onderdelen. Bruikbaar als:

- `mimeType` begint met `image/` (png, jpeg, gif, webp), **of**
- er is een `filename` met beeld-extensie, **of**
- er is een `body.attachmentId` bij een image-part

Per bruikbaar deel:

```
gmail_downloadAttachment
  messageId:     <id uit gmail_search / gmail_get>
  attachmentId:  <body.attachmentId van die part>
  localPath:     <absoluut pad, bijv. …/assets/{slug}/base/raw-01.jpg>
```

**Inline CID:** parts met header `Content-ID` (bijv. `<img001@…>`) horen bij
`src="cid:…"` in de HTML. Download die op dezelfde manier via
`attachmentId`. Koppel CID ↔ bestand via die header (strip `<>` bij vergelijken).

Kleine body zonder `attachmentId` maar mét `body.data` (base64url) komt soms
voor bij hele kleine parts — die kun je lokaal decoderen; meestal is er wel een
`attachmentId`.

**2. HTML `<img>` met http(s)-URL (CDN)**

Als de HTML externe image-URL's heeft (geen cid): download alleen echte
contentbeelden. Sla over:

- trackingpixels / beacons (1×1, of domeinen als open/click-trackers)
- iconen, social buttons, spacer-gifs

Logo's van de klant in de mail: niet als themabeeld gebruiken — die komen uit
`clients/{slug}.yaml` → `logo`.

Lage resolutie (typisch bij CDN-thumbnails) is **geen** reden om het beeld te
verwerpen — zie 5b (upscale).

#### 5b. Resolutie checken → AI-upscale bij te klein

Na download: check breedte × hoogte. Te klein als bv.:

- kortste zijde < ~600 px (`NEWSLETTER_SOURCE_MIN_SHORT_SIDE_PX` in
  `pmax/specs.py`), of
- het beeld na center-crop onder het PMax-minimum voor landscape/square/portrait
  zou uitkomen

Dan: **AI-upscale van dat mailbeeld** — compositie en onderwerp behouden,
scherpte/resolutie verhogen. Geen nieuwe scene verzinnen, geen andere
bestemming of props toevoegen.

Bewaar het ge-upscalede bestand als bron voor `pmax images` (vervang of zet
naast het raw-bestand; de bestandsnaam die je aan thema’s koppelt is het
upscaled bronbeeld). Noteer desgewenst in de campagne-yaml
`source.image_source: newsletter_upscaled`.

Is de resolutie al voldoende → sla upscale over.

#### 5c. Mappen op asset-group-thema's

Eén sterk bronbeeld per thema (asset group). Kies op inhoud: onderwerp in het
midden, herkenbaar bij het thema, geen collage van vijf bestemmingen als je
één stad adverteert.

Naamgeving onder `assets/{slug}/base/` (of run-specifiek
`runs/{slug}/{datum}/base/`):

```
bogota.jpg
santiago.jpg
…
```

Bestandsnaam = stem die `pmax images` later als mapnaam gebruikt. Zet in de
campagne-yaml daarna de gegenereerde paden onder `images.landscape` /
`square` / `portrait`.

Meerdere kandidaten per thema: kies de scherpste / grootste; bewaar de rest
desnoods als `…-alt` maar voer die niet mee tenzij de gebruiker dat wil.

#### 5d. Ratio's + logo — altijd via scripts

```
python -m pmax images --client {slug} \
  --input-dir assets/{slug}/base \
  --output-dir runs/{slug}/{datum}
```

(Of `--input-dir runs/{slug}/{datum}/base` als je run-specifiek werkte.)

Standaard pakt `pmax images` png/jpg/jpeg/webp/gif. Lever per ratio een versie
met én zonder logo. Zet die paden in de campagne-yaml.

#### 5e. Geen bruikbare mailbeelden? Pas dan nieuwe AI (na akkoord)

Alleen als de mail **geen** bruikbare contentbeelden heeft (alleen trackers,
logo's, of niets bruikbaars om te upscalen):

1. Zeg dat kort tegen de gebruiker.
2. Vraag of je **volledig nieuwe** AI-beelden mag genereren als fallback.
3. Doe dat **niet** uit jezelf.

Bij akkoord: per thema één hoogresoluut bronbeeld met het onderwerp in het
midden, daarna dezelfde `pmax images`-stap.

**Let op:** upscale (5b) ≠ nieuwe AI-beelden (5e). Upscale houdt het
mailbeeld; 5e verzint een nieuwe scene.

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
- Bronbeelden uit de nieuwsbrief; te klein → AI-upscale (zelfde compositie);
  volledig nieuwe AI-beelden alleen na expliciet akkoord.
- Verstuur nooit zelf een mail en publiceer nooit zelf een campagne.
- `pmax validate` moet groen zijn voor je iets deelt.
