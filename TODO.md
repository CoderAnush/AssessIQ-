# TODO - SMART DOMAIN-CONSTRAINED FALLBACK EXPANSION

## Step 1
Implement domain competency chains + domain-constrained expansion helpers
- File: app/services/skill_graph.py
- Add: domain adjacency mapping for BACKEND / DATA_AI / FRONTEND
- Add: helper like `get_domain_expansion_chain(domain)` and `expand_skills_by_domain(query_domain, seed_skills, depth)`

## Step 2
Trigger SMART fallback only within the detected domain
- File: app/services/retriever.py
- Change: expansion should occur when exact domain matches are below threshold
- Ensure: NO cross-domain leakage (use domain chain + existing _is_domain_mismatch)
- Add metadata to each fallback item:
  - expansion_matched / is_fallback (existing)
  - expansion_label (e.g. "Expanded Match" or "Related Competency Match")

## Step 3
Allow expanded candidates to pass ranking without losing precision
- File: app/services/ranker_v2.py
- Change: domain locking should still prevent leakage, but expanded/related candidates should:
  - receive confidence decay (larger than current)
  - remain eligible even if their normalized assessment domain is in the same adjacency chain
- Improve explanation labeling using expansion_label

## Step 4
UI transparency + minimum pipeline guarantee
- File: app/routes/chat.py
- Change:
  - Surface label in `recruiter_insight` (and/or subtitle)
  - Ensure: if at least some domain-compatible assessments exist, return at least 3–5 recommendations (prefer expanded ones with lower confidence)

## Step 5
Run/verify validation tests (if available)
- scripts/fallback_expansion_validation.py and related scripts
