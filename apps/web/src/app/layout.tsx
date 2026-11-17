import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "./analysis.css";
import "./map-workspace.css";
import "./ui-theme.css";
import "./controls.css";
export const metadata: Metadata = {
  title: "CropPilot",
  description:
    "Compare three plans for your next three main crops.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  // Extensions such as Dark Reader add attributes to <html> before hydration.
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
