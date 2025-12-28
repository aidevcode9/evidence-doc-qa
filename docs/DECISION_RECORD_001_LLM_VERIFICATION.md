# Decision Record 001: LLM Verification for Refusal Correctness

**Date:** 2025-12-28  
**Status:** Accepted  
**Context:** Task 013 (Improve Refusal Correctness)

## The Problem: Similarity $\neq$ Relevance
Our current RAG system relies solely on **Vector/Hybrid Retrieval Scores** to decide whether to answer a question. 
- **Issue:** High semantic similarity (e.g., keyword overlap) does not guarantee the document actually contains the answer.
- **Symptom:** The system answers questions like "What is the CEO's phone number?" with irrelevant text about the CEO, rather than refusing. 
- **Eval Metric:** `refusal_correctness` is currently ~42%.

## The Solution: Logical Entailment (LLM Verification)
We will implement a **"Corrective RAG" (CRAG)** step. Before generating a final answer, the system will ask an LLM (`gpt-4o-mini`):
> *"Does the provided context contain the specific information to answer the question? Answer YES or NO."

If the answer is **NO**, the system returns `NO_SUPPORTING_EVIDENCE`, overriding the retrieval score.

## Citations & Evidence

### 1. Corrective RAG (CRAG)
*   **Source:** Yan et al. (2024), *"Corrective Retrieval Augmented Generation"*
*   **Key Finding:** Adding a lightweight "Evaluator" to classify retrieved documents as *Correct*, *Ambiguous*, or *Incorrect* before generation significantly reduces hallucinations.

### 2. Self-RAG
*   **Source:** Asai et al. (2023), *"Self-RAG: Learning to Retrieve, Generate, and Critique"*
*   **Key Finding:** Implementing an explicit `IsREL` (Is Relevant) critique step outperforms standard RAG on correctness benchmarks.

### 3. Industry Standard (Microsoft)
*   **Source:** [Azure AI Search - Semantic Ranking & Grounding](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/use-your-data)
*   **Key Finding:** Microsoft's "On Your Data" implementation uses a "Grounding Score" to verify citation support. If grounding is low, the answer is suppressed.

## Alternatives Considered

### Cross-Encoder Re-ranking
-   **Method:** Use a local BERT model (e.g., `ms-marco-MiniLM`) to score relevance.
-   **Verdict:** Rejected.
-   **Reason:** Requires heavy PyTorch dependencies and CPU/GPU resources incompatible with our "Near-Free" (Azure F1/B1) infrastructure constraints.

## Implementation Plan
1.  **Refactor `ask()` endpoint:** Insert a verification loop after retrieval but before answer generation.
2.  **Multi-Chunk Verification:** The system iterates through the **Top 3** candidate chunks.
    -   If Candidate 1 is verified: **Stop and Answer.**
    -   If Candidate 1 fails, check Candidate 2.
    -   If all 3 fail: **Refuse (`NO_SUPPORTING_EVIDENCE`).**
3.  **Prompt Engineering:** Uses a strict system prompt ("Your only job is to determine...") with `max_completion_tokens=1000` to allow for reasoning models.
4.  **Configuration:** Uses dedicated `AZURE_OPENAI_CHAT_*` environment variables to separate the Verification Model (e.g., `gpt-5-nano`/`o1-mini`) from the Embedding Model.
5.  **Traceability:** Logs full verification decisions and raw LLM responses for debugging.

## Results (Dec 28, 2025)
-   **Citation Coverage:** 100%
-   **Refusal Correctness:** 100%
-   **Trade-off:** Latency increased to ~7s (p50) due to the reasoning depth of the verification model.
