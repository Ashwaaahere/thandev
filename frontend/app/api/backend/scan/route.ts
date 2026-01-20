import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// Force dynamic rendering for authenticated API routes
export const dynamic = 'force-dynamic';
export const revalidate = 0;

// In-memory storage for demo (replace with database in production)
const backendScans = new Map<string, {
  scanId: string;
  userId: string;
  domainId: string;
  domain: string;
  scenario: 'baseline' | 'spike' | 'soak' | 'custom';
  status: 'queued' | 'running' | 'done' | 'error';
  createdAt: Date;
  updatedAt: Date;
  startedAt?: Date;
  finishedAt?: Date;
  summary?: {
    p95LatencyMs: number;
    avgRps: number;
    errorRatePct: number;
    totalRequests: number;
    durationSec: number;
    artifacts?: {
      csvUrl?: string;
      jsonUrl?: string;
    };
  };
  error?: string;
  executionId?: string;
}>();

// Global scan queue limits
const MAX_CONCURRENT_SCANS = 2;
let runningScans = 0;

// Scenario configuration
const SCENARIO_CONFIG = {
  baseline: {
    VUS: 50,
    DURATION: 120,
    SPAWN: 10
  },
  spike: {
    VUS: 200,
    DURATION: 120,
    SPAWN: 100
  },
  soak: {
    VUS: 50,
    DURATION: 300,
    SPAWN: 5
  }
} as const;

type ScenarioType = keyof typeof SCENARIO_CONFIG;

function validateDomain(domain: string): { valid: boolean; error?: string } {
  if (!domain || typeof domain !== 'string') {
    return { valid: false, error: 'Domain is required' };
  }
  
  const cleanDomain = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '');
  const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/;
  
  if (!domainRegex.test(cleanDomain)) {
    return { valid: false, error: 'Invalid domain format' };
  }
  
  return { valid: true };
}

// This function is no longer needed as we use Cloud Run Jobs

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session?.user?.id) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    const { domainId, scenario = 'baseline' } = await request.json();
    
    if (!domainId) {
      return NextResponse.json(
        { error: 'Domain ID is required' },
        { status: 400 }
      );
    }

    // Validate scenario
    const scenarioConfig = SCENARIO_CONFIG[scenario as ScenarioType];
    if (!scenarioConfig) {
      return NextResponse.json(
        { error: 'Invalid scenario. Must be baseline, spike, or soak.' },
        { status: 400 }
      );
    }

    // Check if domain is verified and owned by user
    // In production, this would check against the domain verification database
    const domainVerifications = new Map(); // This would be your actual domain verification storage
    const verification = domainVerifications.get(domainId);
    
    if (!verification || verification.userId !== session.user.id || verification.status !== 'verified') {
      return NextResponse.json(
        { error: 'Domain must be verified and owned by you before running backend scans' },
        { status: 403 }
      );
    }

    // Check if we can start a new scan
    if (runningScans >= MAX_CONCURRENT_SCANS) {
      return NextResponse.json(
        { error: 'Maximum concurrent scans reached. Please try again later.' },
        { status: 429 }
      );
    }

    // Generate scan ID
    const scanId = `backend-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Create scan record
    const scan: {
      scanId: string;
      userId: string;
      domainId: string;
      domain: string;
      scenario: 'baseline' | 'spike' | 'soak' | 'custom';
      status: 'queued' | 'running' | 'done' | 'error';
      createdAt: Date;
      updatedAt: Date;
      executionId?: string;
      startedAt?: Date;
      finishedAt?: Date;
      summary?: {
        p95LatencyMs: number;
        avgRps: number;
        errorRatePct: number;
        totalRequests: number;
        durationSec: number;
        artifacts?: {
          csvUrl?: string;
          jsonUrl?: string;
        };
      };
      error?: string;
    } = {
      scanId,
      userId: session.user.id,
      domainId,
      domain: verification.domain,
      scenario: scenario as 'baseline' | 'spike' | 'soak' | 'custom',
      status: 'queued',
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    backendScans.set(scanId, scan);

    // Backend load testing is not available without Cloud Run
    scan.status = 'error';
    scan.error = 'Backend load testing requires Cloud Run infrastructure which is not configured.';
    scan.updatedAt = new Date();
    backendScans.set(scanId, scan);

    return NextResponse.json(
      { error: 'Backend load testing is not available. Cloud Run infrastructure has been removed.' },
      { status: 503 }
    );

  } catch (error) {
    console.error('Backend scan start error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
