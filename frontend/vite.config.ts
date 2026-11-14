import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow importing the shared examples from ../contracts.
    fs: { allow: [".."] },
    // Local dev: /api goes to the Next.js backend, so no CORS setup is needed.
    proxy: { "/api": "http://localhost:3000" },
  },
});
