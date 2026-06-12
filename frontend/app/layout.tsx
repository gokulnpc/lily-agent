import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lily — PartSelect Assistant",
  description:
    "Find, fit, and install refrigerator and dishwasher parts with Lily, the PartSelect chat assistant.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
