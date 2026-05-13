# Commerce POS QA Bot

> **Hackathon prototype for ABCIIB-207 - PaymentOps QA Commerce POS setups.**
>
> Automates the cross-system QA checks the Payment Operations team performs today
> before activating a new Commerce POS merchant.

## The problem

Today, before a new merchant goes live on Commerce POS, a PaymentOps analyst
manually checks ~27 fields across **5 different systems** (KYC / Salesforce,
Payment Gateway, Commerce Transact, the WP Onboarded Clubs migration spreadsheet,
and Repay). Each merchant takes ~30 minutes and mistakes slip through.

## Before vs After

| | Today (manual) | With this bot |
|---|---|---|
| Time per merchant | ~30 minutes | ~5 seconds |
| Systems open at once | 5 | 0 (one upload) |
| Mismatches caught | Whatever the analyst notices | Every field in the checklist, every time |
| Output to QA ticket | Hand-written notes | Auto-generated color-coded Excel report |
| Onboarding new analyst | Read the checklist + shadow | Open the app |

## The prototype

A Streamlit web app that:

1. Takes the source files (or screenshots/exports) for one merchant.
2. Parses them into one normalized view (`MerchantFacts`).
3. Runs the QA rules straight from the existing `Commerce QA checklist - MS.xlsx`.
4. Builds an AI comparison packet from the setup document/KYC record, Repay
   configuration, and Commerce POS records, then produces an AI validation brief.
5. Produces a color-coded PASS / FAIL / WARN dashboard and a downloadable Excel
   QA report the analyst can attach to the QA ticket.

Same logic, ~5 seconds per merchant instead of ~30 minutes.

## Quick start

```bash
cd commerce-qa-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Demo script (60 seconds)

1. Open the app. Pick **Commerce POS Migration** from the workflow dropdown.
2. Click **Load mock merchant: FAIL** in the sidebar.
3. The app renders in ~1 second:
   - Red banner: "**5 issues found out of 17 checks**".
   - Red rows for: TIN last-4 mismatch, Billing Descriptor too long, Bank
     transfer set to Wire, Repay MID still open, and KYC stage still in progress.
   - Each FAIL row shows **Expected (KYC)** vs **Actual (Payment Gateway /
     Commerce Transact / Repay)** and which checklist line it maps to.
4. Open the **AI review** tab. It summarizes the setup document/KYC, Repay
   configuration, and Commerce POS records into an activation recommendation.
5. Click **Download QA Report (Excel)**. The analyst can attach this to the QA
   ticket today.
6. Click **Load mock merchant: PASS**. Everything green: "Ready to activate."
7. Close: "Every rule came directly from the existing QA checklist - we're not
   making judgement calls, just automating what's already documented."

## AI-assisted comparison

The prototype explicitly supports the idea wording: use AI to compare setup
documents, Repay configuration, and Commerce POS records before merchants are
flipped live.

- **Setup documents:** represented by `kyc_record.json` in the demo. In a pilot,
  this can be produced from a KYC PDF / setup document extraction step.
- **Repay configuration:** represented by `repay_status.csv`.
- **Commerce POS records:** represented by `payment_gateway_export.csv`,
  `commerce_transact_export.csv`, and `wp_onboarded_clubs_row.xlsx`.
- **AI review:** `ai_reviewer.py` builds an AI prompt/comparison packet covering
  fees, merchant details, banking, processor, terminals, card types, and
  activation readiness. Without an API key, the app uses a local AI-style brief
  so the hackathon demo works offline. With `OPENAI_API_KEY` set, it can call a
  live LLM using the same packet.

## What we'd ask Missy / Stephanie for next

To go from prototype to pilot, we need a real example merchant:

- A CSV or Excel export of one merchant from Payment Gateway Merchant Management.
- The matching Commerce Transact profile / deposits / rates export.
- The KYC client information form (PDF is fine - we add a parsing step).
- The WP Onboarded Clubs row.
- The Repay status entry.

One PASS example + one historical FAIL example is ideal.

## How the rules map to your checklist

Every rule in `rules.py` carries a `checklist_ref` quoting the line from
`Commerce QA checklist - MS.xlsx` it comes from. Examples:

| Rule (in app) | Checklist line |
|---|---|
| `tin_last4_match` | "Last 4 of the Tax ID are correct" |
| `billing_descriptor_format` | "Billing Descriptor - Includes ABC*P and club number. Max character limit is 25." |
| `processor_correct` | "Processor shows Worldpay Core POS ON1061 (CAD: 0TP831; PR: ON1061 NOT 0N1064)" |
| `bank_transfer_method` | "Bank account for POS should be set for ACH not Wire" |
| `repay_mid_closed` | "Check that Repay MID has been closed" |
| `kyc_stage_complete` | "Stage is not on 'MS Stage 1 - In Progress'" |
| `device_fees_present` | "If the club has device fees, both POS06 and POS07 have been added" |

No new judgement calls - just automating what's already documented.

## Project layout

```
commerce-qa-bot/
├── app.py                  Streamlit UI
├── extractors.py           parse each source file -> dict
├── facts.py                MerchantFacts dataclass (normalized cross-system view)
├── rules.py                one function per QA rule, returns CheckResult
├── workflows.py            which rules apply to each workflow
├── report.py               build downloadable Excel QA report
├── ai_reviewer.py          AI comparison packet + validation brief
├── mock_data/
│   ├── merchant_pass/      5 files - everything matches
│   └── merchant_fail/      5 files with planted mismatches
├── requirements.txt
└── README.md
```
