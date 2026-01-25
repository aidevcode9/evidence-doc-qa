# Documentation & Workflow Roadmap

> Feedback synthesis from senior engineering perspectives. Prioritized for a small, agile team.

---

## Executive Summary

**What we have:** A comprehensive 8-command workflow with non-negotiable gates for AI-specific safety.

**The tension:** Thoroughness vs. velocity. Process vs. pragmatism.

**The answer:** Keep the two non-negotiables. Let everything else flex based on context.

---

## Boris's Take (Anthropic Senior Engineer)

### What Actually Matters for a Small Team

**Reality check:** You're not Google. You don't have 10 engineers, a dedicated SRE team, or quarterly OKR cycles. You have deadlines, a demo for senior advisors, and an AI system that could hallucinate citations if you're not careful.

Here's what I'd prioritize:

### Tier 1: Non-Negotiable (Keep These)

| Gate | Why It Matters | Cost to Skip |
|------|----------------|--------------|
| `/wsresearch` | Prevents building the wrong thing | Days of rework |
| `/wsskeptic` | Catches AI failure modes | Broken demo, lost trust |

These two gates exist because **AI systems fail differently than traditional software**. A normal bug crashes. An AI bug confidently gives wrong answers with fake citations. The cost asymmetry justifies the process overhead.

### Tier 2: High Value, Low Overhead (Do These)

| Practice | Effort | Payoff |
|----------|--------|--------|
| TDD for core logic | Medium | Catches regressions early |
| `CHECKPOINT.md` logging | Low | Audit trail, resume context |
| Commit with FR reference | Low | Traceability |

### Tier 3: Nice to Have (Do When You Scale)

| Practice | When to Add |
|----------|-------------|
| OWNERS files | When you have 3+ engineers |
| Automated doc drift checks | When docs start rotting |
| Design docs for large changes | When changes span >1 week |
| Hotfix workflow | After first production incident |
| Metrics on workflow effectiveness | After 20+ FRs shipped |

### What to Explicitly Skip (For Now)

1. **Formal design docs** — Your `/wsresearch` output is enough for current scale
2. **OWNERS files** — You are the owner. You know who owns what.
3. **Automated CI for doc freshness** — Manual review is fine until it's not
4. **Parallel work protocols** — You're not parallelizing yet
5. **Incident runbooks** — Build after first incident, not before

---

## Feedback Synthesis

### From the "Anthropic Perspective"

**Strengths identified:**
- AI-specific adversarial review is ahead of industry
- Research-before-code prevents common AI-assisted development failures
- Checkpoint logging creates accountability

**Concerns raised:**
- 8 commands might lead to abandonment under pressure
- No rollback protocol documented
- No metrics to know if workflow is working

**Recommendation:** Keep non-negotiables strict. Let everything else be "should do" not "must do."

### From the "Google Perspective"

**Strengths identified:**
- Mandatory review aligns with LGTM culture
- Documentation sync requirements mirror internal doc standards
- Readability-like pattern enforcement via `/wsresearch`

**Concerns raised:**
- Relies on discipline, not automation
- No ownership model for critical files
- Missing incident/hotfix workflow
- Doesn't scale to multiple engineers

**Recommendation:** Automate enforcement over time. Add OWNERS when team grows.

---

## Prioritized Roadmap

### Now (Before Demo)

- [x] `/wsresearch` and `/wsskeptic` as non-negotiable gates
- [x] Documentation sync requirements documented
- [x] `docs/WORKFLOW.md` for technical audience
- [ ] Langfuse integration (NFR-045) — **observability for demo**

### Soon (Post-Demo, Pre-Scale)

| Item | Trigger | Effort |
|------|---------|--------|
| `/wshotfix` workflow | First production incident | 2 hrs |
| Basic metrics tracking | 10+ FRs shipped | 4 hrs |
| Automated env var check | Third time someone forgets | 2 hrs |

### Later (When Scaling)

| Item | Trigger | Effort |
|------|---------|--------|
| OWNERS files | 3+ engineers | 1 hr |
| Automated doc drift CI | Docs rot visibly | 4 hrs |
| Design doc template | Multi-week features | 2 hrs |
| Parallel work protocol | Merge conflicts | 2 hrs |

### Maybe Never

| Item | Why Skip |
|------|----------|
| Full Google-style presubmit | Overkill for team size |
| Formal readability reviews | `/wsresearch` covers this |
| OKR-driven prioritization | STATUS.md is enough |

---

## The Two Rules That Matter

If you remember nothing else:

### Rule 1: Research Before Code
```
/wsresearch → then code
```
**Why:** AI assistants generate plausible-looking code fast. Without context, it's plausible-looking *wrong* code. 5 minutes of research saves 5 hours of rework.

### Rule 2: Adversarial Review Before Ship
```
code → /wsskeptic → then commit
```
**Why:** AI systems fail silently. They don't crash — they confidently return wrong answers. `/wsskeptic` is your last line of defense against shipping a system that hallucinates citations to senior advisors.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Tempting | Why It Fails |
|--------------|-------------------|--------------|
| "I already know the patterns" | Feels fast | You miss the edge case that breaks everything |
| "It's a small change" | Seems low-risk | Small changes to `policy.py` break invariants |
| "We'll add tests later" | Shipping pressure | Later never comes; bugs ship instead |
| "Skip skeptic, it's just a typo fix" | Overhead feels silly | The one time you skip it, you ship a bug |
| "Docs can wait" | Code is more fun | Future you has no idea what past you did |

---

## Measuring Success (When Ready)

When you have bandwidth, track these:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Skip rate on non-negotiables | 0% | Honor system / PR review |
| Defect escape rate | <5% | Bugs found post-merge |
| Research → Shipped time | Decreasing | CHECKPOINT.md timestamps |
| Rework rate | <10% | PRs that revert or fix previous PRs |

**Don't measure yet.** Ship the demo first. Measure when you have enough data points to learn from.

---

## Summary for Small Teams

```
┌─────────────────────────────────────────────────────┐
│           MINIMUM VIABLE WORKFLOW                    │
│                                                      │
│   /wsresearch  →  code  →  /wsskeptic  →  ship     │
│        ⛔              ⛔                            │
│   NON-NEGOTIABLE    NON-NEGOTIABLE                  │
│                                                      │
│   Everything else? Nice to have. Do when it hurts.  │
└─────────────────────────────────────────────────────┘
```

**The goal isn't process perfection. The goal is shipping software that doesn't embarrass you in front of Boris and the senior advisors.**

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-25 | Initial roadmap based on workflow review feedback |
