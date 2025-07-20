This is a list of questions that can be asked, based on the type of fraud & othe details modify and formulate the questions accordingly. Dont hallucinate the Qestions.

Based on the provided ANZ Fraud SOP, here's a list of questions that your agents can frame and ask, categorized by context and designed to avoid hallucinations by directly referencing the SOP's decision rules and scripting.

### General Questions (Applicable to most alerts)

These are for initial contact and identity verification.

1.  **Identity Verification:**
    *   "Can you please confirm your full name and date of birth for security purposes?" (from SOP, Section 5)
    *   "To verify your identity, can you tell me about a recent transaction on your account or confirm your registered address?" (from SOP, Section 5)
    *   "Could you please confirm the email address or phone number you used for your last login?" (from SOP, Section 5)

2.  **Transaction Confirmation (Initial):**
    *   "We've noticed a potentially suspicious transaction on your account and need to confirm some details. Did you authorize a transaction for roughly $[Amount] on [Date] to [Recipient]?" (adapted from SOP, Section 5 conversation sample)
    *   "Are you currently attempting to make a payment to [Recipient]?"
    *   "Have you recently initiated any large transfers from your account?"

### Specific Questions (Triggered by Rule ID / Fraud Type)

These questions should be framed by the Dialogue Agent based on the `Rule ID` and the specific context (`TransactionContext`, `UserContext`, etc.) identified by the upstream agents.

**A. Fraud Type: Password Change + Large Transfer (RUL-TX901)**

*   "We've observed a password change on your account recently, followed by a transfer of $[Amount] to [Payee Name]. Did you make these changes and authorize this transfer?"
*   "Is [Payee Name] a new recipient for you, or have you sent money to them before?"
*   "Have you changed your password multiple times in the last 24 hours?"
*   "Can you confirm if [Payee Name] is on your trusted list of recipients, or if you've sent them money in the last 3 months?" (for `Skip Call if` evaluation)
*   "Is this type of transfer amount and recipient consistent with your usual banking behaviour?" (for `Skip Call if` evaluation)

**B. Fraud Type: New Device + Large Transfer (RUL-TX817)**

*   "We've detected a login from a new device, immediately followed by a large transfer of $[Amount]. Was this login authorized by you?"
*   "Can you confirm the device you are currently using to access your banking?"
*   "Is the destination of this transfer to an investment or cryptocurrency platform?"
*   "Did you verify this new device with biometrics or a security code when you logged in?" (for `Skip Call if` evaluation)
*   "Is this pattern of new device login and transfer consistent with your past banking behaviour?" (for `Skip Call if` evaluation)

**C. Fraud Type: Investment Scam (RUL-TX488)**

*   "We've identified a new investment transaction of $[Amount] to [Entity]. Can you confirm if you initiated this?"
*   "How were you introduced to [Entity]? Was it through social media, a cold call, or another channel?" (from SOP, Section 5)
*   "Are you aware if [Entity] is licensed by ASIC?" (from SOP, Section 5)
*   "Is this entity known to you, or have you verified their legitimacy through official channels?"

**D. Fraud Type: Full Balance Outflow (RUL-TX778)**

*   "We've noticed a transfer of over 80% of your account balance. Can you confirm if you intended to transfer this amount?"
*   "Is the recipient of this transfer [Recipient Name] known to you? Is it an individual or a company?"
*   "Is the recipient related to cryptocurrency or a digital wallet service?"
*   "Were you aware of multiple rapid transfers occurring from your account?"

**E. Fraud Type: Offshore Investment (RUL-TX234)**

*   "We've observed a first-time offshore transfer of $[Amount] to [Jurisdiction/Entity]. Can you confirm this transaction?"
*   "Is [Jurisdiction/Entity] considered a high-risk jurisdiction for investments?" (Agent would use internal data for this, but could prompt for customer awareness)
*   "Is this entity licensed and known to you, or part of your regular investment portfolio?" (for `Skip Call if` evaluation)
*   "Is this type of offshore transfer a regular part of your financial activity?" (for `Skip Call if` evaluation)

**F. Fraud Type: Drip Transfer Anomaly (RUL-TX155)**

*   "We've noticed multiple small transfers occurring daily from your account over the last few days, totaling over $2,000. Can you confirm these transfers?"
*   "Are these daily small transfers part of a regular payment or investment activity you're undertaking?" (for `Skip Call if` evaluation)

**G. Fraud Type: Business Invoice Redirection (RUL-TX230)**

*   "We've detected a change in the account details for [Vendor Name], a vendor you regularly pay. Did you authorize this change?"
*   "Is the amount of this payment, $[Amount], consistent with your usual payments to [Vendor Name]?"
*   "Are you aware of using a new payment channel for this vendor recently?"
*   "Was this account detail change verified through a secure communication channel directly with [Vendor Name]?" (for `Skip Call if` evaluation)

**H. Fraud Type: New Device + Account Cleanout (RUL-TX817 variant)**

*   "We've detected a login from an unverified device, followed by a significant transfer of over 50% of your balance to a cryptocurrency service, occurring outside your usual banking hours. Can you confirm this activity?"
*   "Were you aware of these transfers to a crypto service?"
*   "Can you confirm your whereabouts and activities at [Time] on [Date]?"

**I. For Feedback Collection (Post-Resolution)**

*   "To help us improve our fraud detection, can you confirm if this alert was a true fraud incident or a legitimate transaction?"
*   "What was the final outcome of this transaction?"

**Important Considerations for Agent Implementation:**

*   **Context-Driven Selection:** The Dialogue Agent must intelligently select which specific questions to ask based on the `Rule ID` and the presence/absence of other relevant context (e.g., `UserContext`, `DeviceContext`).
*   **Logical Flow:** Questions should follow a natural conversational progression (e.g., identity verification first, then transaction specifics, then deeper probing based on scam indicators).
*   **Templating:** Use placeholders like `[Amount]`, `[Recipient]`, `[Entity]` that are dynamically filled from the `TransactionContext` or other relevant contexts.
*   **No Hallucinations:** The agent should ONLY draw questions from the pre-defined SOP rules and conversation samples. It should not generate new, unverified questions.
*   **Adaptive Questioning:** If a customer's answer resolves the suspicion (e.g., "Yes, that's my new phone and I logged in with biometrics"), the agent should pivot to closing the inquiry or escalate as per the SOP, rather than asking irrelevant follow-up questions.