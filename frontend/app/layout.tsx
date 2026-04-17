import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "RentWise - Hong Kong Rental Research Agent",
  description: "AI-powered rental listing analysis and decision support",
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
