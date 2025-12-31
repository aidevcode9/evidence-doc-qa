# Task 016 - Semantic Ranking and Highlights

## Scope
- Upgrade retrieval to use Azure AI Search's Semantic Ranker (L2 Reranking).
- Capture and display Semantic Scores (0-4) to users.
- Render "Hit Highlighting" in the Evidence Panel so users can see exactly why a chunk was retrieved.

## Why
- **Precision:** RRF (Hybrid) is good, but Semantic Reranking understands intent and drastically improves precision (Hit@1).
- **Confidence:** "Senior Engineer" users expect L2 reranking in a production-grade RAG system.
- **Explainability:** Highlighting matching terms builds trust.

## Changes
### Backend
- `apps/api/app/retrieval.py`: 
    - Updated `_azure_search` payload to include `queryType="semantic"`, `semanticConfiguration="default"`, and `captions`.
    - Improved local `_overlap_score` with a stop-word filter to increase signal-to-noise ratio during fallback.
- `apps/api/app/evidence.py`: 
    - Updated grading logic to trust high Semantic Scores (>2.5) as "Grade A" evidence.
    - Improved `evidence_grade` resilience: Verified matches now require less lexical overlap, accounting for synonyms (e.g., "automobile" vs "car").
- `apps/api/app/schemas.py`: Added `highlighted_text` to `Citation` and `reranker_score` to `EvidenceSupport`.
- `apps/api/app/main.py`: Populated new fields in the response.

### Frontend
- `apps/web/types/index.ts`: Updated TypeScript definitions.
- `apps/web/components/EvidencePanel.tsx`: 
    - Added "Semantic Rank" display with high-fidelity tooltips explaining L2 reranking.
    - Implemented `dangerouslySetInnerHTML` to render highlighted text (bolding) from Azure captions.
    - Added `cursor-help` to tooltips for better UX.

## Verification
- **Run:** `apps/api/main.py` (via `uvicorn`) and check logs for "Reranker=" output.
- **UI:** Ask a question and verify that citations show bolded keywords and the Evidence Panel shows a "Semantic" score.
