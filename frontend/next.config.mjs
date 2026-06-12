/** @type {import('next').NextConfig} */
const nextConfig = {
  // Small runtime image for the in-cluster deployment (Phase 3c).
  output: "standalone",
  // Part images are served from PartSelect's CDN.
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
};

export default nextConfig;
