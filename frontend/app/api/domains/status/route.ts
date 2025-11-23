import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// In-memory storage (same as other endpoints)
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

    const { searchParams } = new URL(request.url);
    const domain = searchParams.get('domain');
    
    if (!domain) {
      return NextResponse.json(
        { error: 'Domain parameter is required' },
        { status: 400 }
      );
    }

    const cleanDomain = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '');
    const key = `${session.user.id}:${cleanDomain}`;
    
    // Get verification record
    const verification = domainVerifications.get(key);
    if (!verification) {
      return NextResponse.json({
        status: 'unverified',
        domain: cleanDomain
      });
    }

    // Check if expired
    if (verification.expiresAt < new Date()) {
      verification.status = 'expired';
    }

    return NextResponse.json({
      status: verification.status,
      domain: cleanDomain,
      createdAt: verification.createdAt.toISOString(),
      verifiedAt: verification.verifiedAt?.toISOString(),
      expiresAt: verification.expiresAt.toISOString(),
      lastCheckAt: verification.lastCheckAt?.toISOString(),
    });

  } catch (error) {
    console.error('Domain status error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}


