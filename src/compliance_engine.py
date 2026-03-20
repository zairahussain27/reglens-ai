import os
from groq import Groq
from retriever import retrieve
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def build_query(business_profile: dict) -> str:
    return f"""
    Business type: {business_profile['business_type']}
    Industry: {business_profile['industry']}
    Services offered: {business_profile['services']}
    Customer type: {business_profile['customer_type']}
    Transaction type: {business_profile['transaction_type']}
    Annual revenue: {business_profile['revenue']}
    """

def run_compliance_check(business_profile: dict) -> str:
    query = build_query(business_profile)
    
    # Retrieve relevant regulation chunks
    results = retrieve(query, n_results=8)
    
    # Build regulatory context
    regulatory_context = ""
    for chunk, source in results:
        regulatory_context += f"\n[Source: {source}]\n{chunk}\n"
    
    # Load prompt template
    with open("prompts/compliance.txt", "r", encoding="utf-8") as f:
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
                "content": "You are RegLens AI, a strict regulatory compliance assistant for Indian FinTechs and MSMEs. Never hallucinate. Only use provided context."
            },
            {
                "role": "user",
                "content": filled_prompt
            }
        ]
    )
    
    return response.choices[0].message.content

