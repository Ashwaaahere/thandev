import NextAuth from 'next-auth'
import { authOptions } from '@/lib/auth'

const handler = NextAuth(authOptions)

// Force dynamic rendering for NextAuth API routes
export const dynamic = 'force-dynamic'
export const revalidate = 0

export { handler as GET, handler as POST }


