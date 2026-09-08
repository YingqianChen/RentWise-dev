import type { Metadata } from "next";
import "./globals.css";


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
    <html lang="en" className="font-sans">
      <body>{children}</body>
    </html>
  );
}
