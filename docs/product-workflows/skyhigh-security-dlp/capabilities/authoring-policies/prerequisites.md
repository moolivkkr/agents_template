# Authoring Policies -- Dependency Chain & Prerequisites
## Skyhigh Security DLP (SSE Platform)

> Capability: authoring-policies | Generated: 2026-05-21

---

## Dependency Graph

```mermaid
graph TD
    subgraph "Infrastructure Prerequisites"
        LICENSE["Skyhigh SSE License<br/>(Essential, Advanced, or Complete)"]
        TENANT["Skyhigh Cloud Tenant<br/>(provisioned)"]
        SWG["Secure Web Gateway<br/>(for Shadow/Web DLP)"]
        CASB["CASB Connectors<br/>(for Sanctioned DLP)"]
        EPO["Trellix ePO<br/>(for Endpoint DLP only)"]
    end

    subgraph "Level 1: Classifications"
        DICT["Dictionary Definitions"]
        REGEX["Advanced Pattern Definitions<br/>(regex + validators)"]
        KEYWORD["Keyword Definitions"]
        EDM_FP["EDM Fingerprints<br/>(structured data)"]
        IDM_FP["IDM Fingerprints<br/>(unstructured documents)"]
        ML["ML Auto Classifiers<br/>(pre-trained models)"]
        DOC_PROP["Document Properties"]
        FILE_NAME["File Name Sets"]
        CLASS["Classifications<br/>(compose definitions + proximity)"]
    end

    subgraph "Level 2: Sanctioned DLP Policies"
        POLICY["DLP Policy<br/>(name, description, status, scope)"]
        RG["Rule Groups<br/>(Boolean OR between groups)"]
        RULES["Rules<br/>(AND/OR within groups)"]
        EXCEPT["Exceptions<br/>(whitelist conditions)"]
        ACTIONS["Response Actions<br/>(per severity)"]
    end

    subgraph "Level 3: Channels"
        SANC["Sanctioned Channel<br/>(API + inline)"]
        SHADOW["Shadow/Web Channel<br/>(SWG inline)"]
        ENDPOINT["Endpoint Channel<br/>(Trellix DLP agent)"]
    end

    %% Infrastructure
    LICENSE --> TENANT
    LICENSE --> SWG
    LICENSE --> CASB

    %% Level 1
    TENANT --> DICT
    TENANT --> REGEX
    TENANT --> KEYWORD
    TENANT --> DOC_PROP
    TENANT --> FILE_NAME
    LICENSE --> EDM_FP
    LICENSE --> IDM_FP
    LICENSE --> ML
    DICT --> CLASS
    REGEX --> CLASS
    KEYWORD --> CLASS
    EDM_FP --> CLASS
    IDM_FP --> CLASS
    ML --> CLASS
    DOC_PROP --> CLASS
    FILE_NAME --> CLASS

    %% Level 2
    CLASS --> RULES
    RULES --> RG
    RG --> POLICY
    EXCEPT --> POLICY
    ACTIONS --> POLICY

    %% Level 3
    POLICY --> SANC
    POLICY --> SHADOW
    POLICY --> ENDPOINT
    CASB --> SANC
    SWG --> SHADOW
    EPO --> ENDPOINT

    classDef infra fill:#3498db,stroke:#2980b9,color:#fff
    classDef classify fill:#e67e22,stroke:#d35400,color:#fff
    classDef policy fill:#9b59b6,stroke:#8e44ad,color:#fff
    classDef channel fill:#2ecc71,stroke:#27ae60,color:#fff

    class LICENSE,TENANT,SWG,CASB,EPO infra
    class DICT,REGEX,KEYWORD,EDM_FP,IDM_FP,ML,DOC_PROP,FILE_NAME,CLASS classify
    class POLICY,RG,RULES,EXCEPT,ACTIONS policy
    class SANC,SHADOW,ENDPOINT channel
```

---

## Ordered Configuration Sequence

### Phase 0: Infrastructure (Before Any Policy Work)

| # | Prerequisite | What It Is | What Happens If Missing |
|---|-------------|-----------|------------------------|
| 0.1 | **Skyhigh SSE License** | Skyhigh Security Service Edge subscription (Essential, Advanced, or Complete tier) | DLP features may be limited or unavailable depending on tier. Advanced DLP (EDM, IDM, ML classifiers) requires Advanced or Complete tier |
| 0.2 | **Skyhigh Cloud Tenant** | Provisioned Skyhigh Security cloud tenant | No access to Skyhigh Dashboard; cannot create classifications or policies |
| 0.3 | **CASB Connectors** (for Sanctioned DLP) | API connectors to sanctioned cloud services (M365, Google Workspace, Box, Salesforce, etc.) | Sanctioned DLP scanning cannot inspect cloud service content |
| 0.4 | **Secure Web Gateway** (for Shadow/Web DLP) | Skyhigh SWG deployed and traffic routed through it | Shadow IT and web DLP cannot inspect browser/web traffic |
| 0.5 | **Trellix ePO** (for Endpoint DLP) | Trellix ePolicy Orchestrator with DLP Endpoint agent deployed | Endpoint DLP is not available; only cloud DLP (CASB/SWG) functions |

