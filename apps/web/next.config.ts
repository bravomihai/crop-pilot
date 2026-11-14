import type { NextConfig } from "next";
import path from "node:path";
const config: NextConfig = {
  output: "standalone",
  transpilePackages: ["@fieldshift/contracts"],
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  poweredByHeader: false,
};
export default config;
