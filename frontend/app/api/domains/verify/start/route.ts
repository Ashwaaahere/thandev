import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import crypto from 'crypto';

// Force dynamic rendering for authenticated API routes
export const dynamic = 'force-dynamic';
export const revalidate = 0;

// In-memory storage for demo (replace with database in production)
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

// Rate limiting (in-memory for demo)
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();

function isRateLimited(userId: string): boolean {
  const now = Date.now();
  const userLimit = rateLimitMap.get(userId);
  
  if (!userLimit || now > userLimit.resetTime) {
    rateLimitMap.set(userId, { count: 1, resetTime: now + 60000 }); // 1 minute window
    return false;
  }
  
  if (userLimit.count >= 3) { // 3 requests per minute
    return true;
  }
  
  userLimit.count++;
  return false;
}

function validateDomain(domain: string): { valid: boolean; error?: string } {
  // Basic domain validation
  if (!domain || typeof domain !== 'string') {
    return { valid: false, error: 'Domain is required' };
  }
  
  // Remove protocol and www
  const cleanDomain = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '');
  
  // Check for valid domain format
  const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/;
  if (!domainRegex.test(cleanDomain)) {
    return { valid: false, error: 'Invalid domain format' };
  }
  
  // Block private/localhost domains
  const privatePatterns = [
    /^localhost$/,
    /^127\./,
    /^192\.168\./,
    /^10\./,
    /^172\.(1[6-9]|2[0-9]|3[01])\./,
    /\.local$/,
    /\.internal$/,
  ];
  
  if (privatePatterns.some(pattern => pattern.test(cleanDomain))) {
    return { valid: false, error: 'Private domains are not allowed' };
  }
  
  // Must have a valid TLD
  const parts = cleanDomain.split('.');
  if (parts.length < 2 || parts[parts.length - 1].length < 2) {
    return { valid: false, error: 'Domain must have a valid TLD' };
  }
  
  return { valid: true };
}

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session?.user?.id) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    const { domain } = await request.json();
    
    if (!domain) {
      return NextResponse.json(
        { error: 'Domain is required' },
        { status: 400 }
      );
    }

    // Rate limiting
    if (isRateLimited(session.user.id)) {
      return NextResponse.json(
        { error: 'Rate limit exceeded. Please try again later.' },
        { status: 429 }
      );
    }

    // Validate domain
    const validation = validateDomain(domain);
    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    const cleanDomain = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '');
    const key = `${session.user.id}:${cleanDomain}`;
    
    // Check if domain is already verified
    const existing = domainVerifications.get(key);
    if (existing && existing.status === 'verified' && existing.expiresAt > new Date()) {
      return NextResponse.json({
        recordName: `_thandev-verify.${cleanDomain}`,
        recordType: 'TXT',
        recordValue: 'thandev-verify=<existing-token>',
        expiresAt: existing.expiresAt.toISOString(),
      });
    }

    // Generate new token
    const token = crypto.randomBytes(32).toString('hex');
    const tokenHash = crypto.createHash('sha256').update(token).digest('hex');
    const expiresAt = new Date(Date.now() + 48 * 60 * 60 * 1000); // 48 hours

    // Store verification record
    domainVerifications.set(key, {
      userId: session.user.id,
      domain: cleanDomain,
      tokenHash,
      status: 'pending',
      createdAt: new Date(),
      expiresAt,
    });

    return NextResponse.json({
      recordName: `_thandev-verify.${cleanDomain}`,
      recordType: 'TXT',
      recordValue: `thandev-verify=${token}`,
      expiresAt: expiresAt.toISOString(),
    });

  } catch (error) {
    console.error('Domain verification start error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}


