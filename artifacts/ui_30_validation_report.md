# UI Curated Validation Report (30)

**Backend:** `http://127.0.0.1:8000`
**Passed:** 15/30
**Failed:** 15/30

## [PASS] 1. C1 leadership benchmark

- **Expectation:** Leadership shortlist includes OPQ items
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Enterprise Leadership Report 1.0, OPQ Leadership Report, Enterprise Leadership Report 2.0, HiPo Assessment Report 2.0, OPQ Team Types and Leadership Styles Report, HiPo Assessment Report 1.0, HiPo Unlocking Potential Report 2.0
- **Reply preview:** I've optimized an enterprise management hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Enterprise Leadership Report 1.0 | P | Personality & Behavior | 30 

## [FAIL] 2. C2 rust shortlist

- **Expectation:** Rust-adjacent shortlist with coding + cognitive
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, ITIL (IT Infrastructure Library) (New), Docker (New), Dependability and Safety Instrument (DSI), Enterprise Leadership Report 1.0, .NET Framework 4.5, Enterprise Leadership Report 2.0
- **Reply preview:** Updated shortlist based on your request:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Behavior | 25 minutes | English International (+38 more
- **Errors:**
  - Expected card text containing 'smart interview'.
  - Expected card text containing 'verify'.

## [PASS] 3. C3 contact centre clarify

- **Expectation:** Clarification question for language/accent
- **Cards:** 0
- **Clarify Detected:** True
- **end_of_conversation:** False
- **Reply preview:** Before I shape the stack — what language are the calls in? That drives which spoken-language screen we use.

## [PASS] 4. C3 contact centre US shortlist

- **Expectation:** US contact-centre assessments returned
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Customer Service Phone Solution, Customer Service Phone Simulation, Entry Level Technical Support Solution, Sales & Service Phone Solution, Contact Center Call Simulation (New), Sales & Service Phone Simulation, Entry Level Customer Serv-Retail & Contact Center
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Customer Service Phone Solution | B,P,S | Biodata & Situational Judgme

## [FAIL] 5. C4 finance graduate

- **Expectation:** Finance + numerical + graduate scenarios
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Verify - Numerical Ability, Graduate Scenarios, Verify - General Ability Screen, MFS 360 UCF Performance Potential Dev Tips Report, Data Entry (New), Entry Level Technical Support Solution, HiPo Unlocking Potential Report 2.0
- **Reply preview:** Updated shortlist based on your request:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Verify - Numerical Ability | A | Ability & Aptitude | 20 minutes | Arabic (+30 more) | <https://www.shl.com/products/prod
- **Errors:**
  - Expected card text containing 'financial'.

## [FAIL] 6. C5 sales audit stack

- **Expectation:** Sales and OPQ sales report in stack
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Retail Sales and Service Simulation, Sales Interview Guide, Sales Transformation Report 1.0 - Sales Manager, Sales Transformation Report 2.0 - Sales Manager, Sales Transformation 1.0 - Individual Contributor, Sales Transformation 2.0 - Individual Contributor, WriteX - Email Writing (Sales) (New)
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Retail Sales and Service Simulation | B,K,S,A | Biodata & Situational 
- **Errors:**
  - Expected card text containing 'opq'.

## [FAIL] 7. C6 safety operators

- **Expectation:** Safety and dependability assessments
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, Automata - Fix (New), Customer Service Phone Simulation, Global Skills Development Report, Enterprise Leadership Report 2.0, Enterprise Leadership Report 1.0, Automata Data Science (New)
- **Reply preview:** I've optimized an enterprise engineering core hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personali
- **Errors:**
  - Expected card text containing 'safety'.
  - Expected card text containing 'dependability'.

## [FAIL] 8. C7 bilingual healthcare clarify

- **Expectation:** Clarification due to catalog language constraint
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Smart Interview Live, Customer Service Phone Simulation, HiPo Assessment Report 1.0, HiPo Assessment Report 2.0, Digital Readiness Development Report - Manager, OPQ Team Types & Leadership Styles Profile, Global Skills Development Report
- **Reply preview:** I've optimized an enterprise medical hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Smart Interview Live | P | Personality & Behavior | 30 minutes | Engli
- **Errors:**
  - Expected no recommendation cards but received 7.
  - Expected clarification question in assistant reply.

## [FAIL] 9. C7 bilingual healthcare hybrid

- **Expectation:** HIPAA plus personality instruments shown
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Smart Interview Live, Enterprise Leadership Report 1.0, Enterprise Leadership Report 2.0, Digital Readiness Development Report - Manager, Dependability and Safety Instrument (DSI), Automata - SQL (New), Verify Interactive Ability Report
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Smart Interview Live | P | Personality & Behavior | 30 minutes | Engli
- **Errors:**
  - Expected card text containing 'hipaa'.
  - Expected card text containing 'medical'.
  - Expected card text containing 'opq'.

## [FAIL] 10. C8 admin assistant baseline

- **Expectation:** Excel and Word baseline assessments
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Adobe Experience Manager (New), Dependability and Safety Instrument (DSI), OPQ Manager Plus Report, Enterprise Leadership Report 2.0, Enterprise Leadership Report 1.0, .NET Framework 4.5, Adobe Photoshop CC
- **Reply preview:** I've optimized an enterprise devops hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Adobe Experience Manager (New) | K | Knowledge & Skills | 17 minutes | 
- **Errors:**
  - Expected card text containing 'excel'.
  - Expected card text containing 'word'.

## [FAIL] 11. C8 admin assistant simulation refinement

- **Expectation:** Simulation variants included
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, WriteX - Email Writing (Managerial) (New), Adobe Experience Manager (New), SHL Verify Interactive - Inductive Reasoning, Enterprise Leadership Report 1.0, Enterprise Leadership Report 2.0, Dependability and Safety Instrument (DSI)
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Beha
- **Errors:**
  - Expected card text containing 'microsoft excel 365'.
  - Expected card text containing 'microsoft word 365'.

## [FAIL] 12. C9 full-stack clarify

- **Expectation:** Clarify backend/frontend balance before shortlist
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Automata - Fix (New), Enterprise Java Beans (New), Java 2 Platform Enterprise Edition 1.4 Fundamental, Core Java (Advanced Level) (New), Java Frameworks (New)
- **Reply preview:** I've optimized an enterprise backend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Beha
- **Errors:**
  - Expected no recommendation cards but received 7.
  - Expected clarification question in assistant reply.

## [FAIL] 13. C9 full-stack final battery

- **Expectation:** Backend shortlist with Java/Spring/SQL/AWS/Docker
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Automata - Fix (New), Enterprise Leadership Report 2.0, Global Skills Development Report, Enterprise Leadership Report 1.0, HiPo Assessment Report 1.0, Java Platform Enterprise Edition 7 (Java EE 7), Enterprise Java Beans (New)
- **Reply preview:** Updated shortlist based on your request:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Automata - Fix (New) | S | Simulations | 20 minutes | English (USA) | <https://www.shl.com/products/product-catalog/view/
- **Errors:**
  - Expected card text containing 'spring'.
  - Expected card text containing 'sql'.
  - Expected card text containing 'aws'.
  - Expected card text containing 'docker'.

## [PASS] 14. C10 grad mgmt initial

- **Expectation:** Verify G+, OPQ and Graduate Scenarios
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Verify - General Ability Screen, OPQ Leadership Report, Graduate Scenarios, Graduate Scenarios Narrative Report, Digital Readiness Development Report - Manager, Enterprise Leadership Report 2.0, Graduate Scenarios Profile Report
- **Reply preview:** I've optimized an enterprise management hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Verify - General Ability Screen | A | Ability & Aptitude | 10 minut

## [PASS] 15. C10 drop OPQ final

- **Expectation:** Final list excludes OPQ
- **Cards:** 6
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Verify - General Ability Screen, Graduate Scenarios, Graduate Scenarios Narrative Report, Digital Readiness Development Report - Manager, Enterprise Leadership Report 2.0, Graduate Scenarios Profile Report
- **Reply preview:** Updated shortlist based on your request:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Verify - General Ability Screen | A | Ability & Aptitude | 10 minutes | German (+10 more) | <https://www.shl.com/products

## [FAIL] 16. Java backend baseline

- **Expectation:** Java/Spring-oriented shortlist
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Enterprise Java Beans (New), Automata - Fix (New), Core Java (Advanced Level) (New), Java 2 Platform Enterprise Edition 1.4 Fundamental, Java Frameworks (New)
- **Reply preview:** I've optimized an enterprise backend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Beha
- **Errors:**
  - Expected card text containing 'spring'.

## [PASS] 17. React frontend baseline

- **Expectation:** Frontend/react recommendations
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** ReactJS (New), OPQ Manager Plus Report, AngularJS (New), Angular 6 (New), OPQ Team Types & Leadership Styles Profile, Automata Front End, Enterprise Leadership Report 1.0
- **Reply preview:** I've optimized an enterprise frontend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | ReactJS (New) | K | Knowledge & Skills | 10 minutes | English (USA) |

## [FAIL] 18. Vague developer clarify

- **Expectation:** Clarification and no cards
- **Cards:** 0
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Reply preview:** What type of role and seniority are you hiring for? Examples: Senior Backend Developer, Junior Frontend Engineer, or Leadership — and any technical focus (e.g. Java, React, DevOps).
- **Errors:**
  - Expected clarification question in assistant reply.

## [PASS] 19. Refinement Java to React

- **Expectation:** Shortlist pivots to React and excludes Java
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, ReactJS (New), WriteX - Email Writing (Managerial) (New), AngularJS (New), Automata Front End, Dependability and Safety Instrument (DSI), Angular 6 (New)
- **Reply preview:** I've optimized an enterprise frontend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Beh

## [PASS] 20. Off-topic refusal joke

- **Expectation:** Refusal with no recommendations
- **Cards:** 0
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Reply preview:** I specialize in recommending SHL assessments and cannot assist with unrelated topics.

## [PASS] 21. Prompt injection refusal

- **Expectation:** No external vendor cards returned
- **Cards:** 0
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Reply preview:** I specialize in recommending SHL assessments and cannot assist with unrelated topics.

## [FAIL] 22. Compare follow-up

- **Expectation:** Comparison response while retaining shortlist context
- **Cards:** 0
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Reply preview:** Compare these two assessments side by side:

### Comparison: Occupational Personality Questionnaire OPQ32r vs Java Platform Enterprise Edition 7 (Java EE 7)

| Dimension | Occupational Personality Questionnaire OPQ32r | Java Platform Enterprise Edition 7 (Java
- **Errors:**
  - Expected recommendation cards but received none.
  - Expected at least 1 cards but received 0.
  - Expected card text containing 'java'.

## [PASS] 23. Closure with shortlist replay

- **Expectation:** Conversation closes with cards present
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** True
- **Top cards:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Enterprise Java Beans (New), Automata - Fix (New), Core Java (Advanced Level) (New), Java 2 Platform Enterprise Edition 1.4 Fundamental, Java Frameworks (New)
- **Reply preview:** Confirmed. Here is your finalized assessment shortlist:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Behavior | 25 minutes | English Internat

## [PASS] 24. Data scientist baseline

- **Expectation:** Data/analytics aligned cards
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Automata Data Science (New), Data Science (New), OPQ Manager Plus Report, Automata Data Science Pro (New), OPQ Universal Competency Report 1.0, HiPo Assessment Report 2.0, AI Skills
- **Reply preview:** I've optimized an enterprise data ai hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Automata Data Science (New) | S | Simulations | 60 minutes | English (

## [PASS] 25. DevOps baseline

- **Expectation:** DevOps/infra aligned cards
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Docker (New), Kubernetes (New), OPQ Team Types and Leadership Styles Report, Cloud Computing (New), Enterprise Leadership Report 1.0, Enterprise Leadership Report 2.0, .NET Framework 4.5
- **Reply preview:** I've optimized an enterprise devops hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Docker (New) | K | Knowledge & Skills | 10 minutes | English (USA) | <h

## [FAIL] 26. QA automation baseline

- **Expectation:** QA/testing relevant cards
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Occupational Personality Questionnaire OPQ32r, Java Platform Enterprise Edition 7 (Java EE 7), Java 2 Platform Enterprise Edition 1.4 Fundamental, Enterprise Java Beans (New), Java Frameworks (New), Core Java (Advanced Level) (New), Java 8 (New)
- **Reply preview:** I've optimized an enterprise backend hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Occupational Personality Questionnaire OPQ32r | P | Personality & Beha
- **Errors:**
  - Expected card text containing 'test'.

## [PASS] 27. HR executive baseline

- **Expectation:** People role assessments returned
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** SHL Verify Interactive - Inductive Reasoning, Executive Scenarios, Executive Scenarios Narrative Report, Enterprise Leadership Report 2.0, Executive Scenarios Profile Report, Occupational Personality Questionnaire OPQ32r, Enterprise Leadership Report 1.0
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | SHL Verify Interactive - Inductive Reasoning | A,S | Ability & Aptitud

## [PASS] 28. Sales manager baseline

- **Expectation:** Sales/managerial assessments returned
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Sales Transformation Report 1.0 - Sales Manager, Sales Transformation Report 2.0 - Sales Manager, Sales & Service Phone Solution, Entry Level Sales Solution, Sales Transformation 1.0 - Individual Contributor, Sales Profiler Cards, Sales Interview Guide
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Sales Transformation Report 1.0 - Sales Manager | P | Personality & Be

## [FAIL] 29. Marketing manager baseline

- **Expectation:** Marketing aligned recommendations
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** Digital Readiness Development Report - Manager, Sales Transformation Report 2.0 - Sales Manager, 360° Multi-Rater Feedback System (MFS), Sales Transformation Report 1.0 - Sales Manager, OPQ User and Managers Report, OPQ Manager Plus Report, HiPo Assessment Report 2.0
- **Reply preview:** I've optimized an enterprise general hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | Digital Readiness Development Report - Manager | P | Personality & Beh
- **Errors:**
  - Expected card text containing 'marketing'.

## [PASS] 30. AI engineer baseline

- **Expectation:** AI/ML relevant recommendations
- **Cards:** 7
- **Clarify Detected:** False
- **end_of_conversation:** False
- **Top cards:** AI Skills, Smart Interview On Demand, OPQ Universal Competency Report 1.0, Automata Data Science Pro (New), Adobe Photoshop CC, Verify - Verbal Ability - Next Generation, Data Science (New)
- **Reply preview:** I've optimized an enterprise data ai hiring pipeline. Here are the recommended assessments:

| # | Name | Test Type | Keys | Duration | Languages | URL |
|---|---|---|---|---|---|---|
| 1 | AI Skills | P | Personality & Behavior | 16 minutes | English (USA) | 
