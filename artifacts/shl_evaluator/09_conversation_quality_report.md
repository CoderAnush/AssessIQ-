# Conversation Quality Report

## Public trace fidelity (C1–C10)

| Trace | Turns | Recall@10 | Quality notes |
|-------|-------|-----------|---------------|
| C1 leadership | 4 | 1.00 | Clarifies audience → selection → OPQ/leadership; `end=true` on closure |
| C2 Rust | 2 | 1.00 | Sparse-catalog honesty + proxies (Smart Interview, Linux, Verify) |
| C3 contact centre | 3 | 1.00 | Clarifies English/US before SVAR/customer service |
| C4 finance grad | 2 | 1.00 | Numerical + finance + graduate scenarios |
| C5 sales reskill | 1 | 1.00 | Global skills + OPQ + sales |
| C6 safety | 1 | 1.00 | Safety/dependability instruments |
| C7 healthcare | 2 | 1.00 | HIPAA + medical terminology + OPQ |
| C8 admin | 2 | 1.00 | Excel/Word after simulation opt-in |
| C9 fullstack | 4 | 1.00 | Multi-clarify → refine drop REST / add AWS Docker |
| C10 grad mgmt | 2 | 1.00 | Drop OPQ → Verify G+ + Graduate Scenarios |

**Mean Recall@10: 1.00**

## Clarify quality

- Vague: "I need an assessment", "programmer", "Need something technical" → seniority/role questions, 0 recs
- Contact centre: asks language before shortlist
- C9: asks backend vs frontend, then senior IC vs tech lead

## Refinement quality

- Add OPQ after Java shortlist: OPQ present
- Drop OPQ with full history: OPQ removed
- Java → Python swap: Spring gone, Python present
- C9 REST drop: Java/Spring/SQL retained (REST-only drop)

## Comparison quality

- Named compare OPQ32r vs Verify G+: grounded table in `reply`

## Weak spot

- `React and TypeScript` without role → immediate 7-card frontend shortlist (no seniority clarify). Inconsistent with `programmer` path.

## Overall

Strong on assignment traces and official personas. One tech-only edge case for turn-1 clarify policy.
