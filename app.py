import os
import re
import uuid
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from rag_engine import PlacementRAG

DB_PATH = os.environ.get("DB_PATH", "chat_history.db")

# ── Database Init ─────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            company TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_session(session_id: str = None, title: str = "New Chat"):
    if not session_id:
        session_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
        (session_id, title, created_at)
    )
    conn.commit()
    conn.close()
    return {"id": session_id, "title": title, "created_at": created_at}

def get_sessions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_messages(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_message(session_id: str, role: str, content: str, company: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content, company, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, company, created_at)
    )
    
    # Update session title if it is "New Chat" and this is the first user message
    if role == "user":
        cursor.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if session and session["title"] == "New Chat":
            words = content.split()
            title = " ".join(words[:5])
            if len(words) > 5:
                title += "..."
            title = title[:50]
            cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
            
    conn.commit()
    conn.close()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
    session = cursor.fetchone()
    title = session["title"] if session else "New Chat"
    conn.close()
    return title

def delete_session(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ── Migration Helper ───────────────────────────────────────────────────────────
def extract_company_name_from_text(text: str, filename: str) -> str:
    match = re.search(r"Company name\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if match:
        name = match.group(1).strip().split("\n")[0]
        name = re.sub(r'[\/:*?"<>|]', '', name)
        return name.strip()
    
    stem = Path(filename).stem
    stem_clean = re.sub(r'(?i)(_FB|Feedback|FEEDBACK|_Feedback|\(1\)|\(2\))', '', stem)
    stem_clean = stem_clean.replace("_", " ").replace("-", " ").strip()
    return stem_clean.title()


# ── FastAPI App Setup ──────────────────────────────────────────────────────────
app = FastAPI(title="CIT Placement Assistant")

# Init DB
init_db()

# Init RAG (Lazy Loader)
import threading
rag = None
rag_lock = threading.Lock()

def get_rag():
    global rag
    if rag is None:
        with rag_lock:
            if rag is None:
                print("Initializing RAG engine (loading sentence-transformers)...")
                rag = PlacementRAG()
                print("RAG engine initialized successfully!")
    return rag

def run_migration():
    pdf_dir = Path("pdfs")
    kb_dir = Path("knowledge_base")
    if pdf_dir.exists():
        pdf_files = list(pdf_dir.rglob("*.pdf"))
        if pdf_files:
            print(f"Found {len(pdf_files)} PDFs in pdfs/ folder. Migrating to knowledge_base/...")
            kb_dir.mkdir(parents=True, exist_ok=True)
            for pdf_path in pdf_files:
                try:
                    text = get_rag().extract_text_from_pdf(str(pdf_path))
                    company = extract_company_name_from_text(text, pdf_path.name)
                    
                    company_folder = kb_dir / company
                    company_folder.mkdir(parents=True, exist_ok=True)
                    
                    target_path = company_folder / pdf_path.name
                    shutil.move(str(pdf_path), str(target_path))
                    print(f"Migrated {pdf_path.name} -> knowledge_base/{company}/{pdf_path.name}")
                except Exception as e:
                    print(f"Failed to migrate {pdf_path.name}: {e}")
                    
            try:
                for root, dirs, files in os.walk(str(pdf_dir), topdown=False):
                    for d in dirs:
                        dir_path = Path(root) / d
                        if dir_path.exists() and not any(dir_path.iterdir()):
                            dir_path.rmdir()
                if not any(pdf_dir.iterdir()):
                    pdf_dir.rmdir()
            except Exception as e:
                print(f"Error cleaning up empty pdf folders: {e}")

# Index knowledge base contents asynchronously in the background so it doesn't block startup
def bg_load():
    try:
        # Run file migration to organize PDFs by company subdirectory in the background
        run_migration()
        # Initialize RAG engine in background
        rag_instance = get_rag()
        print("Starting background knowledge base indexing...")
        rag_instance.load_knowledge_base()
        print("Background indexing complete!")
    except Exception as e:
        print(f"Error in background indexing: {e}")

threading.Thread(target=bg_load, daemon=True).start()

# Static files directory structure
static_dir = Path("static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Request Validation Models ──────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    company: Optional[str] = None
    session_id: str
    settings: Optional[Dict[str, Any]] = None

class SessionRequest(BaseModel):
    title: Optional[str] = "New Chat"

class ScrapeRequest(BaseModel):
    company: str
    serper_api_key: Optional[str] = None


# ── REST Endpoints ─────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Placement Assistant Backend</h1><p>Static files not found yet.</p>")

@app.get("/api/companies")
def get_companies():
    companies = []
    kb_dir = Path("knowledge_base")
    if kb_dir.exists():
        companies = sorted([d.name for d in kb_dir.iterdir() if d.is_dir()])
    return {"companies": companies}

@app.get("/api/history")
def get_all_sessions():
    sessions = get_sessions()
    if not sessions:
        new_sess = create_session()
        sessions = [new_sess]
    return sessions

@app.get("/api/history/{session_id}")
def get_session_messages(session_id: str):
    messages = get_messages(session_id)
    return {"session_id": session_id, "messages": messages}

@app.post("/api/history/new")
def post_new_session(req: Optional[SessionRequest] = None):
    title = req.title if req else "New Chat"
    sess = create_session(title=title)
    return sess

@app.delete("/api/history/{session_id}")
def delete_chat_session(session_id: str):
    delete_session(session_id)
    return {"status": "success"}

@app.post("/api/query")
def post_query(req: QueryRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE id = ?", (req.session_id,))
    session_exists = cursor.fetchone()
    conn.close()
    
    current_session_id = req.session_id
    if not session_exists:
        create_session(session_id=current_session_id)
        
    answer = get_rag().query(req.question, company=req.company, settings=req.settings)
    
    add_message(current_session_id, "user", req.question, req.company)
    updated_title = add_message(current_session_id, "assistant", answer, req.company)
    
    return {
        "answer": answer,
        "session_id": current_session_id,
        "session_title": updated_title
    }

@app.post("/api/upload")
async def upload_files(
    company: str = Form(...),
    files: List[UploadFile] = File(...)
):
    if not company or not company.strip():
        raise HTTPException(status_code=400, detail="Company name is required")
        
    company_cleaned = company.strip()
    kb_dir = Path("knowledge_base")
    company_folder = kb_dir / company_cleaned
    company_folder.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    for file in files:
        file_path = company_folder / file.filename
        try:
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file.filename)
        except Exception as e:
            print(f"Error saving uploaded file {file.filename}: {e}")
            
    get_rag().load_knowledge_base()
    
    return {
        "status": "success",
        "company": company_cleaned,
        "files": saved_files,
        "total_documents": get_rag().get_doc_count()
    }

@app.post("/api/reindex")
def post_reindex():
    get_rag().rebuild_database()
    return {
        "status": "success",
        "total_documents": get_rag().get_doc_count(),
        "companies": sorted(list(get_rag().company_names))
    }

@app.post("/api/scrape")
def post_scrape(req: ScrapeRequest):
    serper_key = req.serper_api_key or os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        raise HTTPException(status_code=400, detail="Serper API key is required. Configure it in the Settings modal.")
    
    company = req.company.strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company name is required")
        
    queries = [
        f"{company} interview experience Glassdoor",
        f"{company} interview questions GeeksforGeeks",
        f"{company} reviews AmbitionBox"
    ]
    
    markdown_content = f"# Web Scraped Feedback for {company}\n\n"
    markdown_content += f"Compiled on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
    
    headers = {
        "X-API-KEY": serper_key,
        "Content-Type": "application/json"
    }
    
    total_results = 0
    
    import urllib.request
    import json
    
    for q in queries:
        url = "https://google.serper.dev/search"
        payload = {"q": q, "num": 8}
        
        try:
            req_obj = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers
            )
            with urllib.request.urlopen(req_obj, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                organic = res_data.get("organic", [])
                
                if organic:
                    markdown_content += f"## Search Query: {q}\n\n"
                    for item in organic:
                        title = item.get("title", "No Title")
                        link = item.get("link", "#")
                        snippet = item.get("snippet", "")
                        
                        markdown_content += f"### [{title}]({link})\n"
                        markdown_content += f"- **Snippet**: {snippet}\n"
                        
                        attributes = item.get("attributes", {})
                        if attributes:
                            for k, v in attributes.items():
                                markdown_content += f"- **{k.title()}**: {v}\n"
                        
                        sitelinks = item.get("sitelinks", [])
                        if sitelinks:
                            markdown_content += "- **Sitelinks**:\n"
                            for sl in sitelinks:
                                sl_title = sl.get("title", "")
                                sl_link = sl.get("link", "")
                                sl_snippet = sl.get("snippet", "")
                                markdown_content += f"  - [{sl_title}]({sl_link}): {sl_snippet}\n"
                                
                        markdown_content += "\n"
                        total_results += 1
        except Exception as e:
            print(f"Error querying Serper for '{q}': {e}")
            
    if total_results == 0:
        raise HTTPException(status_code=500, detail="Failed to fetch any search results. Please check your Serper API Key.")
        
    kb_dir = Path("knowledge_base")
    company_folder = kb_dir / company
    company_folder.mkdir(parents=True, exist_ok=True)
    
    file_path = company_folder / "web_scraped_feedback.md"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scraped feedback: {e}")
        
    get_rag().load_knowledge_base()
    
    return {
        "status": "success",
        "company": company,
        "filename": "web_scraped_feedback.md",
        "results_count": total_results,
        "total_documents": get_rag().get_doc_count()
    }
