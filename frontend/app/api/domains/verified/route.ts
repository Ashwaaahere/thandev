import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// In-memory storage (same as other domain endpoints)
const domainVerifications = new Map<string, {
  userId: string;
  domain: string;
  tokenHash: string;
  status: 'pending' | 'verified' | 'expired';
  createdAt: Date;
  verifiedAt?: Date;
  expiresAt: Date;
  lastCheckAt?: Date;
}>();

export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session?.user?.id) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Get all verified domains for the current user
    const verifiedDomains = Array.from(domainVerifications.values())
      .filter(verification => 
        verification.userId === session.user.id && 
        verification.status === 'verified' &&
        verification.expiresAt > new Date()
      )
      .map(verification => ({
        id: `${verification.userId}:${verification.domain}`,
        domain: verification.domain,
        verifiedAt: verification.verifiedAt?.toISOString(),
        expiresAt: verification.expiresAt.toISOString(),
      }))
      .sort((a, b) => new Date(b.verifiedAt || 0).getTime() - new Date(a.verifiedAt || 0).getTime());

    return NextResponse.json({
      domains: verifiedDomains,
      count: verifiedDomains.length
    });

  } catch (error) {
    console.error('Verified domains error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}


