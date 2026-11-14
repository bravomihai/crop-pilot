import type { ReactNode } from "react";

export default function Notice({
  title,
  children,
  tone = "info",
  announce = false,
}: {
  title: string;
  children: ReactNode;
  tone?: "info" | "warning" | "error";
  announce?: boolean;
}) {
  return (
    <div
      className={`notice notice--${tone}`}
      role={announce ? (tone === "error" ? "alert" : "status") : undefined}
    >
      <strong>{title}</strong>
      <div>{children}</div>
    </div>
  );
}
