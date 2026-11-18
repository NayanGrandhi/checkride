import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Fonts are bundled in src/fonts (SIL Open Font License, see the LICENSE files there).

// B612: designed by Airbus for cockpit displays. Used for headings, scores, ACS codes.
const b612 = localFont({
  variable: "--font-b612",
  src: [
    { path: "../fonts/b612-latin-400-normal.woff2", weight: "400" },
    { path: "../fonts/b612-latin-700-normal.woff2", weight: "700" },
  ],
});

// Atkinson Hyperlegible: designed for maximum legibility. Used for body text.
const atkinson = localFont({
  variable: "--font-atkinson",
  src: [
    { path: "../fonts/atkinson-hyperlegible-latin-400-normal.woff2", weight: "400" },
    { path: "../fonts/atkinson-hyperlegible-latin-700-normal.woff2", weight: "700" },
  ],
});

export const metadata: Metadata = {
  title: "checkride",
  description: "Practice your Private Pilot oral exam with an AI examiner.",
};

export const viewport: Viewport = {
  themeColor: "#eef2ec",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${b612.variable} ${atkinson.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
