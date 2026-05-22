# Forcepoint DLP -- API Intelligence

> Research collected: 2026-05-21
> Sources: help.forcepoint.com REST API guides (v9.0, v10.x), release notes, SIEM integration docs

---

## 1. REST API Overview

### 1.1 API Guide Locations

| Version | Base URL Pattern | Documentation |
|---------|-----------------|---------------|
| v10.3 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/10.3.0/restapi/ |
| v10.2 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/10.2.0/restapi/ |
| v10.1 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/10.1.0/restapi/ |
| v10.0 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/10/restapi/ |
| v9.0 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/90/restapi/index.html |
| v8.9.1 | `https://<DLP_Manager_IP>:<port>/dlp/rest/v1/` | https://help.forcepoint.com/dlp/891/restapi/ |

### 1.2 Prerequisites

- Forcepoint DLP Management Server must have REST API service enabled
- An **Application administrator** account must be created in Forcepoint Security Manager
- Only Application administrator type can request refresh tokens through the REST API
- HTTPS required (self-signed certificates supported with appropriate client configuration)
- Default port: 443 (configurable)

---

## 2. Authentication

### 2.1 Authentication Flow

```
Client                              DLP Manager
  |                                      |
  |-- POST /dlp/rest/v1/auth/refresh-token -->|  (username + password in headers)
  |<-- 200 { refreshToken: "..." }  ------|
  |                                      |
  |-- POST /dlp/rest/v1/auth/access-token --->|  (refreshToken in header)
  |<-- 200 { accessToken: "..." }   ------|
  |                                      |
  |-- GET /dlp/rest/v1/incidents -------->|  (Authorization: Bearer <accessToken>)
  |<-- 200 { incidents: [...] }     ------|
```

### 2.2 Authentication Endpoints

#### Refresh Token API
```
POST https://<DLP_Manager_IP>:<port>/dlp/rest/v1/auth/refresh-token

Headers:
  X-FPDLP-Username: <application_admin_username>
  X-FPDLP-Password: <application_admin_password>

Response:
  {
    "refreshToken": "<JWT_refresh_token>"
  }
```

#### Access Token API
```
POST https://<DLP_Manager_IP>:<port>/dlp/rest/v1/auth/access-token

Headers:
  X-FPDLP-Refresh-Token: <refresh_token>

Response:
  {
    "accessToken": "<JWT_access_token>"
  }
```

- **Refresh token:** Long-lived, used to obtain access tokens
- **Access token:** Short-lived, used as Bearer token for all API calls
- **Token format:** JSON Web Token (JWT)

---

## 3. API Categories

### 3.1 Incident Management APIs

**Purpose:** Get, filter, update, and remediate DLP and Discovery incidents.

#### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dlp/rest/v1/incidents` | Get list of DLP incidents with optional filters |
| GET | `/dlp/rest/v1/incidents/{id}` | Get specific incident details |
| GET | `/dlp/rest/v1/discovery-incidents` | Get list of Discovery incidents |
| PUT | `/dlp/rest/v1/incidents/{id}` | Update incident (status, severity, assignment, etc.) |

#### Filtering Options

Incidents can be filtered by:
- **Policy** -- filter by policy name or ID
- **Department** -- filter by organizational department
- **Risk Level** -- filter by risk score/level
- **Date range** -- filter by incident creation date
- **Severity** -- filter by severity level
- **Status** -- filter by workflow status
- **Source** -- filter by data source

#### Updatable Incident Fields

- Status (New, In Progress, Resolved, Closed, etc.)
- Severity (Low, Medium, High, Critical)
- Assigned administrator
- Tags
- Comments/notes

### 3.2 Policy Management APIs

**Purpose:** Manage DLP and Discovery policies, rules, and resources remotely.

#### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dlp/rest/v1/policies` | Get list of enabled policies |
| GET | `/dlp/rest/v1/policies/{id}` | Get specific policy details |
| PUT | `/dlp/rest/v1/policies/{id}/enable` | Enable a policy |
| PUT | `/dlp/rest/v1/policies/{id}/disable` | Disable a policy |
| POST | `/dlp/rest/v1/policies/import` | Import policies (from dev/UAT to production) |
| POST | `/dlp/rest/v1/policies/export` | Export policies for migration |

#### Documented Capabilities

- Import/export policies between environments (dev -> UAT -> prod)
- Move risky users and groups between policies
- Enable/disable policies programmatically
- List all enabled policies with their configuration
- Retrieve policy details including rules, conditions, and action plans

**Source:** https://help.forcepoint.com/dlp/90/restapi/3CE93266-7D5D-474B-872F-796CFF5718BF.html

### 3.3 Deploy APIs

**Purpose:** Push policy and configuration changes to Policy Engine and Endpoint servers.

#### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/dlp/rest/v1/deploy` | Trigger deployment of policy changes |
| GET | `/dlp/rest/v1/deploy/status` | Check deployment status |

