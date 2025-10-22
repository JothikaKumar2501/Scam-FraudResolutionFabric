import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: [
      "react-markdown",
      "remark-gfm",
      "rehype-raw",
      "framer-motion",
      "next-themes",
    ],
  },
};

export default nextConfig;
