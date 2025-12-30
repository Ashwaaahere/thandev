import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Webpack configuration for path aliases
  webpack: (config, { isServer, dir }) => {
    // Use the dir parameter which Next.js provides (project directory)
    // This works correctly in both local and Vercel environments
    const projectRoot = dir || __dirname;
    const rootPath = path.resolve(projectRoot);
    
    // Debug logging (will show in Vercel build logs)
    console.log('Webpack config - projectRoot:', projectRoot);
    console.log('Webpack config - rootPath:', rootPath);
    console.log('Webpack config - lib exists:', fs.existsSync(path.resolve(rootPath, 'lib')));
    
    // Create absolute paths for aliases
    const libPath = path.resolve(rootPath, 'lib');
    const componentsPath = path.resolve(rootPath, 'components');
    const appPath = path.resolve(rootPath, 'app');
    
    // Verify lib directory exists
    if (!fs.existsSync(libPath)) {
      console.error('ERROR: lib directory not found at:', libPath);
      console.error('Current working directory:', process.cwd());
      console.error('Project root:', rootPath);
    } else {
      console.log('✓ lib directory found at:', libPath);
      console.log('✓ auth.ts exists:', fs.existsSync(path.join(libPath, 'auth.ts')));
      console.log('✓ cloud-run.ts exists:', fs.existsSync(path.join(libPath, 'cloud-run.ts')));
    }
    
    // Set up aliases - use absolute paths
    // CRITICAL: Webpack needs aliases to point to directories, not files
    // The file extensions are resolved automatically
    const customAliases = {
      '@': rootPath,
      '@/lib': libPath,
      '@/components': componentsPath,
      '@/app': appPath,
    };
    
    console.log('Setting webpack aliases:', JSON.stringify(customAliases, null, 2));
    
    // Override existing aliases with our custom ones
    // This ensures our aliases take precedence
    if (!config.resolve) {
      config.resolve = {};
    }
    if (!config.resolve.alias) {
      config.resolve.alias = {};
    }
    
    // CRITICAL: Clear any existing @ aliases first, then apply ours
    // This prevents conflicts
    const existingAliases = { ...config.resolve.alias };
    Object.keys(existingAliases).forEach(key => {
      if (key.startsWith('@')) {
        delete existingAliases[key];
      }
    });
    
    // Apply our aliases
    config.resolve.alias = {
      ...existingAliases,
      ...customAliases,
    };
    
    // Ensure extensions include TypeScript
    if (!config.resolve.extensions) {
      config.resolve.extensions = [];
    }
    const extensions = ['.ts', '.tsx', '.js', '.jsx', '.json'];
    config.resolve.extensions = [
      ...extensions.filter(ext => !config.resolve.extensions.includes(ext)),
      ...config.resolve.extensions,
    ];
    
    return config;
  },
  
  // SEO and Performance optimizations
  compress: true,
  poweredByHeader: false,
  
  // Image optimization
  images: {
    formats: ['image/webp', 'image/avif'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: '**',
      },
    ],
    dangerouslyAllowSVG: true,
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
  
  // Headers for security and SEO
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          // Prevent MIME type sniffing
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          // Prevent clickjacking attacks
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          // XSS Protection
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          // Referrer Policy
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          // Content Security Policy
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://vercel.live",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: https: blob:",
              "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 http://127.0.0.1:7242 https://thandev-backend.fly.dev https://api.github.com https://github.com https://github.com/login https://github.com/login/oauth https://feeds.feedburner.com https://www.cisa.gov https://nvd.nist.gov",
              "frame-src 'none'",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self' https://github.com",
              "frame-ancestors 'none'",
              "upgrade-insecure-requests"
            ].join('; '),
          },
          // Strict Transport Security (HTTPS only)
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains; preload',
          },
          // Permissions Policy
          {
            key: 'Permissions-Policy',
            value: [
              'camera=()',
              'microphone=()',
              'geolocation=()',
              'payment=()',
              'usb=()',
              'magnetometer=()',
              'gyroscope=()',
              'accelerometer=()'
            ].join(', '),
          },
          // Cross-Origin Policies
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'require-corp',
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin', // Allow cross-origin requests to backend
          },
        ],
      },
      {
        source: '/api/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=300, s-maxage=300',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
        ],
      },
      // Static assets with longer cache
      {
        source: '/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      // Images with appropriate cache
      {
        source: '/:path*\\.(jpg|jpeg|png|gif|webp|avif|svg|ico)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=86400',
          },
        ],
      },
    ];
  },
  
  // Redirects for SEO
  async redirects() {
    return [
      {
        source: '/home',
        destination: '/',
        permanent: true,
      },
      {
        source: '/security-news',
        destination: '/news',
        permanent: true,
      },
      {
        source: '/vulnerability-database',
        destination: '/exploits',
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
// Trigger deployment Wednesday 26 November 2025 01:15:35 PM EST
