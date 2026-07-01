import os
import re
import uuid
import shutil
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt

from rag_engine import PlacementRAG

DB_PATH = os.environ.get("DB_PATH", "chat_history.db")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# ── Allowed Email Whitelist ────────────────────────────────────────────────────
ALLOWED_EMAILS = {
    "71762308001@cit.edu.in", "71762308002@cit.edu.in", "71762308003@cit.edu.in",
    "71762308004@cit.edu.in", "71762308005@cit.edu.in", "71762308006@cit.edu.in",
    "71762308007@cit.edu.in", "71762308008@cit.edu.in", "71762308009@cit.edu.in",
    "71762308010@cit.edu.in", "71762308011@cit.edu.in", "71762308012@cit.edu.in",
    "71762308013@cit.edu.in", "71762308014@cit.edu.in", "71762308015@cit.edu.in",
    "71762308016@cit.edu.in", "71762308017@cit.edu.in", "71762308018@cit.edu.in",
    "71762308019@cit.edu.in", "71762308020@cit.edu.in", "71762308021@cit.edu.in",
    "71762308022@cit.edu.in", "71762308023@cit.edu.in", "71762308024@cit.edu.in",
    "71762308026@cit.edu.in", "71762308027@cit.edu.in", "71762308028@cit.edu.in",
    "71762308029@cit.edu.in", "71762308030@cit.edu.in", "71762308031@cit.edu.in",
    "71762308032@cit.edu.in", "71762308033@cit.edu.in", "71762308034@cit.edu.in",
    "71762308035@cit.edu.in", "71762308036@cit.edu.in", "71762308037@cit.edu.in",
    "71762308038@cit.edu.in", "71762308039@cit.edu.in", "71762308040@cit.edu.in",
    "71762308041@cit.edu.in", "71762308042@cit.edu.in", "71762308043@cit.edu.in",
    "71762308044@cit.edu.in", "71762308045@cit.edu.in", "71762308046@cit.edu.in",
    "71762308047@cit.edu.in", "71762308048@cit.edu.in", "71762308049@cit.edu.in",
    "71762308050@cit.edu.in", "71762308051@cit.edu.in", "71762308052@cit.edu.in",
    "71762308053@cit.edu.in", "71762308054@cit.edu.in", "71762308055@cit.edu.in",
    "71762308056@cit.edu.in", "71762308057@cit.edu.in", "71762308058@cit.edu.in",
    "71762308059@cit.edu.in",
    "2403717624321301@cit.edu.in", "2403717624321302@cit.edu.in",
    "2403717624322303@cit.edu.in", "2403717624322304@cit.edu.in",
    "2403717624321305@cit.edu.in", "2403717624321306@cit.edu.in",
}

# ── Database Init ─────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

    # Check if sessions table has user_id column (for migration)
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and "user_id" not in columns:
        print("Migrating sessions table: adding user_id column...")
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        conn.commit()

    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── Auth Helpers ───────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": user_id, "email": email}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_or_create_user(email: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        user_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO users (id, email, created_at) VALUES (?, ?, ?)",
            (user_id, email, created_at)
        )
        conn.commit()
        user = {"id": user_id, "email": email, "created_at": created_at}
    else:
        user = dict(user)
    conn.close()
    return user

# ── Session DB Helpers ─────────────────────────────────────────────────────────
def create_session(user_id: str, session_id: str = None, title: str = "New Chat"):
    if not session_id:
        session_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO sessions (id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, title, created_at)
    )
    conn.commit()
    conn.close()
    return {"id": session_id, "user_id": user_id, "title": title, "created_at": created_at}

def get_sessions(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
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

def delete_session(session_id: str, user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    conn.commit()
    conn.close()


# ── Migration Helper ───────────────────────────────────────────────────────────
def extract_company_name_from_text(text: str, filename: str) -> str:
    match = re.search(r"Company name\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if match:
        name = match.group(1).strip().split("\n")[0]
        name = re.sub(r'[\\/:*?"<>|]', '', name)
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

def bg_load():
    try:
        run_migration()
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


# ── Request Models ──────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

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

# ── Auth Endpoints ─────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    password = req.password.strip()

    # Check whitelist
    if email not in ALLOWED_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Access restricted to AI&DS Students only. Your email is not authorized."
        )

    # Password must equal their roll number (email prefix)
    expected_password = email.split('@')[0]
    if password != expected_password:
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")

    # Auto-create user on first login
    user = get_or_create_user(email)

    # Issue JWT token
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]}
    }

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# ── Company Endpoint ───────────────────────────────────────────────────────────
@app.get("/api/companies")
def get_companies(current_user: dict = Depends(get_current_user)):
    companies = []
    kb_dir = Path("knowledge_base")
    if kb_dir.exists():
        companies = sorted([d.name for d in kb_dir.iterdir() if d.is_dir()])
    return {"companies": companies}

# ── History Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/history")
def get_all_sessions(current_user: dict = Depends(get_current_user)):
    sessions = get_sessions(current_user["id"])
    if not sessions:
        new_sess = create_session(user_id=current_user["id"])
        sessions = [new_sess]
    return sessions

@app.get("/api/history/{session_id}")
def get_session_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    messages = get_messages(session_id)
    return {"session_id": session_id, "messages": messages}

@app.post("/api/history/new")
def post_new_session(req: Optional[SessionRequest] = None, current_user: dict = Depends(get_current_user)):
    title = req.title if req else "New Chat"
    sess = create_session(user_id=current_user["id"], title=title)
    return sess

@app.delete("/api/history/{session_id}")
def delete_chat_session(session_id: str, current_user: dict = Depends(get_current_user)):
    delete_session(session_id, current_user["id"])
    return {"status": "success"}

# ── Query Endpoint ─────────────────────────────────────────────────────────────
@app.post("/api/query")
def post_query(req: QueryRequest, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE id = ? AND user_id = ?", (req.session_id, current_user["id"]))
    session_exists = cursor.fetchone()
    conn.close()

    current_session_id = req.session_id
    if not session_exists:
        create_session(user_id=current_user["id"], session_id=current_session_id)

    answer = get_rag().query(req.question, company=req.company, settings=req.settings)

    add_message(current_session_id, "user", req.question, req.company)
    updated_title = add_message(current_session_id, "assistant", answer, req.company)

    return {
        "answer": answer,
        "session_id": current_session_id,
        "session_title": updated_title
    }

# ── Upload Endpoint ────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_files(
    company: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
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

# ── Reindex Endpoint ───────────────────────────────────────────────────────────
@app.post("/api/reindex")
def post_reindex(current_user: dict = Depends(get_current_user)):
    get_rag().rebuild_database()
    return {
        "status": "success",
        "total_documents": get_rag().get_doc_count(),
        "companies": sorted(list(get_rag().company_names))
    }

# ── Scrape Endpoint ────────────────────────────────────────────────────────────
@app.post("/api/scrape")
def post_scrape(req: ScrapeRequest, current_user: dict = Depends(get_current_user)):
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
