import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getToken } from 'next-auth/jwt'

const PROTECTED_PATHS = [
  '/dashboard',
  '/projects',
  '/scans',
  '/reports',
  '/notifications',
  '/performance',
  '/admin',
  // '/' removed - landing page should be accessible without login
]

const SENSITIVE_PATHS = [
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
  '/.dockerignore',
]

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Block access to sensitive files/paths early
  if (pathname.match(/\.(env|log|config)$/) || SENSITIVE_PATHS.some((p) => pathname.startsWith(p))) {
    return new NextResponse('Not Found', { status: 404 })
  }

  const isProtected = PROTECTED_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))
  const isAdminRoute = pathname === '/admin' || pathname.startsWith('/admin/')
  const isAuthOrBeta = pathname.startsWith('/auth') || pathname.startsWith('/private-beta')
  // Public pages accessible without login
  const isPublicPage = pathname === '/' || pathname.startsWith('/news') || pathname.startsWith('/docs') || pathname.startsWith('/exploits') || pathname.startsWith('/terms') || pathname.startsWith('/privacy')

  if (isProtected && !isAuthOrBeta && !isPublicPage) {
    const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET })

    if (!token) {
      const signInUrl = new URL('/auth', req.url)
      return NextResponse.redirect(signInUrl)
    }

    const isAdmin = Boolean((token as any).isAdmin)
    const isApproved = Boolean((token as any).isApproved)
    
    // Check if user is a superadmin by external_user_id (to handle cases where token hasn't been refreshed yet)
    const externalUserId = (token as any).externalUserId || (token as any).sub
    const isSuperadmin = externalUserId && (
      externalUserId === '97579623' || 
      externalUserId === '4708392'
    )
    const effectiveIsAdmin = isAdmin || isSuperadmin

    if (isAdminRoute && !effectiveIsAdmin) {
      const dashboardUrl = new URL('/dashboard', req.url)
      return NextResponse.redirect(dashboardUrl)
    }

    if (!effectiveIsAdmin && !isApproved) {
      const betaUrl = new URL('/private-beta', req.url)
      return NextResponse.redirect(betaUrl)
    }
  }

  const response = NextResponse.next()

  // Security headers
  response.headers.set('X-DNS-Prefetch-Control', 'off')
  response.headers.set('X-Download-Options', 'noopen')
  response.headers.set('X-Permitted-Cross-Domain-Policies', 'none')
  response.headers.delete('X-Powered-By')

  if (pathname.startsWith('/api/')) {
    response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate')
    response.headers.set('Pragma', 'no-cache')
    response.headers.set('Expires', '0')
  }

  return response
}

export const config = {
  matcher: [
    // Match all routes except static assets, auth, favicon, and images.
    '/((?!_next/static|_next/image|favicon.ico|api/auth|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}




