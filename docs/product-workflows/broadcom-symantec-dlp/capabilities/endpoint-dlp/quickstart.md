# Endpoint DLP — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Deploy a DLP agent to one Windows endpoint + enable USB monitoring + block PCI data on USB drives.
> **Time estimate:** 45-60 minutes (includes agent install and first policy match).
> **Prerequisites:** Enforce Server running, Endpoint Prevent Server installed and registered, Oracle DB operational, one Windows test machine.

---

## The 6-Step Fast Path

```
Step 1: Verify Endpoint Prevent Server is running
Step 2: Build an agent package (MSI)
Step 3: Install agent on test machine
Step 4: Create a USB-specific PCI blocking policy
Step 5: Add an Endpoint Prevent Block response rule
Step 6: Test by copying a credit card file to USB
```

---

## Step 1: Verify Endpoint Prevent Server

**Navigation:** System > Servers and Detectors > Overview

1. In the Enforce console, navigate to **System > Servers and Detectors > Overview**
2. Confirm an **Endpoint Prevent** server is listed with status **"Running"**

```
+=========================================================================+
|  System > Servers and Detectors > Overview                               |
+=========================================================================+
|  +-------------------------------------------------------------------+ |
|  | Server Name              | Type              | Status   | Agents  | |
|  |--------------------------|-------------------|----------|--------| |
|  | dlp-eps01.corp.example   | Endpoint Prevent  | Running  | 0      | |
|  | dlp-nps01.corp.example   | Network Prevent   | Running  | --     | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

If no Endpoint Prevent Server is listed, you must install one before proceeding. See the Installation Guide (S19/S20).

[S1, S4, V11] Evidence: A

---

## Step 2: Build Agent Package

**Navigation:** System > Agents > Agent Packages (or standalone Agent Package Builder)

1. Open the Agent Package Builder
2. Set **Endpoint Server Address Type** to **FQDN** (recommended)
3. Enter the Endpoint Prevent Server FQDN: `dlp-eps01.corp.example.com`
4. Set **Server Port** to `443`
5. Select **Platform: Windows x64**
6. Click **Build Package**
7. Save the generated MSI file to a known location

```
+=========================================================================+
|  Agent Package Builder                                                   |
+=========================================================================+
|  Endpoint Server Address Type:  (o) FQDN                                |
|  Server Address:  [dlp-eps01.corp.example.com       ]                   |
|  Server Port:     [443                               ]                  |
|  Agent Platform:  (o) Windows x64                                       |
|                                                                         |
|                                             [Build Package]             |
+=========================================================================+
```

**Output:** `DLP_Agent_Windows_x64.msi` saved to your downloads folder.

[S1, V12, V29] Evidence: A

---

## Step 3: Install Agent on Test Machine

1. Copy the MSI file to your Windows test machine
2. Open an **elevated Command Prompt** (Run as Administrator)
3. Run:

```cmd
msiexec /i "C:\Downloads\DLP_Agent_Windows_x64.msi" /qn
```

4. Wait 2-3 minutes for installation to complete
5. Verify the agent service is running:

```cmd
sc query "Symantec DLP Agent"
```

Expected output:
```
SERVICE_NAME: Symantec DLP Agent
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 4  RUNNING
```

6. Back in the Enforce console, navigate to **System > Agents > Overview**
7. Wait up to 15 minutes for the agent to check in (it polls at the configured interval)
8. Verify your test machine appears in the agent list with status "Online"

```
+=========================================================================+
|  System > Agents > Overview                                              |
+=========================================================================+
|  Total Agents: 1    Online: 1    Offline: 0                             |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | Hostname         | User       | IP           | Status | Last Seen  | |
|  |------------------|------------|--------------|--------|------------| |
|  | WS-TEST-001      | admin      | 10.1.50.101  | Online | 1 min ago  | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

[S1, S4, V12, V29] Evidence: A

---

## Step 4: Create USB-Specific PCI Blocking Policy

**Navigation:** Manage > Policies > Policy List > New Policy > Template List

1. Click **New Policy** > **Template List**
2. Select **"PCI DSS - Credit Card Numbers"** template
3. Click **Next**

```
+=========================================================================+
|  New Policy -- Configure                                                 |
+=========================================================================+
|  Policy Name:  [PCI-USB-Block-QuickStart                    ]           |
|  Description:  [Block credit card data on USB drives         ]          |
|                                                                         |
|  Policy Group: [Default Policy Group                     v]            |
|                                                                         |
|  Detection Rules (from template):                                        |
|  +-------------------------------------------------------------------+ |
|  | Rule: Content Matches Data Identifier                              | |
|  |   Data Identifier: Credit Card Number (Luhn check)                | |
|  |   Min unique matches: 1                                            | |
|  |   Severity: High                                                   | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Policy Status: (o) Test With Notifications                             |
|                 ( ) Enabled                                              |
|                 ( ) Disabled                                             |
|                                                                         |
|                                                          [Save]        |
+=========================================================================+
```

