import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "JobPilot AI", description: "Discover opportunities and prepare applications with confidence." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