### Phase 1: Classifications (Foundation)

| # | Item | Depends On | What It Provides | What Happens If Missing |
|---|------|-----------|-----------------|------------------------|
| 1.1 | **Classification Definitions** (Dictionary, Advanced Pattern, Keyword, Doc Properties, File Name, File Size, True File Type) | Tenant (0.2) | Building blocks that identify sensitive content patterns | Cannot create meaningful classifications; rules have nothing to match |
| 1.2 | **EDM Fingerprints** (optional) | Advanced/Complete License + DLP Integrator tool | Exact matching against structured records (database exports) | Cannot detect specific database records; regex-only has higher FP |
| 1.3 | **IDM Fingerprints** (optional) | Advanced/Complete License + IDMTrain tool | Unstructured document fingerprinting for proprietary documents | Cannot detect copies/derivatives of specific sensitive documents |
| 1.4 | **ML Auto Classifiers** (optional) | Advanced/Complete License | Pre-trained ML models for text + image classification | Must rely on regex/dictionary only; no AI-assisted detection |
| 1.5 | **Classifications** | At least one definition type (1.1) | Named, reusable classification objects with match criteria and proximity | Rules cannot reference detection logic; policies have no content criteria |

**Minimum viable:** One classification (1.5) using a built-in definition (e.g., predefined Credit Card regex) is sufficient for a first policy.

### Phase 2: Sanctioned DLP Policies

| # | Item | Depends On | What It Provides | What Happens If Missing |
|---|------|-----------|-----------------|------------------------|
| 2.1 | **Rules** (at least one) | Classifications (1.5) | Match criteria with severity level | Policy has no detection logic |
| 2.2 | **Rule Groups** (at least one) | Rules (2.1) | Boolean containers; multiple rule groups combined with OR | Cannot compose complex detection logic |
| 2.3 | **Exceptions** (optional) | Rule types (same as rules) | Whitelist conditions to exclude specific matches | All matches trigger; no way to exclude known good |
| 2.4 | **Response Actions** | Policy (2.5) | What happens on match (alert, block, quarantine, encrypt) | No enforcement action; detections have no consequence |
| 2.5 | **DLP Policy** | Rule Groups (2.2) + Response Actions (2.4) | Complete policy object ready for channel assignment | No enforcement container; classifications and rules exist but are not active |

### Phase 3: Channel Assignment

| # | Item | Depends On | What It Provides | What Happens If Missing |
|---|------|-----------|-----------------|------------------------|
| 3.1 | **Enable policy on Sanctioned channel** | Policy (2.5) + CASB Connectors (0.3) | DLP inspection of sanctioned cloud service content | Cloud services are unmonitored |
| 3.2 | **Enable policy on Shadow/Web channel** | Policy (2.5) + SWG (0.4) | DLP inspection of web/shadow IT traffic | Web browsing and shadow IT data unmonitored |
| 3.3 | **Sync policy to Endpoint channel** | Policy (2.5) + Trellix ePO (0.5) | DLP inspection of desktop application activity | Endpoint data movements unmonitored |

---

## Fast-Path: Using Policy Templates

Skyhigh provides pre-built policy templates (GDPR, HIPAA, PCI, GLBA, SOX) that include pre-configured classifications and rules:

```
Infrastructure (Phase 0)
    |
    v
Select a Policy Template (Phase 2 -- includes Phase 1 pre-configured)
    |
    v
Customize rules and thresholds
    |
    v
Set Response Actions
    |
    v
Enable on channels (Phase 3)
```

This skips manual classification creation entirely.

---

## License Tier Impact on DLP Features

| Feature | Essential | Advanced | Complete |
|---------|-----------|----------|----------|
| Basic classifications (Dictionary, Regex, Keyword) | Yes | Yes | Yes |
| Sanctioned DLP policies | Yes | Yes | Yes |
| Shadow/Web DLP policies | Yes | Yes | Yes |
| EDM fingerprints | No | Yes | Yes |
| IDM fingerprints | No | Yes | Yes |
| ML Auto Classifiers | No | Yes | Yes |
| AI RegEx Generator | No | Yes | Yes |
| Endpoint DLP (Trellix) | No | No | Yes |
| Advanced incident management | No | Yes | Yes |

---

## Prerequisite Verification Checklist

```
[ ] Skyhigh Dashboard accessible: https://<tenant>.myshn.net
[ ] DLP module visible: Policy > DLP Policy appears in navigation
[ ] At least one CASB connector active: Settings > Service Management shows connected services
[ ] SWG deployed and traffic routing confirmed (for Shadow/Web DLP)
[ ] Built-in classifications visible: Policy > DLP Policy > Classifications shows predefined items
[ ] Your account has DLP Administrator role
[ ] (For EDM) DLP Integrator v6.4.0+ installed on secure server
[ ] (For IDM) IDMTrain tool available on Windows or Linux
[ ] (For Endpoint DLP) Trellix ePO accessible with DLP extension installed
```
