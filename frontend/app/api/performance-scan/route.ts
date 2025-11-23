import { NextRequest, NextResponse } from 'next/server';

// Force dynamic rendering for API routes
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function POST(request: NextRequest) {
  try {
    const { url, device = 'desktop' } = await request.json();

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

    // Send request to FastAPI backend
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
    
    console.log('Sending performance scan request to:', `${backendUrl}/api/performance-scan`);
    console.log('Request payload:', { url, device });
    
    const response = await fetch(`${backendUrl}/api/performance-scan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url,
        device,
        // Backend expects url as HttpUrl, device as string, user_id is optional
      }),
    });

    if (!response.ok) {
      // Try to get error details from backend
      let errorMessage = `Backend API failed: ${response.statusText}`;
      let errorDetail = '';
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || errorData.error || '';
        errorMessage = errorDetail || errorMessage;
        console.error('Backend error response:', errorData);
      } catch {
        // If response is not JSON, try to get text
        try {
          const errorText = await response.text();
          console.error('Backend error text:', errorText);
          errorMessage = errorText || errorMessage;
        } catch {
          // Use status text as fallback
        }
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    
    return NextResponse.json({
      success: true,
      jobId: data.jobId,
      message: 'Performance scan initiated',
      estimatedDuration: '30-60 seconds',
    });

  } catch (error) {
    console.error('Performance scan error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('Backend URL:', process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000');
    return NextResponse.json(
      { 
        error: 'Failed to initiate performance scan',
        details: errorMessage,
        backendUrl: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'
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

    // Check status with FastAPI backend
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
    
    const response = await fetch(`${backendUrl}/api/performance-scan/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      // Try to get error details from backend
      let errorMessage = `Backend API failed: ${response.statusText}`;
      let errorDetail = '';
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || errorData.error || '';
        errorMessage = errorDetail || errorMessage;
        console.error('Backend error response:', errorData);
      } catch {
        // If response is not JSON, try to get text
        try {
          const errorText = await response.text();
          console.error('Backend error text:', errorText);
          errorMessage = errorText || errorMessage;
        } catch {
          // Use status text as fallback
        }
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    
    return NextResponse.json(data);

  } catch (error) {
    console.error('Performance scan status error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to get scan status',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}
