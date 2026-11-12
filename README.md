# SplitSmart — The Financial Memory of a Group

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%202.5-4285F4.svg)](https://ai.google.dev/)
[![PayPal Sandbox](https://img.shields.io/badge/PayPal-Orders%20v2%20REST-003087.svg)](https://developer.paypal.com/)
[![Tests Passing](https://img.shields.io/badge/tests-27%2F27%20passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **"The Financial Memory of a Group"**
> SplitSmart is an intelligent group activity management and financial intelligence platform. It tracks, organizes, analyzes, and manages group financial activities from kickoff to final settlement—connecting people, activities, expenses, receipts, payment proofs, budgets, and digital settlements into an audit-ready financial history.

---

## 🌟 Why SplitSmart?

Traditional expense splitters force members to manually enter repetitive expense forms, guess who owes what, and struggle with forgotten receipts after a trip or event.

SplitSmart solves this with an **Information & Evidence Collection Centre**:
- **Not just trips**: Built for **college events & symposiums**, **roommates & flatshares**, **family budgets**, **weddings & celebrations**, **clubs & NGOs**, **group bulk purchases**, and **vacations**.
- **AI Group Architect**: Describe any event in plain language (e.g., *"3-day college symposium with 8 participants, budget ₹30,000, separate activities for food, decoration, transport, accommodation, photography"*). Gemini creates a tailored structure with activities, budgets, and categories.
- **Activities & Customization**: Break down any group into sub-activities with allocated budgets, custom expense categories, and granular role permissions.
- **Multimodal Evidence Intake**: Upload photos of paper receipts, hotel invoices (PDFs), voice audio voice memos, activity videos, WhatsApp chat exports, or natural language text.
- **AI-Assisted, Deterministically Calculated**: Gemini extracts structured drafts, but **exact Python backend arithmetic** (in integer paise) calculates shares, percentages, balances, and minimal settlement paths.
- **Function Calling & AI Tools**: Gemini uses controlled backend functions to query group summaries, check real-time balances, retrieve expenses, and create activities dynamically.
- **Authentication & Owner Retention**: Secure user registration, password hashing (PBKDF2-SHA256), session tokens, and strict owner protection (a group's last active owner cannot be removed or demoted).
- **Grounded AI Financial Assistant**: An in-app assistant grounded strictly in your group's live database—ask *"How much have we spent so far?"*, *"Who paid the most?"*, or *"What was our largest expense?"* without hallucinations.
- **PayPal Sandbox Orders v2 Integration**: Verifiable, end-to-end sandbox payments with real-time capture verification, double-capture prevention, and transaction audit logging.

---

## 🏗️ Architecture & Technology Stack

```
SplitSmart AI/
├── app/
│   ├── core/
│   │   └── config.py               # Pydantic v2 application settings (.env)
│   ├── database/
│   │   ├── database.py             # SQLAlchemy session & idempotent SQLite migrations
│   │   └── models.py               # ORM Models: Group, Member, Expense, ExpenseShare,
│   │                               #   Settlement, ExpenseEvidence, PaymentTransaction
│   ├── routes/
│   │   ├── ai.py                   # Natural language parsing, draft confirmation, assistant chat
│   │   ├── analytics.py            # Financial overview, categories, contributions, budget, forecast, timeline
│   │   ├── evidence.py             # Multimodal upload, SHA-256 duplicate detection, document serving
│   │   ├── expenses.py             # Equal, custom, and percentage split expense management
│   │   ├── groups.py               # Group lifecycle, activity types, budgets, member roles
│   │   ├── payments.py             # PayPal Orders v2 create, capture, status, and audit ledger
│   │   └── settlements.py          # Balance tracking, debt graph simplification, completion
│   ├── schemas/                    # Pydantic validation schemas
│   ├── services/
│   │   ├── ai_service.py           # Gemini 2.5 Flash multimodal + deterministic fallbacks
│   │   ├── duplicate_detector.py   # Exact hash + fuzzy similarity detection
│   │   ├── expense_calculator.py   # Integer paise split engine (equal, custom, percentage)
│   │   ├── financial_analyst.py    # KPIs, burn rates, explainable forecasts, recommendations
│   │   ├── paypal_service.py       # PayPal REST Orders v2 API client (OAuth2 + capture)
│   │   ├── settlement_engine.py    # Graph debt minimization algorithm
│   │   └── whatsapp_parser.py      # Regex financial message extractor for WhatsApp .txt exports
│   ├── static/
│   │   ├── css/style.css           # Modern, responsive CSS design system
│   │   └── js/app.js               # Reactive vanilla JavaScript frontend controller
│   ├── templates/
│   │   └── index.html              # Single-Page Application interface
│   └── main.py                     # FastAPI application factory and route mounting
├── tests/
│   ├── test_financial_logic.py     # Split arithmetic & debt simplification tests
│   └── test_v2_features.py         # End-to-end v2 workflow scenarios
├── uploads/                        # Evidence storage directory (images, PDFs, audio, video)
├── .env.example                    # Sample environment configuration template
├── requirements.txt                # Exact pinned dependencies
└── README.md
```

### Tech Stack Details:
- **Backend**: Python 3.11 - 3.13, FastAPI, SQLAlchemy 2.0 (SQLite), Pydantic v2.
- **AI Engine**: Google Gemini API (`gemini-2.5-flash`) with deterministic offline-safe fallback parser.
- **Payments**: PayPal REST API v2 (Sandbox Mode) with automatic INR-to-USD conversion (₹85/USD).
- **Frontend**: Lightweight SPA using modern semantic HTML5, CSS custom properties, and modular vanilla JavaScript.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.11, 3.12, or 3.13 installed.
- Git.

### 2. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/SplitSmart-AI.git
cd "SplitSmart AI"

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Application Metadata
APP_NAME="SplitSmart"
APP_VERSION="2.0.0"
DEBUG=True

# Database Configuration (preserves your existing splitsmart.db)
DATABASE_URL="sqlite:///./splitsmart.db"

# Google Gemini API Key (Get free key from https://aistudio.google.com/)
GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-2.5-flash"

# PayPal Sandbox Credentials (https://developer.paypal.com/dashboard/applications/sandbox)
PAYPAL_CLIENT_ID="your_paypal_sandbox_client_id"
PAYPAL_CLIENT_SECRET="your_paypal_sandbox_client_secret"
PAYPAL_BASE_URL="https://api-m.sandbox.paypal.com"
PAYPAL_MODE="sandbox"

# Evidence & File Uploads
UPLOAD_DIR="uploads"
MAX_UPLOAD_SIZE_MB=25
```

> **Note on Offline / Sandbox Mode**: If `GEMINI_API_KEY` is omitted or network access is restricted, SplitSmart automatically switches to its deterministic parsing and analysis engines, ensuring all features continue to function seamlessly.

### 4. Run the Application

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Web App**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **FastAPI Interactive API Docs (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Docs**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Running the Test Suite

SplitSmart includes a comprehensive test suite (27 tests) covering mathematical precision, edge cases, duplicate detection, AI group creation, custom activities, and full v2 end-to-end scenarios.

```bash
# Run all tests (executes in an isolated in-memory SQLite database)
.\.venv\Scripts\python.exe -m pytest -v

# Or using standard pytest if activated:
pytest -v
```

### Test Coverage Highlights (27 / 27 Passing):
- **`test_financial_logic.py`** (5 tests):
  - `test_equal_split_shares`: Verifies zero remainder and exact 1-paise distribution on fractional splits (e.g., ₹100 split 3 ways = 33.34, 33.33, 33.33).
  - `test_percentage_split_rounding`: Validates strict 100% total validation and exact paise rounding.
  - `test_custom_split_validation`: Confirms custom amounts must sum exactly to the total.
  - `test_settlement_simplification`: Verifies debt graph minimization (reduces N-party circular debts to minimum transaction paths).
  - `test_zero_balance_settlement`: Verifies no phantom settlement paths when net balances are zero.
- **`test_splitsmart_v2_comprehensive.py`** (12 tests):
  - `test_full_v2_workflow_college_symposium`: Complete lifecycle from AI natural-language proposal to confirmation, member assignment, and budget allocation.
  - `test_custom_activities_and_budgets`: CRUD operations for activities and sub-event budget tracking.
  - `test_custom_categories_and_roles`: Custom role permissions and expense category creation.
  - `test_owner_protection_rule`: Verifies that a group's last active owner cannot be deleted or demoted.
  - `test_safe_cascade_group_deletion`: Ensures deleting a group cleanly cleans up activities, expenses, evidence links, and settlements.
  - `test_partial_settlement_workflow`: Tracks partial settlement amounts and keeps outstanding balances accurate.
  - `test_settlement_cancellation`: Verifies cancelling a settlement restores the original balance.
  - `test_user_registration_and_authentication`: PBKDF2 password hashing, login token verification, and profile fetching.
  - `test_ai_refine_group_proposal`: Conversational follow-up instructions modifying group proposals.
  - `test_ai_function_calling_tools`: Server-side Gemini function calling and tool execution.
  - `test_paypal_webhook_idempotency`: Idempotent processing of PayPal order capture webhooks.
  - `test_zero_sum_ledger_invariance`: Mathematical verification that the sum of all member net balances always equals zero ($\sum balances = 0$).
- **`test_v2_features.py`** (10 tests):
  - End-to-end multi-member expense sharing, evidence deduplication, WhatsApp chat parsing, financial forecasting, and grounded Q&A.

---

## 💡 Key Capabilities Walkthrough

### 1. Activity Group Management
Create groups for any activity type:
- 🏖️ **Trip / Vacation** (e.g., "Goa Beach Trip 2026")
- 🏠 **Roommates / Flatshare** (e.g., "Flat 402 Indiranagar")
- 👨‍👩‍👧‍👦 **Family Expenses** (e.g., "Family Monthly Groceries")
- 💍 **Wedding & Reception** (e.g., "Ananya & Rahul Wedding")
- 🎓 **College Event / Student Project** (e.g., "Robotics Hackathon Team")
- ⚽ **Club / NGO Activity** (e.g., "Weekend Football League")
- 🛒 **Group Bulk Purchase** (e.g., "Costco Wholesale Bulk Order")
- 💼 **Other Shared Expense**

Each group maintains independent start/end dates, target budget (in ₹ INR), currency, and member roles (`Owner`, `Admin`, `Member`).

### 2. Evidence Collection Centre & Duplicate Detection
Drop any file directly onto the Evidence tab or paste text:
- **Receipt / Invoice OCR**: Images (`.jpg`, `.png`, `.webp`) and PDFs (`.pdf`).
- **Voice Memos**: Audio files (`.mp3`, `.wav`, `.m4a`) transcribed for expense amount, merchant, and payer.
- **Activity Video**: Safe storage and metadata logging.
- **WhatsApp Chat Exports**: Upload `.txt` chat logs; SplitSmart identifies financial messages (e.g., *"Paid 1200 for lunch"*).
- **Fraud & Duplicate Protection**:
  1. **Exact File Hash Match**: Checks SHA-256 hash of every uploaded file.
  2. **Fuzzy Semantic Match**: Flags potential duplicates if an expense with the same amount (±5%), same merchant, and nearby date already exists.

### 3. AI Draft Confirmation Workflow (Fix for Known HTTP 400 Bug)
In SplitSmart, natural language inputs never write directly to the database without user confirmation:
1. User enters: `"Rahul paid ₹2,400 for dinner at BBQ Nation"`.
2. `POST /api/ai/parse-expense` returns a **draft** with confidence score, detected fields, and any missing items (e.g., payer selection if ambiguous).
3. The UI presents the editable draft modal.
4. User reviews and clicks **Confirm & Save Expense** (`POST /api/ai/confirm-draft`), preventing transaction rollbacks and zero-member validation errors.

### 4. Financial Intelligence & Analytics
- **KPI Summary Cards**: Total budget, total spent, remaining funds, and utilization percentage.
- **Category Spending Distribution**: Interactive progress bars by category (Food & Dining, Transportation, Fuel, Accommodation, Shopping, Tickets & Events, Bills & Utilities, General).
- **Member Contribution Matrix**: Who paid what, who owes what, and net balances (+ to receive, - to pay).
- **Budget Health Monitor**: Automated color-coded alerts:
  - 🟢 **Safe**: < 80% budget consumed.
  - 🟡 **Warning**: 80% - 99% budget consumed.
  - 🔴 **Danger**: ≥ 100% budget exceeded.
- **Explainable Linear Spending Forecast**: Calculates daily burn rate based on elapsed activity days and forecasts total spend over the remaining activity schedule.
- **Historical Activity Recommendations**: Actionable insights based on spending patterns (e.g., contingency reserve alerts if budget was exceeded).

### 5. Chronological Group Financial Timeline
View every event across the group's lifespan in a single unified feed:
- 💳 **Expense Recorded** (amount, payer, category, shares).
- 📎 **Evidence Uploaded** (receipt file, extracted data, review status).
- 🤝 **Settlement Completed** (debt marked resolved).
- 🌐 **PayPal Payment Captured** (order ID, capture ID, status).

### 6. PayPal Sandbox Orders v2 Integration
- Initiates an authentic PayPal v2 order for group debt settlements.
- Automatic conversion of INR integer paise to USD (standard demonstration rate: ₹85 / USD).
- Returns the official PayPal Sandbox buyer approval URL:
  ```
  https://www.sandbox.paypal.com/checkoutnow?token=...
  ```
- Backend capture endpoint (`POST /api/payments/paypal/capture-order`) verifies the capture with PayPal REST API, updates the transaction ledger, and marks the corresponding settlement as **Completed**.
- *Transparency Notice*: Domestic Indian UPI/RuPay digital rails are not fabricated; international PayPal Sandbox is used for authentic digital payment demonstration.

### 7. Grounded AI Financial Assistant
Click the **AI Assistant** tab to ask natural language questions about your active group:
- *"How much have we spent so far?"*
- *"Who paid the most?"*
- *"What was our largest single expense?"*
- *"How much does Bob owe?"*
- *"What is our remaining budget?"*

The assistant builds a strict database ground truth context from the active SQLite session and answers strictly from recorded data.

---

## 🔒 Security, Privacy & Integrity

1. **Deterministic Financial Math**: Never relies on LLMs for calculations. All splits, shares, and balances are computed in integer paise using exact Python algorithms.
2. **Safe Database Migrations**: Existing `splitsmart.db` records are fully preserved; schema additions (`activity_type`, `budget_paise`, `role`, etc.) execute idempotently without dropping tables.
3. **No Credential Leakage**: API keys and secrets are strictly loaded from environment variables (`.env`) and never exposed in frontend scripts, templates, or logs.
4. **Voluntary Information Only**: Processes only files and text explicitly uploaded by group members. No unauthorized scraping or WhatsApp background monitoring.

---

## 📄 License & Academic Notice

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for complete details.

SplitSmart is developed as an educational software engineering and AI systems demonstration project. Built with ❤️ by Kishore (`Kishore7-web`).
