import os
from groq import Groq
from retriever import retrieve
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SUPPORTED_INDUSTRIES = [
    "fintech", "digital payments", "lending", "nbfc", "msme",
    "manufacturing", "gst", "ecommerce", "e-commerce", "services"
]

def is_in_scope(business_profile: dict) -> bool:
    combined = (
        business_profile.get("industry", "") +
        business_profile.get("services", "") +
        business_profile.get("transaction_type", "")
    ).lower()
    return any(keyword in combined for keyword in SUPPORTED_INDUSTRIES)

def build_query(business_profile: dict) -> str:
    return f"""
    Business type: {business_profile['business_type']}
    Industry: {business_profile['industry']}
    Services offered: {business_profile['services']}
    Customer type: {business_profile['customer_type']}
    Transaction type: {business_profile['transaction_type']}
    Annual revenue: {business_profile['revenue']}
    """

def assess_retrieval_quality(results: list) -> bool:
    # If fewer than 3 chunks retrieved, confidence is low
    return len(results) >= 3

def run_compliance_check(business_profile: dict) -> str:

    # Guardrail 1: Out of scope check
    if not is_in_scope(business_profile):
        return """
## ⚠️ Out of Scope

RegLens AI currently covers:
- FinTech & Digital Payments
- Lending & NBFC
- MSME (Manufacturing & Services)
- E-Commerce
- GST registered businesses

Your business profile does not clearly match any supported domain.

**What to do:** Consult a qualified compliance professional for domain-specific regulatory guidance.
        """

    query = build_query(business_profile)

    # Retrieve relevant regulation chunks
    results = retrieve(query, n_results=8)

    # Guardrail 2: Low confidence check
    if not assess_retrieval_quality(results):
        return """
## ⚠️ Insufficient Regulatory Data

RegLens AI could not retrieve enough relevant regulatory information for your specific business profile.

This may happen if:
- Your business model is highly specialized
- The relevant regulations are not yet in our knowledge base

**What to do:** Consult a qualified compliance professional. Do not rely on AI guidance for this case.
        """

    # Build regulatory context
    regulatory_context = ""
    for chunk, source in results:
        regulatory_context += f"\n[Source: {source}]\n{chunk}\n"

    # Load prompt template
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "compliance.txt"), "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Fill prompt
    filled_prompt = prompt_template.replace(
        "{business_profile}", query
    ).replace(
        "{regulatory_context}", regulatory_context
    )

    # Call Groq API
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2000,
        messages=[
            {
                "role": "system",
                "content": """You are RegLens AI, a strict regulatory compliance assistant for Indian FinTechs and MSMEs.

STRICT RULES:
1. Only use information from the regulatory context provided. Never use your own memory for legal facts.
2. If unsure about any regulation, explicitly flag it with ⚠️ UNCERTAIN.
3. Never present this as legal advice. Always recommend professional consultation for final decisions.
4. If a regulation is not clearly supported by the context, write INSUFFICIENT DATA — do not guess."""
            },
            {
                "role": "user",
                "content": filled_prompt
            }
        ],
        temperature=0.1  # Low temperature = more factual, less creative
    )

    return response.choices[0].message.content