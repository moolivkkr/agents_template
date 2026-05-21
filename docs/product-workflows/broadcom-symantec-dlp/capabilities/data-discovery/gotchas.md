# Gotchas: Data Discovery (Network Discover)

> **Source:** Broadcom TechDocs, Network Discover Tuning Guide [S17], Video Intelligence Report, Community KB articles
> **Impact Ratings:** CRITICAL = blocks scanning / loses data; HIGH = significant operational impact; MEDIUM = performance or accuracy degradation; LOW = minor inconvenience

---

## Scan Performance

### 1. Initial Full Scan on Large File Shares Can Take Days (HIGH)

**Problem:** A full scan of a 10 TB file share with millions of files can run for 48-72 hours, consuming significant network bandwidth and Discover server resources.

**Symptoms:** Scan shows "Running" for days; other scans queue behind it; users report slow file server access.

**Mitigation:**
- Schedule initial full scans during long weekends or maintenance windows
- Use content filters to restrict first scan (e.g., only `.docx`, `.xlsx`, `.pdf`)
- Enable bandwidth throttling during business hours
- Split large shares into multiple scan targets for parallel execution
- After initial full scan, switch to incremental (80-95% faster)

### 2. High Speed Discovery Requires DLP 16.1+ and File System Targets Only (MEDIUM)

**Problem:** High Speed Discovery (up to 1 TB/hour) only works with file system (CIFS) targets. SharePoint, Exchange, database, and cloud targets use standard scanning speeds.

**Symptoms:** Admin enables High Speed Discovery but sees no improvement for non-file-system targets.

**Mitigation:** Use High Speed Discovery for CIFS targets; accept standard scan speeds for other target types; plan scan windows accordingly.

### 3. Antivirus on the Discover Server Scans Every Extracted File (HIGH)

**Problem:** Antivirus software on the Network Discover Server intercepts every file downloaded for content inspection, effectively scanning each file twice (AV + DLP). This can halve throughput.

**Symptoms:** Discover server CPU at 100%; scan throughput far below expected; AV quarantines DLP temp files.

**Mitigation:** Exclude the Discover server's temporary extraction directory from AV real-time scanning. The specific path depends on installation, typically: `<install_dir>\Protect\temp\` or `/opt/Vontu/Protect/temp/`

---

## Credential Management

### 4. Service Account Password Expiry Causes Silent Scan Failures (HIGH)

**Problem:** When the service account password expires, scans fail to connect to targets. The failure is logged but not always surfaced prominently to admins.

**Symptoms:** Scans that were running successfully suddenly show "Failed" or "Completed with errors"; scan logs show authentication failures.

**Mitigation:**
- Use Group Managed Service Accounts (gMSA) for automatic password rotation
- If using standard accounts, set calendar reminders for password renewal
- Monitor System Events (System > Servers and Detectors > Events) for authentication errors
- Create a system event alert for credential failure events

### 5. Credential Storage Is Per-Target, Not Centralized (MEDIUM)

**Problem:** Each scan target stores its own credentials. If the service account password changes, you must update it in every target that uses that account.

**Symptoms:** After password rotation, some scans succeed (updated targets) while others fail (missed targets).

**Mitigation:**
- Document which targets use which service accounts
- Use gMSA to avoid manual password updates
- Consider a naming convention that maps targets to service accounts
- After password rotation, verify all scans succeed in the next cycle

---

## Incremental Scan Limitations

### 6. Incremental Scan Cache Corruption Forces Full Re-Scan (MEDIUM)

**Problem:** The scan cache that tracks file modification timestamps can become corrupted (server crash, disk failure, abrupt scan termination). When corrupted, the next "incremental" scan becomes a full scan.

**Symptoms:** An incremental scan takes as long as the original full scan; Discover server disk usage spikes as the cache is rebuilt.

