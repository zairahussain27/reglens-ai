import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from compliance_engine import run_compliance_check

# Test business profile — Digital Payments Startup
test_profile = {
    "business_type": "Private Limited Company",
    "industry": "FinTech - Digital Payments",
    "services": "Online payment gateway, wallet services, UPI transactions",
    "customer_type": "Retail Consumers (B2C)",
    "transaction_type": "Digital Payments / UPI",
    "revenue": "Under ₹1 Crore"
}
print("🔍 Running RegLens AI compliance check...\n")
result = run_compliance_check(test_profile)
print(result)