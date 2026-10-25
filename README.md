# SkillBridge AI — AI-Powered Quiz/MCQ Generation Module (MoSPI / SIH26101)

Standalone, production-grade Quiz/MCQ Generation module for **SkillBridge AI**. This module takes uploaded training material (PDF/DOCX/TXT), retrieves the most relevant content for a given skill using local vector embeddings, and generates source-grounded multiple-choice questions with zero hallucinated facts using Google Gemini API.

---

## 🌟 Key Features

1. **Zero-Hallucination Source Traceability ("Why this Question?")**:
   - Every single generated question contains a `source_excerpt` verbatim quote from the training manual.
   - Interactive UI reveals the originating document title, chunk index, and exact sentence.
2. **Defensive Grounding & Quality Guardrails**:
   - **Structured Schema Enforcement**: Uses `google-genai` SDK's native JSON schema validation (`response_schema=QuizGenerationResponse`).
   - **Fuzzy Grounding Validation**: Evaluates string similarity ratio using `difflib.SequenceMatcher` (threshold >= 0.85). Questions failing grounding checks are discarded.
   - **Option Count & Correct Index Check**: Rejects any questions not having exactly 4 distinct options and valid index (0-3).
   - **Near-Duplicate Question Rejection**: Automatically detects and prunes duplicate formulations.
   - **Transparent Notes (`generation_notes`)**: If source material lacks distinct facts, the system generates fewer questions and explains why instead of padding with hallucinations.
3. **Local & Production Embeddings**:
   - Local `sentence-transformers` (`all-MiniLM-L6-v2`) and persistent `ChromaDB` for development; Gemini embeddings and Qdrant Cloud for production.
4. **Interactive Glassmorphic Web UI**:
   - Document Hub with upload, token chunking, and embedding progress animations.
   - Assessment Station with one-question-at-a-time evaluation, timers, auto-grading, and instant feedback.
   - Full Audit & AI Logs modal for demo judges.

---

## 🚀 Quick Start

### 1. Configure Environment
Edit `.env` (or copy from `.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
DATABASE_URL=sqlite:///./skillbridge.db
CHROMA_PERSIST_DIR=./chroma_data
MAX_QUESTIONS_PER_REQUEST=10
GENERATION_TEMPERATURE=0.3
MOCK_GEMINI_ON_MISSING_KEY=true
```

For local development, install the development dependencies, which include the local ChromaDB and optional sentence-transformer embedding backend:
```powershell
python -m pip install -r requirements-dev.txt
```

### 2. Seed Sample Training Curricula
Seed the Indian Government / MoSPI official statistical manuals:
```powershell
python backend/seed.py
```

### 3. Start the Server
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser!

---

## 🧪 Running Automated Tests
```powershell
python -m unittest tests/test_pipeline.py
```

---

## 📡 REST API Endpoints

- `POST /api/materials/upload` — Upload PDF/DOCX/TXT and trigger chunking and vector indexing.
- `GET /api/materials` & `GET /api/materials/{skill_id}` — List uploaded materials.
- `POST /api/quizzes/generate` — Generate grounded quiz with Gemini structured output.
- `GET /api/quizzes` & `GET /api/quizzes/{quiz_id}` — Fetch quizzes and questions.
- `POST /api/quizzes/{quiz_id}/submit` — Submit answers and calculate auto-grading results.
- `GET /api/quizzes/{quiz_id}/questions/{question_id}/source` — Fetch exact verbatim source excerpt for the "Why this question?" UI.
- `GET /api/logs` — Inspect AI generation audit logs & discarded non-grounded questions.

---

## Deploying the complete app to Vercel

The Vercel deployment runs the FastAPI app as a Python Function. Vercel's function filesystem is temporary, so production uses managed services instead of the local SQLite/Chroma directories:

- **Neon Postgres** for application data (`DATABASE_URL`)
- **Qdrant Cloud** for persistent vector search (`QDRANT_URL` and `QDRANT_API_KEY`)
- **Vercel Blob**, configured as a **private** store, for uploaded source files
- **Google Gemini API** for quiz generation and production embeddings (`GEMINI_API_KEY`)
- **Vercel SSO deployment protection** for team-only app access

The deployed upload flow sends files directly from the browser to private Blob storage, so supported PDF, DOCX, and TXT uploads can be up to 25 MB without passing through Vercel Function request-body limits. The project must remain SSO-protected; custom domains are not covered by the current protection scope.

### One-time setup

1. Connect the Vercel project to `Dinesh03-19/SkillBridge-AI`, with the repository root as the project root.
2. Create/connect a Neon Postgres database and add its connection string as `DATABASE_URL`. Use the pooled connection URL when available.
3. Create a Qdrant Cloud cluster and add `QDRANT_URL` and `QDRANT_API_KEY`. The app creates its configured collection on first use.
4. Create a **private** Vercel Blob store and connect it to the Vercel project. The Blob SDK uses Vercel OIDC or `BLOB_READ_WRITE_TOKEN`.
5. Add `GEMINI_API_KEY` and these production settings in Vercel:
   ```text
   VECTOR_STORE=qdrant
   QDRANT_COLLECTION=skillbridge_materials
   EMBEDDING_MODEL=gemini-embedding-001
   EMBEDDING_DIMENSION=768
   ```
6. Keep Vercel SSO protection enabled for all deployment URLs. The project has no application login, so this is required to restrict the API and upload-token endpoint to team members.
7. Deploy to Production. After the environment variables are configured, initialize the demo data once from the project root:
   ```powershell
   vercel env run --environment=production -- python -m backend.seed
   ```

Never commit `.env` or paste deployment secrets into source control. The repository's `.env.example` contains local-development defaults; set production values in Vercel Project Settings.

After editing `frontend/blob-upload.js`, rebuild its static browser module before deploying:
```powershell
npm install
npm run bundle:uploads
```
