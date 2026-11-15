import os, shutil, uuid, threading
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from detector import analyze_video

BASE = os.path.dirname(os.path.abspath(__file__))
UP, OUT = f"{BASE}/uploads", f"{BASE}/outputs"
os.makedirs(UP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
app = FastAPI(title="RoadWatch AI")
jobs = {}
messages = {}
lock = threading.RLock()

class Verification(BaseModel):
    confirmed: bool

class ChatMessage(BaseModel):
    sender: str = Field(pattern="^(operator|hospital)$")
    text: str = Field(min_length=1, max_length=2000)

def get_verified(job_id):
    with lock:
        j = jobs.get(job_id)
        if j is None:
            raise HTTPException(404, "Job not found")
        if j.get("emergency_status") != "verified":
            raise HTTPException(403, "Operator must verify this incident first")
        return j

def run(job_id, path):
    try:
        out = f"{OUT}/{job_id}.mp4"
        result = analyze_video(path, out, OUT, job_id,
                               lambda p: jobs[job_id].update(progress=p))
        with lock:
            jobs[job_id].update(status="done", progress=100,
                                video=f"/outputs/{job_id}.mp4", **result)
    except Exception as e:
        with lock:
            jobs[job_id].update(status="error", error=str(e))

@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(400, "Please upload a video file")
    job_id = uuid.uuid4().hex[:10]
    path = f"{UP}/{job_id}_{os.path.basename(file.filename or 'video.mp4')}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with lock:
        jobs[job_id] = {"status": "processing", "progress": 0, "emergency_status": "unverified"}
    threading.Thread(target=run, args=(job_id, path), daemon=True).start()
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, "Unknown job")
        return jobs[job_id]

@app.post("/api/emergency/{job_id}/verify")
def verify(job_id: str, body: Verification):
    with lock:
        j = jobs.get(job_id)
        if j is None:
            raise HTTPException(404, "Job not found")
        if j.get("status") != "done" or not j.get("events"):
            raise HTTPException(400, "No completed analysis with detected incidents")
        j["emergency_status"] = "verified" if body.confirmed else "dismissed"
        return {"emergency_status": j["emergency_status"], "external_alert_sent": False}

@app.get("/api/emergency/incidents")
def incidents():
    with lock:
        return [{"job_id": jid, "events": j.get("events", []), "status": j["emergency_status"]}
                for jid, j in jobs.items() if j.get("emergency_status") == "verified"]

@app.get("/api/emergency/{job_id}/messages")
def get_messages(job_id: str):
    get_verified(job_id)
    with lock:
        return list(messages.get(job_id, []))

@app.post("/api/emergency/{job_id}/messages")
def post_message(job_id: str, body: ChatMessage):
    get_verified(job_id)
    entry = {"sender": body.sender, "text": body.text.strip(),
             "time": datetime.now(timezone.utc).isoformat()}
    if not entry["text"]:
        raise HTTPException(400, "Empty message")
    with lock:
        messages.setdefault(job_id, []).append(entry)
    return entry

app.mount("/outputs", StaticFiles(directory=OUT), name="outputs")
app.mount("/static", StaticFiles(directory=f"{BASE}/static"), name="static")

@app.get("/")
def index():
    return FileResponse(f"{BASE}/static/index.html")

@app.get("/hospital")
def hospital():
    return FileResponse(f"{BASE}/static/hospital.html")
