import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // pnpm workspace root, so standalone tracing finds hoisted dependencies.
  outputFileTracingRoot: path.join(__dirname, "../.."),
};

export default nextConfig;
