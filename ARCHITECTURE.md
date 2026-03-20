# RegLens AI — Architecture Document
### ET AI Hackathon 2026 | Problem Statement 5: Domain-Specialized AI with Compliance Guardrails

---

## 1. System Overview

RegLens AI is a Retrieval-Augmented Generation (RAG) based compliance assistant 
that maps Indian government regulations to specific business profiles. It does not 
summarize documents — it makes applicability decisions with explainable reasoning.

**Core Design Principle:** Every answer must be grounded in a real government 
document. If it cannot be grounded, the system flags it rather than guessing.

---

## 2. Architecture Diagram
```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│              Streamlit Web Application                   │
│         (Business Profile Form + Results View)          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 GUARDRAIL LAYER                          │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │ Scope Validator │     │ Confidence Assessor      │   │
│  │                 │     │                          │   │
│  │ Checks if biz   │     │ Checks if retrieved      │   │
│  │ is in supported │     │ chunks are sufficient    │   │
│  │ domain          │     │ (min 3 chunks required)  │   │
│  └────────┬────────┘     └─────────────┬────────────┘   │
│           │ PASS                       │ PASS            │
└───────────┼────────────────────────────┼────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────┐
│                  RETRIEVAL LAYER                         │
│                                                          │
│   Business Profile → Query Builder → Embedding Model    │
│   (all-MiniLM-L6-v2 / sentence-transformers)            │
│                      │                                   │
│                      ▼                                   │
│              ChromaDB Vector Store                       │
│         (1,356 chunks from 11 government PDFs)          │
│                      │                                   │
│                      ▼                                   │
│         Top 8 Most Relevant Regulation Chunks           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│               REASONING LAYER                            │
│                                                          │
│   Prompt Template + Business Profile + Regulation Chunks │
│                      │                                   │
│                      ▼                                   │
│         LLaMA 3.3 70B via Groq API                      │
│         Temperature: 0.1 (strict factual mode)          │
│                      │                                   │
│   Output:                                                │
│   - Applicable / Conditional / Not Applicable           │
│   - Why it applies (grounded in retrieved chunks)       │
│   - Compliance checklist                                 │
│   - Risk level (High / Medium / Low)                    │
│   - Flags & uncertainties                               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                OUTPUT LAYER                              │
│         Structured Compliance Analysis Report            │
│    Displayed in Streamlit UI with source citations      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Knowledge Base (regulations/)
11 official government documents ingested as the sole source of truth:

| File | Authority | Coverage |
|---|---|---|
| RBI KYC Master Direction | RBI | Identity verification requirements |
| RBI Payment Aggregators Guidelines | RBI | Payment gateway compliance |
| RBI PPI Master Directions | RBI | Prepaid payment instruments |
| RBI Digital Lending Guidelines | RBI | Digital lending framework |
| RBI NBFC Master Direction | RBI | NBFC registration & operations |
| RBI Fair Practices Code | RBI | NBFC customer treatment |
| CGST Rules 2017 | GST Council | GST registration & composition |
| MSME Udyam Registration | Ministry of MSME | MSME definition & registration |
| Income Tax TDS Section 194 | CBDT | TDS provisions for businesses |
| FEMA Basic Compliance | RBI | Foreign exchange management |
| Companies Act 2013 | MCA | Company registration & filing |

### 3.2 Ingestion Pipeline (src/ingest.py)
- Parses PDFs using pdfplumber
- Chunks text into 500-word segments with 50-word overlap
- Generates embeddings using sentence-transformers (all-MiniLM-L6-v2)
- Stores in ChromaDB persistent vector store
- Total: 1,356 chunks indexed

### 3.3 Retrieval Engine (src/retriever.py)
- Converts business profile into a natural language query
- Embeds query using same model as ingestion
- Performs cosine similarity search in ChromaDB
- Returns top 8 most relevant chunks with source filenames

### 3.4 Guardrail Layer (src/compliance_engine.py)
Three enforced guardrails:
1. **Scope Validator** — rejects out-of-domain business types
2. **Confidence Assessor** — requires minimum 3 retrieved chunks
3. **Strict Mode Prompt** — LLM instructed to flag uncertainty 
   rather than guess; temperature set to 0.1

### 3.5 Reasoning Engine (src/compliance_engine.py)
- Model: LLaMA 3.3 70B Versatile via Groq API
- System prompt enforces strict grounding rules
- Prompt template structures output into fixed format
- Output always includes source citation per regulation

### 3.6 User Interface (src/app.py)
- Built with Streamlit
- Two-column business profile form
- Real-time compliance analysis on submission
- Displays structured report with risk indicators
- Disclaimer enforced on every result

---

## 4. Agent Communication Flow
```
User Input
    │
    ▼
Scope Check ──FAIL──► Out of Scope Message (no LLM called)
    │
   PASS
    │
    ▼
Query Builder
    │
    ▼
Vector Search (ChromaDB)
    │
    ▼
Confidence Check ──FAIL──► Insufficient Data Message (no LLM called)
    │
   PASS
    │
    ▼
Prompt Assembly (profile + chunks + template)
    │
    ▼
LLaMA 3.3 70B (Groq) ── temperature=0.1
    │
    ▼
Structured Compliance Report
    │
    ▼
Streamlit UI Display
```

---

## 5. Error Handling & Auditability

| Scenario | System Response |
|---|---|
| Business outside supported domain | Scope rejection message, no LLM call |
| Fewer than 3 relevant chunks found | Insufficient data warning, no LLM call |
| LLM uncertain about a regulation | Flags with ⚠️ UNCERTAIN in output |
| Regulation not in context | Returns INSUFFICIENT DATA, not a guess |
| API failure | Streamlit error message displayed |

Every output includes source document citations — making every 
decision auditable and traceable to a specific government document.

---

## 6. Tech Stack Summary

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| LLM | LLaMA 3.3 70B via Groq API |
| Vector DB | ChromaDB (persistent, local) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| PDF Parsing | pdfplumber |
| Backend | Python |
| Version Control | GitHub |

---

## 7. Scalability Path

- **More regulations:** Add PDFs to regulations/ folder, re-run ingest.py
- **More languages:** Swap embedding model for multilingual variant
- **More domains:** Extend scope validator and add domain-specific PDFs
- **Production:** Replace ChromaDB with Pinecone, deploy on AWS/GCP
- **Real-time updates:** Schedule RBI/GST portal scraping for new circulars