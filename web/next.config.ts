import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8090/api/:path*" },
      { source: "/embed/:path*", destination: "http://localhost:8090/apps/:path*" },
    ];
  },
};

export default nextConfig;
