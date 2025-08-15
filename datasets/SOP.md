Here is the **final, comprehensive Standard Operating Procedure (SOP)** tailored for the ANZ Bank Fraud Use Case, integrating your detailed fraud transaction protocols, triage decision rules, customer interaction scripting, escalation framework, and compliance references. This SOP is designed for operational teams and agentic AI systems handling fraud alerts for ANZ Bank.

# 🛡️ STANDARD OPERATING PROCEDURE (SOP)  
**Title:** ANZ Bank Fraud Transaction Protocol (FTP) Alert Handling & Triage Agent Decision Protocol  
**Department:** ANZ Fraud Risk & Intelligence  
**Issued By:** Head of Financial Crime Compliance, ANZ Bank  
**Effective Date:** 19 December 2024  
**Version:** 4.0  
**Applies To:** ANZ Fraud Analysts, Triage Agents, Digital Operations, Contact Centre, Case Management Teams, AI Agentic Systems

## 1. PURPOSE  
To establish a **structured, compliant, and risk-driven framework** for identifying, validating, triaging, and resolving suspected fraudulent financial activity detected via ANZ’s Fraud Transaction Protocol (FTP) alerting system. This SOP ensures:  
- Customer protection and harm minimisation  
- Regulatory compliance with APRA, ASIC, Scamwatch, AUSTRAC, and ANZ internal policies  
- Efficient, data-driven analyst and agent response using rule-based and GenAI-enhanced methodologies

## 2. SCOPE  
Applies to:  
- All FTP-generated alerts across ANZ channels: Online Banking, Mobile App, SWIFT, PayID, BPAY, etc.  
- Threat vectors including credential compromise, phishing, account takeover, investment/romance scams, remote access frauds, business email compromise (BEC), invoice redirection, and device/IP anomalies.

## 3. FTP ALERT INPUTS & CONTEXT MANAGEMENT  
Alerts are ingested and orchestrated via **MCP (Model Context Protocol)**, generating structured, strongly-typed JSON contexts:  
- **TransactionContext:** Transaction details (txn_id, amount, timestamp, location)  
- **UserContext:** Customer demographics, transaction & call history  
- **MerchantContext:** Merchant risk profiles and past reports  
- **DeviceContext:** Device ID, geo-location, login anomalies  
- **SOPContext:** ANZ Bank policies, fraud rules, exceptions  
- **AlertContext:** FTP metadata (alertId, ruleId, priority, description)  

All context reads/writes are logged with ownership, TTL, and versioning metadata for auditability by ANZ.

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
“Hi [Customer Name], this is [Agent Name] from ANZ’s Fraud Team. We’ve noticed a potentially suspicious transaction on your ANZ account and need to confirm some details.”  

If crypto/investment related:  
“We understand you sent $[Amount] to [Entity]. Please confirm how you were introduced to them. Are you aware if they are ASIC licensed?”

## 6. ESCALATION FRAMEWORK  

| Tier     | Role                     | Responsibilities                                         |
|----------|--------------------------|----------------------------------------------------------|
| Tier 1   | ANZ Triage Analyst           | Case intake, customer calls, documentation in CMS        |
| Tier 2   | ANZ Fraud Lead / Team Leader | Complex cases (> $20k, overseas, legal risk), fund blocking decisions |
| Tier 3   | ANZ Legal / Compliance       | Police reports, scam recovery, regulator reporting (AUSTRAC/ASIC) |

## 7. SLA & TIMELINES  

| Priority | Call SLA   | Resolution SLA | Monitoring Frequency |
|----------|------------|---------------|---------------------|
| High     | 30 minutes | 2 hours       | Daily               |
| Medium   | 2 hours    | 6 hours       | Bi-weekly           |
| Low      | Same day   | 24 hours      | Monthly QA          |

## 8. SYSTEMS & DOCUMENTATION  

- ANZ CRM & CMS systems to record all customer interactions, analyst notes, and case decisions  
- Audio logs retained for 90 days  
- All resolved alerts tagged with SOP adherence flags for audit  

## 9. AUDIT, SECURITY & GOVERNANCE  

- Full MCP logs of context reads/writes, tool calls, decisions, and timestamps (ANZ)  
- Role-based ACLs and data guardrails to prevent unauthorized data access  
- MCP servers enforce schema validation and security controls  
- Compliance with ANZ enterprise risk frameworks ([k2view.com], [swimlane.com], [anthropic.com])  

## 10. COMPLIANCE & REFERENCES  

- **APRA CPG 234** (Prudential Standard for Information Security) - Information security controls and customer protection requirements
- **ASIC RG 271** (Internal Dispute Resolution) - Consumer harm prevention and scam prevention guidelines  
- **AUSTRAC AML/CTF Act 2024** - Anti-money laundering and counter-terrorism financing regulations
- **Scamwatch.gov.au** - Australian government scam reporting and prevention
- **ANZ Fraud Money Back Guarantee** - Customer protection for fraudulent transactions
- **ANZ Falcon®** - ANZ's anti-fraud technology preventing $112M in losses in 2023
- **Confirmation of Payee** - Account name matching service for payment security
- **Digital Padlock** - Real-time account locking capability for cybercrime protection
- **Passwordless Web Banking** - Advanced authentication methods for ANZ Plus  

## 11. REVISION HISTORY  

