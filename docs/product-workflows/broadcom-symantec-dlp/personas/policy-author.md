# Persona: Policy Author / DLP Administrator

> **Product:** Broadcom Symantec Data Loss Prevention
> **Persona:** Policy Author / DLP Administrator
> **RBAC Requirement:** Policy Authoring + Response Rule Management + Server Administration privileges
> **Typical Title:** DLP Administrator, Security Engineer (DLP), Data Protection Analyst

---

## Role Overview

The Policy Author is the primary configuration persona in Symantec DLP. This role is responsible for the full lifecycle of data protection policies: identifying what sensitive data to protect, selecting detection technologies, composing detection rules, defining exceptions, configuring response actions, assembling complete policies, and deploying them to detection servers via policy groups.

This is the most time-intensive persona. A complete policy authoring workflow (from data preparation through production deployment) can take 1-4 weeks depending on the detection technologies involved (EDM/IDM/VML require data preparation; DCM-only policies can be created in hours).

**Key responsibilities:**
- Design detection strategies for regulatory compliance (PCI, HIPAA, GDPR, SOX) and intellectual property protection
- Create and maintain EDM profiles (structured data fingerprints), IDM profiles (document fingerprints), and VML profiles (ML classifiers)
- Author detection rules combining multiple technologies with appropriate thresholds
- Define exceptions to reduce false positives without creating bypass vectors
- Configure response rules (automated and manual) appropriate to each data channel
- Manage policy templates and policy groups for multi-server deployment
- Tune policies based on incident feedback (false positive rate, detection gaps)
- Manage the Test > Notify > Block staged rollout lifecycle

---

## Daily Flow Diagram

```
                                    POLICY AUTHOR DAILY FLOW
  ============================================================================

  +---------------------+     +----------------------+     +-------------------+
  | MORNING TRIAGE      |     | ACTIVE AUTHORING     |     | AFTERNOON OPS     |
  | (30-60 min)         |     | (2-4 hrs)            |     | (1-2 hrs)         |
  +---------------------+     +----------------------+     +-------------------+
  |                     |     |                      |     |                   |
  | Review overnight    |     | Create/edit          |     | Monitor deployed  |
  | incidents for FP    |---->| detection rules      |---->| policies          |
  | patterns            |     | and policies         |     |                   |
  |                     |     |                      |     | Check indexing    |
  | Check EDM/IDM       |     | Update EDM/IDM       |     | status for EDM/   |
  | index status        |     | profiles if data     |     | IDM profiles      |
  |                     |     | source changed       |     |                   |
  | Review exception    |     | Author response      |     | Review policy     |
  | requests from       |     | rules for new        |     | group assignments |
  | business units      |     | policies             |     | and server health |
  +---------------------+     +----------------------+     +-------------------+
           |                           |                           |
           v                           v                           v
  +---------------------+     +----------------------+     +-------------------+
  | WEEKLY TASKS        |     | MONTHLY TASKS        |     | QUARTERLY TASKS   |
  | (2-4 hrs/week)      |     | (4-8 hrs/month)      |     | (1-2 days/qtr)    |
  +---------------------+     +----------------------+     +-------------------+
  |                     |     |                      |     |                   |
  | Review FP rates     |     | Audit exception      |     | Re-train VML      |
  | per policy          |     | list for decay       |     | profiles with     |
  |                     |     |                      |     | fresh documents   |
  | Tune thresholds     |     | Verify EDM/IDM       |     |                   |
  | based on FP data    |     | index freshness      |     | Review compliance |
  |                     |     |                      |     | coverage gaps     |
  | Process exception   |     | Refresh directory    |     |                   |
  | requests            |     | group membership     |     | Plan new policy   |
  |                     |     |                      |     | rollouts          |
  | Graduate policies   |     | Generate compliance  |     |                   |
  | (Test > Notify >    |     | reports for          |     | Validate upgrade  |
  |  Block)             |     | stakeholders         |     | path readiness    |
  +---------------------+     +----------------------+     +-------------------+
```

---

## Step-by-Step Workflow: Creating a Complete DLP Policy

### Phase 1: Detection Technology Selection & Preparation (1-5 days)

**Time estimate:** 2-8 hours for DCM-only; 1-5 days if EDM/IDM/VML involved

#### Step 1.1: Identify Sensitive Data Types

