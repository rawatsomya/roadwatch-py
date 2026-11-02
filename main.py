import os, shutil, uuid, threading
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from detector import analyze_video

BASE = os.path.dirname(os.path.abspath(__file__))
UP, OUT = f"{BASE}/uploads", f"{BASE}/outputs"
os.makedirs(UP, exist_ok=True); os.makedirs(OUT, exist_ok=True)

app = FastAPI(title="RoadWatch AI")
jobs = {}


def run(job_id, path):
    try:
        out = f"{OUT}/{job_id}.mp4"
        result = analyze_video(path, out, OUT, job_id,
                               lambda p: jobs[job_id].update(progress=p))
        jobs[job_id].update(status="done", progress=100,
                            video=f"/outputs/{job_id}.mp4", **result)
    except Exception as e:
        jobs[job_id].update(status="error", error=str(e))


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(400, "Please upload a video file")
    job_id = uuid.uuid4().hex[:10]
    path = f"{UP}/{job_id}_{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    jobs[job_id] = {"status": "processing", "progress": 0}
    threading.Thread(target=run, args=(job_id, path), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Unknown job")
    return jobs[job_id]


app.mount("/outputs", StaticFiles(directory=OUT), name="outputs")

app.mount("/static", StaticFiles(directory=f"{BASE}/static"), name="static")

@app.get("/")
def index():
    return FileResponse(f"{BASE}/static/index.html")
