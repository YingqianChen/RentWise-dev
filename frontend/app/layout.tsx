import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "RentWise — Hong Kong Rental Research Agent",
  description:
    "Collect Hong Kong rental listings, surface missing facts, and decide what to verify next.",
  icons: {
    icon: [
      { url: "/logo.svg", type: "image/svg+xml" },
      { url: "/favicon.png", type: "image/png" },
    ],
  },
  openGraph: {
    title: "RentWise — Hong Kong Rental Research Agent",
    description:
      "Collect Hong Kong rental listings, surface missing facts, and decide what to verify next.",
    images: [{ url: "/logo-with-text.png", width: 1200, height: 1200 }],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className={cn("font-sans", inter.variable)}>
      <body className={inter.className}>{children}</body>
    </html>
  );
}
