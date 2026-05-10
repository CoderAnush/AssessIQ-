# Approach

## Architecture Overview
AssessIQ is a stateless FastAPI service that accepts the full conversation history on every `/chat` request. The backend reconstructs the hiring context from `messages[]`, routes the request through a decision layer, retrieves catalog items, ranks them, and returns a strict schema with `reply`, `recommendations`, and `end_of_conversation`.

## Retrieval Strategy
The system uses lightweight hybrid retrieval over the SHL catalog. Query expansion covers common technical and recruiter vocabulary so short or ambiguous prompts still surface relevant catalog items. Retrieval is intentionally catalog-bound so the API never invents assessments.

## Ranking Logic
Ranking combines semantic relevance, role/domain alignment, skill overlap, seniority fit, and refinement signals. The ranker keeps a narrow top candidate pool before final selection so the API stays fast and deterministic.

## Clarification Strategy
When the request does not contain enough hiring context, the assistant asks for the missing high-value details first. That keeps the flow efficient and avoids premature recommendations that would need correction later.

## Hallucination Prevention
All recommendations must resolve to catalog entries. URLs, names, and test types are validated against the catalog, and fallback responses never fabricate assessment details. Comparison responses are also grounded in catalog metadata rather than free-form LLM text.

## Stateless Design
The endpoint does not depend on server-side session memory for evaluator behavior. Each request is resolved from the message history provided by the client, which makes the API predictable, replayable, and easier to test.

## Evaluation Methodology
Submission readiness is verified with `scripts/run_eval_suite.py` and `scripts/recruiter_scenarios.py`. The regression suite covers clarification, recommendation quality, comparison behavior, off-topic refusal, prompt injection refusal, malformed payload handling, turn-cap compliance, and stateless replay stability.

## Tradeoffs
The implementation favors grounded and repeatable behavior over open-ended conversational flexibility. That reduces hallucination risk and improves evaluator compliance, but it also means the assistant prefers clarification when the hiring context is incomplete.

## Failures Encountered
The main issues during hardening were stale backend processes, schema drift in fallback paths, and overly permissive interpretation of vague requests. Those were corrected by tightening the response model, making the route stateless, and validating behavior against the live backend.

## AI Tools Used
The project uses deterministic backend logic for the evaluator path and keeps LLM usage optional. That makes deployment safer and reduces latency while preserving a path for richer language generation when credentials are available.
