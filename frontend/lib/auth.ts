import { NextAuthOptions } from 'next-auth'
import GithubProvider from 'next-auth/providers/github'

declare module 'next-auth' {
  interface User {
    id: string
  }
  interface Session {
    user: User
  }
}

// Support both GITHUB_ID/GITHUB_SECRET and GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET
// for compatibility with different naming conventions
const githubClientId = process.env.GITHUB_CLIENT_ID || process.env.GITHUB_ID
const githubClientSecret = process.env.GITHUB_CLIENT_SECRET || process.env.GITHUB_SECRET

if (!githubClientId || !githubClientSecret) {
  throw new Error(
    'Missing GitHub OAuth credentials. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET ' +
    '(or GITHUB_ID and GITHUB_SECRET) environment variables.'
  )
}

export const authOptions: NextAuthOptions = {
  providers: [
    GithubProvider({
      clientId: githubClientId,
      clientSecret: githubClientSecret,
    }),
  ],
  callbacks: {
    async session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub
      }
      return session
    },
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
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
  secret: process.env.NEXTAUTH_SECRET,
  // Required for Vercel deployment
  trustHost: true,
}
