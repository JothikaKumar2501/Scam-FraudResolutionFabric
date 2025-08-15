# ANZ BANK AI AGENT - Enhanced Fraud Detection Questions & Scripts

This is a comprehensive list of questions and scripts for the ANZ BANK AI AGENT, based on the enhanced dataset structure and current ANZ Bank policies. All questions and scripts are for ANZ BANK AI AGENT. Modify and formulate the questions accordingly. Do not hallucinate the Questions. Strictly follow ANZ rules and context, and only ask relevant questions. Minimize the number of questions you ask (make this super fast to finalize based on the questions you asked and the responses that customer provided).

You are specialized for ANZ BANK AI AGENT to solve this problem.

**Enhanced Dataset Integration:**
- Customer Demographics: KYC status, AML risk level, CDD level, digital literacy
- Transaction History: Device fingerprinting, location risk, velocity risk, amount risk
- Call History: Analyst details, call quality, regulatory reporting requirements
- FTP Alerts: Enhanced risk scoring (0-1000), escalation levels (L1/L2/L3), compliance flags

### General Questions (Applicable to most ANZ alerts)

These are for initial contact and identity verification by ANZ.

1.  **Identity Verification:**
    *   "Can you please confirm your full name and date of birth for ANZ security purposes?" (from ANZ SOP, Section 5)
    *   "To verify your identity for ANZ, can you tell me about a recent transaction on your ANZ account or confirm your registered address?" (from ANZ SOP, Section 5)
    *   "Could you please confirm the email address or phone number you used for your last ANZ login?" (from ANZ SOP, Section 5)

2.  **Transaction Confirmation (Initial):**
    *   "We've noticed a potentially suspicious transaction on your ANZ account and need to confirm some details. Did you authorize a transaction for roughly $[Amount] on [Date] to [Recipient]?" (adapted from ANZ SOP, Section 5 conversation sample)
    *   "Are you currently attempting to make a payment to [Recipient] from your ANZ account?"
    *   "Have you recently initiated any large transfers from your ANZ account?"

### Specific Questions (Triggered by Rule ID / Fraud Type)

These questions should be framed by the Dialogue Agent based on the `Rule ID` and the specific context (`TransactionContext`, `UserContext`, etc.) identified by the upstream agents. All questions must be ANZ-branded and reference ANZ where appropriate.

# --- FRAUD QUESTION TEMPLATES ---

# (For each YAML block and question, add 'ANZ' or 'ANZ Bank' where it makes sense, especially in customer-facing language)

---
fraud_type: RUL-TX901
core_facts:
  - identity_verified
  - authorization
  - device
  - recipient
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "Can you please confirm your full name and date of birth for ANZ security purposes?"
  - "Did you authorize a transaction for $[Amount] to [Recipient] from your ANZ account?"
  - "Is [Recipient] a new payee for you, or have you sent money to them before from your ANZ account?"
  - "Have you changed your ANZ password multiple times in the last 24 hours?"
  - "Is this type of transfer amount and recipient consistent with your usual ANZ banking behaviour?"
---
fraud_type: RUL-TX817
core_facts:
  - identity_verified
  - device
  - authorization
  - recipient
  - purpose
finalize_if:
  - user_confirms_biometrics OR (user_denies_authorization AND identity_verified)
questions:
  - "We've detected a login from a new device, immediately followed by a large transfer of $[Amount] from your ANZ account. Was this login authorized by you?"
  - "Can you confirm the device you are currently using to access your ANZ banking?"
  - "Is the destination of this transfer to an investment or cryptocurrency platform?"
  - "Did you verify this new device with biometrics or a security code when you logged in to ANZ?"
  - "Is this pattern of new device login and transfer consistent with your past ANZ banking behaviour?"
---
fraud_type: RUL-TX488
core_facts:
  - identity_verified
  - authorization
  - recipient
  - investment_entity
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've identified a new investment transaction of $[Amount] to [Entity]. Can you confirm if you initiated this?"
  - "How were you introduced to [Entity]? Was it through social media, a cold call, or another channel?"
  - "Are you aware if [Entity] is licensed by ASIC?"
  - "Is this entity known to you, or have you verified their legitimacy through official channels?"
---
fraud_type: RUL-TX778
core_facts:
  - identity_verified
  - authorization
  - recipient
  - amount
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've noticed a transfer of over 80% of your account balance. Can you confirm if you intended to transfer this amount?"
  - "Is the recipient of this transfer [Recipient Name] known to you? Is it an individual or a company?"
  - "Is the recipient related to cryptocurrency or a digital wallet service?"
  - "Were you aware of multiple rapid transfers occurring from your account?"
---
fraud_type: RUL-TX234
core_facts:
  - identity_verified
  - authorization
  - recipient
  - jurisdiction
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've observed a first-time offshore transfer of $[Amount] to [Jurisdiction/Entity]. Can you confirm this transaction?"
  - "Is [Jurisdiction/Entity] considered a high-risk jurisdiction for investments?"
  - "Is this entity licensed and known to you, or part of your regular investment portfolio?"
  - "Is this type of offshore transfer a regular part of your financial activity?"