**Mitigation:**
- Monitor incremental scan duration -- if it suddenly equals full scan duration, the cache was rebuilt
- Ensure Discover server has reliable storage (RAID, SSD)
- Do not force-kill scan processes; use the Stop button in the console

### 7. Incremental Scans Miss Files With Unchanged Timestamps (LOW)

**Problem:** Incremental scanning relies on file modification timestamps. If a file's content changes but its modification timestamp is preserved (e.g., by backup restore, file copy with timestamp preservation), the incremental scan skips it.

**Symptoms:** Known-sensitive files are not detected after a backup restore or migration.

**Mitigation:** Run a periodic full scan (quarterly) to catch files with preserved timestamps; be aware of this limitation after any large-scale file migration or backup restore.

### 8. Policy Changes Require Full Re-Scan (MEDIUM)

**Problem:** When you add a new detection policy to the Discover server's policy group, existing incremental scan results were generated against the old policy set. Previously-scanned files that violate the new policy will not be detected until the next full scan.

**Symptoms:** New policy added but no incidents appear for data that was scanned before the policy existed.

**Mitigation:** After adding a new policy, run a one-time full scan on critical targets. Then resume incremental scanning.

---

## Target-Specific Issues

### 9. SharePoint Throttling (HTTP 429) Slows Scans to a Crawl (HIGH)

**Problem:** SharePoint aggressively throttles API calls. When the Discover server hits the throttle limit, SharePoint returns HTTP 429 responses and the scan pauses/retries.

**Symptoms:** SharePoint scan progress stalls; scan takes 10x longer than expected; SharePoint admin reports excessive API calls.

**Mitigation:**
- Reduce concurrent connections to SharePoint targets (e.g., from 10 to 3)
- Schedule scans during off-peak hours
- Contact SharePoint admin to request throttling limit increases
- Split large SharePoint farms into multiple targets (one per site collection)

### 10. DFS Scanning Requires Windows-Based Discover Server (HIGH)

**Problem:** DFS namespace resolution uses Windows-only APIs. A Linux-based Network Discover Server cannot resolve DFS paths.

**Symptoms:** DFS scan target creation fails; scan starts but cannot enumerate files under DFS root.

**Mitigation:** Deploy at least one Windows-based Network Discover Server for DFS targets. Linux Discover Servers can handle all other target types.

### 11. Exchange ApplicationImpersonation Scope Is Too Broad by Default (MEDIUM)

**Problem:** The ApplicationImpersonation role, when granted without a management scope, allows the service account to impersonate ALL mailboxes in the organization. This is a security risk.

**Symptoms:** No immediate symptoms -- this is a privilege escalation risk.

**Mitigation:** Create a custom management scope that limits impersonation to only the mailboxes you need to scan:
```powershell
New-ManagementScope -Name "DLP Scan Scope" -RecipientRestrictionFilter {Department -eq "Finance"}
New-ManagementRoleAssignment -Name "DLP Scanner" -Role ApplicationImpersonation -User "dlp-exchange-svc" -CustomRecipientWriteScope "DLP Scan Scope"
```

### 12. JDBC Driver Version Mismatch Causes Database Scan Failures (MEDIUM)

**Problem:** The JDBC driver installed on the Discover server must match the target database version. Mismatched drivers cause connection failures or silent data truncation.

**Symptoms:** Database scan fails with "Connection refused" or "Unsupported protocol version"; scan connects but returns fewer results than expected.

**Mitigation:**
- Oracle: Use ojdbc8.jar for Oracle 12c+; ojdbc11.jar for Oracle 19c+
- SQL Server: Use mssql-jdbc matching your SQL Server version
- DB2: Use db2jcc4.jar for DB2 10.5+
- Test connectivity with a simple JDBC client before configuring the scan target

### 13. Cloud OAuth Token Expiry Stops Scans Without Warning (MEDIUM)

**Problem:** OAuth tokens for cloud storage scanning (Box, Google Drive, OneDrive) expire. If auto-refresh fails, scans stop.