| Activity | Navigation | API Automatable? | Time |
|----------|-----------|-----------------|------|
| Review regulatory requirements (PCI, HIPAA, etc.) | External -- compliance documentation | N/A | 1-2 hrs |
| Identify data types to protect (SSN, CC, PHI, IP) | External -- data classification exercise | N/A | 1-4 hrs |
| Select detection technology per data type | Internal analysis -- match data type to DCM/EDM/IDM/VML | N/A | 30 min |

**Decision matrix for technology selection:**

| Data Type | Best Technology | Why |
|-----------|----------------|-----|
| Known structured records (SSN, CC from DB) | EDM | Exact match on actual records eliminates false positives |
| Pattern-based data (any SSN, any CC) | DCM (Data Identifiers) | Built-in validators (Luhn, format check) for common patterns |
| Confidential documents (contracts, specs) | IDM | Fingerprints detect full or partial copies |
| Content categories (financial reports, source code) | VML | ML learns content characteristics across diverse documents |
| Specific keywords (project code names) | DCM (Keywords) | Direct text matching for known terms |
| Custom formats (employee IDs, internal codes) | DCM (Regex) | Flexible pattern matching for proprietary formats |
| Scanned forms (W-2, medical) | Form Recognition + OCR | Layout-aware detection for form-based data |

#### Step 1.2: Prepare Data Sources (EDM/IDM/VML only)

| Technology | Preparation | Console Navigation | API | Time |
|-----------|------------|-------------------|-----|------|
| **EDM** | Export structured data to CSV; clean data (remove empty rows, validate types); identify key fields | Manage > Data Profiles > Exact Data Profiles > Add | Index trigger only (`POST /edm/index`) -- profile creation is console-only | 2-8 hrs |
| **IDM** | Collect source documents into directory; ensure native format (not scanned images for partial matching) | Manage > Data Profiles > Indexed Document Profiles > Add | Console-only | 1-4 hrs |
| **VML** | Prepare 50+ positive documents, 50+ negative documents; ensure diversity in authors/formats/dates | Manage > Data Profiles > Vector Machine Learning Profiles > Add | Console-only | 4-16 hrs |

#### Step 1.3: Create Data Profiles and Run Indexing/Training

| Profile Type | Steps | Console Screen | Time |
|-------------|-------|---------------|------|
| **EDM Profile** | 1. Name profile; 2. Upload CSV or connect DB; 3. Map columns to field types; 4. Mark key fields; 5. Set error threshold (default 5%); 6. Click "Index Now" or set schedule | Manage > Data Profiles > Exact Data Profiles | 30 min + indexing time (minutes for <100K records, hours for 1M+) |
| **IDM Profile** | 1. Name profile; 2. Point to source directory or upload; 3. Select match type (full/partial/both); 4. Set partial threshold; 5. Enable endpoint IDM (optional) | Manage > Data Profiles > Indexed Document Profiles | 30 min + indexing time |
| **VML Profile** | 1. Name profile; 2. Upload positive training set; 3. Upload negative training set; 4. Train model; 5. Review accuracy score; 6. Accept if >85% | Manage > Data Profiles > Vector Machine Learning Profiles | 30 min + training time |

**Gotchas at this stage:**
- EDM: Error threshold of 5% causes silent indexing failures on messy data (G-EDM-2)
- EDM: Large data sources impact Enforce Server performance; use Remote Indexer for 1M+ records (G-EDM-3)
- IDM: Binary files (JPEG, CAD) only support exact match, not partial content matching (G-IDM-1)
- IDM: Endpoint partial matching requires explicit opt-in checkbox (G-IDM-4)
- VML: Training data quality matters more than quantity; diverse representative docs > many similar docs (G-VML-1)

---

### Phase 2: Detection Rule Creation (1-4 hours)

**Console Navigation:** Manage > Policies > Policy List > [New Policy or existing] > Detection tab > Add Rule

| Activity | Console Screen | API Automatable? | Time |
|----------|---------------|-----------------|------|
| Create simple rules (single condition) | Policy > Detection > Add Rule | NO (console-only) | 15 min per rule |
| Create compound rules (multiple AND conditions) | Policy > Detection > Add Compound Rule | NO (console-only) | 30 min per rule |
| Set severity per rule (High/Medium/Low/Informational) | Rule > Severity dropdown | NO (console-only) | 2 min per rule |
| Configure "Look In" scope (body, subject, attachments) | Rule > Look In checkboxes | NO (console-only) | 2 min per rule |
| Set match thresholds (minimum matches, unique vs all) | Rule > Condition parameters | NO (console-only) | 5 min per rule |

