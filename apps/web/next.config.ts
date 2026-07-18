import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the dev overlay badge out of the terminal frame (screenshot loop, §12.4).
  devIndicators: false,
};

export default nextConfig;
