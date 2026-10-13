# Crisis ResQ — Cache Cube

**Disaster-resilient mesh communication prototype with SOS intake, store-and-forward simulation, and optional Groq LLM triage.**

This is a formal Python MVP based on the uploaded HACK-X pitch deck. It includes a Streamlit rescue dashboard, SQLite persistence, rule-based priority scoring, a multi-hop relay simulator, CSV export, and an optional Groq-hosted LLM summary. The configured LLM is `openai/gpt-oss-20b` (20B parameters; within the requested cap).

> **Scope and safety:** This Python MVP simulates relay behavior. It does not implement actual Android BLE/Wi-Fi Direct transport, phone GPS APIs, or dispatch emergency services. It is a hackathon prototype, not an operational emergency system. AI summaries are advisory and must be reviewed by people.

## Features

- Structured SOS form: emergency type, people affected, location coordinates/description, battery, and message.
- Local SQLite storage with unique message IDs and status tracking.
- Transparent priority heuristic (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- Mesh relay simulation: hops, TTL limit, duplicate-message detection, intermittent connectivity, and store-and-forward queue behavior.
- Optional Groq LLM incident brief with a rule-based fallback if no key is configured or the API is unavailable.
- Filterable message log and CSV export.
- Unit tests for priority and relay logic.

## Project structure

```text
crisis_resq/
├── app.py                 # Streamlit UI / command dashboard
├── src/
│   ├── __init__.py
│   ├── ai_service.py      # Groq LLM and fallback triage summary
│   ├── database.py        # SQLite persistence
│   └── mesh.py            # Priority rules and relay simulation
├── tests/
│   └── test_mesh.py
├── data/                  # Local database (ignored by Git)
├── .env.example           # Safe template; no real secrets
├── .gitignore
├── requirements.txt
└── README.md
```

## Run on Windows (PowerShell)

1. Install Python 3.10 or newer.
2. Extract the ZIP and open the `crisis_resq` folder in VS Code.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt and run `.venv\Scripts\activate.bat` instead.

4. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

5. Create your private environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

   Open `.env` and replace `your_groq_api_key_here` with your real Groq API key. Never paste the key into Python source code, screenshots, or Git commits. Keep `.env` private; `.gitignore` excludes it.

6. Start the app:

   ```powershell
   python -m streamlit run app.py
   ```

   Streamlit will show a local URL, usually `http://localhost:8501`.

7. To run tests:

   ```powershell
   python -m pytest -q
   ```

## Groq model configuration

Default: `openai/gpt-oss-20b`, configured by `GROQ_MODEL` in `.env`. It is a hosted API model; the weights are not downloaded or run locally on your laptop. Before presenting, verify that the model is currently enabled for your Groq account. If Groq retires or restricts it, choose a currently available Groq model with **20B parameters or fewer** and update `GROQ_MODEL`. Do not use 70B models under the stated constraint.

If `GROQ_API_KEY` is empty, the app still runs and uses a rule-based summary. API errors are caught and fall back to the local summary.

## Demo walkthrough

1. Open **Submit SOS**, create an alert for a trapped person or medical emergency.
2. Return to **Overview** to see the alert and summary metrics.
3. Open **Mesh Simulator**, select the SOS and simulate a connected or intermittent network.
4. Open **AI Triage** and generate a brief; the app uses Groq if configured, otherwise it falls back to deterministic text.
5. Open **Message Log** to update status and export CSV.

## Architecture

`SOS intake → SQLite local persistence → rule-based priority → relay simulator (message ID + hop limit + queue behavior) → gateway/server concept → rescue dashboard → optional Groq-generated triage brief`

## Security and limitations

- Do not commit `.env` or publish API keys.
- The demo stores personal/location details in a local SQLite database; use fictional data in presentations.
- This version does not provide authentication, encryption, real peer discovery, guaranteed delivery, or production-grade medical triage.
- Rule-based priority is a demonstration heuristic, not a validated emergency severity model.
- Real mesh networking would require a native Android implementation using Nearby Connections / Wi-Fi Direct and rigorous testing under network loss, battery constraints, and background execution limits.
