import { NextResponse, type NextRequest } from "next/server";

// CORS for the React frontend, which is served from a different origin.
const ALLOWED_ORIGIN = process.env.FRONTEND_ORIGIN ?? "http://localhost:5173";

export function middleware(req: NextRequest) {
  const headers = {
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
  };
  if (req.method === "OPTIONS") {
    return new NextResponse(null, { status: 204, headers });
  }
  const res = NextResponse.next();
  for (const [k, v] of Object.entries(headers)) res.headers.set(k, v);
  return res;
}

export const config = {
  // The SMS webhook is called by the provider, not the browser.
  matcher: ["/api/((?!sms).*)"],
};
