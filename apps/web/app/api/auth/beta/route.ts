import { NextResponse } from "next/server";
import { randomUUID } from "crypto";

const ATTEMPT_WINDOW_MS = 10 * 60 * 1000;
const ATTEMPT_LIMIT = 5;
const attempts = new Map<string, { count: number; resetAt: number }>();

function rateLimitKey(request: Request) {
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded?.split(",")[0]?.trim() || "unknown";
}

function checkRateLimit(key: string) {
  const now = Date.now();
  const entry = attempts.get(key);
  if (!entry || entry.resetAt <= now) {
    attempts.set(key, { count: 1, resetAt: now + ATTEMPT_WINDOW_MS });
    return true;
  }
  if (entry.count >= ATTEMPT_LIMIT) {
    return false;
  }
  entry.count += 1;
  return true;
}

export async function POST(request: Request) {
  const key = rateLimitKey(request);
  if (!checkRateLimit(key)) {
    return NextResponse.json({ error: "Too many attempts. Try again later." }, { status: 429 });
  }

  const body = await request.json().catch(() => ({}));
  const name = String(body.name || "").trim();
  const email = String(body.email || "").trim();
  const betaCode = String(body.betaCode || "").trim();

  if (!name || !email || !betaCode) {
    return NextResponse.json({ error: "All fields are required." }, { status: 400 });
  }

  const expected = process.env.DOCQA_BETA_CODE;
  if (!expected || betaCode !== expected) {
    return NextResponse.json({ error: "Invalid beta code." }, { status: 401 });
  }

  const sessionId = randomUUID();
  const response = NextResponse.json({ ok: true, sessionId });
  response.cookies.set("docqa_beta", sessionId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 12 * 60 * 60,
    path: "/",
  });
  response.cookies.set(
    "docqa_user",
    JSON.stringify({
      userId: `beta-${sessionId}`,
      tenantId: "demo-tenant",
      role: "admin",
      name,
      email,
    }),
    {
      httpOnly: false,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      maxAge: 12 * 60 * 60,
      path: "/",
    }
  );
  return response;
}
