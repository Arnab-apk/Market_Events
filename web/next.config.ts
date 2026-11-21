import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The demo runs on `next dev`; hide the route badge on the projector. Compile/runtime errors still surface.
  devIndicators: false,
};

export default nextConfig;
