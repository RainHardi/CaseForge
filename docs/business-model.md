# Business Model and Cost Estimate

**Status:** draft estimate, 21 Nov 2026. Everything below is a planning estimate built from stated assumptions, not measured data. The assumptions are listed in section 6 and each needs a named person to confirm it.

## 1. Price

| Item | Value |
|---|---|
| Price | Annual plan ₩840,000 per firm per year (≈ ₩70,000 a month). Alternative: ₩40,000 per case study (proposed, to be confirmed by the team). The plan assumes about 10 case studies a month per firm |
| Students | Free tier |
| Who pays | Companies subscribe, with one paying user each (our simplifying assumption) |

## 2. Who is involved in a sale

| Role | Who | What they care about |
|---|---|---|
| User | The developer who writes the case study | Saving the 3–4 unpaid hours |
| Buyer | The manager who approves payment | Cost, and whether the tool is worth it |
| Client | The customer the project was done for | Confidentiality: what may be published about their project (this is why CaseForge has anonymising and human approval) |

## 3. Market size

| Step | Number | How |
|---|---|---|
| Software companies in Korea | 67,222 | SPRi SW Statistics Portal, 2024 (2023: 66,403). Newest confirmed figure |
| Fit our first market (serviceable market) | ≈ 6,000 | 67,222 × 60% in Seoul–Gyeonggi × 30% with 10–199 staff × 50% doing client project work = 6,050. The three percentages are stated assumptions, not measured figures |
| First market (SAM, beachhead) | ≈ ₩5.0 B per year | 6,000 × ₩840,000 = ₩5.04 B, with one paying user per company |
| Total addressable market (TAM) | ≈ ₩56.5 B per year | 67,222 × ₩840,000 = ₩56.5 B |

TAM is the ceiling if every software company in Korea paid; SAM is the ceiling for our first market. It is not a forecast.

## 4. Growth plan (team assumption)

Paying companies at the end of each year: **30 → 100 → 250.** That is about 4% of the ≈ 6,000 companies in our first market. Customers join gradually, so revenue in a year is based on the average number of paying companies during it: (start + end) ÷ 2.

| | Start | End | Average | Revenue (average × ₩840,000) |
|---|---|---|---|---|
| Year 1 | 0 | 30 | 15 | ₩12.6 M |
| Year 2 | 30 | 100 | 65 | ₩54.6 M |
| Year 3 | 100 | 250 | 175 | ₩147.0 M |
| **Total** | | | | **₩214.2 M** |

Run-rate at the end of each year (companies × ₩840,000): ₩25 M, ₩84 M, ₩210 M.

## 5. Costs and gross profit

Gross profit here means revenue minus the direct cost of running the service: AI, hosting and payment fees. It is **before** team pay, marketing, support and taxes, so it is not net profit.

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Revenue | ₩12.6 M | ₩54.6 M | ₩147.0 M |
| AI (paid Claude), ₩72,000 per average company per year | ₩1.1 M | ₩4.7 M | ₩12.6 M |
| Hosting (paid plans, **our guess**) | ₩0.6 M | ₩1.8 M | ₩3.6 M |
| Payment fees (3%, **our guess**) | ₩0.4 M | ₩1.6 M | ₩4.4 M |
| **Total costs** | **₩2.1 M** | **₩8.1 M** | **₩20.6 M** |
| **Gross profit** | **₩10.5 M** | **₩46.5 M** | **₩126.4 M** |

The poster rounds these to ₩13 M / 2 / 11, ₩55 M / 8 / 47 and ₩147 M / 21 / 126. The 70–85% margin on the poster is the more cautious figure that leaves room for support, tools and other costs not listed here.

## 6. AI cost per case study

Today the AI is the Gemini free tier (₩0). After the course we plan to switch to Claude and pay per token (see Q-025 in the question log).

**Token estimate for one full project** (about 1,500 words of notes, the case study, and two derived formats, each checked). The code does not log tokens yet, so this is an estimate from the calls in the pipeline:

| | Light | Typical | Heavy |
|---|---|---|---|
| Input tokens | 20,000 | 50,000 | 100,000 |
| Output tokens | 5,000 | 12,000 | 25,000 |

**Claude API prices** (per million tokens, from [Anthropic's pricing page](https://platform.claude.com/docs/en/about-claude/pricing), checked 21 Nov 2026; check again before relying on them):

| Model | Input | Output | Typical project | In won (₩1,400 per $) |
|---|---|---|---|---|
| Haiku 5.5 | $0.10 | $0.50 | ≈ $0.01 | ≈ ₩15 |
| Sonnet 5.5 | $2 | $10 | ≈ $0.22 | ≈ ₩300 |
| Opus 5.5 | $4 | $20 | ≈ $0.44 | ≈ ₩600 |

The Batch API is 50% cheaper. Prompt caching also lowers the cost of repeated text. Neither is included in the estimate.

**Per user per month** (Sonnet 5.5, 10–30 case studies a month, plus about 30% for retries and failed calls): about ₩3,000–9,000, which is 4–13% of the ₩70,000 a month implied by the annual plan. The poster uses ₩6,000 per user per month (about 8.6% of the price) for the 3-year table.

## 7. Assumptions to confirm

| # | Assumption | Who confirms |
|---|---|---|
| 1 | The 60% / 30% / 50% filters (Seoul–Gyeonggi, 10–199 staff, client project work) are assumptions, not measured; source for 67,222 is SPRi SW Statistics Portal, 2024 | Odina and Dilshodjon (determined) |
| 2 | One paying user per company | Mukhammadkodir |
| 3 | Growth of 30 → 100 → 250 paying companies | Anvarbek |
| 4 | Hosting costs after the free tiers (Render and Neon paid plans) | Abdulaziz |
| 5 | Payment fees of 3% | Anvarbek |
| 6 | ₩1,400 per dollar | Mukhammadkodir |
| 7 | Token use per project: measure it by logging input and output tokens for one real run | Abdulaziz |

## 8. Limits of this estimate

- No customer has been asked whether they would pay ₩840,000 a year or ₩40,000 per case study. The price is an assumption until someone tests it.
- The faithfulness results (20 of 20 planted claims caught, 0 of 109 true sentences wrongly flagged) were measured on Gemini, not Claude. They must be re-run after any model change.
- Moving to Claude needs `caseforge/llm.py`, which is written for Gemini, to be extended or replaced.
- Sending real client material to any external AI service is still governed by Q-002; Anthropic's terms for the API need to be checked before then.
