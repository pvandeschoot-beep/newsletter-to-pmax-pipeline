# PMax nieuwsbrief-pipeline — flowchart

Van de **laatste nieuwsbrief van een klant** naar reviewbaar Performance Max-materiaal.

**Kernregel:** bronbeelden komen standaard uit de email. Te lage resolutie → AI-upscale van datzelfde mailbeeld (compositie behouden). Volledig nieuwe AI-beelden alleen als er geen bruikbare mailbeelden zijn, en dan pas na expliciet akkoord.

```mermaid
flowchart TD
  %% ── Start ──────────────────────────────────────────
  Start([Start run]) --> Vraag["1. Vraag: voor welke klant?"]

  %% ── Agent: oordeel ─────────────────────────────────
  subgraph Agent["Agent — oordeel"]
    direction TB
    Vraag --> Profiel{"2. Klantprofiel aanwezig?<br/>clients/{slug}.yaml"}
    Profiel -->|Nee| Init["Init: lege yaml aanmaken<br/>en samen invullen"]
    Init --> Profiel
    Profiel -->|Ja| Gmail["3. Laatste nieuwsbrief<br/>ophalen via Gmail-label"]
    Gmail --> Themas["4. Thema’s kiezen +<br/>landingspagina’s checken"]
    Themas --> Copy["5. Copy schrijven →<br/>campagnes/{slug}/{datum}.yaml"]
    Copy --> Extract["6a. Beelden uit email<br/>extracten → assets/…/base<br/>(bijlagen / inline / HTML CDN)"]
    Extract --> BeeldenOK{"Bruikbare<br/>contentbeelden?"}
    BeeldenOK -->|Nee| VraagAI["Vraag akkoord voor<br/>volledig nieuwe AI-beelden"]
    VraagAI -->|Akkoord| AI["AI-bronbeelden maken<br/>(nieuwe scene)"]
    VraagAI -->|Geen akkoord| StopBeeld([Stop / andere bron])
    AI --> Images
    BeeldenOK -->|Ja| ResOK{"Resolutie OK?<br/>kortste zijde ≥ ~600px<br/>of PMax-min na crop"}
    ResOK -->|Ja| Images
    ResOK -->|Nee| Upscale["6a′. AI-upscale mailbeeld<br/>(compositie/onderwerp behouden;<br/>geen nieuwe scene)"]
    Upscale --> Images
  end

  %% ── Scripts: harde checks ──────────────────────────
  subgraph Scripts["Scripts — harde checks pmax"]
    direction TB
    Images["6b. pmax images<br/>ratio’s + logo-overlay"]
    Images --> Validate{"7. pmax validate<br/>poort naar oplevering"}
    Validate -->|Errors| FixYaml["Campagne-yaml aanpassen"]
    FixYaml -.->|opnieuw| Validate
    Validate -->|OK| Opleveren["8. export + bundle +<br/>handoff-draft"]
  end

  Opleveren --> Mens["Mens reviewt en<br/>verstuurt de mail"]
  Mens --> Klaar([Klaar])

  %% Kleuren: agent vs scripts
  classDef agent fill:#e8f1fa,stroke:#1a3c5e,stroke-width:1.5px,color:#122
  classDef script fill:#e8f6ee,stroke:#27ae60,stroke-width:1.5px,color:#122
  classDef gate fill:#fff3cd,stroke:#b8860b,stroke-width:2px,color:#122
  classDef startend fill:#f0f0f0,stroke:#666,stroke-width:1px,color:#122

  class Vraag,Profiel,Init,Gmail,Themas,Copy,Extract,BeeldenOK,ResOK,Upscale,VraagAI,AI agent
  class Images,FixYaml,Opleveren script
  class Validate gate
  class Start,StopBeeld,Mens,Klaar startend
```

## Wat doet wie?

| Stap | Wie | Wat |
|------|-----|-----|
| 1–2 | Agent | Klant vragen; profiel laden of `pmax init` |
| 3–5 | Agent | Mail lezen, thema’s + URL’s checken, copy in yaml |
| 6a | Agent | Beelden uit de mail (bijlagen / inline / HTML CDN) naar `assets/{slug}/base` |
| 6a′ | Agent | Te klein? AI-upscale van het **mailbeeld** (geen nieuwe scene) |
| 6b | Scripts | `pmax images` — crop/resize + logo |
| 7 | Scripts | `pmax validate` — tekenlimieten, counts, formaten |
| 8 | Scripts + mens | Bundle/export/draft; **mens** stuurt |

Agent en scripts praten via één bestand per run: `campagnes/{slug}/{datum}.yaml`.

## Hoe openen?

1. **In Cursor / VS Code:** open dit bestand en gebruik Mermaid-preview (bijv. extensie “Markdown Preview Mermaid Support”, of de ingebouwde preview als Mermaid aanstaat).
2. **Op GitHub:** push/open de file in de browser — GitHub rendert Mermaid in markdown automatisch.
3. **Online:** plak het blok tussen \`\`\`mermaid … \`\`\` op [mermaid.live](https://mermaid.live).