4. Set **Policy Name** to `PCI-USB-Block-QuickStart`
5. Set **Policy Group** to `Default Policy Group` (or whichever group includes your Endpoint Prevent Server)
6. Leave detection rule as-is (Credit Card Number data identifier, minimum 1 unique match)
7. Set **Policy Status** to **"Test With Notifications"** (safe for initial testing)
8. Click **Save**

[S1, S4, V16] Evidence: A

---

## Step 5: Add Endpoint Prevent Block Response Rule

**Navigation:** Manage > Policies > Response Rules > Add Response Rule

1. Click **Add Response Rule**
2. Select **Automated Response**
3. Click **Next**

```
+=========================================================================+
|  Response Rule: USB-PCI-Block-Action                                     |
+=========================================================================+
|  Rule Name:  [USB-PCI-Block-Action                          ]           |
|  Rule Type:  Automated Response                                         |
|                                                                         |
|  Conditions:                                                             |
|    [x] Severity is: High                                                |
|                                                                         |
|  Actions:                                                                |
|    [+ Add Action]                                                        |
|                                                                         |
|  Action 1: Endpoint Prevent -- Block                                    |
|    Notify User:           [x] Yes                                        |
|    Notification Text:                                                    |
|    +-----------------------------------------------------------+        |
|    | This file contains credit card data and cannot be copied  |        |
|    | to a USB drive. This action violates PCI-DSS policy.      |        |
|    | Contact dlp-support@corp.example.com if you need help.     |        |
|    +-----------------------------------------------------------+        |
|                                                                         |
|                                                         [Save Rule]    |
+=========================================================================+
```

4. Set **Rule Name** to `USB-PCI-Block-Action`
5. Add **Condition**: Severity is High
6. Add **Action**: Endpoint Prevent > Block
7. Enable **Notify User** and enter notification text
8. Click **Save Rule**

Now attach this response rule to your policy:
9. Navigate back to **Manage > Policies > Policy List**
10. Click on **PCI-USB-Block-QuickStart**
11. Go to the **Response** tab
12. Add `USB-PCI-Block-Action` to the response rules list
13. **Save** the policy

[S1, S4, V23] Evidence: A

---

## Step 6: Test the Detection

**Wait 15 minutes** for the policy to propagate to the agent (or less, depending on polling interval).

### Create a Test File

On the test machine, create a test file containing credit card numbers:

1. Open Notepad
2. Enter the following test data (these are standard test card numbers):
```
Test Credit Card Data
Visa: 4111111111111111
MasterCard: 5500000000000004
Amex: 340000000000009
Discover: 6011000000000004
```
3. Save as `test_pci_data.txt` on the Desktop

### Copy to USB Drive

1. Insert a USB drive into the test machine
2. Copy `test_pci_data.txt` to the USB drive

### Expected Result

If the policy has propagated:

```
+===============================================+
|  Symantec DLP Agent                           |
+===============================================+
|                                               |
|  [!] Data Transfer Blocked                    |
|                                               |
|  This file contains credit card data and      |
|  cannot be copied to a USB drive. This action |
|  violates PCI-DSS policy.                     |
|                                               |
|  Contact dlp-support@corp.example.com if      |
|  you need help.                               |
|                                               |
|                              [OK]             |
+===============================================+
```

The file copy is blocked, and the user sees the notification popup.

### Verify Incident in Enforce Console

Navigate to **Incidents > Endpoint > Incident List**

```
+=========================================================================+
|  Incidents > Endpoint                                                    |
+=========================================================================+
|  +-------------------------------------------------------------------+ |
|  | ID     | Policy                   | Severity | User   | Channel   | |
|  |--------|--------------------------|----------|--------|----------| |
|  | 10001  | PCI-USB-Block-QuickStart | High     | admin  | USB      | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

Click the incident to see match details: matched credit card numbers (masked), file name, user, timestamp, and the block action taken.

[S1, S4, V12, V23] Evidence: A

---

## What's Next

After validating the quickstart:

1. **Expand channels** -- Enable email, web, and clipboard monitoring for broader protection
2. **Deploy to more machines** -- Use GPO/SCCM for enterprise-wide deployment (see workflow.md Phase 3)
3. **Create agent groups** -- Apply different configurations to different departments (see workflow.md Phase 7)
4. **Add EDM detection** -- Replace simple data identifier rules with Exact Data Matching for lower false positive rates (see authoring-rules capability)
5. **Switch to Enabled** -- After 2 weeks of "Test With Notifications," switch the policy status to "Enabled" for active enforcement
6. **Review gotchas.md** -- Understand offline behavior, performance impacts, and common pitfalls before production deployment

---

## Quick Reference: Key Navigation Paths

| Task | Navigation |
|------|-----------|
| Verify Endpoint Server | System > Servers and Detectors > Overview |
| Build agent package | System > Agents > Agent Packages |
| View registered agents | System > Agents > Overview |
| Configure agent settings | System > Agents > Agent Configuration |
| Create agent groups | System > Agents > Agent Groups |
| Create policy from template | Manage > Policies > Policy List > New Policy > Template List |
| Create response rule | Manage > Policies > Response Rules > Add Response Rule |
| View endpoint incidents | Incidents > Endpoint > Incident List |

[S1, S4] Evidence: A
