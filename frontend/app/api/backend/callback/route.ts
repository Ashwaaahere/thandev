import { NextRequest, NextResponse } from 'next/server';

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

// Global scan counter
let runningScans = 0;

export async function POST(request: NextRequest) {
  try {
    const { scanId, status, summary, gcsPrefix, error } = await request.json();
    
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

    // Update scan status
    scan.status = status;
    scan.updatedAt = new Date();
    scan.finishedAt = new Date();

    if (status === 'done' && summary) {
      // Process summary and artifacts
      scan.summary = {
        p95LatencyMs: summary.p95LatencyMs || 0,
        avgRps: summary.avgRps || 0,
        errorRatePct: summary.errorRatePct || 0,
        totalRequests: summary.totalRequests || 0,
        durationSec: summary.durationSec || 0,
        artifacts: gcsPrefix ? {
          csvUrl: `https://storage.googleapis.com/${process.env.GCS_BUCKET || 'thandev-reports'}/${gcsPrefix}/locust-results.csv`,
          jsonUrl: `https://storage.googleapis.com/${process.env.GCS_BUCKET || 'thandev-reports'}/${gcsPrefix}/locust-summary.json`
        } : undefined
      };
      
      // Decrease running scans counter
      if (runningScans > 0) {
        runningScans--;
      }
      
    } else if (status === 'error') {
      scan.error = error || 'Unknown error occurred during scan';
      
      // Decrease running scans counter
      if (runningScans > 0) {
        runningScans--;
      }
    }

    // Update the scan record
    backendScans.set(scanId, scan);

    console.log(`Backend scan ${scanId} updated: ${status}`, {
      summary: scan.summary,
      error: scan.error
    });

    return NextResponse.json({
      success: true,
      message: 'Callback processed successfully'
    });

  } catch (error) {
    console.error('Backend scan callback error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}


