/** @type {import('next').NextConfig} */
const csp = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "img-src 'self' data: blob: https://images.unsplash.com https://source.unsplash.com https://*.paddle.com https://*.stripe.com",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://cdn.paddle.com https://js.stripe.com",
  "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 http://localhost:8010 http://127.0.0.1:8010 ws: wss: https://*.paddle.com https://*.stripe.com",
  "frame-src https://*.paddle.com https://js.stripe.com https://*.stripe.com",
].join('; ')

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  transpilePackages: ['@dea/ui'],
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'source.unsplash.com' },
    ],
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
        ],
      },
    ]
  },
};

module.exports = nextConfig;
