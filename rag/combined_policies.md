# Company Policy Handbook
_Combined policy corpus for RAG ingestion — 8 sections_

---

# Return Window Policy
Version: 1.0

## 1. Standard Return Window
Customers may initiate a return or exchange within 30 days of the delivery date shown on the order record. The 30-day window begins on the delivery date, not the order date.

## 2. Premium-Tier Extension
Premium-tier customers receive an extended return window of 45 days from delivery, applied automatically based on the customer's tier field. No additional proof or request is required to qualify for this extension.

## 3. Window Calculation
The return window is calculated as (current date − delivery date). If this value is less than or equal to the applicable window (30 or 45 days depending on tier), the return is within policy. If it exceeds the window, the return is outside policy unless an exception applies (see Escalation Criteria, Section 3).

## 4. Non-Returnable Items
The following categories are excluded from the standard return window regardless of tier: gift cards, personalized/customized items, and items marked "final sale" at time of purchase. Requests involving these categories must be escalated rather than resolved automatically.

## 5. Multiple Items on One Order
When an order contains multiple items, the return window is evaluated per item based on that item's individual delivery date, not the order's overall delivery date, in cases of split shipment.

---

# Refund Eligibility Policy
Version: 1.0

## 1. Standard Eligibility
An order is eligible for a full refund if the return request is made within the applicable return window (see Return Window Policy) and the item is unused, or defective/damaged (see Damaged Items Policy).

## 2. Refunds Outside the Return Window
Refund requests made after the applicable return window has closed are NOT eligible for an automatic refund. No automatic exception exists for "past window" requests based on reason, urgency, or customer sentiment alone. Such cases must be escalated to a human agent per the Escalation Criteria policy — the system must not approve a refund outside the window on its own authority.

## 3. Partial Refunds
If only part of a multi-item order is being returned, the refund amount is calculated per-item based on the original item price, excluding original shipping charges unless the return is due to a defect or fulfillment error.

## 4. Refund Method
Refunds are issued to the original payment method whenever possible (see Payment Method Policy for exceptions). Store credit may be offered as an alternative only if the customer explicitly requests it or the original payment method is no longer valid.

## 5. Refund Processing Time
Once approved, refunds are marked as "refund_processing" immediately in the order system. Actual fund transfer timing depends on the payment provider and is outside the scope of this system's guarantees — the agent should only confirm that the refund was initiated, not that funds have arrived.

## 6. Denied Refunds
If a refund is denied (e.g., outside window, non-returnable item, no defect found), the system must clearly state the specific policy reason for denial rather than a generic rejection.

---

# Replacement Rules Policy
Version: 1.0

## 1. Standard Replacement Eligibility
A customer may request a replacement of the same SKU within the applicable return window if the original item is defective, damaged, or incorrect (wrong item/size/color shipped).

## 2. Stock-Dependent Fallback (important — governs blocked-action handling)
If the requested replacement SKU has zero available stock at the time of processing, the replacement CANNOT be fulfilled as originally requested. In this situation, the following fallback order applies:
   a. Offer an equivalent alternate SKU (same product, different size/color) if one is in stock.
   b. If no equivalent alternate is in stock, convert the case to a standard refund per the Refund Eligibility policy.
   c. If neither a replacement nor a refund is possible (e.g., item is non-returnable per Return Window policy Section 4), escalate the case.
This fallback sequence must be followed in order — do not skip directly to escalation if a valid alternate SKU or refund path exists.

## 2a. Chained Replacement Failures
If an alternate SKU is offered under Section 2(a) and that alternate ALSO has zero stock, the system should not continue attempting further alternates indefinitely. After a second consecutive replacement failure on the same case, the system should fall back to a refund per Section 2(b), or escalate if a refund is also not applicable.

## 3. Replacement vs. Refund Preference
When both a replacement and a refund are valid options, prefer replacement only if the customer's original request indicated they want to keep the product (e.g., wrong size). If the customer explicitly requested a refund, do not substitute a replacement without customer confirmation.

## 4. Premium-Tier Priority
Premium-tier customers' replacement requests should be checked against inventory before regular-tier requests are processed, in cases where the system is handling multiple simultaneous cases for the same limited-stock SKU.

---

# Loyalty-Tier Exceptions Policy
Version: 1.0
Last updated: (update this line when you re-ingest a changed version to simulate a policy update mid-demo)

## 1. Premium-Tier Benefits Summary
Premium-tier customers receive the following exceptions to standard policy:
   - Extended 45-day return window (see Return Window Policy Section 2).
   - Priority stock allocation for replacement requests (see Replacement Rules Section 4).
   - One-time courtesy exception per calendar year allowing a refund up to 15 days past the standard window, subject to manager-tier confirmation being unnecessary — the system MAY approve this specific exception autonomously, but only once per customer per year.

## 2. Tracking the Courtesy Exception
The system must check whether a premium customer has already used their one-time courtesy exception this calendar year before applying Section 1's third bullet. If it has already been used, the request must be escalated rather than auto-approved a second time.

## 3. Regular-Tier Customers
Regular-tier customers are not eligible for any of the exceptions in Section 1. Requests from regular-tier customers that would only be valid under a premium exception must be denied or escalated, not approved by mistake.

