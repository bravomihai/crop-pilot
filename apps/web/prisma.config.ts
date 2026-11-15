import "../../scripts/load-env.mjs";
import { defineConfig } from "prisma/config";
export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  datasource: {
    url:
      process.env.DATABASE_URL ??
      "postgresql://croppilot:croppilot@localhost:5432/croppilot",
  },
});
