import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8001/api/v1/:path*",
      },
      {
        source: "/metrics",
        destination: "http://127.0.0.1:8001/metrics",
      },
    ];
  },
};


export default nextConfig;
