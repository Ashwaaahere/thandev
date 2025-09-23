# backend/api_safe.py
import os
import sys
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker
from models import Exploit, Base
from datetime import datetime, timedelta
import math

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/thandev")

engine = create_engine(DATABASE_URL, future=True)
Session = sessionmaker(bind=engine)

app = FastAPI(title="Thandev Exploit Feed - safe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def exploit_to_safe_dict(e: Exploit):
    # Only safe fields (no code, no raw content)
    return {
        "id": e.id,
        "cve_id": e.cve_id,
        "title": e.title,
        "description": e.description,
        "cvss_v3": e.cvss_v3,
        "severity": e.severity,
        "published_at": e.published_at.isoformat() if e.published_at else None,
        "references": e.references,  # list of {url, source}
        "source_tags": e.source_tags,
        "created_at": e.created_at.isoformat() if e.created_at else None
    }

@app.get("/api/exploits")
def list_exploits(limit: int = Query(20, ge=1, le=200), cursor: int = Query(0, ge=0), severity: str = None):
    session = Session()
    try:
        q = session.query(Exploit).order_by(desc(Exploit.published_at)).offset(cursor).limit(limit)
        if severity:
            q = q.filter(Exploit.severity == severity)
        items = q.all()
        next_cursor = cursor + len(items) if len(items) == limit else None
        return JSONResponse({
            "items": [exploit_to_safe_dict(i) for i in items],
            "next_cursor": next_cursor
        })
    finally:
        session.close()

@app.get("/api/exploits/{exploit_id}")
def get_exploit(exploit_id: int):
    session = Session()
    try:
        e = session.query(Exploit).filter(Exploit.id == exploit_id).one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Not found")
        return JSONResponse(exploit_to_safe_dict(e))
    finally:
        session.close()

@app.get("/api/exploits/top")
def top_exploits(count: int = Query(5, ge=1, le=50)):
    session = Session()
    try:
        # Top defined by severity -> cvss, fallback to published_at
        order = session.query(Exploit).order_by(desc(Exploit.cvss_v3), desc(Exploit.published_at)).limit(count).all()
        return JSONResponse({"items": [exploit_to_safe_dict(e) for e in order]})
    finally:
        session.close()

@app.get("/api/stats")
def stats():
    session = Session()
    try:
        total = session.query(Exploit).count()
        since = datetime.utcnow() - timedelta(days=1)
        new_today = session.query(Exploit).filter(Exploit.published_at >= since).count()
        critical_count = session.query(Exploit).filter(Exploit.severity == "critical").count()
        return JSONResponse({
            "total_exploits": total,
            "new_today": new_today,
            "critical_count": critical_count
        })
    finally:
        session.close()

@app.post("/api/ingest")
def trigger_ingestion():
    """Trigger manual data ingestion"""
    try:
        import subprocess
        import threading
        
        def run_ingestion():
            subprocess.run([sys.executable, "real_data_ingestion.py"], 
                         cwd=os.path.dirname(__file__))
        
        # Run ingestion in background
        thread = threading.Thread(target=run_ingestion)
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            "status": "success",
            "message": "Data ingestion started in background"
        })
    except Exception as e:
        return JSONResponse({
            "status": "error", 
            "message": f"Failed to start ingestion: {str(e)}"
        }, status_code=500)