**Gotchas at this stage:**
- Compound rules use AND logic only -- there is no OR operator. For OR logic, create separate simple rules (G-DR-1)
- "Look In" selection determines scope; unchecking "Subject" means subject line content is invisible to the rule (G-DR-3)
- Severity is per-rule, not per-incident; highest-severity matching rule wins (G-DR-2)

---

### Phase 3: Exception Creation (30 min - 2 hours)

**Console Navigation:** Policy > Detection tab > Add Exception

| Activity | Console Screen | API Automatable? | Time |
|----------|---------------|-----------------|------|
| Add sender/recipient pattern exceptions | Policy > Exception > Sender/Recipient | NO (console-only; patterns API is separate) | 10 min each |
| Add directory group exceptions | Policy > Exception > Directory Group | NO (console-only) | 10 min each |
| Add content-based exceptions | Policy > Exception > Content | NO (console-only) | 15 min each |
| Document exception justification | External (spreadsheet, ticketing system) | N/A | 5 min each |

**Gotchas at this stage:**
- Email address patterns do NOT support regex or wildcards (G-EX-3)
- Domain exception field has 512-character limit (G-EX-4)
- Broad sender/group exceptions create bypass vectors (G-EX-5) -- CRITICAL
- No built-in exception expiration mechanism; schedule quarterly reviews (G-EX-2)
- Exceptions are evaluated AFTER detection, not during -- excepted content still consumes detection resources (G-EX-1)

---

### Phase 4: Response Rule Configuration (1-2 hours)

**Console Navigation:** Manage > Policies > Response Rules > Add Response Rule

| Activity | Console Screen | API Automatable? | Time |
|----------|---------------|-----------------|------|
| Create Automated Response rules | Response Rules > New > Automated > Conditions + Actions | NO (console-only) | 20 min each |
| Create Smart Response rules (manual) | Response Rules > New > Smart > Actions | NO (console-only) | 10 min each |
| Configure syslog action (host, port, CEF template) | Response Rule > Action > Log to Syslog | NO (console-only) | 15 min |
| Configure email notification | Response Rule > Action > Send Email Notification | NO (console-only) | 10 min |
| Configure endpoint block/notify popup | Response Rule > Action > Endpoint Prevent | NO (console-only) | 15 min |
| Configure MIP label application | Response Rule > Action > Apply Classification Label | NO (console-only) | 15 min |

**Gotchas at this stage:**
- NEVER deploy blocking on Day 1 -- start with Test mode (G-RR-1) -- CRITICAL
- Response rules with no conditions fire on EVERY incident (G-RR-2)
- Email gateway must be pre-configured for X-header-based actions (G-RR-3)
- Smart Response rules have limited actions: status, notes, email, log only (G-RR-4)
- Syslog CEF variable names must match exactly; typos produce blank fields (G-RR-5)

---

### Phase 5: Policy Assembly (30 min - 1 hour)

**Console Navigation:** Manage > Policies > Policy List > [New Policy or existing]

| Activity | Console Screen | API Automatable? | Time |
|----------|---------------|-----------------|------|
| Create new policy (from template or blank) | Policy List > New Policy | YES (import XML via API, 25.1+) | 10 min |
| Assign detection rules to policy | Policy > Detection tab | NO (console-only) | 5 min |
| Assign exceptions to policy | Policy > Detection tab | NO (console-only) | 5 min |
| Assign response rules to policy | Policy > Response tab | NO (console-only) | 5 min |
| Set policy mode (Test Without Notifications) | Policy > General tab | YES (via policy apply API) | 2 min |
| Save policy | Policy > Save button | N/A | 1 min |

---

### Phase 6: Policy Group Assignment & Deployment (15-30 min)

**Console Navigation:** System > Servers and Detectors > Policy Groups

| Activity | Console Screen | API Automatable? | Time |
|----------|---------------|-----------------|------|
| Create policy group (if new) | Policy Groups > Add | YES (list via API; creation may be via deploy API) | 5 min |
| Assign detection servers to group | Policy Groups > [group] > Servers | NO (console-only) | 5 min |
| Assign policy to group | Policy > General > Policy Group dropdown | YES (via import/deploy API) | 2 min |
| Apply/deploy policies | Manage > Policies > Apply | YES (`POST /policies/apply`) | 2 min + propagation time |

