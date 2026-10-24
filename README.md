# Web Agent (starter)

Plan, act, observe loop where an LLM picks one step at a time and our code runs it through TinyFish.

## Setup
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # add TINYFISH_API_KEY and ANTHROPIC_API_KEY

## Run
    pytest                               # no keys needed, uses mocks
    python -m scripts.hello_tinyfish     # step 1: live TinyFish call
    python -m scripts.try_agent "goal"   # step 2: full agent loop
    uvicorn app.main:app --reload        # API: POST /goals

## Monitors (the part that makes it agentic over time)
    python -m scripts.add_monitor <url> "read the refund status" status 1   # no LLM needed
    uvicorn app.main:app --reload     # scheduler re-checks due monitors every SCHEDULER_TICK seconds
    GET /monitors   GET /alerts   POST /monitors/{id}/run   POST /goals   POST /goals/{id}/reply

## Demo portal (edit status live to trigger an alert)
    uvicorn demo_portal.app:app --port 9000    # then: ngrok http 9000  (TinyFish runs in the cloud)
    open <public-url>/admin and click a status

## Layout
    app/tinyfish/client.py   TinyFish Agent, Search, Fetch wrapper
    app/agent/tools.py       tools, budgets, read-only guard, pause for user
    app/agent/loop.py        the agent loop + pause/resume
    app/db.py                SQLite: monitors, snapshots, alerts
    app/monitors/            compare.py (diff), runner.py (one check), scheduler.py (timer loop)
    app/notify.py            alerts: console + optional Telegram
    demo_portal/app.py       fake portal for the live demo
    app/main.py              FastAPI entry point
