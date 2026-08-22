import { NextResponse } from "next/server";
import { verifySession } from "@/lib/session";

/**
 * Dipakai halaman utama untuk cek: apakah browser ini sudah login (session
 * cookie valid)? Tidak mengembalikan URL/token bridge apa pun ke browser.
 */
export async function GET() {
  const isLoggedIn = await verifySession();
  return NextResponse.json({ loggedIn: isLoggedIn });
}