**Propagation timing:**
- Detection Servers: near-immediate (seconds to minutes)
- Endpoint Agents: up to 15 minutes (agent poll interval)

---

### Phase 7: Staged Rollout & Tuning (2-8 weeks)

| Stage | Duration | What to Monitor | Graduation Criteria |
|-------|----------|----------------|-------------------|
| **Test Without Notifications** | 1-2 weeks | Incident volume, false positive patterns, detection coverage | FP rate < 10% |
| **Test With Notifications** | 1-2 weeks | User feedback, business impact, exception requests | FP rate < 5%, no critical business disruption |
| **Soft Block (User Cancel)** | 1-2 weeks | User override rate, justification quality, FP refinement | Override rate < 15% |
| **Hard Block (Enabled)** | Ongoing | Incident volume, blocked transaction rate, escalations | Stable FP rate, executive sign-off |

---

## Which Steps Are API-Automatable vs Console-Only

| Phase | Step | API Status | API Endpoint (if available) |
|-------|------|-----------|---------------------------|
| 1 | Create EDM Profile | CONSOLE-ONLY | -- |
| 1 | Trigger EDM Indexing | API | `POST /edm/index` (16.0 RU2+) |
| 1 | Create IDM Profile | CONSOLE-ONLY | -- |
| 1 | Create VML Profile | CONSOLE-ONLY | -- |
| 2 | Create Detection Rules | CONSOLE-ONLY | -- |
| 3 | Create Exceptions | CONSOLE-ONLY | -- |
| 3 | Create Sender/Recipient Patterns | API | `POST /senderRecipientPattern` (16.0+) |
| 4 | Create Response Rules | CONSOLE-ONLY | -- |
| 5 | Import Policy XML | API | `POST /policies/import` (25.1+) |
| 5 | Export Policy XML | API | `POST /policies/export` (25.1+) |
| 5 | List Policies | API | `GET /policies` (16.0+) |
| 6 | Apply/Deploy Policies | API | `POST /policies/apply` (16.0+) |
| 7 | Query Incidents (for tuning) | API | `POST /incidents` (15.7+) |
| 7 | Update Incident Status | API | `PATCH /incidents` (15.7+) |

**Summary:** Approximately 30% of the policy authoring workflow is API-automatable. The core authoring steps (rules, exceptions, response rules, data profiles) are console-only. The deployment, incident review, and policy lifecycle steps are API-enabled.

---

## Pain Points

| Pain Point | Impact | Mitigation |
|-----------|--------|------------|
| No API for rule-level CRUD | HIGH -- all authoring requires manual console work | Use policy XML import/export (25.1+) for promotion between environments |
| 6-layer model complexity | HIGH -- steep learning curve for new admins | Use policy templates as starting points; customize rather than build from scratch |
| EDM/IDM index maintenance | MEDIUM -- stale indexes create silent detection gaps | Automate re-indexing schedules; monitor index status daily |
| VML retraining cycle | MEDIUM -- models decay as content patterns evolve | Re-train annually; track accuracy metrics over time |
| Exception management | HIGH -- no expiration, accumulate over time | Quarterly reviews; document justification and expected expiry for every exception |
| 15-minute endpoint propagation | MEDIUM -- urgent policy changes are delayed | Plan policy changes during maintenance windows; accept latency for routine changes |
| Compound rules AND-only | MEDIUM -- OR logic requires multiple rules | Create separate simple rules for OR conditions; document the logical intent |

---

## Time Estimate for Complete Workflow

| Scenario | Detection Technologies | Total Time |
|----------|----------------------|------------|
| Simple keyword policy from template | DCM (keywords) | 2-4 hours |
| Data identifier policy (SSN, CC) | DCM (data identifiers) | 4-8 hours |
| EDM-based policy (structured data) | EDM + DCM | 1-3 days (includes data prep + indexing) |
| IDM-based policy (document protection) | IDM + DCM | 1-3 days (includes document collection + indexing) |
| VML-based policy (ML classification) | VML + DCM | 3-5 days (includes training document prep + training + validation) |
| Full multi-technology policy | EDM + IDM + VML + DCM | 1-4 weeks (parallel data prep + iterative tuning) |
| Production rollout (Test > Block) | Any | Add 4-8 weeks for staged rollout |

---

*Policy Author persona covering the full 6-layer authoring workflow with time estimates, API coverage, and pain points.*
