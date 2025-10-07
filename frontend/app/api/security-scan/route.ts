import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { url, tier = 'level1', user_id = 'anonymous' } = await request.json();

    if (!url) {
      return NextResponse.json(
        { error: 'URL is required' },
        { status: 400 }
      );
    }

    // Validate URL format
    try {
      new URL(url);
    } catch {
      return NextResponse.json(
        { error: 'Invalid URL format' },
        { status: 400 }
      );
    }

    // Validate tier
    const validTiers = ['level0', 'level1', 'level2'];
    if (!validTiers.includes(tier)) {
      return NextResponse.json(
        { error: 'Invalid tier. Must be level0, level1, or level2' },
        { status: 400 }
      );
    }

    // Send request to FastAPI backend
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    
    const response = await fetch(`${backendUrl}/api/security-scan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url,
        tier,
        user_id,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Backend API failed: ${errorData.detail || response.statusText}`);
    }

    const data = await response.json();
    
    return NextResponse.json({
      success: true,
      jobId: data.jobId,
      message: 'Security scan initiated',
      tier: data.tier,
      estimatedDuration: data.estimated_duration,
    });

  } catch (error) {
    console.error('Security scan error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to initiate security scan',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const jobId = searchParams.get('jobId');

    if (!jobId) {
      return NextResponse.json(
        { error: 'Job ID is required' },
        { status: 400 }
      );
    }

    // Get scan status from FastAPI backend
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    
    const response = await fetch(`${backendUrl}/api/security-scan/status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Backend API failed: ${errorData.detail || response.statusText}`);
    }

    const data = await response.json();
    
    return NextResponse.json({
      success: true,
      jobId: data.jobId,
      status: data.status,
      result: data.result,
      completedAt: data.completedAt,
    });

  } catch (error) {
    console.error('Get scan status error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to get scan status',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

function getEstimatedDuration(scanType: string): string {
  switch (scanType) {
    case 'quick':
      return '5-10 minutes';
    case 'comprehensive':
      return '15-30 minutes';
    case 'deep':
      return '30-60 minutes';
    case 'custom':
      return '10-45 minutes';
    default:
      return '10-30 minutes';
  }
}


