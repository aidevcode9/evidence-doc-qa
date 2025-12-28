# Task 010: UI/UX Refinement (Refusal Transparency)

## Description
Improve the user experience when the system refuses to answer. Instead of a generic error or refusal message, provide the user with clear, actionable reasons (e.g., "Injection Detected", "Low Confidence", "No Evidence") and style them appropriately in the UI.

## Objectives
- [x] Review `apps/api/app/main.py` to ensure all refusal paths return specific `refusal_code` and `reason`.
- [x] Enhance `apps/web/components/MessageBubble.tsx` to render different refusal types with distinct styles.
- [x] Add user-friendly descriptions explaining what each refusal code means for the user.
- [x] Ensure the "Ask" button and input state are correctly managed after a refusal.

## Acceptance Criteria
- [x] Refusals are visually distinguishable from successful answers.
- [x] Users can understand *why* the system refused (e.g., "I couldn't find evidence in the document" vs "Security policy triggered").
