"""Fake refund portal for the live demo. Run: uvicorn demo_portal.app:app --port 9000
TinyFish's browser runs in the cloud, so expose this publicly first, e.g.:  ngrok http 9000
Then watch the public URL, and flip the status from /admin during the demo."""
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()
STATE = {"status": "Initiated", "updated": time.strftime("%d %b %Y, %H:%M")}
STATUSES = ["Initiated", "Processing", "Credited", "Rejected"]


@app.get("/", response_class=HTMLResponse)
def portal():
    return f"""<html><head><title>Refund Portal</title></head><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
<h2>Airline Refund Portal</h2>
<p>Booking reference: <b>ABC123</b></p>
<p>Refund amount: <b>Rs 8,420</b></p>
<p>Refund status: <b id="status">{STATE['status']}</b></p>
<p>Last updated: {STATE['updated']}</p></body></html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin():
    links = " ".join(f'<a href="/set/{s}"><button style="padding:10px;margin:4px">{s}</button></a>' for s in STATUSES)
    return f'<html><body style="font-family:sans-serif;margin:40px"><h3>Demo controls</h3><p>Current: <b>{STATE["status"]}</b></p>{links}</body></html>'


@app.get("/set/{status}")
def set_status(status: str):
    if status in STATUSES:
        STATE["status"], STATE["updated"] = status, time.strftime("%d %b %Y, %H:%M")
    return RedirectResponse("/admin")
