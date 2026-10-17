---
name: viewing-pack
description: Prepare to contact and view one listing the user has been alerted about - a draft enquiry the user sends themselves, questions to ask, documents to have ready and red flags to watch for, using the country pack's sourced checklist. Use when the user says "I want to view this one", "help me enquire about X" or "prepare me for the viewing".
argument-hint: "<listing link or address words>"
---

# Viewing pack

Claude never contacts landlords or agents and never sends the enquiry. It drafts; the user sends.

## Steps

1. Find the listing:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/skills/run-alerts/scripts/laa.py" compare <state> "<ref>"
   ```
   If it is not found, say the plugin only knows listings it has alerted about.
2. Read the pack checklist named in `pack.yaml` under `notes.checklist` (for Ireland, `packs/ie-rentals/notes/viewing-checklist.md`). Use its rules and sources; do not add legal rules from memory.
3. Ask the user, in one question, for anything the draft needs and you do not have: their first name, when they could move, and who would live there (the occupancy rules tell you whether the budget assumes two people).
4. Produce the pack:

   **Enquiry draft** (short, polite, plain): who they are in one line, move-in date, who would live there, two or three questions specific to this listing (for example "Is the second bathroom an en suite?" when bathrooms are missing from the alert), and their availability for a viewing. No personal documents or financial details in a first message.

   **Questions to ask at the viewing**: the checklist's questions, plus questions raised by this listing's flags (missing BER, rent range, "well above market", short travel data).

   **Documents to have ready**: from the checklist, with its advice on sharing copies only after viewing.

   **Red flags for this listing**: the checklist's scam warnings, highlighting any that apply (a "possible scam" flag means: do not pay anything before viewing in person and seeing a written lease).

   **Money check**: the rent, the user's share, the estimated monthly cost if known, and the deposit and advance-rent limits from the checklist, with the source link.
5. Offer to save the draft to Gmail drafts if the Gmail connector can create drafts. Never send it.

## Notes

- Never include or store the landlord's or agent's name, phone number or email address; the user copies the contact details from the listing themselves.
- Every legal or money rule you mention comes with its source link and checked date from the checklist.
