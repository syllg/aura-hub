import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import AppProviders from "./providers/AppProviders";

export const metadata: Metadata = {
  title: { default: "Aura Hub — Retail Intelligence", template: "%s — Aura Hub" },
  description: "Dashboard analytics penjualan dan asisten SOP berbasis retrieval untuk tim operasional PT. XYZ.",
  other: {
    "cache-control": "no-store, no-cache, must-revalidate",
    pragma: "no-cache",
  },
};

export const viewport: Viewport = {
  themeColor: "#f5f7fa",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="id">
      <body><AppProviders>{children}</AppProviders></body>
    </html>
  );
}
