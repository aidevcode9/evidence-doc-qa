import { NextRequest, NextResponse } from "next/server";
import { buildBackendAuthHeaders } from "@/lib/server-auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolved = await params;
  const path = resolved.path.join("/");
  const upstreamUrl = new URL(`${API_URL}/${path}`);
  upstreamUrl.search = request.nextUrl.search;

  let headers: Headers;
  try {
    headers = buildBackendAuthHeaders(request);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Authentication required" },
      { status: 401 }
    );
  }

  const method = request.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();

  const upstream = await fetch(upstreamUrl, {
    method,
    headers,
    body,
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  for (const headerName of ["content-type", "content-disposition", "cache-control"]) {
    const value = upstream.headers.get(headerName);
    if (value) {
      responseHeaders.set(headerName, value);
    }
  }

  const responseBody =
    upstream.status === 204 ? undefined : await upstream.arrayBuffer();

  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
