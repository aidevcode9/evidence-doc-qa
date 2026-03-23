# Task 013: Improve Refusal Correctness (LLM Verification)

## Description
The current system relies solely on retrieval scores to decide whether to answer or refuse. This leads to "hallucinations" where the system returns irrelevant text as an answer because the search found keyword matches (e.g., answering "What is the CEO's phone number?" with a snippet about Azure APIs because of keyword overlap).

To improve `Refusal Correctness` from ~42% to >90%, we must introduce an LLM verification step.

## Objectives
- [ ] **Implement "Is Answerable?" Check:** Before returning the final answer, send the Question + Retrieved Chunks to `gpt-5-mini-mini`.
- [ ] **Prompt Engineering:** Create a prompt that asks: "Does the provided context contain the specific information to answer the question? Answer YES or NO."
- [ ] **Refusal Handling:** 
    - If LLM says NO: Return `NO_SUPPORTING_EVIDENCE`.
    - If LLM says YES: Proceed to generate the answer.
- [ ] **Update Evals:** Re-run `evals/run.py` and verify `refusal_correctness` improves.

## Acceptance Criteria
- [ ] The system refuses questions like "What is the CEO's phone number?" even if retrieval finds high-scoring but irrelevant chunks.
- [ ] `refusal_correctness` metric in the Golden Set is > 90%.
