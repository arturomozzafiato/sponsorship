# Outreach App (Local MVP)

A local Streamlit app that:
- Ingests an org/event proposal PDF (optional)
- Imports a list of companies (CSV)
- (Optionally) researches company websites + finds official contact emails
- Generates customized sponsorship outreach emails (LLM if configured; template fallback if offline)
- Lets you review/edit, then approve drafts
- Sends approved drafts via an SMTP worker with rate limiting + logging

## Quick start

### 1) Create a virtual env + install
```bash
cd outreach_app
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Create `.env`
Copy `.env.example` to `.env` and fill values.

### 3) Run the UI
```bash
streamlit run app.py
```

### 4) Send approved drafts (worker)
Open a second terminal:
```bash
source .venv/bin/activate
python -m outreach_app.queue.worker
```

## Company CSV format
Required column: `name`  
Optional: `website`, `industry`, `notes`

Example:
```csv
name,website,industry,notes
Example Co,example.com,FMCG,Interested in CSR youth programs
```

## LLM configuration

This app supports any **OpenAI-compatible** Chat Completions API.

- OpenAI: set `LLM_PROVIDER=openai`, `LLM_API_KEY=...`
- DeepSeek: set `LLM_PROVIDER=deepseek`, `LLM_API_KEY=...` and model `deepseek-chat` or `deepseek-reasoner` (DeepSeek is OpenAI-compatible; base URL can be `https://api.deepseek.com/v1`).

If you set `LLM_PROVIDER=none`, the app uses a safe template fallback.

## SMTP configuration

Fill these in `.env`:
- `SMTP_HOST`
- `SMTP_PORT` (usually 587)
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_FROM` (optional)

> Tip: For Gmail, you often need an **App Password** (requires 2FA). If you prefer, swap the sender module later to Gmail API / Microsoft Graph.

## Notes
- This MVP avoids “scrape 10 emails per company” because it increases spam risk and can harm deliverability. It focuses on official partnership/CSR inboxes and requires you to approve drafts.
