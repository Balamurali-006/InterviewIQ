import os
import re
import json
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import chromadb
from chromadb.utils import embedding_functions
import pdfplumber

# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_core_company_name(name: str) -> str:
    name = name.lower()
    # Remove common suffixes and clean up
    suffixes = [
        r"\binc\b",
        r"\bco\b",
        r"\bservices\b",
        r"\btechnologies\b",
        r"\bassociates\b",
        r"&\s*co",
        r"\bltd\b",
        r"\blimited\b",
        r"\bfeedback\b"
    ]
    for s in suffixes:
        name = re.sub(s, "", name)
    return name.strip()

SYSTEM_PROMPT = """You are a helpful placement assistant for CIT (Coimbatore Institute of Technology).
You have access to student feedback about companies that visited campus for placements.

Answer questions based ONLY on the context provided. Be specific, helpful and concise.
If the context doesn't have enough info, say so honestly.
Format your answers clearly — use bullet points for rounds/tips, plain text for simple facts.
Never make up salary figures, round counts, or company details.

For any coding questions mentioned, check if a LeetCode, GeeksforGeeks, or similar link exists in the context or if you know the standard link for that problem. If so, always include it immediately after the question in the format: [Link to Question](URL)."""


def format_llm_error(provider: str, e: Exception) -> str:
    err_str = str(e)
    provider = provider.lower()
    provider_upper = provider.upper()
    
    # CASE 1: Quota Exceeded (429)
    if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
        if provider == "gemini":
            return """### ⚠️ Google Gemini API Quota Exceeded (Error 429)
You have exceeded your Gemini API free tier quota (typically 15-20 requests per day). 

#### 🔧 How to fix this:
1. **Get a new/alternate Gemini API Key**:
   * Go to [Google AI Studio](https://aistudio.google.com/).
   * Click **Get API key** and create a new key.
2. **Update the settings in PlacementGPT**:
   * Click **`LLM Settings`** at the bottom-left of the sidebar.
   * Paste your new key into the **API Key** input box.
   * Click **Save Settings** to resume chatting.
3. **Alternative Options**:
   * Switch the LLM Provider to **Ollama** in settings to run models locally on your PC (100% free and unlimited).
   * Or configure an **OpenAI** API key in the settings panel."""
        elif provider == "openai":
            return """### ⚠️ OpenAI API Quota Exceeded (Error 429)
Your OpenAI API key has run out of credits or has exceeded its rate limit.

#### 🔧 How to fix this:
1. **Check your OpenAI Usage**:
   * Go to [OpenAI Usage Dashboard](https://platform.openai.com/usage) to check if your account balance is positive.
2. **Update your API Key**:
   * If you need to supply a new key, go to [OpenAI API Keys](https://platform.openai.com/api-keys) and generate a new key.
   * Click **`LLM Settings`** in the PlacementGPT sidebar.
   * Paste your new key and click **Save Settings**.
3. **Alternative**:
   * Switch provider to **Gemini** (free tier keys can be created at [Google AI Studio](https://aistudio.google.com/)) or **Ollama** (free local offline LLM)."""
           
    # CASE 2: Invalid / Unauthorized API Key (401/403)
    elif "401" in err_str or "403" in err_str or "key" in err_str.lower() or "unauthorized" in err_str.lower() or "invalid" in err_str.lower():
        if provider == "gemini":
            return """### ⚠️ Invalid Google Gemini API Key
Google Gemini rejected the API key provided.

#### 🔧 How to fix this:
1. **Verify your API Key**:
   * Check if the API key was copied correctly from [Google AI Studio](https://aistudio.google.com/).
2. **Update the settings**:
   * Click **`LLM Settings`** in the PlacementGPT sidebar.
   * Paste the correct key and click **Save Settings**."""
        elif provider == "openai":
            return """### ⚠️ Invalid OpenAI API Key
OpenAI rejected the API key provided.

#### 🔧 How to fix this:
1. **Verify your API Key**:
   * Check if the API key was copied correctly from [OpenAI API Keys](https://platform.openai.com/api-keys).
2. **Update the settings**:
   * Click **`LLM Settings`** in the PlacementGPT sidebar.
   * Paste the correct key and click **Save Settings**."""
           
    # CASE 3: General fallback
    return f"""### ⚠️ {provider_upper} API Error
The following error occurred while contacting the {provider_upper} service:

`{err_str}`

#### 🔧 Troubleshooting steps:
1. Click **`LLM Settings`** in the sidebar to verify your API Key, Provider, and Model Name.
2. If using Gemini, you can get a free key from [Google AI Studio](https://aistudio.google.com/).
3. If using OpenAI, ensure your API key has a positive billing balance at [OpenAI Platform](https://platform.openai.com/)."""


