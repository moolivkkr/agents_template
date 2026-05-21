# Cloud DLP — Gotchas
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Purpose:** Comprehensive collection of gotchas, pitfalls, and best-practice warnings for cloud DLP deployment and operation.
> **Evidence sources:** doc-corpus.md [S1-S28], video-intelligence.md [V1-V45, tribal knowledge], api-intelligence.md

---

## Table of Contents

1. [API Rate Limit Gotchas](#1-api-rate-limit-gotchas)
2. [Scanning Delay Gotchas](#2-scanning-delay-gotchas)
3. [Cloud App-Specific Gotchas](#3-cloud-app-specific-gotchas)
4. [Response Action Gotchas](#4-response-action-gotchas)
5. [Policy and Profile Gotchas](#5-policy-and-profile-gotchas)
6. [Proxy Mode Gotchas](#6-proxy-mode-gotchas)
7. [EDM/IDM Cloud Index Gotchas](#7-edmidm-cloud-index-gotchas)
8. [Hybrid Deployment Gotchas](#8-hybrid-deployment-gotchas)
9. [Operational Gotchas](#9-operational-gotchas)

---

## 1. API Rate Limit Gotchas

### G-CD-1: Microsoft Graph API throttling causes scan delays and incomplete coverage
**Impact:** HIGH
**Symptom:** OneDrive/SharePoint scanning falls behind. Incidents appear hours or days after file upload. Some files are never scanned.
**Root cause:** Microsoft Graph API enforces rate limits (10,000 requests per 10 minutes per application). Large-scale scans of thousands of OneDrive accounts exhaust the API quota, causing throttling (HTTP 429 responses).
**Mitigation:**
- Scope scanning to high-risk departments first, not all 5,000 users simultaneously
- Enable incremental scanning (only new/modified files)
- Schedule full rescans during off-hours (weekends) when API contention is lower
- Use Microsoft Graph delta queries (change tracking) instead of full enumeration
- Monitor CloudSOC scan status for throttling indicators
**Evidence:** A [S24, API-intelligence]

### G-CD-2: Google Drive API quota exceeded during initial full scan
**Impact:** HIGH
**Symptom:** Initial scan of Google Workspace stops mid-way. CloudSOC shows "API quota exceeded" error.
**Root cause:** Google Drive API allows 10,000 requests per 100 seconds per project. Scanning thousands of user drives with millions of files quickly exceeds this limit.
**Mitigation:** Stagger initial scans across users. Scan 200-500 users per batch with 24-hour intervals between batches. After initial scan, incremental scanning operates within quota limits.
**Evidence:** A [S24, API-intelligence]

### G-CD-3: Salesforce API daily limit constrains scan frequency
**Impact:** MEDIUM
**Symptom:** Salesforce DLP scanning stops mid-day with "API limit reached" error. No more scans until next day.
**Root cause:** Salesforce Enterprise edition allows 100,000 API calls per 24-hour period. DLP scanning consumes API calls alongside other integrations (CRM tools, reporting, etc.).
**Mitigation:** Coordinate Salesforce API budget with other consumers (integrations, dashboards, automation). Schedule DLP scans during off-peak API consumption hours. Consider Salesforce Unlimited edition for higher API limits.
**Evidence:** B [S24, API-intelligence]

### G-CD-4: Box API rate limiting per-user throttle causes slow scans
**Impact:** MEDIUM
**Symptom:** Box scanning is significantly slower than expected. Scans that should take hours take days.
**Root cause:** Box API enforces per-user rate limits (10 requests per second). Since CloudSOC uses an enterprise-level service account, all requests count against one user's limit.
**Mitigation:** Use JWT server authentication (which has higher rate limits than user-level OAuth). Contact Box support for enterprise API rate limit increases if scanning large volumes.
**Evidence:** B [S24]

---

## 2. Scanning Delay Gotchas

### G-CD-5: API-based scanning has 1-15 minute detection delay (not real-time)
**Impact:** MEDIUM
**Symptom:** File uploaded to OneDrive at 10:00 AM. DLP incident does not appear until 10:12 AM. In the 12-minute gap, the file was shared externally and downloaded by a third party.
**Root cause:** API-based scanning is near-real-time, not true real-time. The sequence is: (1) file uploaded, (2) cloud app API event notification received by CloudSOC (seconds to minutes), (3) file retrieved and sent to CDS for scanning (seconds), (4) CDS evaluates and returns verdict (seconds to minutes).
**Mitigation:** For real-time blocking, use proxy-based inline mode in addition to API-based scanning. Proxy mode intercepts uploads before they reach the cloud app. API mode provides retroactive scanning for data at rest.
**Evidence:** A [S24, V34]

### G-CD-6: Full rescan of large cloud environments takes days
**Impact:** MEDIUM
**Symptom:** Weekly full rescan of 5,000 OneDrive accounts takes 5+ days to complete, overlapping with the next week's scheduled scan.
**Root cause:** Full rescans enumerate and scan ALL content, not just changes. For large environments, this exceeds the API quota window.
**Mitigation:** Use incremental scanning for regular monitoring. Reserve full rescans for quarterly compliance audits. Reduce full rescan scope to high-risk users/departments only.
**Evidence:** B [S24]

---

## 3. Cloud App-Specific Gotchas

### G-CD-7: Microsoft Teams chat message scanning requires additional licensing
**Impact:** MEDIUM
**Symptom:** DLP scanning configured for Teams but chat message content is not being scanned. Only file attachments shared in Teams are detected.
**Root cause:** Teams chat message content scanning (the text of messages) requires Microsoft Graph Compliance APIs and may require Microsoft 365 E5 Compliance or equivalent add-on licensing. Standard Microsoft Graph permissions only grant access to files shared in Teams (stored in SharePoint).
**Mitigation:** For full Teams DLP, obtain Microsoft 365 E5 Compliance licensing and configure the additional Chat.Read.All permissions. For cost-sensitive deployments, file-level scanning (which covers attachments shared in Teams) provides significant coverage without the Compliance API requirement.
**Evidence:** B [S24]

### G-CD-8: SharePoint version scanning dramatically increases scan volume
**Impact:** LOW
**Symptom:** Enabling "Scan all versions" on SharePoint causes API quota exhaustion. Scan time increases 10x.
**Root cause:** SharePoint documents can have hundreds of versions. Each version must be individually retrieved and scanned via the API. A single document with 50 versions consumes 50 API calls.
**Mitigation:** Scan current version only for regular monitoring. Enable version scanning only for specific compliance audits where historical content matters (e.g., finding data that was later redacted). Use specific site collection scoping to limit version scanning to high-risk sites.
**Evidence:** B [S24]

### G-CD-9: Dropbox Paper documents are not scanned as files
**Impact:** LOW
**Symptom:** Sensitive data in Dropbox Paper documents is not detected.
**Root cause:** Dropbox Paper documents are a different content type than standard files. The Paper API may not be covered by the standard DLP connector.
**Mitigation:** Check CloudSOC release notes for Paper support. If not supported, use proxy-based inspection to catch Paper content when accessed via browser. Export Paper documents as standard files for DLP scanning.
**Evidence:** B [S24]

### G-CD-10: Salesforce record field content is not scanned by default
**Impact:** MEDIUM
**Symptom:** Credit card numbers stored directly in Salesforce record fields (e.g., custom "Payment Card" field on Account records) are not detected. Only file attachments are scanned.
**Root cause:** By default, Salesforce DLP scanning covers attachments, Salesforce Files, and Chatter attachments. Scanning record field content (the data in standard and custom fields) requires custom configuration.
**Mitigation:** Enable "Record field content" scanning in the Salesforce connector configuration (if available in your CloudSOC version). Alternatively, create a Salesforce report that exports record fields to CSV, and use on-prem Network Discover to scan the export.
**Evidence:** B [S24]

---

## 4. Response Action Gotchas

### G-CD-11: Cloud quarantine is difficult to reverse at scale
**Impact:** HIGH
**Symptom:** A misconfigured DLP profile quarantines 2,000 files in OneDrive across 500 users. Restoring all files manually takes days.
**Root cause:** Cloud quarantine moves files to a quarantine folder and removes sharing. There is no "bulk restore" button. Each file must be individually restored.
**Mitigation:**
- ALWAYS start with "Notify only" response actions for new DLP profiles
- Test quarantine action on a small pilot group (10-20 users) before enabling organization-wide
- Set minimum match thresholds high enough to avoid false positive quarantines
- Monitor incident volume during the first 24 hours of enforcement
- Document the quarantine restore procedure before enabling quarantine
**Evidence:** B [S24, V-tribal]

### G-CD-12: Revoke Sharing removes ALL external collaborators, not selectively
**Impact:** MEDIUM
**Symptom:** DLP detects PCI data in a file shared with 10 external collaborators. "Revoke Sharing" removes all 10 collaborators, including legitimate business partners.
**Root cause:** The revoke sharing action removes all external sharing. It does not distinguish between legitimate and unauthorized collaborators.
**Mitigation:** Consider using "Notify file owner" instead of automatic revoke sharing for files shared with multiple collaborators. The file owner can then selectively remove inappropriate sharing while preserving legitimate collaborations.
**Evidence:** B [S24]

### G-CD-13: MIP label application requires Microsoft 365 E5 or Azure Information Protection P2
**Impact:** MEDIUM
**Symptom:** "Apply Sensitivity Label" response action configured but labels are not being applied. No error in CloudSOC.
**Root cause:** MIP sensitivity label auto-application requires specific Microsoft licensing (E5 or AIP P2). Without the license, the API call to apply labels silently fails or is rejected.
**Mitigation:** Verify Microsoft 365 licensing includes auto-labeling capabilities. Test MIP label application on a single file before enabling at scale. Check Microsoft Azure portal for AIP licensing status.
**Evidence:** A [S1, S2]

---

## 5. Policy and Profile Gotchas

### G-CD-14: Cloud DLP profiles and Enforce policies can create duplicate incidents
**Impact:** LOW
**Symptom:** Same file generates two separate incidents -- one from CloudSOC Securlet policy and one from Enforce-managed policy deployed to CDS.
**Root cause:** In hybrid mode, both Enforce-managed policies and CloudSOC-native DLP Profiles can evaluate the same content. If both match, two incidents are created.
**Mitigation:** Decide on a single policy authority for cloud DLP. Either use Enforce-managed policies (for unified on-prem + cloud management) OR CloudSOC-native profiles (for cloud-only management). Avoid running parallel policies that cover the same content in the same cloud apps.
**Evidence:** B [S1, S24]

### G-CD-15: VML profiles from on-prem are not directly portable to cloud CDS
**Impact:** MEDIUM
**Symptom:** VML profile works on-prem (detects source code with 95% accuracy) but does not work in cloud. Cloud incidents show zero VML matches.
**Root cause:** On-prem VML models are trained and stored in the Enforce Server database. They are not automatically replicated to the Cloud Detection Service. VML models must be either re-trained for cloud or imported via policy export/import (DLP 25.1+).
**Mitigation:** For critical VML profiles, export the policy XML from Enforce (which includes VML model data) and import into CloudSOC. Alternatively, re-train the VML model directly in CloudSOC if the training data is available. Test cloud VML accuracy against a known test set before relying on it for enforcement.
**Evidence:** B [S1, S24]

### G-CD-16: EDM index stale in cloud while on-prem index is refreshed
**Impact:** HIGH
**Symptom:** New customer records (added to the on-prem EDM data source) are detected by on-prem DLP but NOT by cloud DLP. Cloud DLP misses new customers.
**Root cause:** Cloud EDM indexes are created by the Remote Indexer Tool and manually uploaded to CloudSOC. When the on-prem index is refreshed (automatic schedule), the cloud index is NOT automatically updated.
**Mitigation:** Establish an index refresh schedule for cloud:
1. On-prem EDM index auto-refreshes (daily/weekly)
2. After each refresh, run Remote Indexer Tool to create cloud index
3. Upload new cloud index to CloudSOC
4. Old index is replaced
Automate steps 2-4 via scripting if possible.
**Evidence:** A [S1, S24]

---

## 6. Proxy Mode Gotchas

### G-CD-17: SSL inspection certificate deployment is a prerequisite for proxy DLP
**Impact:** HIGH
**Symptom:** Proxy mode deployed but no DLP incidents from HTTPS traffic. Only HTTP traffic is inspected.
**Root cause:** Modern cloud apps use HTTPS exclusively. Without SSL inspection, the proxy sees encrypted traffic and cannot inspect content. The SSL inspection certificate must be deployed to all endpoint trust stores before enabling proxy DLP.
**Mitigation:** Deploy SSL inspection certificate via GPO, MDM, or SCCM BEFORE enabling proxy DLP. Test with a pilot group. Maintain a bypass list for sites that should not be SSL-inspected (banking, healthcare).
**Evidence:** A [S24]

### G-CD-18: Proxy routing breaks if PAC file is misconfigured
**Impact:** HIGH
**Symptom:** Users cannot access cloud apps. Web traffic times out or returns proxy errors.
**Root cause:** PAC file (Proxy Auto-Configuration) contains errors, excludes the proxy server itself (causing infinite loop), or routes traffic to a proxy that is down.
**Mitigation:** Test PAC file thoroughly before deployment. Include proper bypass rules for internal sites and the proxy server itself. Deploy PAC via WPAD (Web Proxy Auto-Discovery) for easy updates. Have a rollback plan (remove PAC to restore direct internet access).
**Evidence:** B [S24, V-tribal]

### G-CD-19: Proxy mode does not cover native mobile apps (only browser traffic)
**Impact:** MEDIUM
**Symptom:** Sensitive data uploaded via the OneDrive mobile app or Dropbox mobile app is not detected by proxy DLP.
**Root cause:** Mobile apps use native APIs, not web browsers. Unless the device is configured with a VPN or MDM-managed proxy, mobile app traffic does not route through the cloud proxy.
**Mitigation:** For mobile device coverage, use API-based scanning (which scans data regardless of how it was uploaded). Combine proxy mode (for browser coverage) with API mode (for comprehensive coverage including mobile and native app uploads).
**Evidence:** B [S24]

---

## 7. EDM/IDM Cloud Index Gotchas

### G-CD-20: Remote Indexer Tool requires Windows and cannot run on Linux
**Impact:** LOW
**Symptom:** Remote Indexer Tool fails to run on the Linux Discover server.
**Root cause:** The Remote Indexer Tool is a Windows-only application.
**Mitigation:** Install the Remote Indexer Tool on a Windows server. This can be the Enforce Server itself, or a dedicated Windows machine with access to the source data.
**Evidence:** A [S1, S24]

### G-CD-21: Cloud index upload size limits may constrain large EDM profiles
**Impact:** MEDIUM
**Symptom:** Remote Indexer generates a 5 GB index file from a 10 million row customer database. Upload to CloudSOC fails or times out.
**Root cause:** CloudSOC may have upload size limits for cloud indexes. Very large indexes may exceed these limits.
**Mitigation:** Split large data sources into multiple smaller EDM profiles (e.g., by region or department). Each profile generates a smaller index that fits within upload limits. Alternatively, contact Broadcom Support for increased upload limits.
**Evidence:** B [S24]

---

## 8. Hybrid Deployment Gotchas

### G-CD-22: Enforce Server and CloudSOC have different incident formats
**Impact:** MEDIUM
**Symptom:** Analysts must check two different consoles for incidents. Reporting is fragmented between on-prem and cloud.
**Root cause:** Enforce Server incidents and CloudSOC incidents use different data models, different UIs, and different APIs. There is no single unified incident view across both platforms.
**Mitigation:** Export incidents from both platforms to a common SIEM (Splunk, Sentinel) for unified reporting. Use the Enforce REST API and CloudSOC API to pull incidents into a centralized dashboard. Long-term, Broadcom is working on deeper integration.
**Evidence:** B [S1, S24, API-intelligence]

### G-CD-23: Policy changes in Enforce take time to propagate to CDS
**Impact:** LOW
**Symptom:** Policy created in Enforce at 10:00 AM. Cloud detection using this policy does not start until 10:30 AM.
**Root cause:** Enforce-managed policies must be deployed to CDS via the policy group mechanism. There is a propagation delay (typically 15-30 minutes) between policy save in Enforce and availability in CDS.
**Mitigation:** For urgent cloud policy changes, create the policy directly in CloudSOC as a DLP Profile (available immediately). Sync with Enforce-managed policies later.
**Evidence:** B [S1, S24]

---

## 9. Operational Gotchas

### G-CD-24: Cloud app API permission changes can silently break DLP scanning
**Impact:** HIGH
**Symptom:** DLP scanning stops working for a specific cloud app. No errors in CloudSOC dashboard.
**Root cause:** A cloud app administrator (Azure AD admin, Google Workspace admin, Box admin) revokes or modifies the API permissions granted to CloudSOC. Without the required permissions, CloudSOC cannot read file content.
**Mitigation:** Document all API permissions granted to CloudSOC in a central registry. Implement monitoring for permission changes in Azure AD audit logs, Google Admin audit, and Box admin events. Set up periodic permission verification tests.
**Evidence:** B [S24, V-tribal]

### G-CD-25: Cloud app data residency requirements conflict with CDS scanning
**Impact:** MEDIUM
**Symptom:** EU legal team objects that customer data in EU-hosted SharePoint sites is being sent to US-hosted CDS for DLP scanning.
**Root cause:** CDS may be hosted in a different region than the cloud app data. Sending data to CDS for scanning may violate GDPR or other data residency requirements.
**Mitigation:** Use the EU CloudSOC endpoint (`app.eu.elastica.net`) for EU customers. Verify CDS hosting region matches your data residency requirements. For strict residency requirements, consider on-prem Enforce with Distributed Detection Service (DDS) -- self-hosted DLP detection within your own infrastructure.
**Evidence:** B [S11, S24]

### G-CD-26: Shadow IT discovery only works with proxy mode deployed
**Impact:** LOW (expectations management)
**Symptom:** CloudSOC Dashboard shows zero unsanctioned apps despite knowing employees use personal cloud storage.
**Root cause:** Shadow IT discovery requires proxy-based traffic analysis. Without the cloud proxy (WSS/SWG), CloudSOC has no visibility into which cloud apps users are accessing.
**Mitigation:** Deploy Symantec Web Security Service (WSS/SWG) proxy for Shadow IT discovery. If proxy deployment is not feasible, use endpoint DLP (Cloud File Sync channel) as a partial alternative for detecting personal cloud storage use.
**Evidence:** A [S24]

---

## Gotcha Severity Summary

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 6 | G-CD-1, G-CD-2, G-CD-11, G-CD-16, G-CD-17, G-CD-24 |
| MEDIUM | 13 | G-CD-3, G-CD-4, G-CD-5, G-CD-6, G-CD-7, G-CD-10, G-CD-12, G-CD-13, G-CD-15, G-CD-18, G-CD-19, G-CD-21, G-CD-22, G-CD-25 |
| LOW | 7 | G-CD-8, G-CD-9, G-CD-14, G-CD-20, G-CD-23, G-CD-26 |

[S1, S2, S11, S24, V34, V35, V-tribal, API-intelligence] Evidence: A-B
