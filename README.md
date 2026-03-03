# TechZone WhatsApp Business Automation System

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)
![Flask](https://img.shields.io/badge/Flask-SocketIO-lightgrey.svg)
![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E.svg)
![Redis](https://img.shields.io/badge/Cache-Redis-red.svg)
![Railway](https://img.shields.io/badge/Deploy-Railway-blueviolet.svg)

An enterprise-grade WhatsApp customer service automation system powered by multi-agent AI architecture. Built for TechZone Electronics as a portfolio demonstration of production-ready AI automation.

---

## Portfolio

**Website:** https://datawebify.com
**Project Page:** https://datawebify.com/projects/whatsapp-automation
**GitHub:** https://github.com/umair801/whatsApp_business_automation
**Live API:** https://leads.datawebify.com

---

## Overview

TechZone WhatsApp Automation handles customer inquiries 24/7 with intelligent routing, multilingual support, and real-time business analytics; eliminating 73% of manual support costs while scaling to 5x conversation volume.

**Key Results:**
- Response time reduced from 18 minutes to under 2 seconds
- Support cost reduced from Rs. 240,000/month to Rs. 65,000/month
- 4.2-month ROI payback period
- 175% ROI over 12 months

---

## Features

### Core Agent
- Multi-agent pipeline: Language → Sentiment → Intent → Response
- Multilingual support: English, Urdu, Roman Urdu
- RAG-powered product knowledge base (ChromaDB)
- Function calling for live order placement and inventory checks
- Conversation memory with Redis caching + Supabase persistence

### Business Intelligence
- Real-time dashboard with WebSocket live updates
- Sentiment analysis with automatic complaint escalation (SLA: 15 min)
- Analytics engine: KPIs, peak hours, revenue tracking, satisfaction scores
- CSV and PDF export with branded ReportLab reports
- Role-based access with JWT authentication (8-hour sessions)

### Production Infrastructure
- Gunicorn + Eventlet production server
- Redis caching with graceful fallback
- Structured JSON logging with health check endpoints
- Startup validation for environment and knowledge base
- Railway-ready deployment configuration

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask, Flask-SocketIO |
| AI | OpenAI GPT-4o-mini, LangChain |
| Vector DB | ChromaDB (RAG) |
| Database | Supabase (PostgreSQL) |
| Cache | Redis |
| WhatsApp | Twilio API |
| Auth | PyJWT |
| Export | ReportLab |
| Deployment | Railway, Gunicorn, Eventlet |

---

## Project Structure

```
whatsApp_business_automation/
├── app.py                  # Main application entry point
├── analytics.py            # Analytics engine and KPI tracking
├── auth_manager.py         # JWT authentication
├── escalation_handler.py   # Complaint escalation with SLA tracking
├── export_manager.py       # CSV and PDF report generation
├── health_checks.py        # Production health check endpoints
├── logging_config.py       # Structured JSON logging
├── order_manager.py        # Order placement via function calling
├── product_knowledge.py    # RAG knowledge base (ChromaDB)
├── redis_cache.py          # Redis caching with graceful fallback
├── sentiment_analyzer.py   # Sentiment analysis and escalation triggers
├── startup_check.py        # Production startup validation
├── websocket_manager.py    # Real-time WebSocket events
├── templates/
│   ├── dashboard.html      # Flask analytics dashboard
│   └── login.html          # JWT login page
├── Procfile                # Railway/Heroku process configuration
├── railway.json            # Railway deployment settings
├── requirements.txt        # Python dependencies
├── runtime.txt             # Python version pinning
└── .env.example            # Environment variable template
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook` | Twilio WhatsApp webhook receiver |
| GET | `/health` | Production health check |
| GET | `/dashboard` | Analytics dashboard (JWT required) |
| POST | `/login` | JWT authentication |
| GET | `/api/analytics` | Analytics data (JWT required) |
| GET | `/api/conversations` | Conversation history (JWT required) |
| GET | `/api/escalations` | Active escalations (JWT required) |
| GET | `/export/csv` | Export conversations as CSV |
| GET | `/export/pdf` | Export report as PDF |
| GET | `/api/stats` | System stats and cache status |

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/umair801/whatsApp_business_automation.git
cd whatsApp_business_automation
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

Required variables:
- `OPENAI_API_KEY` — OpenAI API key
- `SUPABASE_URL` and `SUPABASE_KEY` — Supabase project credentials
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` — Twilio credentials
- `JWT_SECRET` — Secret key for JWT token signing
- `ADMIN_USERNAME` and `ADMIN_PASSWORD` — Dashboard login credentials

### 4. Run Locally

```bash
python app.py
```

For production server:

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

### 5. Deploy to Railway

1. Push this repository to GitHub
2. Create a new project on [Railway](https://railway.app) from your GitHub repo
3. Add a Redis service from the Railway dashboard
4. Set all environment variables in Railway > Variables
5. Railway auto-deploys on every push to main

---

## Architecture

```
WhatsApp User
     │
     ▼
Twilio API (webhook)
     │
     ▼
┌─────────────────────────────────┐
│        Multi-Agent Pipeline     │
│  Language → Sentiment → Intent  │
│         → Response Agent        │
└─────────────────────────────────┘
     │              │
     ▼              ▼
Supabase DB     Redis Cache
(persistence)   (sessions)
     │
     ▼
┌──────────────────────────┐
│   Business Intelligence  │
│  Dashboard + WebSocket   │
│  Analytics + Export      │
│  JWT Auth + Escalation   │
└──────────────────────────┘
```

---

## Business Impact

This system demonstrates enterprise AI automation with measurable ROI:

- **73% cost reduction** in customer support operations
- **5x increase** in handled conversation volume
- **100% after-hours coverage** (previously 0%)
- **<2 second response time** (previously 18 minutes average)
- **4.2-month payback period** on total investment

Full ROI case study available upon request.

---

## Portfolio

This is **Project 1 of 50** in an enterprise Agentic AI portfolio targeting $10K–$50K automation solutions for mid-market and enterprise clients.

**Consultant:** Muhammad Umair  
**Specialization:** Agentic AI Architecture, Enterprise Automation, Multi-Agent Systems  
**Stack:** Python, OpenAI, LangChain, Supabase, Redis, Docker, Railway

---

## License

This project is proprietary and developed as a portfolio demonstration. Contact for licensing or enterprise deployment inquiries.
