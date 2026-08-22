import { NextResponse } from "next/server";
import { verifySession } from "@/lib/session";

/**
 * Dipanggil browser (lewat useLiveData) untuk dapat tiket WebSocket.
 * Server ini yang pegang BRIDGE_TOKEN asli, lalu menukarnya ke bridge
 * (server-to-server) untuk dapat tiket sekali-pakai berumur pendek.
 * Browser cuma menerima tiket itu, tidak pernah BRIDGE_TOKEN asli.
 */
export async function POST() {
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

  try {
    const res = await fetch(`${bridgeUrl.replace(/\/$/, "")}/ws-ticket`, {
      method: "POST",
      headers: { Authorization: `Bearer ${bridgeToken}` },
    });
    if (!res.ok) {
      return NextResponse.json({ detail: "Bridge menolak permintaan tiket" }, { status: 502 });
    }
    const data = await res.json();

    // Browser butuh tahu alamat WS bridge untuk connect langsung (tiket
    // sudah aman untuk dikirim, tapi ini tetap membocorkan HOSTNAME bridge
    // ke browser -- itu perlu, karena WebSocket harus connect langsung dari
    // browser ke bridge, tidak bisa lewat proxy REST biasa. Token TIDAK ikut.
    const wsBase = bridgeUrl.replace(/\/$/, "").replace(/^http/, "ws");

    return NextResponse.json({
      ws_url: `${wsBase}/ws?ticket=${encodeURIComponent(data.ticket)}`,
      expires_in: data.expires_in,
    });
  } catch {
    return NextResponse.json(
      { detail: "Gagal menghubungi bridge untuk minta tiket WebSocket." },
      { status: 502 }
    );
  }
}
