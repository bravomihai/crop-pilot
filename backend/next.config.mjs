/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output = small self-contained server, easy to run in a container on AWS.
  // CORS for the React frontend is handled in middleware.ts (it also answers OPTIONS preflight).
  output: "standalone",
};

export default nextConfig;
