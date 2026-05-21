# Network DLP — Quickstart Guide
## Broadcom Symantec DLP (Enforce Server, version 16.x/25.x/26.x)

> **Goal:** Set up email monitoring using Network Monitor to passively detect PCI data in outbound SMTP traffic.
> **Time estimate:** 60-90 minutes (includes server setup, SPAN configuration, and first detection).
> **Prerequisites:** Enforce Server running, Oracle DB operational, a dedicated server with 2 NICs, access to core network switch for SPAN/mirror configuration.

---

## The 6-Step Fast Path

```
Step 1: Install Network Monitor Server (dedicated server, 2 NICs)
Step 2: Configure SPAN/mirror port on core switch
Step 3: Verify SMTP traffic is reaching the monitoring interface
Step 4: Create PCI detection policy
Step 5: Send a test email with credit card numbers
Step 6: Verify incident in Enforce console
```

---

## Step 1: Install Network Monitor Server

1. Prepare a dedicated server (Linux recommended) with 2 network interfaces:
   - **NIC 1 (eth0):** Management interface -- connects to corporate LAN, communicates with Enforce Server
   - **NIC 2 (eth1):** Monitoring interface -- receives mirrored traffic from switch SPAN port

2. Run the Symantec DLP Detection Server installer
3. During installation, select **"Network Monitor"** as the server type
4. Enter the Enforce Server hostname: `dlp-enforce01.corp.example.com`
5. Complete installation

6. Verify in Enforce console: **System > Servers and Detectors > Overview**

```
+=========================================================================+
|  System > Servers and Detectors > Overview                               |
+=========================================================================+
|  +-------------------------------------------------------------------+ |
|  | Server Name              | Type              | Status   | Version | |
|  |--------------------------|-------------------|----------|--------| |
|  | dlp-netmon01.corp.example| Network Monitor   | Running  | 16.0   | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

[S1, S4, S19, V11] Evidence: A

---

## Step 2: Configure SPAN/Mirror Port

On your core network switch, configure port mirroring to copy SMTP traffic to the Network Monitor's monitoring interface.

**Cisco IOS Example:**
```
interface GigabitEthernet0/24
  description DLP-Network-Monitor-SPAN
  switchport mode access
!
monitor session 1 source interface GigabitEthernet0/1 - 23 both
monitor session 1 destination interface GigabitEthernet0/24
monitor session 1 filter ip address
```

**Cisco Nexus Example:**
```
monitor session 1 type erspan-source
  source interface Ethernet1/1-48 both
  destination ip 10.1.50.200
  erspan-id 100
  no shut
```

**Key requirements:**
- Mirror traffic from interfaces carrying outbound email (SMTP ports 25, 587)
- Destination: the monitoring NIC (eth1) on the Network Monitor Server
- Verify the SPAN port is not oversubscribed (mirror of all traffic may exceed port bandwidth)

[S1, S4] Evidence: A

---

## Step 3: Verify Traffic Reaching Monitor

On the Network Monitor Server, verify SMTP traffic is visible on the monitoring interface:

```bash
# On the Network Monitor Server (Linux)
sudo tcpdump -i eth1 -c 20 port 25
```

Expected output:
```
10:15:23.456789 IP 10.1.50.101.12345 > mail01.corp.example.com.25: Flags [S], seq 12345
10:15:23.456890 IP mail01.corp.example.com.25 > 10.1.50.101.12345: Flags [S.], seq 67890
...
```

If you see SMTP traffic (port 25), the SPAN port is working correctly. If no traffic appears, verify:
- SPAN session is configured correctly on the switch
- The monitoring NIC is in promiscuous mode (the DLP service enables this automatically)
- The cable is connected to the correct switch port

[S1] Evidence: A

---

## Step 4: Create PCI Detection Policy

**Navigation:** Manage > Policies > Policy List > New Policy > Template List

1. Click **New Policy** > **Template List**
2. Select **"PCI DSS - Credit Card Numbers"**
3. Click **Next**
4. Configure the policy:

```
+=========================================================================+
|  New Policy from Template: PCI DSS - Credit Card Numbers                 |
+=========================================================================+
|  Policy Name:  [PCI-Network-Monitor-QuickStart              ]           |
|  Description:  [Monitor outbound email for credit card data  ]          |
|                                                                         |
|  Policy Group: [Default Policy Group                      v]           |
|                (ensure Network Monitor is in this group)                 |
|                                                                         |
|  Detection Rules (from template):                                        |
|  +-------------------------------------------------------------------+ |
|  | Rule: Content Matches Data Identifier                              | |
|  |   Data Identifier: Credit Card Number (Luhn check)                | |
|  |   Min unique matches: 1                                            | |
|  |   Severity: High                                                   | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  Policy Status: (o) Enabled                                             |
|                 ( ) Test With Notifications                              |
|                 ( ) Disabled                                             |
|                                                                         |
+=========================================================================+
```

5. Set Status to **Enabled** (Network Monitor is passive -- no risk of blocking)
6. Click **Save**

**Note:** Since Network Monitor is passive (it only observes traffic), you can safely enable the policy immediately. There is no risk of blocking or disrupting email flow.

[S1, S4, V16] Evidence: A

---

## Step 5: Send a Test Email

From a machine whose email traffic flows through the monitored network path, send a test email containing credit card numbers.

1. Open your email client (Outlook, webmail, etc.)
2. Compose a new email:
   - **To:** testrecipient@external-domain.com (or an internal test address)
   - **Subject:** DLP Test - PCI Detection
   - **Body:**
   ```
   Customer Payment Information:
   Visa: 4111111111111111
   MasterCard: 5500000000000004
   Amex: 340000000000009
   ```
3. Send the email

The email will be delivered normally (Network Monitor does not block). The DLP server inspects the copy of the traffic and generates an incident.

[S1] Evidence: A

---

## Step 6: Verify Incident in Enforce Console

**Navigation:** Incidents > Network > Incident List

Wait 1-5 minutes for the Network Monitor to process the traffic and report the incident.

```
+=========================================================================+
|  Incidents > Network                                                     |
+=========================================================================+
|  +-------------------------------------------------------------------+ |
|  | ID     | Policy                         | Severity | Protocol    | |
|  |--------|--------------------------------|----------|------------| |
|  | 10001  | PCI-Network-Monitor-QuickStart | High     | SMTP       | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

