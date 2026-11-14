import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ ok: true, engine: process.env.ENGINE_URL ? "remote" : "mock" });
}
