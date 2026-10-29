/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async redirects() {
    return [{ source: "/timeline", destination: "/tape", permanent: true }];
  },
};
export default nextConfig;
