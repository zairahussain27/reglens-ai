# RegLens AI — Impact Model
### ET AI Hackathon 2026 | Problem Statement 5

---

## 1. Problem Scale (India)

| Metric | Figure | Source |
|---|---|---|
| Total MSMEs in India | 63 million | Ministry of MSME |
| FinTech startups in India | 10,000+ | RBI Annual Report 2023 |
| MSMEs outside formal compliance | ~70% | MSME Ministry Data |
| Cost of compliance consultant | ₹25,000–₹2,00,000/year | Industry estimate |
| Annual GST penalties collected | ₹1,200+ crore | CBIC Data 2023 |
| Businesses penalized for KYC non-compliance | 40%+ of RBI-regulated entities | RBI Report |

---

## 2. Time Saved Per Business

### Current State (without RegLens AI)
| Task | Time Taken |
|---|---|
| Identifying relevant regulations manually | 4–8 hours |
| Reading and interpreting legal PDFs | 6–12 hours |
| Consulting a CA or legal advisor | 2–5 hours (+ scheduling delay) |
| **Total per compliance review** | **12–25 hours** |

### With RegLens AI
| Task | Time Taken |
|---|---|
| Fill business profile form | 2 minutes |
| Receive compliance analysis | 30 seconds |
| Review and act on checklist | 1–2 hours |
| **Total per compliance review** | **~2 hours** |

**Time saved per business per review: 10–23 hours**
**Assuming 2 compliance reviews per year: 20–46 hours saved annually**

---

## 3. Cost Saved Per Business

| Scenario | Current Cost | With RegLens AI | Saving |
|---|---|---|---|
| Hiring compliance consultant | ₹50,000/year | ₹0 (free tool) | ₹50,000 |
| CA for GST + TDS filing advice | ₹25,000/year | ₹0 | ₹25,000 |
| Penalty avoided (avg GST penalty) | ₹15,000/incident | ₹0 if compliant | ₹15,000 |
| **Total saving per MSME per year** | | | **₹75,000–₹90,000** |

---

## 4. Aggregate Impact (Scaled)

### Conservative Scenario (0.1% of MSMEs adopt)
```
Target users     = 63,000,000 × 0.1% = 63,000 MSMEs
Time saved       = 63,000 × 30 hours = 1,890,000 hours/year
Cost saved       = 63,000 × ₹75,000 = ₹472.5 crore/year
Penalties avoided = 63,000 × ₹15,000 = ₹94.5 crore/year
```

### Moderate Scenario (1% of MSMEs adopt)
```
Target users     = 63,000,000 × 1% = 630,000 MSMEs
Time saved       = 630,000 × 30 hours = 18,900,000 hours/year
Cost saved       = 630,000 × ₹75,000 = ₹4,725 crore/year
Penalties avoided = 630,000 × ₹15,000 = ₹945 crore/year
```

---

## 5. Revenue Recovery (FinTech Segment)

| Metric | Estimate |
|---|---|
| FinTech startups in India | 10,000+ |
| Avg revenue lost to compliance delays | ₹5–20 lakh/year |
| Startups that could avoid shutdown due to non-compliance | ~15% |
| Revenue recovered per startup | ₹10 lakh (conservative) |
| **Total recoverable revenue (1,000 startups)** | **₹100 crore/year** |

---

## 6. Compliance Accuracy Improvement

| Metric | Baseline (Manual) | RegLens AI |
|---|---|---|
| Regulation identification accuracy | ~60% | ~85%+ |
| Time to identify applicable laws | 12–25 hours | 2 minutes |
| Source citation per answer | Rarely | Always |
| Hallucination risk | High (generic AI) | Low (RAG grounded) |

---

## 7. Key Assumptions

1. Average MSME spends 12–25 hours per compliance review — based on 
   industry surveys on regulatory burden for small businesses.
2. Consultant cost of ₹50,000/year is conservative — many MSMEs pay 
   more for CA + legal retainers.
3. Penalty avoidance figure of ₹15,000 per incident is based on 
   minimum GST late filing penalties — actual penalties can be higher.
4. Adoption rate of 0.1–1% is conservative given India's rapid 
   digitization and MSME smartphone penetration (70%+).
5. Accuracy improvement from 60% to 85% is based on RAG vs. 
   generic LLM performance on domain-specific QA benchmarks.

---

## 8. Non-Financial Impact

- **Democratization:** Small businesses get the same compliance 
  quality as large enterprises with legal teams
- **Innovation unlock:** Startups can enter regulated markets 
  faster without fear of unknown compliance requirements
- **Trust:** Source-cited answers build regulatory trust — 
  businesses know exactly which law applies and why
- **Formalization:** More MSMEs enter formal compliance systems, 
  contributing to GST revenue and financial inclusion