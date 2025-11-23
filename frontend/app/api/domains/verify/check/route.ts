import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import dns from 'dns';
import { promisify } from 'util';

const resolveTxt = promisify(dns.resolveTxt);

// In-memory storage (same as start endpoint)
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

// Rate limiting
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();

function isRateLimited(userId: string): boolean {
  const now = Date.now();
  const userLimit = rateLimitMap.get(userId);
  
  if (!userLimit || now > userLimit.resetTime) {
    rateLimitMap.set(userId, { count: 1, resetTime: now + 60000 }); // 1 minute window
    return false;
  }
  
  if (userLimit.count >= 5) { // 5 checks per minute
    return true;
  }
  
  userLimit.count++;
  return false;
}

async function checkDnsRecord(domain: string): Promise<string[]> {
  try {
    const recordName = `_thandev-verify.${domain}`;
    const records = await resolveTxt(recordName);
    
    // Flatten all TXT records
    const allValues: string[] = [];
    for (const record of records) {
      allValues.push(...record);
    }
    
    return allValues;
  } catch (error) {
    console.error('DNS resolution error:', error);
    return [];
  }
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

    const cleanDomain = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '');
    const key = `${session.user.id}:${cleanDomain}`;
    
    // Get verification record
    const verification = domainVerifications.get(key);
    if (!verification) {
      return NextResponse.json({
        ok: false,
        status: 'not_found',
        reason: 'No verification record found. Please start verification first.'
      });
    }

    // Check if expired
    if (verification.expiresAt < new Date()) {
      verification.status = 'expired';
      return NextResponse.json({
        ok: false,
        status: 'expired',
        reason: 'Verification token has expired. Please start a new verification.'
      });
    }

    // Check if already verified
    if (verification.status === 'verified') {
      return NextResponse.json({
        ok: true,
        status: 'verified'
      });
    }

    // Update last check time
    verification.lastCheckAt = new Date();

    try {
      // Check DNS record
      const txtRecords = await checkDnsRecord(cleanDomain);
      
      // Look for our verification record
      const expectedPrefix = 'thandev-verify=';
      const matchingRecord = txtRecords.find(record => record.startsWith(expectedPrefix));
      
      if (matchingRecord) {
        const token = matchingRecord.substring(expectedPrefix.length);
        const tokenHash = require('crypto').createHash('sha256').update(token).digest('hex');
        
        // Verify token matches
        if (tokenHash === verification.tokenHash) {
          verification.status = 'verified';
          verification.verifiedAt = new Date();
          
          return NextResponse.json({
            ok: true,
            status: 'verified'
          });
        }
      }
      
      // No matching record found
      return NextResponse.json({
        ok: false,
        status: 'pending',
        reason: 'No matching TXT record found yet. Please wait a few minutes and try again.'
      });
      
    } catch (dnsError) {
      console.error('DNS check error:', dnsError);
      return NextResponse.json({
        ok: false,
        status: 'pending',
        reason: 'DNS lookup failed. Please try again later.'
      });
    }

  } catch (error) {
    console.error('Domain verification check error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}


