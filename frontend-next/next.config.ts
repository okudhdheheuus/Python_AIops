/** @type {import('next').NextConfig}  */
const nextConfig = {
  output: "standalone",
  trailingSlash: false,
  // LLM + SSH 管道可能超过30秒默认超时
  experimental: {
    proxyTimeout: 300000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `http://${process.env.BACKEND_HOST || "localhost"}:8000/api/:path*`,
      },
      {
        source: "/health/:path*",
        destination: `http://${process.env.BACKEND_HOST || "localhost"}:8000/health/:path*`,
      },
      {
        source: "/metrics",
        destination: `http://${process.env.BACKEND_HOST || "localhost"}:8000/metrics`,
      },
    ];
  },
};
module.exports = nextConfig;
