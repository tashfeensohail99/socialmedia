import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` builds a minimal Node runtime (~50MB) into .next/standalone
  // suitable for Docker deploy. Avoids shipping node_modules or build tooling.
  output: "standalone",
};

export default nextConfig;
