import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// In-memory storage (same as scan endpoint)
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
    const scanId = searchParams.get('scanId');
    
    if (!scanId) {
      return NextResponse.json(
        { error: 'Scan ID is required' },
        { status: 400 }
      );
    }

    // Get scan record
    const scan = backendScans.get(scanId);
    if (!scan) {
      return NextResponse.json(
        { error: 'Scan not found' },
        { status: 404 }
      );
    }

    // Check if user owns this scan
    if (scan.userId !== session.user.id) {
      return NextResponse.json(
        { error: 'Access denied' },
        { status: 403 }
      );
    }

    // Calculate progress based on status and time
    let progress = 0;
    if (scan.status === 'queued') {
      progress = 10;
    } else if (scan.status === 'running') {
      const elapsed = Date.now() - scan.createdAt.getTime();
      const estimatedDuration = {
        baseline: 30000,
        spike: 60000,
        soak: 300000,
        custom: 120000,
      }[scan.scenario] || 60000;
      
      progress = Math.min(90, 20 + (elapsed / estimatedDuration) * 70);
    } else if (scan.status === 'done') {
      progress = 100;
    }

    const response: any = {
      scanId: scan.scanId,
      status: scan.status,
      domain: scan.domain,
      scenario: scan.scenario,
      progress: Math.round(progress),
      createdAt: scan.createdAt.toISOString(),
      updatedAt: scan.updatedAt.toISOString(),
    };

    if (scan.startedAt) {
      response.startedAt = scan.startedAt.toISOString();
    }

    if (scan.finishedAt) {
      response.finishedAt = scan.finishedAt.toISOString();
    }

    if (scan.summary) {
      response.summary = scan.summary;
    }

    if (scan.error) {
      response.error = scan.error;
    }

    return NextResponse.json(response);

  } catch (error) {
    console.error('Backend scan status error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
