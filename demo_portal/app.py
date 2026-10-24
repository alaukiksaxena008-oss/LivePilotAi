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


@app.get("/scholarship", response_class=HTMLResponse)
@app.post("/scholarship", response_class=HTMLResponse)
def scholarship_portal(
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    dob: str | None = None,
    id_number: str | None = None,
    college: str | None = None,
    degree: str | None = None,
    cgpa: str | None = None,
):
    if full_name and email and college:
        return f"""<html><head><title>Scholarship Confirmation</title></head><body style="font-family:sans-serif;max-width:540px;margin:40px auto;background:#E5E6E5;padding:24px;border-radius:12px;border:1px solid #c7cac7">
<div style="text-align:center;color:#0e7979"><h2>🎉 Application Submitted Successfully!</h2></div>
<p style="font-size:14px;color:#334155">Your application for the <b>National Higher Education Scholarship 2026</b> has been received and logged.</p>
<hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0"/>
<p>Application ID: <b style="color:#0e7979">#SCH-2026-8941</b></p>
<p>Applicant Name: <b>{full_name}</b></p>
<p>Email: <b>{email}</b> | Phone: <b>{phone or 'Verified'}</b></p>
<p>Date of Birth: <b>{dob or 'Verified'}</b> | ID Number: <b>{id_number or 'Verified'}</b></p>
<p>College / Institute: <b>{college}</b></p>
<p>Degree: <b>{degree or 'B.Tech'}</b> | CGPA: <b>{cgpa or '8.9'}</b></p>
<p>Application Status: <b style="color:#0284c7;background:#e0f2fe;padding:2px 8px;border-radius:4px">UNDER REVIEW</b></p>
<p style="font-size:12px;color:#64748b;margin-top:20px">Verification timestamp: {time.strftime('%d %b %Y, %H:%M')}. An alert has been dispatched to your registered LifePilot account.</p>
</body></html>"""
    else:
        return """<html><head><title>National Scholarship Application Portal</title></head><body style="font-family:sans-serif;max-width:540px;margin:40px auto;background:#E5E6E5;padding:24px;border-radius:12px;border:1px solid #c7cac7">
<h2 style="color:#0e7979;margin-top:0">National Higher Education Scholarship 2026</h2>
<p style="font-size:13px;color:#64748b">Please enter your candidate details below to submit your application.</p>
<form method="get" action="/scholarship" style="display:flex;flex-direction:column;gap:12px">
  <div>
    <label style="font-size:12px;font-weight:bold;color:#334155">Full Legal Name *</label><br/>
    <input type="text" name="full_name" id="full_name" placeholder="e.g. Riya Sharma" required style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
  </div>
  <div>
    <label style="font-size:12px;font-weight:bold;color:#334155">Email Address *</label><br/>
    <input type="email" name="email" id="email" placeholder="e.g. riya@lifepilot.ai" required style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <div>
      <label style="font-size:12px;font-weight:bold;color:#334155">Phone Number</label><br/>
      <input type="text" name="phone" id="phone" placeholder="+91 98765 43210" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#334155">Date of Birth (YYYY-MM-DD)</label><br/>
      <input type="text" name="dob" id="dob" placeholder="1999-04-12" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
    </div>
  </div>
  <div>
    <label style="font-size:12px;font-weight:bold;color:#334155">Government ID / Passport / Aadhaar Number</label><br/>
    <input type="text" name="id_number" id="id_number" placeholder="IND-849204" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
  </div>
  <div>
    <label style="font-size:12px;font-weight:bold;color:#334155">College / University Name *</label><br/>
    <input type="text" name="college" id="college" placeholder="Delhi Technological University" required style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <div>
      <label style="font-size:12px;font-weight:bold;color:#334155">Degree Program</label><br/>
      <input type="text" name="degree" id="degree" placeholder="B.Tech Computer Science" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
    </div>
    <div>
      <label style="font-size:12px;font-weight:bold;color:#334155">Cumulative GPA / Percentage</label><br/>
      <input type="text" name="cgpa" id="cgpa" placeholder="8.9" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box" />
    </div>
  </div>
  <div style="margin-top:12px">
    <button type="submit" id="submit-application-btn" style="background:#0e7979;color:white;padding:10px 20px;border:none;border-radius:6px;font-weight:bold;cursor:pointer">Submit Scholarship Application</button>
  </div>
</form>
</body></html>"""