---
fraud_type: RUL-TX155
core_facts:
  - identity_verified
  - authorization
  - recipient
  - amount
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've noticed multiple small transfers occurring daily from your account over the last few days, totaling over $2,000. Can you confirm these transfers?"
  - "Are these daily small transfers part of a regular payment or investment activity you're undertaking?"
---
fraud_type: RUL-TX230
core_facts:
  - identity_verified
  - authorization
  - recipient
  - vendor
  - purpose
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've detected a change in the account details for [Vendor Name], a vendor you regularly pay. Did you authorize this change?"
  - "Is the amount of this payment, $[Amount], consistent with your usual payments to [Vendor Name]?"
  - "Are you aware of using a new payment channel for this vendor recently?"
  - "Was this account detail change verified through a secure communication channel directly with [Vendor Name]?"
---
fraud_type: RUL-TX817v2
core_facts:
  - identity_verified
  - device
  - authorization
  - recipient
  - amount
finalize_if:
  - user_denies_authorization AND identity_verified
questions:
  - "We've detected a login from an unverified device, followed by a significant transfer of over 50% of your balance to a cryptocurrency service, occurring outside your usual banking hours. Can you confirm this activity?"
  - "Were you aware of these transfers to a crypto service?"
  - "Can you confirm your whereabouts and activities at [Time] on [Date]?"
---
# Add more fraud types as needed in the same format.

**I. For Feedback Collection (Post-Resolution)**

*   "To help us improve ANZ fraud detection, can you confirm if this alert was a true fraud incident or a legitimate transaction?"
*   "What was the final outcome of this transaction with ANZ?"

**Important Considerations for Agent Implementation:**

*   **Context-Driven Selection:** The Dialogue Agent must intelligently select which specific questions to ask based on the `Rule ID` and the presence/absence of other relevant context (e.g., `UserContext`, `DeviceContext`).
*   **Logical Flow:** Questions should follow a natural conversational progression (e.g., identity verification first, then transaction specifics, then deeper probing based on scam indicators).
*   **Templating:** Use placeholders like `[Amount]`, `[Recipient]`, `[Entity]` that are dynamically filled from the `TransactionContext` or other relevant contexts.
*   **No Hallucinations:** The agent should ONLY draw questions from the pre-defined ANZ SOP rules and conversation samples. It should not generate new, unverified questions.
*   **Adaptive Questioning:** If a customer's answer resolves the suspicion (e.g., "Yes, that's my new phone and I logged in with ANZ biometrics"), the agent should pivot to closing the inquiry or escalate as per the ANZ SOP, rather than asking irrelevant follow-up questions.

**Enhanced Risk Assessment Questions:**

*   **Digital Literacy Assessment:** "How comfortable are you with online banking and security features?"
*   **Device Verification:** "Can you confirm if you're using your usual device for ANZ banking?"
*   **Location Verification:** "Are you currently in [Location] where this transaction originated?"
*   **Behavioral Pattern:** "Is this transaction amount and timing consistent with your usual ANZ banking behavior?"
*   **Education Material:** "Have you completed ANZ's scam education materials recently?"

# Expanded Questions for RAG

### Romance Scam (RUL-RS001)
* "Can you tell me how you met the recipient of this transfer?"
* "Have you met this person in person, or is your relationship only online?"
* "Has anyone asked you to keep this transaction secret from friends or family?"
* "Did the recipient request money for travel, emergencies, or investment opportunities?"

### Mule Account (RUL-MA002)
* "Can you explain the source and purpose of recent inbound and outbound transfers?"
* "Are you receiving payments on behalf of someone else?"
* "Do you know all the people sending or receiving money from your account?"
* "Has anyone offered you a commission to move money through your account?"

### Phishing/Smishing (RUL-PS003)
* "Did you receive any suspicious emails or SMS messages before this transaction?"
* "Did any message ask you to click a link or provide your banking details?"
* "Have you noticed any unauthorized logins or device changes?"

### Social Engineering (RUL-SE004)
* "Has anyone pressured you to make this payment urgently?"
* "Did anyone claim to be from the bank, police, or another authority?"
* "Were you told not to speak to anyone else about this transaction?"

### Authorized Push Payment (APP) (RUL-APP005)
* "Did you feel under any pressure or threat when making this payment?"
* "Did you verify the recipient’s identity independently?"
* "Was this payment for goods, services, or an investment?"

### Synthetic Identity (RUL-SI006)
* "Can you confirm all your personal details and recent account activity?"
* "Did you open this account yourself, and have you used it regularly?"
* "Have you received any communication about your identity or account being used by others?"

### Insider Threat (RUL-IT007)
* "Can you explain why you accessed this account at this time?" (for staff)
* "Did you notice any unusual staff activity or communication?" (for customers)

### Business Email Compromise (RUL-BEC008)
* "Did you receive any requests to change vendor payment details via email?" (ANZ)
* "Did you verify the new bank details directly with the vendor using a phone number from a previous ANZ invoice or their official website?" (ANZ secure verification)
* "Is the payment amount or recipient consistent with your usual pattern for this vendor?" (ANZ)
* "Was the vendor name or email slightly different (e.g., abbreviation or small change)?" (ANZ)
* "Did you receive duplicate invoices or a follow-up asking to ‘redirect’ the payment?" (ANZ)