**Source:** https://help.forcepoint.com/dlp/10/restapi/7EE4EF10-8C92-4F78-BAD0-E78DE2FEF140.html

#### Deploy Workflow via API

1. Make policy changes via Policy Management APIs
2. Call POST `/dlp/rest/v1/deploy` to push changes
3. Poll GET `/dlp/rest/v1/deploy/status` to monitor rollout
4. Status transitions: Processing -> Success / Failed (per component)

### 3.4 App Data Security API (v10.1+)

**Purpose:** Cloud application data security operations.

**Source:** https://help.forcepoint.com/dlp/10.1.0/release-notes/718D7B4A-D9F6-4AB5-8634-67B511905D2C.html

---

## 4. Integration Patterns

### 4.1 SIEM Integration

#### Via REST API (Pull Model)

```
SIEM/SOAR  ----GET /dlp/rest/v1/incidents----> DLP Manager
           <---JSON incident list--------------
           ----PUT /dlp/rest/v1/incidents/{id}-> (update status after triage)
```

- Poll-based: SIEM pulls incidents on a schedule
- Supports filtering to retrieve only new/unprocessed incidents
- Can update incident status after SOAR playbook completes

#### Via Syslog (Push Model)

```
DLP Manager ----syslog (UDP/TCP)----> SIEM Server
```

**Configuration:** Settings > General > Remediation (in Data Security module)

**Supported Formats:**
| Format | Target SIEM |
|--------|-------------|
| CEF (Common Event Format) | ArcSight, generic |
| Key-Value Pairs | Splunk, generic |
| LEEF (Log Event Extended Format) | IBM QRadar |
| Custom | Any (user-defined format string) |

**CEF Message Format:**
```
CEF:0|Forcepoint|Forcepoint DLP|<version>|{id}|DLP Syslog|{severity}|
  act={action}
  duser={destinations}
  fname={attachments}
  msg={details}
  suser={source}
  cat={policyCategories}
```

**Trigger:** Add "Send syslog message" action to the action plan for policies that should forward to SIEM.

#### Supported SIEM Platforms (Documented Integrations)

| Platform | Integration Method | Documentation |
|----------|-------------------|---------------|
| Splunk | Syslog + Splunk Add-on | https://docs.splunk.com/Documentation/AddOns/released/WebsenseDLP/Setup |
| ArcSight | CEF syslog | Via CEF format |
| IBM QRadar | LEEF syslog | Via LEEF format |
| Google SecOps (Chronicle) | Default parser | https://cloud.google.com/chronicle/docs/ingestion/default-parsers/forcepoint-dlp |
| DNIF HYPERCLOUD | Native integration | https://dnif.it/kb/device-integration/forcepoint-dlp/ |
| Netenrich | Syslog | https://support.netenrich.com/hc/en-us/articles/11698943292317 |

### 4.2 SOAR Integration

- Use REST API to pull incidents into SOAR platform
- SOAR playbook can:
  - Retrieve incident details (GET)
  - Update severity based on enrichment (PUT)
  - Assign to analyst (PUT)
  - Change status after resolution (PUT)
  - Trigger redeployment after policy changes (POST deploy)

### 4.3 Policy Lifecycle Automation

```
Dev Environment                    UAT Environment                   Production
     |                                  |                                |
     |-- POST /policies/export -------->|                                |
     |                                  |-- POST /policies/import ------>|
     |                                  |                                |
     |                                  |-- POST /deploy --------------->|
     |                                  |                                |
     |                                  |<-- GET /deploy/status ---------|
```

Use cases:
- **CI/CD for DLP policies:** Export from dev, import to UAT, test, import to prod
- **Emergency policy push:** Disable compromised policy across all environments
- **User risk migration:** Move users between policy groups based on HR events
- **Compliance reporting:** Pull incident statistics for audit reports

---

## 5. Webhook and Event-Driven Integration

### 5.1 Native Webhook Support

Forcepoint DLP does **not** natively expose a webhook callback mechanism (no outbound HTTP POST to a customer-specified URL on incident creation). Instead, event-driven integration relies on:

1. **Syslog push** -- Real-time event forwarding to SIEM, which can then trigger webhooks
2. **REST API polling** -- Periodic pull of new incidents
3. **Email notifications** -- Action plans can send emails, which can trigger downstream automation via email-to-webhook bridges
4. **Endpoint remediation scripts** -- Custom scripts executed on endpoints when incidents occur

### 5.2 Workaround Patterns for Webhook-Like Behavior

| Pattern | How It Works |
|---------|-------------|
| Syslog -> SIEM -> Webhook | DLP sends syslog to SIEM; SIEM triggers webhook on correlation rule |
| Email -> Webhook Bridge | DLP sends email notification; email integration (e.g., Zapier, Power Automate) converts to webhook |
| REST API Polling -> Event Bus | Scheduled job polls REST API for new incidents; publishes to Kafka/SNS/EventBridge |
| Endpoint Script -> API Call | Remediation script on endpoint makes HTTP call to internal service |

---

## 6. API Limitations and Considerations

