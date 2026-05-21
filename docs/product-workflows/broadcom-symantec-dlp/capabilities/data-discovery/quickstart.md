# Quickstart: Set Up Your First Discovery Scan on a File Share

> **Time to complete:** 30-45 minutes (assuming Network Discover Server is already installed)
> **Result:** A weekly incremental scan of a Windows file share for PII (Social Security Numbers)
> **Prerequisites:** Network Discover Server registered with Enforce Server; a Windows file share to scan; a domain service account with read access

---

## Step 1: Verify Network Discover Server Is Online (2 minutes)

1. Log in to the **Enforce Console** at `https://enforce-server:443/ProtectManager`
2. Navigate to **System > Servers and Detectors > Overview**
3. Confirm your Network Discover Server shows status **Running** (green indicator)
4. If the server is not listed, it needs to be installed and registered first (see prerequisites.md)

---

## Step 2: Verify a Detection Policy Exists (5 minutes)

You need at least one policy to scan against. Use a built-in template:

1. Navigate to **Manage > Policies > Policy List**
2. Click **New Policy**
3. Select **Template List**
4. Find and select **"US Social Security Numbers"** (or "PCI DSS" if scanning for credit cards)
5. Click **Next**
6. Accept defaults for the policy name and rules
7. Under **Policy Group**, select the policy group assigned to your Network Discover Server
   - Not sure which group? Check: System > Servers and Detectors > [your Discover server] > Policy Group
8. Click **Save**
9. The policy is now active and will be evaluated during discovery scans

---

## Step 3: Create the File Share Scan Target (10 minutes)

1. Navigate to **Manage > Discover > Discover Targets**
2. Click **New Target**
3. Select **File System** as the target type
4. Fill in the configuration:

| Field | Value |
|-------|-------|
| Target Name | "My First Discovery Scan - HR Share" |
| Discover Server | (select your Network Discover Server) |
| Policy Group | (same group as your policy in Step 2) |

5. Under **Scan Paths**, click **Add** and enter:
   - `\\your-fileserver\share-name\`
   - Replace with an actual UNC path you want to scan

6. Under **Credentials**:
   - Username: `DOMAIN\service-account` (your domain service account)
   - Password: (enter the password)

7. Under **Content Filters** (optional but recommended for first scan):
   - File types: `.docx, .xlsx, .pdf, .csv, .txt`
   - File size max: 50 MB
   - This keeps the first scan fast and focused

8. Under **Schedule**:
   - For the quickstart, leave as **One-Time** (we will start it manually)

9. Click **Save**

---

## Step 4: Start the Scan (1 minute)

1. You should see your new target in the **Discover Targets** list
2. Select the checkbox next to your target
3. Click **Start**
4. The Status column changes to **Running**

---

## Step 5: Monitor Scan Progress (5-15 minutes depending on share size)

1. Stay on the **Discover Targets** page
2. Watch the **Progress** and **Files Scanned** columns update
3. You can click the target name to see detailed scan progress:
   - Files enumerated
   - Files scanned
   - Files with errors (inaccessible, too large, unsupported format)
4. Wait for status to change to **Completed**

---

## Step 6: Review Discovery Results (5 minutes)

1. Navigate to **Incidents > Discover/Network**
2. You should see incidents listed if the scan found any SSNs (or whatever your policy detects)
3. Click on an incident to see:
   - **Policy Matched**: Which policy triggered
   - **Matched Content**: The specific data found (highlighted)
   - **File Location**: Full path to the file containing sensitive data
   - **Severity**: Risk level assigned by the policy
4. This is the core output of data discovery -- now you know where sensitive data lives

---

## Step 7: Convert to Weekly Incremental Scan (2 minutes)

Now that the initial full scan is complete, set up recurring scans:

1. Navigate to **Manage > Discover > Discover Targets**
2. Click on your target name to edit it
3. Under **Schedule**:
   - Change to **Recurring**
   - Frequency: Weekly
   - Day: Sunday
   - Time: 02:00 AM
   - Enable: **Incremental** (checkbox)
4. Click **Save**

The scan will now run every Sunday at 2 AM, only scanning files that changed since the previous scan.

---

## What You Have Now

After completing this quickstart:

- A **weekly automated scan** of your file share for SSNs
- **Incidents** created for every file containing detected sensitive data
- **Incremental scanning** so subsequent scans are fast (only new/changed files)
- A foundation to expand: add more shares, more policies, more target types

## Next Steps

1. **Add more scan targets** -- SharePoint, Exchange, databases (see advanced.md)
2. **Add more policies** -- PCI DSS, HIPAA, GDPR templates
3. **Enable Protect actions** -- Quarantine or encrypt files with violations (see workflow.md Section 10)
4. **Set up notifications** -- Email alerts when high-severity violations are found
5. **Review and tune** -- Check for false positives after a few scan cycles