class PlacementRAG:
    def __init__(self, kb_path: str = "knowledge_base"):
        chroma_path = os.environ.get("CHROMA_PATH", "chroma_db")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="placement_data",
            embedding_function=self.ef
        )
        self._loaded_files = set()
        self.company_names = set()
        self.kb_path = Path(kb_path)
        
        # Load from Chroma DB existing metadata if any
        try:
            existing = self.collection.get()
            if existing and "metadatas" in existing and existing["metadatas"]:
                for meta in existing["metadatas"]:
                    if meta and "company" in meta:
                        self.company_names.add(meta["company"])
                        if "source" in meta:
                            self._loaded_files.add(f"{meta['company']}/{meta['source']}")
        except Exception as e:
            print(f"Error loading company names: {e}")

    def rebuild_database(self):
        try:
            self.client.delete_collection(name="placement_data")
        except Exception as e:
            print(f"Error deleting collection: {e}")
        self.collection = self.client.get_or_create_collection(
            name="placement_data",
            embedding_function=self.ef
        )
        self._loaded_files = set()
        self.company_names = set()
        self.load_knowledge_base()

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
        return text.strip()

    def extract_text_from_textfile(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""

    def chunk_text(self, text: str, company_name: str, chunk_size: int = 400) -> list[dict]:
        chunks = []
        words = text.split()
        overlap = 50
        i = 0
        chunk_id = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append({"text": chunk_text, "company": company_name, "chunk_id": chunk_id})
            i += chunk_size - overlap
            chunk_id += 1
        return chunks

    def load_knowledge_base(self):
        if not self.kb_path.exists():
            self.kb_path.mkdir(parents=True, exist_ok=True)
            return

        for company_dir in self.kb_path.iterdir():
            if not company_dir.is_dir():
                continue
            company = company_dir.name
            self.company_names.add(company)
            
            # Find all files in the company's folder
            files = []
            for ext in ["*.pdf", "*.txt", "*.md"]:
                files.extend(list(company_dir.glob(ext)))
                
            for file_path in files:
                # Key is company/filename to uniquely track loaded status
                file_key = f"{company}/{file_path.name}"
                if file_key in self._loaded_files:
                    continue
                try:
                    text = ""
                    if file_path.suffix.lower() == ".pdf":
                        text = self.extract_text_from_pdf(str(file_path))
                    elif file_path.suffix.lower() in [".txt", ".md"]:
                        text = self.extract_text_from_textfile(str(file_path))
                        
                    if not text:
                        continue
                        
                    chunks = self.chunk_text(text, company)
                    if not chunks:
                        continue
                    
                    # Generate safe ids
                    company_safe = re.sub(r"[^a-zA-Z0-9]", "_", company)
                    file_safe = re.sub(r"[^a-zA-Z0-9]", "_", file_path.stem)
                    ids = [f"{company_safe}_{file_safe}_{c['chunk_id']}" for c in chunks]
                    documents = [c["text"] for c in chunks]
                    metadatas = [{"company": company, "source": file_path.name} for c in chunks]
                    
                    existing = set(self.collection.get(ids=ids)["ids"])
                    new_items = [(i, d, m) for i, d, m in zip(ids, documents, metadatas) if i not in existing]
                    if new_items:
                        n_ids, n_docs, n_metas = zip(*new_items)
                        self.collection.add(ids=list(n_ids), documents=list(n_docs), metadatas=list(n_metas))
                    
                    self._loaded_files.add(file_key)
                except Exception as e:
                    print(f"Error loading file {file_path.name} for {company}: {e}")

    def get_doc_count(self) -> int:
        return self.collection.count()

    def query(self, question: str, company: str = None, settings: dict = None, n_results: int = 5) -> str:
        if self.collection.count() == 0:
            return "⚠️ No placement data loaded yet. Please upload company feedback documents in the sidebar."

        # Setup metadata filter
        where_filter = None
        if company and company != "All Companies":
            where_filter = {"company": company}
        
        # Determine number of chunks to query
        query_n_results = 12 if where_filter else n_results
        query_n_results = min(query_n_results, self.collection.count())

        results = self.collection.query(
            query_texts=[question],
            n_results=query_n_results,
            where=where_filter
        )
        
        if not results or not results["documents"] or not results["documents"][0]:
            return f"No relevant placement feedback found for query in context of {company or 'all companies'}."

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        context_parts = []
        for doc, meta in zip(docs, metas):
            context_parts.append(f"[Source: {meta['company']} - {meta['source']}]\n{doc}")
        context = "\n\n---\n\n".join(context_parts)

        # Parse LLM configurations
        settings = settings or {}
        provider = settings.get("provider", "gemini").lower()
        model_name = settings.get("model", "")
        api_key = settings.get("api_key", "")
        api_url = settings.get("api_url", "")

        # ── LLM Dispatcher ─────────────────────────────────────────────────────────────
        if provider == "gemini":
            api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                return "⚠️ Gemini API key is missing. Please set GEMINI_API_KEY in your env or configure it in the UI Settings modal."
            
            model_to_use = model_name or "gemini-2.5-flash"
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name=model_to_use,
                    system_instruction=SYSTEM_PROMPT
                )
                response = model.generate_content(
                    f"Context from placement feedback:\n\n{context}\n\nQuestion: {question}"
                )
                return response.text
            except Exception as e:
                return format_llm_error("gemini", e)

        elif provider == "openai":
            api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return "⚠️ OpenAI API key is missing. Please set OPENAI_API_KEY in your env or configure it in the UI Settings modal."
            
            model_to_use = model_name or "gpt-4o"
            url = api_url or "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context from placement feedback:\n\n{context}\n\nQuestion: {question}"}
                ],
                "temperature": 0.2
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    return res_data["choices"][0]["message"]["content"]
            except Exception as e:
                return format_llm_error("openai", e)

        elif provider == "ollama":
            model_to_use = model_name or "llama3"
            base_url = api_url or "http://localhost:11434"
            
            # Attempt OpenAI-compatible endpoint first
            url = f"{base_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context from placement feedback:\n\n{context}\n\nQuestion: {question}"}
                ],
                "temperature": 0.2
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    return res_data["choices"][0]["message"]["content"]
            except Exception as e:
                # Fallback to Ollama's direct /api/generate endpoint
                try:
                    generate_url = f"{base_url.rstrip('/')}/api/generate"
                    payload_gen = {
                        "model": model_to_use,
                        "prompt": f"System prompt: {SYSTEM_PROMPT}\n\nContext from placement feedback:\n\n{context}\n\nQuestion: {question}",
                        "stream": False,
                        "options": {"temperature": 0.2}
                    }
                    req = urllib.request.Request(generate_url, data=json.dumps(payload_gen).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_data = json.loads(response.read().decode("utf-8"))
                        return res_data["response"]
                except Exception as e2:
                    return f"⚠️ Ollama API Error: Could not connect to Ollama at {base_url}. Error: {str(e2)}. Make sure Ollama is running and model '{model_to_use}' is pulled."

        else:
            return f"⚠️ Unsupported LLM provider: {provider}"