Click the incident to see details:

```
+=========================================================================+
|  Incident Detail: 10001                                                  |
+=========================================================================+
|  Policy:       PCI-Network-Monitor-QuickStart                           |
|  Severity:     High                                                      |
|  Status:       New                                                       |
|  Protocol:     SMTP                                                      |
|  Sender:       jsmith@corp.example.com                                   |
|  Recipient:    testrecipient@external-domain.com                         |
|  Subject:      DLP Test - PCI Detection                                  |
|  Detected:     2025-05-21 10:18:23 AM                                   |
|                                                                         |
|  Matches:                                                                |
|  +-------------------------------------------------------------------+ |
|  | Rule                    | Match                | Count             | |
|  |-------------------------|--------------------- |-------------------| |
|  | Credit Card Number      | 4111111111111111     | 3 unique matches  | |
|  |                         | 5500000000000004     |                   | |
|  |                         | 340000000000009      |                   | |
|  +-------------------------------------------------------------------+ |
+=========================================================================+
```

Detection is working. The Network Monitor is passively monitoring outbound email and detecting credit card data.

[S1, S4] Evidence: A

---

## What's Next

After validating the quickstart:

1. **Add email prevention** -- Deploy Network Prevent for Email to actively block/quarantine emails containing PCI data (see workflow.md Phase 2)
2. **Add web prevention** -- Deploy Network Prevent for Web to monitor/block web uploads (see workflow.md Phase 3)
3. **Scan data at rest** -- Deploy Network Discover to scan file shares for stored PCI data (see workflow.md Phase 4)
4. **Add response rules** -- Configure syslog forwarding to SIEM, email notifications to compliance team
5. **Enable additional protocols** -- Enable HTTP and FTP monitoring on the Network Monitor for broader visibility
6. **SSL inspection** -- Enable SSL/TLS inspection to monitor encrypted traffic
7. **Review gotchas.md** -- Understand SSL certificate issues, ICAP performance tuning, and scan credential management

---

## Quick Reference: Key Navigation Paths

| Task | Navigation |
|------|-----------|
| View detection servers | System > Servers and Detectors > Overview |
| Configure Network Monitor | System > Servers and Detectors > [server] > Configure |
| Manage policy groups | System > Servers and Detectors > Policy Groups |
| Create policy from template | Manage > Policies > Policy List > New Policy > Template List |
| Create response rule | Manage > Policies > Response Rules > Add Response Rule |
| View network incidents | Incidents > Network > Incident List |
| Manage Discover targets | Manage > Discover Scanning > Discover Targets |

[S1, S4] Evidence: A
