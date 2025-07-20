Here is the **final, comprehensive Standard Operating Procedure (SOP)** tailored for the ANZ Fraud Use Case, integrating your detailed fraud transaction protocols, triage decision rules, customer interaction scripting, escalation framework, and compliance references. This SOP is designed for operational teams and agentic AI systems handling fraud alerts.

# 🛡️ STANDARD OPERATING PROCEDURE (SOP)  
**Title:** Fraud Transaction Protocol (FTP) Alert Handling & Triage Agent Decision Protocol  
**Department:** Fraud Risk & Intelligence  
**Issued By:** Head of Financial Crime Compliance  
**Effective Date:** 08 July 2025  
**Version:** 3.1  
**Applies To:** Fraud Analysts, Triage Agents, Digital Operations, Contact Centre, Case Management Teams

## 1. PURPOSE  
To establish a **structured, compliant, and risk-driven framework** for identifying, validating, triaging, and resolving suspected fraudulent financial activity detected via ANZ’s Fraud Transaction Protocol (FTP) alerting system. This SOP ensures:  
- Customer protection and harm minimisation  
- Regulatory compliance with APRA, ASIC, Scamwatch, AUSTRAC  
- Efficient, data-driven analyst and agent response using rule-based and GenAI-enhanced methodologies

## 2. SCOPE  
Applies to:  
- All FTP-generated alerts across channels: Online Banking, Mobile App, SWIFT, PayID, BPAY, etc.  
- Threat vectors including credential compromise, phishing, account takeover, investment/romance scams, remote access frauds, business email compromise (BEC), invoice redirection, and device/IP anomalies.

## 3. FTP ALERT INPUTS & CONTEXT MANAGEMENT  
Alerts are ingested and orchestrated via **MCP (Model Context Protocol)**, generating structured, strongly-typed JSON contexts:  
- **TransactionContext:** Transaction details (txn_id, amount, timestamp, location)  
- **UserContext:** Customer demographics, transaction & call history  
- **MerchantContext:** Merchant risk profiles and past reports  
- **DeviceContext:** Device ID, geo-location, login anomalies  
- **SOPContext:** Bank policies, fraud rules, exceptions  
- **AlertContext:** FTP metadata (alertId, ruleId, priority, description)  

All context reads/writes are logged with ownership, TTL, and versioning metadata for auditability.

## 4. FRAUD STRATEGIES & TRIAGE DECISION RULES  

| Fraud Type                     | Rule ID     | Call Required IF…                                                      | Skip Call IF…                                  |
|-------------------------------|-------------|------------------------------------------------------------------------|-----------------------------------------------|
| Password Change + Large Transfer | RUL-TX901   | Transfer > $5,000 within 60 mins of password change AND unknown payee   | Payee trusted > 3 months, transaction matches usual behaviour |
| New Device + Large Transfer    | RUL-TX817   | New device login + transfer > $10,000 to investment/crypto platform     | Biometrics verified, device previously approved |
| Investment Scam (First Time)   | RUL-TX488   | New investment > $5,000 to unlicensed/unverified entity or blacklist match | *No skip allowed*                             |
| Full Balance Outflow           | RUL-TX778   | >80% balance transferred to unknown/crypto or multiple rapid transfers  | *No skip allowed*                             |
| Offshore Investment            | RUL-TX234   | First-time offshore transfer > $10,000 to high-risk jurisdiction         | Licensed entity AND pattern regular           |
| Drip Transfer Anomaly          | RUL-TX155   | Daily small transfers > 3 days totaling > $2,000 with round amounts     | Matches existing legitimate pattern           |
| Business Invoice Redirection   | RUL-TX230   | Vendor bank details changed & payment >10% deviation from norm          | Securely verified change                       |
| New Device + Account Cleanout  | RUL-TX817v2 | Unverified device + >50% balance moved to crypto out-of-hours           | *No skip allowed*                             |

## 5. CUSTOMER INTERACTION SCRIPTING & VALIDATION  

**Identity Verification:**  
- Full Name  
- Date of Birth  
- Recent Transaction or Address  
- Optional: Email or Phone used in last login  

**Sample Script:**  
“Hi [Customer Name], this is [Agent Name] from ANZ’s Fraud Team. We’ve noticed a potentially suspicious transaction on your account and need to confirm some details.”  

If crypto/investment related:  
“We understand you sent $[Amount] to [Entity]. Please confirm how you were introduced to them. Are you aware if they are ASIC licensed?”

## 6. ESCALATION FRAMEWORK  

| Tier     | Role                     | Responsibilities                                         |
|----------|--------------------------|----------------------------------------------------------|
| Tier 1   | Triage Analyst           | Case intake, customer calls, documentation in CMS        |
| Tier 2   | Fraud Lead / Team Leader | Complex cases (> $20k, overseas, legal risk), fund blocking decisions |
| Tier 3   | Legal / Compliance       | Police reports, scam recovery, regulator reporting (AUSTRAC/ASIC) |

## 7. SLA & TIMELINES  

| Priority | Call SLA   | Resolution SLA | Monitoring Frequency |
|----------|------------|---------------|---------------------|
| High     | 30 minutes | 2 hours       | Daily               |
| Medium   | 2 hours    | 6 hours       | Bi-weekly           |
| Low      | Same day   | 24 hours      | Monthly QA          |

## 8. SYSTEMS & DOCUMENTATION  

- CRM & CMS systems to record all customer interactions, analyst notes, and case decisions  
- Audio logs retained for 90 days  
- All resolved alerts tagged with SOP adherence flags for audit  

## 9. AUDIT, SECURITY & GOVERNANCE  

- Full MCP logs of context reads/writes, tool calls, decisions, and timestamps  
- Role-based ACLs and data guardrails to prevent unauthorized data access  
- MCP servers enforce schema validation and security controls  
- Compliance with enterprise risk frameworks ([k2view.com], [swimlane.com], [anthropic.com])  

## 10. COMPLIANCE & REFERENCES  

- APRA CPG 234 (Prudential Standard)  
- ASIC Scams Database  
- AUSTRAC AML Guidelines  
- Scamwatch.gov.au  
- ANZ internal Fraud Money Back Guarantee and card security policies  

## 11. REVISION HISTORY  

| Version | Date       | Notes                                           |
|---------|------------|-------------------------------------------------|
| 3.1     | 2025-07-10 | Added MCP orchestration, GenAI agent logic, audit guardrails |
| 3.0     | 2025-07-08 | Combined FTP SOP with agent-based triage rules  |
| 2.1     | 2025-07-06 | Defined fraud strategy thresholds                |
| 2.0     | 2025-06-30 | Legacy triage-only framework                      |

**This SOP is mandatory for all personnel and systems involved in fraud alert handling and triage at ANZ. Strict adherence ensures customer safety, regulatory compliance, and operational excellence.**