## 4. Note on Policy Volatility
This exceptions policy is reviewed quarterly and is more likely to change than other policies in this corpus. Agents relying on this document should treat it as authoritative only for its current ingested version — if a newer version has been ingested with different terms (e.g., the one-time courtesy exception being removed or its threshold changed), the newer version governs, and any case in progress that assumed the old terms should be re-verified against the current version before finalizing.

---

# Cancellation Rules Policy
Version: 1.0

## 1. Pre-Shipment Cancellation
An order may be cancelled with no fee at any time before its status changes to "shipped." Cancellation should immediately restore the reserved inventory quantity for the cancelled SKU.

## 2. Post-Shipment Cancellation
Once an order's status is "shipped," it can no longer be cancelled outright. The customer must instead be routed to the Return Window / Refund Eligibility process once the item is delivered — a shipped-but-not-yet-delivered order is not eligible for cancellation, only for a future return once received.

## 3. Cancellation Fees
No cancellation fee applies to standard orders. Custom or personalized orders (see Return Window Policy Section 4) may be cancelled only within 2 hours of order placement, after which they are considered non-cancellable and non-returnable.

## 4. Payment Reversal on Cancellation
When a pre-shipment cancellation is approved, any payment already captured must be reversed using the same method described in the Payment Method Policy for refunds.

---

# Escalation Criteria Policy
Version: 1.0

## 1. Purpose
This policy defines when a case must be handed to a human agent rather than resolved automatically. The automated system must never approve an action that falls outside these boundaries by inventing a workaround or exception not explicitly stated in this policy corpus.

## 2. Mandatory Escalation Triggers
A case must be escalated, not auto-resolved, when any of the following are true:
   a. The requested action falls outside the return window with no applicable exception found (see Refund Eligibility Section 2, Loyalty Exceptions Section 1).
   b. The item is in a non-returnable category (gift cards, personalized items, final-sale items).
   c. A premium customer's one-time courtesy exception has already been used this year and they are requesting it again.
   d. Two consecutive resolution attempts on the same case have failed (e.g., a replacement blocked, then its fallback alternate also blocked, per Replacement Rules Section 2a) without a valid refund path resolving it.
   e. The customer's identity or order ownership cannot be confidently confirmed (e.g., email does not match any customer record).
   f. Any policy document required to make the decision returns a low-confidence or no-match retrieval result.

## 3. What Escalation Means
Escalating a case means: the system stops attempting further automated actions, records the specific reason from Section 2 in the case's escalation_reason field, and the final customer-facing email must clearly state that a team member will follow up — it must not imply the issue has been resolved.

## 4. Escalation Is Not a Failure State
Escalating a correctly-identified out-of-policy or ambiguous case is the CORRECT outcome, not a system error. The system should not attempt repeated retries or alternate justifications to avoid escalating a case that meets the criteria in Section 2.

---

# Damaged and Defective Items Policy
Version: 1.0

## 1. Definition
An item qualifies as damaged or defective if the customer reports it arrived broken, malfunctioning, or materially different from its description, and this is not attributable to normal wear from customer use.

## 2. Extended Eligibility
Damaged or defective items are eligible for a refund or replacement regardless of the standard return window in Section 1 of the Return Window Policy, provided the report is made within 60 days of delivery. This overrides the standard 30/45-day window specifically for confirmed damage/defect cases.

## 3. Non-Returnable Exception Override
Unlike other non-returnable categories, a personalized or final-sale item that arrives damaged or defective IS still eligible for a refund or replacement under this policy — the non-returnable restriction in Return Window Policy Section 4 applies only to buyer's-remorse returns, not to defects.

## 4. No Manual Inspection Requirement
For the purposes of this automated system, a customer's clear description of damage/defect in their message is sufficient evidence to proceed with resolution — the system does not require a photo or physical inspection before offering a refund or replacement, though it may request a photo for its own audit record if convenient.

## 5. Preferred Resolution
For damaged/defective items, replacement is the preferred resolution if the customer wants to keep the product and stock is available; otherwise apply the standard replacement fallback sequence (see Replacement Rules Section 2).

---

# Payment Method Policy
Version: 1.0

## 1. Standard Refund Method
Refunds are returned to the original payment method used at purchase (credit card, debit card, or digital wallet) whenever that method is still valid and active on the customer's account.

## 2. Store Credit Alternative
If the original payment method is no longer valid (e.g., expired card), or if the customer explicitly requests it, the refund may instead be issued as store credit equal to the refund amount, applied immediately to the customer's account.

## 3. Cash-on-Delivery Orders
For orders originally paid via cash-on-delivery, no direct payment reversal is possible. These refunds must be issued as store credit by default, unless the customer requests a bank transfer, which requires escalation to collect bank details securely.

## 4. Split or Partial Payments
If an order was paid using a combination of store credit and a card, refunds are applied in the reverse order of how payment was applied: store credit is refunded first, and any remaining balance is returned to the card.

## 5. Payment Verification
The system should not process a refund without confirming the payment method on record for the order matches an active method. If the payment method flagged for reversal appears invalid or missing, this is a data conflict and must be escalated per Escalation Criteria Section 2(f).

---
