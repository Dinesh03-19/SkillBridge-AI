# SkillBridge AI — AI-Powered Quiz/MCQ Generation Module (MoSPI / SIH26101)

Standalone, production-grade Quiz/MCQ Generation module for **SkillBridge AI**. This module takes uploaded training material (PDF/DOCX/TXT), retrieves the most relevant content for a given skill using local vector embeddings, and generates source-grounded multiple-choice questions with zero hallucinated facts using Google Gemini API (`gemini-2.0-flash` / `gemini-2.5-pro`).

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
3. **Local & Free Embeddings**:
   - Local `sentence-transformers` (`all-MiniLM-L6-v2`) and persistent `ChromaDB` vector storage with zero embedding API cost.
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
GEMINI_MODEL=gemini-2.0-flash
DATABASE_URL=sqlite:///./skillbridge.db
CHROMA_PERSIST_DIR=./chroma_data
MAX_QUESTIONS_PER_REQUEST=10
GENERATION_TEMPERATURE=0.3
MOCK_GEMINI_ON_MISSING_KEY=true
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

- `POST /api/materials/upload` — Upload PDF/DOCX/TXT and trigger chunking & ChromaDB embedding.
- `GET /api/materials` & `GET /api/materials/{skill_id}` — List uploaded materials.
- `POST /api/quizzes/generate` — Generate grounded quiz with Gemini structured output.
- `GET /api/quizzes` & `GET /api/quizzes/{quiz_id}` — Fetch quizzes and questions.
- `POST /api/quizzes/{quiz_id}/submit` — Submit answers and calculate auto-grading results.
- `GET /api/quizzes/{quiz_id}/questions/{question_id}/source` — Fetch exact verbatim source excerpt for the "Why this question?" UI.
- `GET /api/logs` — Inspect AI generation audit logs & discarded non-grounded questions.
