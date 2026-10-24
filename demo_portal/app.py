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


@app.get("/passport", response_class=HTMLResponse)
def passport_page(otp: str | None = None):
    if otp == "482910":
        return """<html><head><title>Passport Status</title></head><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
<h2>Passport Application Portal</h2>
<p>Application: <b>IND-849204</b></p>
<p>Status: <b id="status" style="color:green;font-size:18px">Dispatched via Speed Post</b></p>
<p>Tracking number: <b>SP9482019IN</b></p>
<p style="color:gray;font-size:12px">Expected delivery within 2-3 business days.</p>
</body></html>"""
    elif otp:
        return """<html><head><title>Passport Login</title></head><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
<h2>Passport Application Portal</h2>
<p style="color:red"><b>Invalid OTP. Please enter the correct 6-digit OTP sent to your phone.</b></p>
<form method="get" action="/passport">
  <p>Application ID: <b>IND-849204</b></p>
  <label for="otp">Enter 6-digit OTP:</label><br><br>
  <input type="text" id="otp" name="otp" placeholder="Enter 6-digit OTP" style="padding:8px" required />
  <button type="submit" id="submit-btn" style="padding:8px 16px">Verify & View Status</button>
</form>
</body></html>"""
    else:
        return """<html><head><title>Passport Login</title></head><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
<h2>Passport Application Portal</h2>
<p>Application ID: <b>IND-849204</b></p>
<p style="background:#fff3cd;padding:10px;border-radius:4px">⚠️ <b>Authentication Required:</b> An OTP has been sent to your registered mobile phone ending in ****89.</p>
<form method="get" action="/passport">
  <label for="otp">Enter 6-digit OTP to view status:</label><br><br>
  <input type="text" id="otp" name="otp" placeholder="e.g. 482910" style="padding:8px" required />
  <button type="submit" id="submit-btn" style="padding:8px 16px">Verify & View Status</button>
</form>
</body></html>"""

