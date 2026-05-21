# Cloud DLP — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Connect Microsoft 365 to CloudSOC and enable DLP scanning on OneDrive to detect PCI data.
> **Time estimate:** 30-60 minutes (includes Azure AD app registration, CloudSOC connection, and first DLP scan).
> **Prerequisites:** CloudSOC account (app.elastica.net), Microsoft 365 tenant with Global Admin access, Cloud Detection Service enabled.

---

## The 6-Step Fast Path

```
Step 1: Register an application in Azure AD for CloudSOC
Step 2: Connect Microsoft 365 in CloudSOC console
Step 3: Create a DLP Profile with credit card detection
Step 4: Apply the DLP Profile to OneDrive
Step 5: Upload a test file with credit card data to OneDrive
Step 6: Verify the incident in CloudSOC
```

---

## Step 1: Register Application in Azure AD

1. Sign in to the Azure Portal: https://portal.azure.com
2. Navigate to **Azure Active Directory > App registrations > New registration**
3. Configure:
   - **Name:** `Symantec CloudSOC DLP Scanner`
   - **Supported account types:** Accounts in this organizational directory only
   - **Redirect URI:** Web - `https://app.elastica.net/callback`
4. Click **Register**
5. Note the **Application (client) ID** and **Directory (tenant) ID**
6. Navigate to **Certificates & secrets > New client secret**
   - Description: `CloudSOC DLP`
   - Expiry: 24 months
   - Copy the **Secret value** immediately (it will not be shown again)
7. Navigate to **API permissions > Add a permission > Microsoft Graph**
   - Application permissions:
     - `Files.Read.All`
     - `Mail.Read`
     - `Sites.Read.All`
     - `User.Read.All`
8. Click **Grant admin consent for [your tenant]**

```
Summary of values needed:
  Application (client) ID:  a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Directory (tenant) ID:    12345678-abcd-ef01-2345-6789abcdef01
  Client Secret:            xxxxxx~xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

[S24] Evidence: A

---

## Step 2: Connect Microsoft 365 in CloudSOC

1. Log in to CloudSOC: https://app.elastica.net (US) or https://app.eu.elastica.net (EU)
2. Navigate to **Admin > App Connectors > Add App**
3. Select **Microsoft 365**
4. Enter connection details:

```
+=========================================================================+
|  CloudSOC > Admin > App Connectors > Microsoft 365                       |
+=========================================================================+
|                                                                         |
|  Tenant ID:        [12345678-abcd-ef01-2345-6789abcdef01 ]             |
|  Application ID:   [a1b2c3d4-e5f6-7890-abcd-ef1234567890]             |
|  Client Secret:    [********                               ]            |
|                                                                         |
|                                            [Test Connection]            |
|                                                                         |
+=========================================================================+
```

5. Click **Test Connection** -- should show "Connection successful"
6. Click **Save**
7. Enable scan scope:
   - [x] OneDrive for Business
   - [ ] SharePoint (optional -- enable later)
   - [ ] Exchange Online (optional -- enable later)

[S24, V8] Evidence: A

---

## Step 3: Create a DLP Profile

**Navigation:** CloudSOC > Protect > DLP Profiles > New Profile

1. Click **New Profile**
2. Configure:

```
+=========================================================================+
|  CloudSOC > Protect > DLP Profiles > New                                 |
+=========================================================================+
|                                                                         |
|  Profile Name:     [PCI-OneDrive-QuickStart                ]            |
|  Description:      [Detect credit card data in OneDrive     ]           |
|                                                                         |
|  Rules:                                                                  |
|    [+ Add Rule]                                                          |
|                                                                         |
|    Rule 1:                                                               |
|      Detection type:  [Data Identifier                    v]            |
|      Identifier:      [Credit Card Number (Luhn check)    v]            |
|      Min matches:     [1  ]                                              |
|      Severity:        [High                               v]            |
|                                                                         |
|  Response Actions:                                                       |
|    [x] Notify file owner (email notification)                           |
|    [ ] Quarantine file                                                   |
|    [ ] Revoke sharing                                                    |
|                                                                         |
|                                                          [Save]        |
+=========================================================================+
```

3. Set **Profile Name** to `PCI-OneDrive-QuickStart`
4. Add rule: Data Identifier > Credit Card Number (Luhn check), min matches: 1
5. Set **Severity** to High
6. For this quickstart, enable only **Notify file owner** (safe for initial testing)
7. Click **Save**

[S24, API-intelligence] Evidence: A

---

## Step 4: Apply DLP Profile to OneDrive

**Navigation:** CloudSOC > Protect > App Policies

1. Navigate to **Protect > App Policies**
2. Select the **Microsoft 365** connector
3. Assign the `PCI-OneDrive-QuickStart` profile
4. Enable:
   - [x] Real-time monitoring (near-real-time event processing)
   - [x] Incremental scanning (scan new/modified files)

```
+=========================================================================+
|  CloudSOC > Protect > App Policies > Microsoft 365                       |
+=========================================================================+
|                                                                         |
|  Applied DLP Profiles:                                                   |
|    [x] PCI-OneDrive-QuickStart                                          |
|    [ ] (add more profiles later)                                        |
|                                                                         |
|  Scan Mode:                                                              |
|    [x] Real-time event monitoring                                        |
|    [x] Incremental scanning                                              |
|    [ ] Full rescan (schedule later)                                     |
|                                                                         |
|                                                     [Apply & Enable]    |
+=========================================================================+
```

5. Click **Apply & Enable**

[S24] Evidence: A

---

## Step 5: Upload Test File to OneDrive

1. Open OneDrive for Business: https://onedrive.live.com or via Microsoft 365 portal
2. Create a test file `test_pci_data.xlsx` with the following content:

```
| Customer Name | Credit Card Number  | Expiry |
|---------------|---------------------|--------|
| John Smith    | 4111111111111111    | 12/26  |
| Jane Doe      | 5500000000000004    | 03/27  |
| Bob Johnson   | 340000000000009     | 06/28  |
```

3. Upload the file to your OneDrive
4. Optionally, share the file via an external sharing link (this will test revoke-sharing when enabled)

[S24] Evidence: A

---

## Step 6: Verify Incident in CloudSOC

Wait 5-15 minutes for the Cloud Detection Service to scan the newly uploaded file.

**Navigation:** CloudSOC > Investigate > Incidents

```
+=========================================================================+
|  CloudSOC > Investigate > Incidents                                      |
+=========================================================================+
|  +-------------------------------------------------------------------+ |
|  | ID     | App       | File                 | Severity | Action     | |
|  |--------|-----------|----------------------|----------|------------| |
|  | C-1001 | O365-OD   | test_pci_data.xlsx   | High     | Notified   | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

