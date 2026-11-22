# The Missing Rupee 

> **Financial Discovery & Anti-Dark Patterns Engine**\
> Uncover recurring subscription commitments, detect sneaky price hikes and trial conversions, and take back control of your recurring debit mandates.

\
Product Overview

**The Missing Rupee** is a financial intelligence engine engineered for the Indian digital payments ecosystem (**UPI AutoPay**, **NACH Mandates**, **Credit/Debit Card Standing Instructions**).

While modern fintech apps make subscribing effortless, cancelling or detecting silent micro-debits remains friction-heavy. **The Missing Rupee** ingests raw bank statements (**PDF**) to expose hidden dark patterns, calculate annual commitment baselines, and walk users through safe, legal **contract-first cancellations**.

## Key USPs & Core Features

### 1. **Smart Payment Discovery:** Detects recurring payments, even with irregular amounts or billing intervals.

### 2. **Intelligent Alerts:** Flags silent price hikes, trial-to-paid conversions and billing frequency increases.

### 3. **Merchant Identification and guided cancellation:** Decodes cryptic bank statement descriptions into recognizable merchant names and provides mechanism-specific cancellation steps and escalation guidance.

### 4. **Forensic Graph Engine (Neo4j Integration)**

* Maps fragmented transaction descriptors to clean parent **`(:Merchant)`** entities.

* Analyzes **`[:PRICE_HIKE]`** relationships and computes upcoming cashflow obligation collisions ("Safe-to-Spend Runway").

## Repository & Zip Structure

```
The_Zamned-Hackfront-main/
├── app.py                  # Main FastAPI application & static file router
├── config.py               # Environment variables, API keys & CORS setup
├── core.py                 # Deterministic cadence calculation & financial math
├── gemini_analyzer.py      # LLM dark pattern analysis & commitment enrichment
├── neo4j_graph.py          # Neo4j Graph Database engine & Cypher query builder
├── pdf_parser.py           # PyMuPDF statement & text extraction parser
├── store.py                # Data persistence, memory store & metrics calculator
├── sample_data.json        # Pre-loaded baseline transactions for instant demo
├── INTEGRATION.md          # Technical documentation for partner tech (Neo4j / AI)
├── requirements.txt        # Python dependency manifest
├── .env.example            # Environment variables configuration template
├── routers/
│   ├── analysis.py         # Metrics, commitments & OCR upload API endpoints
│   ├── auth.py             # User access control & authentication router
│   ├── graph.py            # Neo4j graph nodes & entity relation endpoints
│   └── upload.py           # Multi-format statement & screenshot ingestion
└── public/
    ├── index.html          # Responsive single-page web dashboard
    └── assets/             # Branding logos, theme icons & visual assets

```

## Tech Stack

* **Backend Framework:** Python 3.10+, FastAPI, Uvicorn

* **AI & Vision Model:** Google GenAI SDK (`gemini-3.5-flash-lite`)

* **Graph Database:** Neo4j (Cypher Queries, Knowledge Graph)

* **Document Processing:** PyMuPDF (FitZ), Pillow (PIL), CSV

* **Frontend UI:** Single-Page Vanilla JavaScript, CSS Grid, HTML5 (Responsive layout)

## Installation & Quick Start

### 1. Clone or Unzip Project

```
unzip "The_Zamned-Hackfront-main (1).zip"
cd The_Zamned-Hackfront-main

```

### 2. Set Up Virtual Environment

```
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
NEO4J_URI=neo4j+ssc://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
JWT_SECRET=32_or_more_character_key

```

### 3. Configure Environment Variables

Create a `.env` file from `.env.example`:

```
cp .env.example .env

```

Update your credentials inside `.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
CORS_ORIGINS=["*"]

```

### 4. Run the Application

```
uvicorn app:app --reload --port 8000

```

Open **`http://127.0.0.1:8000`** in your browser.

## API Reference

| Endpoint | Method | Description | 
| ----- | ----- | ----- | 
| `GET /api/analysis` | `GET` | Returns aggregated metrics, commitment list, alerts, and metadata | 
| `POST /api/ocr/upload` | `POST` | Uploads and processes bank statement PDFs, CSVs, or UPI screenshots | 
| `GET /api/graph/merchants` | `GET` | Returns mapped merchant nodes and price hike edges from Neo4j | 
| `POST /api/auth/login` | `POST` | User authentication and session management | 

## License

Distributed under the **MIT License**. Built for hackFront India 2026.
