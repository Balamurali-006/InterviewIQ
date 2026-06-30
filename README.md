# 🎯 CIT PlacementGPT Assistant

A premium, ChatGPT-style web application for CIT (Coimbatore Institute of Technology) students to prepare for placements using a local knowledge base of seniors' interview feedback and live external web-scraped feedback.

---

## 🚀 Features

- **ChatGPT-Style Layout**: Sleek, glassmorphic dark mode, responsive sidebar, auto-expanding text inputs, and smooth transitions.
- **Company Selection Context**: Restrict queries to a specific company context from the sidebar or search across all companies.
- **Dynamic Knowledge Base**: Scans subdirectories in the `knowledge_base/` folder. Files uploaded are indexed automatically.
- **🌐 Web Scraped Feedback (Serper API)**:
  - **Inline Search**: Under any assistant response, click the `🌐 Check Web Feedback` button to instantly scrape external reviews (Glassdoor, AmbitionBox, GeeksforGeeks) for the active company. It automatically triggers search queries and integrates findings into the chat.
  - **Fallback API Key**: Uses the default `SERPER_API_KEY` from `.env` or allows users to override it via the Settings modal.
- **Configurable LLM**: Choose between Google Gemini, OpenAI, or a local Ollama instance directly from the UI settings.
- **Chat History**: Session management with automatic session naming, reloading, and deletion stored in a local SQLite database.
- **Markdown & Code Support**: Markdown content rendering with structured bullet points, tables, code blocks, and a one-click copy button.

---

## 🛠️ Setup & Running

### 1. Create and Activate a Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell):
.venv\Scripts\activate

# Activate (Mac/Linux):
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys & Env Variables

Create or edit the `.env` file in the root of the project:

```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
SERPER_API_KEY=68d789ab1509004b741f7b8aabd9cf82a8dbe0cc
```

*Note: You can also configure API keys dynamically inside the web interface Settings modal, which will take precedence.*

### 4. Build Knowledge Base

You can structure your documents inside the `knowledge_base/` folder:

```
placement-chatbot/
├── knowledge_base/
│   ├── Zoho/
│   │   ├── Zoho_technical_questions.pdf
│   │   └── Zoho_interview_prep.txt
│   ├── Caterpillar/
│   │   └── Caterpillar_feedback.pdf
│   └── MKS Vision/
│       └── MKS_feedback.md
```

*On startup, the system will automatically scan `pdfs/` (if it exists) and migrate any flat files into organized company folders inside `knowledge_base/` for you.*

### 5. Run the Application

Start the FastAPI backend with:

```bash
python -m uvicorn app:app --reload
```

The application will be hosted at: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Testing the Web Feedback Scraper

1. Select a company (e.g. **Zoho**) in the sidebar.
2. Ask a question about that company (e.g. *"What is the interview process?"*).
3. Under the chatbot's response, click the **`🌐 Check Web Feedback`** button.
4. The system will search Google via Serper for Glassdoor, AmbitionBox, and GeeksforGeeks reviews, write them to `knowledge_base/<company>/web_scraped_feedback.md`, re-index them on the fly, and automatically trigger a chat summary query!

---

## 💻 Tech Stack & Architecture

- **Frontend**: HTML5, Vanilla CSS3 (glassmorphic theme), JavaScript (ES6+), [Marked.js](https://marked.js.org/) for rendering markdown.
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python) for asynchronous endpoints.
- **Vector Database**: [ChromaDB](https://www.trychroma.com/) for local embedding retrieval.
- **Database**: SQLite3 (built-in) for chat session storage.
- **Embeddings**: Sentence-Transformers `all-MiniLM-L6-v2` running locally.

---

## 🌐 Hosting on Render

You can easily host this application on [Render](https://render.com/)! Follow these steps:

### 1. Push Code to GitHub
1. Initialize git in your project folder (if not done already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit of placement chatbot"
   ```
2. Create a repository on GitHub and push your code there.

### 2. Create Render Web Service
1. Go to your [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the settings:
   - **Name**: `placement-assistant`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`

### 3. Add Environment Variables
Under the **Environment** tab, add the following variables:
- `PYTHON_VERSION`: `3.11.0` (Ensures compatibility with ChromaDB's dependencies)
- `GEMINI_API_KEY`: *(Your default Gemini key, so it works out of the box for visitors)*
- `SERPER_API_KEY`: `68d789ab1509004b741f7b8aabd9cf82a8dbe0cc` *(Your default Serper key for web scraping)*

### 4. Enable Persistence (Optional but Recommended)
By default, Render's disk is ephemeral (data resets on restarts). To persist chat history and dynamic file uploads:
1. Go to the **Disks** tab of your Render Web Service.
2. Click **Add Disk**:
   - **Name**: `placement-data`
   - **Mount Path**: `/data`
   - **Size**: `1 GB` (or lowest free/paid tier)
3. Go back to the **Environment** tab and add:
   - `DB_PATH`: `/data/chat_history.db`
   - `CHROMA_PATH`: `/data/chroma_db`