Click the incident to see details:

```
+=========================================================================+
|  Incident Detail: C-1001                                                 |
+=========================================================================+
|  DLP Profile:  PCI-OneDrive-QuickStart                                  |
|  Severity:     High                                                      |
|  App:          Microsoft 365 - OneDrive                                  |
|  File:         test_pci_data.xlsx                                        |
|  Owner:        jsmith@corp.example.com                                   |
|  Location:     /Documents/test_pci_data.xlsx                            |
|  Shared:       External link (if applicable)                             |
|  Detected:     2025-05-21 10:28:15 AM                                   |
|                                                                         |
|  Matches:                                                                |
|  +-------------------------------------------------------------------+ |
|  | Rule                    | Match                | Count             | |
|  |-------------------------|--------------------- |-------------------| |
|  | Credit Card Number      | 4111111111111111     | 3 unique matches  | |
|  |                         | 5500000000000004     |                   | |
|  |                         | 340000000000009      |                   | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Actions Taken:                                                          |
|    [x] File owner notified (email sent)                                 |
+=========================================================================+
```

Cloud DLP is working. The CDS scanned the OneDrive file and detected credit card data.

[S24] Evidence: A

---

## What's Next

After validating the quickstart:

1. **Enable quarantine and revoke sharing** -- Update the DLP Profile response actions to quarantine files and remove sharing links (see workflow.md Phase 6)
2. **Add more cloud apps** -- Connect Google Workspace, Box, Dropbox, Salesforce (see workflow.md Phase 3)
3. **Enable SharePoint and Exchange** -- Expand O365 scope beyond OneDrive
4. **Add EDM/IDM profiles** -- Use Remote Indexer Tool to create cloud-compatible indexes for exact data matching
5. **Enable Shadow IT detection** -- Configure proxy-based scanning to discover unsanctioned cloud apps (see workflow.md Phase 8)
6. **Integrate with Enforce Server** -- For hybrid deployments, connect CloudSOC to on-prem Enforce for unified incident management
7. **Review gotchas.md** -- Understand API rate limits, scanning delays, and per-app limitations

---

## Quick Reference: Key Navigation Paths

| Task | Navigation |
|------|-----------|
| Connect cloud app | CloudSOC > Admin > App Connectors > Add App |
| Create DLP profile | CloudSOC > Protect > DLP Profiles > New Profile |
| Apply profile to app | CloudSOC > Protect > App Policies |
| View cloud incidents | CloudSOC > Investigate > Incidents |
| Shadow IT discovery | CloudSOC > Detect > Cloud App Discovery |
| DLP configuration | CloudSOC > Admin > DLP Configuration |
| Manage DLP profiles via API | `GET/POST /api/clouddlp/protect/public/profile` |
| List data identifiers via API | `GET /api/clouddlp/protect/public/dataIdentifiers` |

[S24, API-intelligence] Evidence: A
