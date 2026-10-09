import type { Metadata, Viewport } from "next";
import { Hind_Siliguri, Sora } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

const sora = Sora({ variable: "--font-sora", subsets: ["latin"] });

// Sora has no Bengali glyphs; the browser falls back to Hind Siliguri for Bangla text.
// Not preloaded: most visitors read English first, and Bangla glyphs load on demand.
const bangla = Hind_Siliguri({
  variable: "--font-bangla",
  subsets: ["bengali"],
  weight: ["400", "600"],
  preload: false,
});

export const metadata: Metadata = {
  title: { default: "Rokkha — help, dispatched in seconds", template: "%s · Rokkha" },
  description:
    "Public-safety dispatch and Online GD: press SOS, the nearest available officer is assigned automatically, and both sides follow it live.",
};

export const viewport: Viewport = {
  themeColor: "#fff6ec",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sora.variable} ${bangla.variable} h-full`}>
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