**Symptoms:** Cloud scans that were running successfully suddenly fail; CloudSOC shows "Authorization Required" status.

**Mitigation:** CloudSOC handles auto-refresh for most providers, but admin consent may need to be re-granted periodically (especially Microsoft 365 after Conditional Access policy changes). Monitor CloudSOC connection health dashboard.

---

## Capacity and Storage

### 14. Evidence Storage Growth from Discovery Scans (HIGH)

**Problem:** Each discovery incident stores matched content snippets and metadata in the Enforce database. Scanning millions of files across many targets generates massive incident volumes, growing the Oracle database.

**Symptoms:** Oracle database disk usage grows rapidly; Enforce Console performance degrades; backup duration increases.

**Mitigation:**
- Use the **Limit Incident Data Retention** response rule action to auto-purge old discovery incidents
- Set retention periods: keep discovery incidents for 90-180 days, not indefinitely
- Archive incident data before purging
- Monitor Oracle tablespace usage
- Use content filters to reduce scan scope (don't scan everything if you don't need to)

### 15. Quarantine Storage Fills Up (MEDIUM)

**Problem:** When Network Protect quarantines files, they accumulate in the quarantine directory. Without cleanup, the quarantine share fills up and Protect actions fail.

**Symptoms:** Quarantine actions fail with "disk full" errors; new quarantine operations are skipped.

**Mitigation:**
- Define a quarantine retention policy (e.g., delete quarantined files after 180 days if not restored)
- Monitor quarantine share disk usage
- Set up automated cleanup for aged quarantine files
- Size the quarantine share to at least 10% of total scanned data volume

---

## Accuracy

### 16. OCR Scanning Misses Low-Quality Images (LOW)

**Problem:** OCR in Network Discover works well on high-quality scanned documents but struggles with low-resolution images, handwritten text, or heavily compressed JPEGs.

**Symptoms:** Known-sensitive content in images is not detected; false negative rate higher for image-heavy file shares.

**Mitigation:** OCR is best-effort; for critical image-based documents (scanned tax forms, medical records), consider supplementing with Form Recognition and IDM (fingerprinting) detection technologies. Set realistic expectations for image-based detection.

### 17. Encrypted Files Cannot Be Scanned (MEDIUM)

**Problem:** Files encrypted with client-side encryption (BitLocker, VeraCrypt, PGP-encrypted files) cannot have their content extracted for scanning. DLP detects that the file is encrypted but cannot inspect the content.

**Symptoms:** Encrypted files show as "Content not available" or generate a file-property-based incident (encrypted file detected) but no content-based violations.

**Mitigation:**
- Create a policy that detects and flags encrypted files as a finding itself ("encrypted file found on file share")
- For organizational encryption (e.g., MIP encryption), ensure DLP has access to decryption keys
- Use Endpoint Prevent to scan content before encryption occurs

---

## Operational

### 18. Scan Target Deletion Does Not Delete Incidents (LOW)

**Problem:** Deleting a scan target from the Enforce Console removes the target configuration but does not delete incidents previously generated by that target. This can cause confusion.

**Symptoms:** Incidents reference a scan target that no longer exists; incident remediation links to non-existent targets.

**Mitigation:** Before deleting a scan target, resolve or archive all associated incidents. Use incident search to find all incidents from the target, then bulk-update status to "Resolved" before deleting the target.

### 19. Multiple Discover Servers Scanning Same Path Creates Duplicate Incidents (MEDIUM)

**Problem:** If two Network Discover Servers scan overlapping paths (e.g., both scan `\\fileserver01\data\`), each server creates its own incidents. This doubles the incident count for the same files.

**Symptoms:** Duplicate incidents for the same file, each from a different Discover server.

**Mitigation:** Ensure scan target paths do not overlap between Discover servers. Use a target naming convention that includes the Discover server name. Document which server owns which scan targets.
