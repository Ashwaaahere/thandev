import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const response = NextResponse.next()

  // Security headers that can be set in middleware
  response.headers.set('X-DNS-Prefetch-Control', 'off')
  response.headers.set('X-Download-Options', 'noopen')
  response.headers.set('X-Permitted-Cross-Domain-Policies', 'none')
  
  // Remove server information
  response.headers.delete('X-Powered-By')
  
  // Add security headers for specific paths
  if (request.nextUrl.pathname.startsWith('/api/')) {
    response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate')
    response.headers.set('Pragma', 'no-cache')
    response.headers.set('Expires', '0')
  }

  // Block access to sensitive files
  if (request.nextUrl.pathname.match(/\.(env|log|config)$/)) {
    return new NextResponse('Not Found', { status: 404 })
  }

  // Block access to common sensitive paths
  const sensitivePaths = [
    '/.env',
    '/.env.local',
    '/.env.production',
    '/.env.development',
    '/package.json',
    '/package-lock.json',
    '/yarn.lock',
    '/.git',
    '/.gitignore',
    '/README.md',
    '/Dockerfile',
    '/docker-compose.yml',
    '/.dockerignore'
  ]

  if (sensitivePaths.some(path => request.nextUrl.pathname.startsWith(path))) {
    return new NextResponse('Not Found', { status: 404 })
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}




