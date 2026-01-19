---
description: Adversarial code review for AI failure modes
---

Review this code as a skeptic. Focus on AI-specific failure modes.

You are reviewing code for an AI system that must be trustworthy. Be adversarial.

## 1. Failure Modes

Check each and report:
- [ ] **Empty retrieval:** What happens when no chunks are found?
- [ ] **Low confidence:** Is the threshold (0.70) enforced? What happens below it?
- [ ] **LLM timeout:** Does it return an error or hallucinate?
- [ ] **Malformed input:** What happens with bad PDFs, empty queries, special characters?
- [ ] **Token limits exceeded:** What happens with very long documents or queries?

## 2. Data Leakage

Check each and report:
- [ ] **Tenant isolation:** Is tenant_id checked on EVERY database query?
- [ ] **Prompt injection:** Could a malicious query extract other users' data?
- [ ] **Logging:** Are queries/responses logged? Could PII leak into logs?
- [ ] **Error messages:** Do errors reveal internal structure or other tenants' data?

## 3. Citation Integrity

Check each and report:
- [ ] **Citation validation:** Is every LLM claim checked against retrieved chunks?
- [ ] **Fabrication risk:** Could the LLM invent a citation that passes validation?
- [ ] **Validation failure:** What happens when a citation doesn't validate? (Must refuse, not return)
- [ ] **Chunk mapping:** Does citation [1] always map to a real, retrieved chunk?

## 4. Refusal Behavior

Check each and report:
- [ ] **Refusal triggers:** When should the system refuse? Is this enforced?
- [ ] **Refusal message:** Is it helpful without revealing system internals?
- [ ] **No silent failures:** Does every code path either succeed with citation OR refuse explicitly?
- [ ] **Confidence gating:** Is there any path that bypasses the confidence check?

## 5. Edge Cases

Consider:
- [ ] **Empty documents:** Zero text extracted
- [ ] **Non-English:** Does it handle correctly or refuse gracefully?
- [ ] **Scanned PDFs:** OCR failures
- [ ] **Concurrent requests:** Race conditions?
- [ ] **Rate limits:** What happens when LLM rate limits hit?

## Output Format

For each issue found:

```
CRITICAL: [description]
   Location: [file:line]
   Risk: [what could go wrong]
   Fix: [how to fix]

HIGH: [description]
   Location: [file:line]
   Risk: [what could go wrong]
   Fix: [how to fix]

LOW: [description]
   Location: [file:line]
   Suggestion: [improvement]
```

## Summary

At the end, provide:
- Total issues: X critical, Y high, Z low
- Recommendation: BLOCK / APPROVE WITH FIXES / APPROVE
- Evals to add: [any new golden queries this code needs]

If any CRITICAL issues exist, recommendation must be BLOCK.
