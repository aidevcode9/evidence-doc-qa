# Task 011 - Vercel Frontend Deployment

## Scope
- Configure the repository for Vercel monorepo deployment.
- Add `vercel.json` to the root to point to `apps/web`.
- Set up GitHub Actions or Vercel Dashboard integration for automatic deployment from `main`.
- Configure `NEXT_PUBLIC_API_URL` in Vercel environment variables.
- Ensure CORS in the API allows the Vercel deployment URL.

## Acceptance tests
- Merging to `main` triggers a Vercel build.
- The Vercel deployment successfully builds and serves the Next.js app.
- The frontend can successfully communicate with the Azure-hosted API (when configured).

## Deployment Steps
1.  **Dashboard Integration:** Link the GitHub repository in the Vercel Dashboard.
2.  **Project Settings:** In the "General" settings, set **Root Directory** to `apps/web`.
3.  **Environment Variables:** Add `NEXT_PUBLIC_API_URL` to the Vercel project settings.
4.  **CORS Update:** Update your Azure API's `DOCQA_ALLOWED_ORIGINS` with the Vercel URL.

## Files likely touched
- `vercel.json`
- `apps/api/app/main.py`
- `tasks/_project_status.md`
