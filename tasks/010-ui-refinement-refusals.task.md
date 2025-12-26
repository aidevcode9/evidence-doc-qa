# Task 010: UI/UX Refinement (Refusal Transparency)

## Description
Improve the user experience when the system refuses to answer. Instead of a generic error or refusal message, provide the user with clear, actionable reasons (e.g., "Injection Detected", "Low Confidence", "No Evidence") and style them appropriately in the UI.

## Objectives
- [ ] Review `apps/api/app/main.py` to ensure all refusal paths return specific `refusal_code` and `reason`.
- [ ] Enhance `apps/web/components/MessageBubble.tsx` to render different refusal types with distinct styles.
- [ ] Add tooltips or help text explaining what each refusal code means for the user.
- [ ] Ensure the "Ask" button and input state are correctly managed after a refusal.

## Acceptance Criteria
- [ ] Refusals are visually distinguishable from successful answers.
- [ ] Users can understand *why* the system refused (e.g., "I couldn't find evidence in the document" vs "Security policy triggered").
