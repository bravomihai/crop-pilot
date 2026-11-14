import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "FieldShift — planificarea culturilor",
  description:
    "Compară trei planuri pentru următoarele trei culturi principale.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro">
      <body>{children}</body>
    </html>
  );
}
