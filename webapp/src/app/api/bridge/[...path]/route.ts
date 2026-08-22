import { NextRequest, NextResponse } from "next/server";
import { verifySession } from "@/lib/session";

/**
 * Semua request REST dari browser ke bridge lewat sini.
 * Browser TIDAK PERNAH tahu BRIDGE_URL atau BRIDGE_TOKEN — keduanya
 * cuma ada di environment variable server ini, tidak pernah dikirim
 * ke client. Browser cuma perlu punya session cookie yang valid
 * (didapat lewat halaman /login).
 */

async function handler(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const isLoggedIn = await verifySession();
  if (!isLoggedIn) {
    return NextResponse.json({ detail: "Belum login" }, { status: 401 });
  }

  const bridgeUrl = process.env.BRIDGE_URL;
  const bridgeToken = process.env.BRIDGE_TOKEN;
  if (!bridgeUrl || !bridgeToken) {
    return NextResponse.json(
      { detail: "BRIDGE_URL / BRIDGE_TOKEN belum diatur di server (.env.local)" },
      { status: 500 }
    );
  }

  const { path } = await context.params;
  const targetPath = "/" + path.join("/");
  const search = req.nextUrl.search; // teruskan query string (misal ?days=30)
  const targetUrl = `${bridgeUrl.replace(/\/$/, "")}${targetPath}${search}`;

  const init: RequestInit = {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${bridgeToken}`,
    },
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const body = await req.text();
    if (body) init.body = body;
  }

  try {
    const res = await fetch(targetUrl, init);
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Gagal menghubungi bridge. Cek apakah bridge sedang jalan & BRIDGE_URL benar." },
      { status: 502 }
    );
  }
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as DELETE,
  handler as PATCH,
};
