import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Terminal | MT5 Dashboard",
  description: "Dashboard trading pribadi terhubung ke MT5",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
