
# SplitSmart AI – Intelligent Group Expense Manager

SplitSmart AI is an AI-powered group expense management application designed to simplify shared expenses among friends, roommates, and travel groups.

It uses artificial intelligence to understand expense descriptions written in natural language, while a deterministic backend calculates expense shares and balances accurately.

## Problem Statement

Managing shared expenses among friends, roommates, and travel groups often leads to confusion and calculation errors. SplitSmart AI uses artificial intelligence to automatically analyze expenses, calculate each person's share, and determine who owes whom.

## Key Features

- Group creation and management
- Member management
- Expense recording and history
- Equal and custom expense splitting
- AI-powered natural-language expense parsing
- Automatic expense creation using Gemini AI
- Member balance calculation
- Simplified settlement suggestions
- Settlement history and status tracking
- Dashboard with group and expense statistics

## Technology Stack

**Backend**
- Python
- FastAPI
- SQLAlchemy
- Pydantic

**Frontend**
- HTML
- CSS
- JavaScript

**Database**
- SQLite

**Artificial Intelligence**
- Google Gemini API

**Other**
- Uvicorn
- Git and GitHub

## Project Architecture

```text
SplitSmart AI/
│
├── app/
│   ├── core/
│   ├── database/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   ├── templates/
│   └── main.py
│
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/SplitSmart-AI.git
cd SplitSmart-AI
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate it

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Configure environment variables

Copy `.env.example` to `.env` and enter your own Gemini API key.

### 6. Start the application

```bash
python -m uvicorn app.main:app --reload
```

### 7. Open the application

Dashboard: http://127.0.0.1:8000

API Documentation: http://127.0.0.1:8000/docs

## Financial Calculation

SplitSmart AI stores monetary values as integer paise to avoid floating-point calculation errors.

AI extracts expense details, while the backend independently performs the financial calculations.

## Project Status

The backend APIs and initial frontend dashboard are implemented. Further development includes expanded member management, settlement interface improvements, payment integration and additional AI capabilities.

PayPal Sandbox integration is planned for payment workflow demonstration. Live domestic peer-to-peer payments in India are not claimed.

## Security Notice

This is an educational project prototype. Do not commit API keys, credentials, database files or other private information. Authentication and production security measures should be implemented before handling real users' financial data.

## Developer

**SplitSmart AI – Intelligent Group Expense Manager**
