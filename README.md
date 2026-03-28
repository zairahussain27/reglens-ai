# RegLens AI 🔍
### AI-Powered Regulatory Compliance Assistant for FinTechs & MSMEs

## Problem
Indian FinTechs and MSMEs operate under regulations from RBI, GST Council, 
SEBI, and MCA — published as complex legal PDFs. Most businesses either 
under-comply (risking penalties) or over-comply (wasting resources) because 
they cannot interpret and apply regulations to their specific business context.

## Solution
RegLens AI reads real government regulations, understands your business 
profile, and tells you exactly which laws apply and what you must do — 
with explainable, auditable reasoning.

## How It Works
1. User inputs business profile (type, sector, transaction nature)
2. RAG pipeline retrieves relevant regulation chunks from 12 government documents
3. LLM reasons applicability: Applicable / Conditional / Not Applicable
4. System outputs compliance checklist + risk level + plain-English explanation

## Tech Stack
- **LLM:** Claude API (claude-sonnet-4-20250514)
- **Vector DB:** ChromaDB
- **Embeddings:** sentence-transformers
- **Backend:** Python + FastAPI
- **Frontend:** Streamlit
- **PDF Parsing:** pdfplumber

## Regulatory Coverage
- RBI KYC Master Direction
- RBI Payment Aggregators Guidelines
- RBI Digital Lending Guidelines 2022
- RBI NBFC Master Directions
- CGST Rules 2017
- MSME Udyam Registration
- FEMA 1999
- Companies Act 2013 (MCA)

## Setup Instructions
```bash
git clone https://github.com/YOUR_USERNAME/reglens-ai
cd reglens-ai
pip install -r requirements.txt
streamlit run src/app.py
```

## Hackathon
ET AI Hackathon 2026 — Problem Statement 5: Domain-Specialized AI Agents 
with Compliance Guardrails

## Team - ZenAI
- Zaira Hussain — zairahussain27
- Divyanhi Prajapati — divyanshiprajapti