| Limitation | Detail |
|------------|--------|
| No native webhook | Must use syslog or polling for event-driven workflows |
| Application admin only | Regular admin accounts cannot use the REST API |
| JWT expiry | Access tokens are short-lived; must refresh periodically |
| Rate limiting | Not publicly documented; assume conservative polling intervals |
| Policy creation | API supports import/export and enable/disable; full policy creation from scratch via API may be limited |
| Classifier management | Direct classifier creation via API not documented; use Security Manager UI |
| Deployment scope | Deploy API pushes all pending changes, not individual policy changes |
| Version parity | API capabilities vary by version; v10.x has more endpoints than v9.0 |

---

## 7. API Code Examples (Conceptual)

### 7.1 Authenticate and Get Incidents (Python)

```python
import requests

DLP_HOST = "https://dlp-manager.example.com"

# Step 1: Get refresh token
resp = requests.post(
    f"{DLP_HOST}/dlp/rest/v1/auth/refresh-token",
    headers={
        "X-FPDLP-Username": "api_admin",
        "X-FPDLP-Password": "secure_password"
    },
    verify=False  # self-signed cert
)
refresh_token = resp.json()["refreshToken"]

# Step 2: Get access token
resp = requests.post(
    f"{DLP_HOST}/dlp/rest/v1/auth/access-token",
    headers={
        "X-FPDLP-Refresh-Token": refresh_token
    },
    verify=False
)
access_token = resp.json()["accessToken"]

# Step 3: Get incidents
resp = requests.get(
    f"{DLP_HOST}/dlp/rest/v1/incidents",
    headers={
        "Authorization": f"Bearer {access_token}"
    },
    params={
        "severity": "high",
        "status": "new"
    },
    verify=False
)
incidents = resp.json()
```

### 7.2 Update Incident Status (Python)

```python
incident_id = "INC-2026-001234"
resp = requests.put(
    f"{DLP_HOST}/dlp/rest/v1/incidents/{incident_id}",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    },
    json={
        "status": "In Progress",
        "assignedTo": "analyst@example.com",
        "comment": "Investigating potential PII exfiltration"
    },
    verify=False
)
```

### 7.3 Deploy Policy Changes (Python)

```python
# Trigger deployment
resp = requests.post(
    f"{DLP_HOST}/dlp/rest/v1/deploy",
    headers={
        "Authorization": f"Bearer {access_token}"
    },
    verify=False
)

# Check deployment status
import time
while True:
    resp = requests.get(
        f"{DLP_HOST}/dlp/rest/v1/deploy/status",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        verify=False
    )
    status = resp.json()
    if status.get("overallStatus") in ("Success", "Failed"):
        break
    time.sleep(5)
```

---

## 8. SIEM Format Reference

### 8.1 CEF Fields for Forcepoint DLP

| CEF Field | DLP Mapping | Description |
|-----------|-------------|-------------|
| `act` | Action taken | permit, block, quarantine, encrypt |
| `duser` | Destinations | Email recipients, cloud upload targets |
| `fname` | Attachments | Filename(s) that triggered the policy |
| `msg` | Details | Policy violation description |
| `suser` | Source | User who triggered the incident |
| `cat` | Policy categories | HIPAA, PCI-DSS, Custom, etc. |
| `severity` | Severity level | 1-10 scale |
| `id` | Incident ID | Unique identifier |

### 8.2 Available SIEM Formats

| Format | Target | Configuration |
|--------|--------|---------------|
| syslog/CEF | ArcSight and generic | Settings > General > Remediation |
| syslog/Key-Value Pairs | Splunk and generic | Settings > General > Remediation |
| syslog/LEEF | IBM QRadar | Settings > General > Remediation |
| Custom format string | Any SIEM | User-defined format template |

---

## 9. Integration Architecture Patterns

### 9.1 Recommended Architecture: Full Integration Stack

```
                                    +------------------+
                                    |   SOAR Platform   |
                                    |  (Playbook runs)  |
                                    +--------+---------+
                                             |
                              REST API (pull incidents,
                              update status)
                                             |
+------------------+    syslog    +----------+----------+
| Forcepoint DLP   |------------>|    SIEM Platform     |
| Management Server|             | (correlation rules,  |
+--------+---------+    REST     |  dashboards, alerts) |
         |             API       +----------+-----------+
         |<--------------------------+      |
         |                                  |
         |    Deploy API                    | webhook/alert
         |                                  |
+--------+---------+             +----------+-----------+
| Policy Engine    |             |   Ticketing System    |
| Endpoint Agents  |             |  (ServiceNow, Jira)  |
| Network Sensors  |             +----------------------+
+------------------+
```

### 9.2 Minimal Integration: Syslog Only

```
Forcepoint DLP ---> syslog (CEF) ---> Splunk/QRadar/Chronicle
```

### 9.3 API-First Integration: SOAR-Driven

```
SOAR ---> REST API ---> Forcepoint DLP (pull incidents, update, deploy)
```
