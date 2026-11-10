# SplitSmart AI 2.0 — The Financial Memory of a Group

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%202.5-4285F4.svg)](https://ai.google.dev/)
[![PayPal Sandbox](https://img.shields.io/badge/PayPal-Orders%20v2%20REST-003087.svg)](https://developer.paypal.com/)
[![Tests Passing](https://img.shields.io/badge/tests-15%2F15%20passing-brightgreen.svg)]()

> **"The Financial Memory of a Group"**
> SplitSmart AI 2.0 is an intelligent group activity management and financial intelligence platform. It tracks, organizes, analyzes, and manages group financial activities from kickoff to final settlement—connecting people, activities, expenses, receipts, payment proofs, budgets, and digital settlements into an audit-ready financial history.

---

## 🌟 Why SplitSmart AI 2.0?

Traditional expense splitters force members to manually enter repetitive expense forms, guess who owes what, and struggle with forgotten receipts after a trip or event.

SplitSmart AI 2.0 solves this with an **Information & Evidence Collection Centre**:
- **Not just trips**: Built for **roommates**, **family budgets**, **weddings & receptions**, **college events & student projects**, **clubs & NGOs**, **group bulk purchases**, and **vacations**.
- **Multimodal Evidence Intake**: Upload photos of paper receipts, hotel invoices (PDFs), voice audio voice memos, activity videos, WhatsApp chat exports, or natural language text.
- **AI-Assisted, Deterministically Calculated**: Gemini extracts structured drafts, but **exact Python backend arithmetic** (in integer paise) calculates shares, percentages, balances, and minimal settlement paths.
- **Grounded AI Financial Assistant**: An in-app assistant grounded strictly in your group's live database—ask *"How much have we spent so far?"*, *"Who paid the most?"*, or *"What was our largest expense?"* without hallucinations.
- **PayPal Sandbox Orders v2 Integration**: Verifiable, end-to-end sandbox payments with real-time capture verification and transaction audit logging.

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
APP_NAME="SplitSmart AI 2.0"
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

> **Note on Offline / Sandbox Mode**: If `GEMINI_API_KEY` is omitted or network access is restricted, SplitSmart AI 2.0 automatically switches to its deterministic parsing and analysis engines, ensuring all features continue to function seamlessly.

### 4. Run the Application

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Web App**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **FastAPI Interactive API Docs (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Docs**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Running the Test Suite

SplitSmart AI 2.0 includes a comprehensive test suite covering mathematical precision, edge cases, duplicate detection, and full v2 end-to-end scenarios.

```bash
# Run all tests
.\.venv\Scripts\python.exe -m pytest -v

# Or using standard pytest if activated:
pytest -v
```

### Test Coverage Highlights:
- **`test_financial_logic.py`**:
  - `test_equal_split_shares`: Verifies zero remainder and exact 1-paise distribution on fractional splits (e.g., ₹100 split 3 ways = 33.34, 33.33, 33.33).
  - `test_percentage_split_rounding`: Validates strict 100% total validation and exact paise rounding.
  - `test_custom_split_validation`: Confirms custom amounts must sum exactly to the total.
  - `test_settlement_simplification`: Verifies debt graph minimization (reduces N-party circular debts to minimum transaction paths).
  - `test_zero_balance_settlement`: Verifies no phantom settlement paths when net balances are zero.
- **`test_v2_features.py`**:
  - `test_scenario_1_group_and_members`: Tests activity types, start/end dates, budgets, member roles, contact details.
  - `test_scenario_2_equal_and_percentage_expenses`: Verifies multi-category expenses and share allocations.
  - `test_scenario_3_and_4_evidence_and_duplicate_detection`: Tests image/PDF/audio uploads, SHA-256 hash checks, and fuzzy semantic duplicate detection.
  - `test_scenario_whatsapp_parser`: Tests financial message extraction from WhatsApp text exports.
  - `test_scenario_5_financial_analysis`: Validates financial overview, category breakdown, contribution balances, and budget alerts.
  - `test_scenario_6_ai_assistant_grounded_answers`: Validates Q&A responses grounded in real database records.
  - `test_scenario_7_settlement_and_simplification`: Confirms balance calculation and settlement marking.
  - `test_scenario_8_paypal_order_lifecycle`: Tests PayPal Orders v2 mock creation, approval URL, and capture verification.
  - `test_scenario_9_chronological_timeline`: Tests unified chronological sorting across expenses, uploads, and payments.
  - `test_scenario_10_ai_parse_and_confirm_workflow`: Validates the fix for the known HTTP 400 bug with full draft review and confirmation.

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
In SplitSmart AI 2.0, natural language inputs never write directly to the database without user confirmation:
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

SplitSmart AI 2.0 is developed as an educational software engineering and AI systems demonstration project. Built with ❤️ by the SplitSmart AI Team.
