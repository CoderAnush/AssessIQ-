# Curated Browser Scenario Validation (10)

**Backend:** `http://127.0.0.1:8000`

Scenario 1 was visually verified in Streamlit (recommendation cards with Java assessments).

## 1. Java backend

- **Expect:** Recommendation cards with Java/ability assessments
- **Recommendations:** 7
- **end_of_conversation:** False
- **Shortlist:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Enterprise Java Beans (New), Core Java (Advanced Level) (New), Java 2 Platform Enterprise Edition 1.4 Fundamental, Java Frameworks (New), Java 8 (New)
- **Reply preview:** I've optimized an enterprise backend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupation...

## 2. Vague developer clarify

- **Expect:** Clarification only, no recommendation cards
- **Recommendations:** 0
- **end_of_conversation:** False
- **Reply preview:** What type of role and seniority are you hiring for? Examples: Senior Backend Developer, Junior Frontend Engineer, or Leadership — and any technical focus (e.g. Java, React, DevOps)....

## 3. Finance graduate

- **Expect:** Financial/numerical/graduate assessments
- **Recommendations:** 7
- **end_of_conversation:** False
- **Shortlist:** Verify - Numerical Ability, Graduate Scenarios, Data Entry (New), MFS 360 UCF Performance Potential Dev Tips Report, Verify - General Ability Screen, Entry Level Technical Support Solution, HiPo Unlocking Potential Report 2.0
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Verify - N...

## 4. Contact centre

- **Expect:** Language clarify or SVAR/contact-centre items
- **Recommendations:** 0
- **end_of_conversation:** False
- **Reply preview:** SVAR has four English variants in the catalog: US, UK, Australian, and Indian accent. Which fits your operation?...

## 5. Leadership multi-turn

- **Expect:** OPQ/leadership after clarification
- **Recommendations:** 7
- **end_of_conversation:** False
- **Shortlist:** Enterprise Leadership Report 1.0, OPQ Leadership Report, Enterprise Leadership Report 2.0, HiPo Assessment Report 2.0, OPQ Team Types and Leadership Styles Report, HiPo Assessment Report 1.0, HiPo Unlocking Potential Report 2.0
- **Reply preview:** I've optimized an enterprise management hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Enterpr...

## 6. React frontend

- **Expect:** React/frontend assessments
- **Recommendations:** 7
- **end_of_conversation:** False
- **Shortlist:** ReactJS (New), HiPo Assessment Report 1.0, Automata Front End, Digital Readiness Development Report - Manager, HiPo Assessment Report 2.0, Software Business Analysis, Automata Selenium
- **Reply preview:** I've optimized an enterprise frontend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | ReactJS (...

## 7. Compare named

- **Expect:** Comparison table in chat
- **Recommendations:** 0
- **end_of_conversation:** False
- **Reply preview:** Compare these two assessments side by side:

### Comparison: Occupational Personality Questionnaire OPQ32r vs Verify - General Ability Screen

| Dimension | Occupational Personality Questionnaire OPQ3...

## 8. Refinement React

- **Expect:** Shortlist shifts to frontend
- **Recommendations:** 7
- **end_of_conversation:** False
- **Shortlist:** SHL Verify Interactive - Inductive Reasoning, ReactJS (New), AngularJS (New), Automata Front End, Angular 6 (New), Adobe Experience Manager (New), Entry Level Technical Support Solution
- **Reply preview:** I've optimized an enterprise frontend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | SHL Verif...

## 9. Off-topic refusal

- **Expect:** Refusal, no recommendations
- **Recommendations:** 0
- **end_of_conversation:** False
- **Reply preview:** I specialize in recommending SHL assessments and cannot assist with unrelated topics....

## 10. Closure

- **Expect:** end_of_conversation closure with shortlist
- **Recommendations:** 7
- **end_of_conversation:** True
- **Shortlist:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Enterprise Java Beans (New), Core Java (Advanced Level) (New), Java 2 Platform Enterprise Edition 1.4 Fundamental, Java Frameworks (New), Java 8 (New)
- **Reply preview:** Confirmed. Here is your finalized assessment shortlist:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r ...
