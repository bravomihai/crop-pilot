"use client";
import { useEffect, useState } from "react";

export default function ThemeControl() {
  const [theme, setTheme] = useState("system");
  useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);
  return (
    <label className="theme-control">
      Theme
      <select
        aria-label="Colour theme"
        value={theme}
        onChange={(event) => setTheme(event.target.value)}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
