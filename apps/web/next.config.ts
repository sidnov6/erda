import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the dev overlay badge out of the terminal frame (screenshot loop, §12.4).
  devIndicators: false,
  // Same-origin proxy to the FastAPI data plane — no CORS, one origin in prod.
  async rewrites() {
    const api = process.env.ERDA_API_URL ?? "http://localhost:8000";
    return [{ source: "/api/erda/:path*", destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;
