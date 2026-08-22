import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const COOKIE_NAME = "mt5_session";

// Route yang boleh diakses TANPA login
const PUBLIC_PATHS = ["/login", "/api/login"];

async function hasValidSession(req: NextRequest): Promise<boolean> {
  const token = req.cookies.get(COOKIE_NAME)?.value;
  if (!token) return false;
  const secret = process.env.SESSION_SECRET;
  if (!secret) return false;
  try {
    await jwtVerify(token, new TextEncoder().encode(secret));
    return true;
  } catch {
    return false;
  }
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next();
  }

  const loggedIn = await hasValidSession(req);
  if (!loggedIn) {
    // API routes: balas 401 JSON, bukan redirect (biar fetch() di client bisa handle)
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ detail: "Belum login" }, { status: 401 });
    }
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Jalan di semua route kecuali file statis Next.js sendiri
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
