import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";
import { createSession } from "@/lib/session";

function safeCompare(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  // panjang beda -> pasti tidak sama, tapi tetap lakukan compare dummy
  // supaya waktu eksekusi tidak membocorkan info panjang password lewat timing
  if (bufA.length !== bufB.length) {
    timingSafeEqual(bufA, bufA);
    return false;
  }
  return timingSafeEqual(bufA, bufB);
}

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  const correctPassword = process.env.DASHBOARD_PASSWORD;
  if (!correctPassword) {
    return NextResponse.json(
      { ok: false, error: "DASHBOARD_PASSWORD belum diatur di server." },
      { status: 500 }
    );
  }

  if (typeof password !== "string" || !safeCompare(password, correctPassword)) {
    return NextResponse.json({ ok: false, error: "Password salah." }, { status: 401 });
  }

  await createSession();
  return NextResponse.json({ ok: true });
}