| Version | Date       | Notes                                           |
|---------|------------|-------------------------------------------------|
| 4.0     | 2024-12-19 | Production-ready SOP with current ANZ policies, enhanced MCP integration, and AI agentic systems |
| 3.1     | 2025-07-10 | Added MCP orchestration, GenAI agent logic, audit guardrails (ANZ) |
| 3.0     | 2025-07-08 | Combined FTP SOP with agent-based triage rules  |
| 2.1     | 2025-07-06 | Defined fraud strategy thresholds                |
| 2.0     | 2025-06-30 | Legacy triage-only framework                      |

**This SOP is mandatory for all ANZ personnel and systems involved in fraud alert handling and triage at ANZ. Strict adherence ensures customer safety, regulatory compliance, and operational excellence.**

# Expanded SOP for richer RAG

## 12. ADDITIONAL FRAUD SCENARIOS & ESCALATION CRITERIA

| Fraud Type                     | Rule ID     | Call Required IF…                                                      | Skip Call IF…                                  |
|-------------------------------|-------------|------------------------------------------------------------------------|-----------------------------------------------|
| Romance Scam                   | RUL-RS001   | Large transfer to new overseas individual met online                   | Customer confirms in-person relationship      |
| Mule Account                   | RUL-MA002   | Multiple inbound/outbound transfers with no clear source/purpose        | Legitimate business with documentation        |
| Phishing/Smishing              | RUL-PS003   | Login from new device after suspicious SMS/email, followed by transfer  | Customer confirms no suspicious comms         |
| Social Engineering             | RUL-SE004   | Customer pressured to transfer funds urgently, mentions "bank staff"    | Customer confirms no external pressure        |
| Authorized Push Payment (APP)  | RUL-APP005  | Customer authorizes large payment to new payee under duress             | Customer confirms payment was voluntary       |
| Synthetic Identity             | RUL-SI006   | New account with mismatched ID, rapid high-value activity               | All KYC checks passed, no anomalies           |
| Insider Threat                 | RUL-IT007   | Unusual access by staff to dormant/high-value accounts                  | Access justified by work order                |
| Business Email Compromise      | RUL-BEC008  | Vendor payment details changed after suspicious email                   | Change verified via secure channel            |

### Escalation Triggers
- Any transaction >$20,000 to new payee or overseas (ANZ)
- Multiple failed login attempts followed by successful high-value transfer (ANZ)
- Customer reports being on a call with "ANZ bank staff" or "police"
- Device/IP mismatch with customer profile (ANZ)
- Any case matching AUSTRAC/ASIC/Scamwatch typologies

### Compliance Notes
- All escalations must be logged with reason and supporting evidence (ANZ)
- Adhere to APRA CPG 234, ASIC RG 271, AUSTRAC AML/CTF Act, and ANZ internal policies
- For APP fraud, follow Scamwatch and UK APP code best practices (ANZ)
- For synthetic identity, reference AUSTRAC and KYC/AML guidelines (ANZ)
- For insider threat, notify ANZ compliance and HR immediately

# --- FRAUD SOP STRUCTURED BLOCKS ---

---
fraud_type: RUL-BEC008
call_required_if:
  - Vendor bank details changed via email/request
  - Abbreviated/altered vendor name in invoice or email
  - Duplicate invoice reference or redirection request
skip_call_if:
  - Change verified directly with vendor via a secure, previously known channel (phone number from prior invoice/website)
finalize_if:
  - change_not_verified_via_secure_channel AND (duplicate_invoice OR vendor_name_manipulation)
escalation_triggers:
  - Any BEC with confirmed payment sent to new account details
  - Repeat victim indicators or prior BEC history
compliance_notes:
  - APRA CPG 234
  - AUSTRAC AML/CTF Act (Suspicious Matter Report if funds misdirected)
  - ASIC RG 271 (customer protection)
---
# Add more fraud types as needed in the same format.
fraud_type: RUL-TX901
call_required_if:
  - Transfer > $5,000 within 60 mins of password change AND unknown payee
skip_call_if:
  - Payee trusted > 3 months
  - Transaction matches usual behaviour
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
  - Multiple failed login attempts followed by successful high-value transfer (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX817
call_required_if:
  - New device login + transfer > $10,000 to investment/crypto platform
skip_call_if:
  - Biometrics verified
  - Device previously approved
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX488
call_required_if:
  - New investment > $5,000 to unlicensed/unverified entity or blacklist match
skip_call_if:
  - No skip allowed
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX778
call_required_if:
  - >80% balance transferred to unknown/crypto or multiple rapid transfers
skip_call_if:
  - No skip allowed
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX234
call_required_if:
  - First-time offshore transfer > $10,000 to high-risk jurisdiction
skip_call_if:
  - Licensed entity AND pattern regular
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX155
call_required_if:
  - Daily small transfers > 3 days totaling > $2,000 with round amounts
skip_call_if:
  - Matches existing legitimate pattern
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX230
call_required_if:
  - Vendor bank details changed & payment >10% deviation from norm
skip_call_if:
  - Securely verified change
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
fraud_type: RUL-TX817v2
call_required_if:
  - Unverified device + >50% balance moved to crypto out-of-hours
skip_call_if:
  - No skip allowed
escalation_triggers:
  - Any transaction >$20,000 to new payee or overseas (ANZ)
compliance_notes:
  - APRA CPG 234
  - ASIC Scams Database
  - AUSTRAC AML Guidelines
---
# Add more fraud types as needed in the same format.