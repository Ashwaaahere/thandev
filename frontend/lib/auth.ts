import { NextAuthOptions } from 'next-auth'
import GithubProvider from 'next-auth/providers/github'
import CredentialsProvider from 'next-auth/providers/credentials'
import type { Provider } from 'next-auth/providers'

declare module 'next-auth' {
  interface User {
    id: string
    tenantId?: string
    tenantPlan?: string
    isAdmin?: boolean
    isApproved?: boolean
  }
  interface Session {
    user: User
    uuidValid?: boolean
    bootstrapError?: string
    externalUserId?: string
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    userId?: string
    tenantId?: string
    tenantPlan?: string
    provider?: string
    externalUserId?: string
    userEmail?: string
    userName?: string
    bootstrapError?: string
    isAdmin?: boolean
    isApproved?: boolean
  }
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const isUuid = (value?: string | null) => !!value && UUID_REGEX.test(String(value))

// Support both GITHUB_ID/GITHUB_SECRET and GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET
// for compatibility with different naming conventions
const githubClientId = process.env.GITHUB_CLIENT_ID || process.env.GITHUB_ID
const githubClientSecret = process.env.GITHUB_CLIENT_SECRET || process.env.GITHUB_SECRET
const isDevelopment = process.env.NODE_ENV === 'development'
const backendApiBase =
  process.env.BACKEND_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  'http://localhost:8000'

// Debug logging in development
if (isDevelopment) {
  console.log('[Auth Config] GitHub Client ID:', githubClientId ? '✓ Set' : '✗ Missing')
  console.log('[Auth Config] GitHub Client Secret:', githubClientSecret ? '✓ Set' : '✗ Missing')
  console.log('[Auth Config] NEXTAUTH_SECRET:', process.env.NEXTAUTH_SECRET ? '✓ Set' : '✗ Missing')
  console.log('[Auth Config] NEXTAUTH_URL:', process.env.NEXTAUTH_URL || 'Not set')
}

// Build providers array
const providers: Provider[] = []

// Check if we're in build context (Next.js build phase)
const isBuildTime = process.env.NEXT_PHASE === 'phase-production-build' || 
                     process.env.NEXT_PHASE === 'phase-development-build' ||
                     process.env.VERCEL === '1' && !process.env.VERCEL_ENV

// Add GitHub provider if credentials are available
if (githubClientId && githubClientSecret) {
  // Log the actual values being used (mask secret)
  if (isDevelopment) {
    console.log('[Auth Config] Using GitHub Client ID:', githubClientId)
    console.log('[Auth Config] Using GitHub Client Secret:', githubClientSecret.substring(0, 8) + '...')
  }
  
  providers.push(
    GithubProvider({
      clientId: githubClientId,
      clientSecret: githubClientSecret,
      authorization: {
        params: {
          scope: 'read:user user:email',
        },
      },
    })
  )
} else if (isDevelopment || isBuildTime) {
  // In development or build time, use a credentials provider as fallback
  // This allows the build to complete even without GitHub credentials
  if (isDevelopment && !isBuildTime) {
    console.warn(
      '⚠️  GitHub OAuth credentials not found. Using development-only credentials provider.\n' +
      '   To enable GitHub OAuth, set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env.local\n' +
      '   For now, you can sign in with any username/password in development mode.'
    )
  }
  providers.push(
    CredentialsProvider({
      name: 'Development',
      credentials: {
        username: { label: 'Username', type: 'text', placeholder: 'dev' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        // In development or build time, accept any credentials (for build to succeed)
        if ((isDevelopment || isBuildTime) && credentials) {
          return {
            id: 'dev-user',
            name: credentials.username || 'Development User',
            email: `${credentials.username || 'dev'}@localhost`,
          }
        }
        return null
      },
    })
  )
} else {
  // In production runtime without credentials, use a stub provider that shows an error
  // This prevents the app from crashing and allows a graceful error message
  providers.push(
    CredentialsProvider({
      name: 'Configuration Error',
      credentials: {},
      async authorize() {
        // This will never succeed, but prevents the app from crashing
        // The error will be shown in the UI instead
        return null
      },
    })
  )
  
  // Log error for debugging (won't crash the app)
  if (typeof console !== 'undefined') {
    console.error(
      '⚠️  GitHub OAuth credentials missing in production.\n' +
      '   Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in Vercel project settings.\n' +
      '   Authentication will not work until credentials are configured.'
    )
  }
}

// Ensure we have at least one provider (required by NextAuth)
if (providers.length === 0) {
  // Fallback: add a minimal credentials provider to prevent NextAuth from crashing
  providers.push(
    CredentialsProvider({
      name: 'Unavailable',
      credentials: {},
      async authorize() {
        return null
      },
    })
  )
}

export const authOptions: NextAuthOptions = {
  providers,
  callbacks: {
    async session({ session, token }) {
      if (session.user) {
        // Only accept UUIDs; never fall back to numeric/sub IDs
        session.uuidValid = isUuid(token.userId) && isUuid(token.tenantId)
        session.bootstrapError = token.bootstrapError
        session.externalUserId = token.externalUserId

        session.user.id = isUuid(token.userId) ? String(token.userId) : ''
        session.user.tenantId = isUuid(token.tenantId) ? String(token.tenantId) : undefined
        if (token.tenantPlan) {
          session.user.tenantPlan = String(token.tenantPlan)
        }
        session.user.isAdmin = typeof token.isAdmin === 'boolean' ? token.isAdmin : false
        session.user.isApproved = typeof token.isApproved === 'boolean' ? token.isApproved : false
      }

      if (isDevelopment) {
        console.info('[Auth] session UUIDs', {
          uuidValid: session.uuidValid,
          userId: session.user.id,
          tenantId: session.user.tenantId,
          bootstrapError: session.bootstrapError,
        })
      }
      return session
    },
    async jwt({ token, user, account, profile }) {
      // Store provider info on initial sign-in for later bootstrap on refresh
      if (user && account) {
        token.provider = account.provider || 'github'
        token.externalUserId = String(user.id)
        // Store real email/username from initial sign-in (critical for refresh)
        token.userEmail = user.email || ''
        token.userName = user.name || user.email?.split('@')[0] || ''
      }
      
      // Bootstrap if UUIDs missing OR admin/approval flags missing (to pick up new admin grants)
      // Also bootstrap if user is a superadmin but token shows isAdmin=false (to handle admin grants after migration)
      const isSuperadmin = token.externalUserId && (
        token.externalUserId === '97579623' || 
        token.externalUserId === '4708392'
      )
      const needsBootstrap =
        !isUuid(token.userId) ||
        !isUuid(token.tenantId) ||
        typeof token.isAdmin !== 'boolean' ||
        typeof token.isApproved !== 'boolean' ||
        (isSuperadmin && token.isAdmin === false)
      
      if (needsBootstrap && token.sub) {
        try {
          const externalUserId = token.externalUserId || token.sub
          const provider = token.provider || 'github'
          
          // Use stored email from initial sign-in, or from current user object, or generate valid placeholder
          let email = token.userEmail || user?.email
          if (!email) {
            // Generate a valid email format (not .local which Pydantic rejects)
            email = `user-${externalUserId}@example.com`
          }
          
          // Use stored username from initial sign-in, or from current user object, or generate
          let username = token.userName || user?.name || user?.email?.split('@')[0]
          if (!username) {
            username = `github-${externalUserId}`
          }
          
          const name = token.userName || user?.name || username
          
          const bootstrapPayload = {
            provider,
            external_user_id: String(externalUserId),
            username,
            email,
            name,
          }

          // Fetch with timeout to prevent hanging
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 8000) // 8 second timeout
          
          try {
            const res = await fetch(`${backendApiBase}/api/auth/bootstrap`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(bootstrapPayload),
              signal: controller.signal,
            })
            clearTimeout(timeoutId)

            if (!res.ok) {
              const detail = await res.text()
              throw new Error(`Bootstrap failed: ${res.status} ${detail}`)
            }

            const data = await res.json()
            token.userId = data.user_id
            token.tenantId = data.tenant_id
            token.tenantPlan = data.tenant_plan
            token.isAdmin = data.is_admin ?? false
            token.isApproved = data.is_approved ?? true
            token.bootstrapError = undefined
          } catch (fetchError) {
            clearTimeout(timeoutId)
            if (fetchError instanceof Error && fetchError.name === 'AbortError') {
              throw new Error('Bootstrap failed: Request timeout after 8s')
            }
            throw fetchError
          }
        } catch (err) {
          console.error('[Auth] Bootstrap failed', err)
          token.bootstrapError = err instanceof Error ? err.message : 'Bootstrap failed'
          // Clear potentially invalid IDs to avoid sending numeric IDs
          token.userId = undefined
          token.tenantId = undefined
          token.tenantPlan = undefined
        }
      }
      return token
    },
  },
  pages: {
    signIn: '/auth',
    error: '/auth/error',
  },
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  jwt: {
    maxAge: 24 * 60 * 60, // 24 hours
  },
  secret: process.env.NEXTAUTH_SECRET || (isBuildTime ? 'build-time-secret-placeholder' : undefined),
  debug: process.env.NODE_ENV === 'development', // Enable debug in development
}
