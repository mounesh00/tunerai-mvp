import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TunerAI — Tune AI to your domain",
  description:
    "Turn specialized data into measurable, deployable domain-specialized AI models.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased bg-[var(--background)] text-[var(--foreground)]">
        {children}
      </body>
    </html>
  );
}
