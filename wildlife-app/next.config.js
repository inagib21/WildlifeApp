/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
  transpilePackages: ['@tabler/icons-react', 'lucide-react'],
  images: {
    domains: ['localhost'],
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8001',
        pathname: '/media/**',
      },
    ],
  },
  bundlePagesRouterDependencies: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8001/:path*',
      },
      {
        source: '/media/:path*',
        destination: 'http://localhost:8001/media/:path*',
      },
      {
        source: '/events/:path*',
        destination: 'http://localhost:8001/events/:path*',
      },
    ]
  },
}

module.exports = nextConfig 