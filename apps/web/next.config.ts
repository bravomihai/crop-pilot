import type { NextConfig } from "next";
import path from "node:path";
const config: NextConfig = {
  output: "standalone",
  transpilePackages: ["@croppilot/contracts"],
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  poweredByHeader: false,
};
export default config;
