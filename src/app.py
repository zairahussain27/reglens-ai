import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from compliance_engine import run_compliance_check

# Page config
st.set_page_config(
    page_title="RegLens AI",
    page_icon="🔍",
    layout="wide"
)

# Header
st.markdown("""
    <h1 style='text-align: center; color: #1a1a2e;'>🔍 RegLens AI</h1>
    <h4 style='text-align: center; color: #16213e;'>AI-Powered Regulatory Compliance Assistant for Indian FinTechs & MSMEs</h4>
    <hr>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/law.png", width=80)
    st.markdown("### About RegLens AI")
    st.markdown("""
    RegLens AI reads **real government regulations** and tells you exactly:
    - Which laws apply to your business
    - Why they apply
    - What you must do
    - Your compliance risk level
    """)
    st.markdown("---")
    st.markdown("**Regulatory Coverage:**")
    st.markdown("""
    - 🏦 RBI KYC & Payment Guidelines
    - 💰 NBFC & Digital Lending Rules
    - 🧾 GST & CGST Rules 2017
    - 🏭 MSME Udyam Registration
    - 📊 Income Tax TDS Provisions
    - 🌐 FEMA Compliance
    - 🏢 Companies Act 2013
    """)
    st.markdown("---")
    st.caption("ET AI Hackathon 2026 — PS5")

# Main form
st.markdown("## 📋 Enter Your Business Profile")
st.markdown("Fill in your business details below. RegLens AI will analyze which regulations apply to you.")

col1, col2 = st.columns(2)

with col1:
    business_type = st.selectbox(
        "Business Type",
        ["Private Limited Company", "LLP", "Sole Proprietorship", "Partnership Firm", "OPC"]
    )

    industry = st.selectbox(
        "Industry",
        [
            "FinTech - Digital Payments",
            "FinTech - Lending / NBFC",
            "MSME - Manufacturing",
            "MSME - Services",
            "E-Commerce",
            "SaaS / Technology"
        ]
    )

    services = st.text_area(
        "Services / Products Offered",
        placeholder="e.g. Online payment gateway, wallet services, UPI transactions",
        height=100
    )

with col2:
    customer_type = st.selectbox(
        "Customer Type",
        ["Retail Consumers (B2C)", "Businesses (B2B)", "Both B2B and B2C", "Government (B2G)"]
    )

    transaction_type = st.selectbox(
        "Primary Transaction Type",
        [
            "Digital Payments / UPI",
            "Lending / Credit",
            "Investment / Wealth",
            "Insurance",
            "Product Sales",
            "Service Billing"
        ]
    )

    revenue = st.selectbox(
        "Annual Revenue",
        [
            "Under ₹1 Crore",
            "₹1 Crore – ₹5 Crore",
            "₹5 Crore – ₹25 Crore",
            "Above ₹25 Crore"
        ]
    )

st.markdown("---")

# Submit button
if st.button("🔍 Run Compliance Check", type="primary", use_container_width=True):
    if not services.strip():
        st.error("Please describe your services before running the compliance check.")
    else:
        business_profile = {
            "business_type": business_type,
            "industry": industry,
            "services": services,
            "customer_type": customer_type,
            "transaction_type": transaction_type,
            "revenue": revenue
        }

        with st.spinner("🔍 Analyzing regulations for your business... This may take 15–30 seconds."):
            try:
                result = run_compliance_check(business_profile)

                st.markdown("---")
                st.markdown("## 📊 Compliance Analysis Report")
                st.markdown(result)

                st.markdown("---")
                st.success("✅ Analysis complete. This report is based on official government documents only.")
                st.warning("⚠️ This tool provides AI-assisted guidance only. Consult a qualified compliance professional for legal decisions.")

            except Exception as e:
                st.error(f"Error running compliance check: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
RegLens AI — Built for ET AI Hackathon 2026 | Powered by LLaMA 3.3 70B + RAG on RBI, GST, SEBI, MCA Documents
</div>
""", unsafe_allow_html=True)