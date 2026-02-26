import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const AUTH_HEADERS: [string, string][] = [
  ['x-thandev-user-id', 'X-Thandev-User-Id'],
  ['x-thandev-tenant-id', 'X-Thandev-Tenant-Id'],
];

/**
 * Proxy POST /api/code-scans/unlink-repo to the backend.
 * Forwards auth headers from the client request so unlink works when frontend calls same-origin.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const linked_repo_id = body?.linked_repo_id;
    if (!linked_repo_id || typeof linked_repo_id !== 'string') {
      return NextResponse.json(
        { detail: 'linked_repo_id is required' },
        { status: 400 }
      );
    }

    const backendUrl = (process.env.NEXT_PUBLIC_API_BASE || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
    const apiUrl = `${backendUrl}/api/code-scans/unlink-repo`;

    const forwardHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    for (const [incoming, outgoing] of AUTH_HEADERS) {
      const value = request.headers.get(incoming);
      if (value) forwardHeaders[outgoing] = value;
    }

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: forwardHeaders,
      body: JSON.stringify({ linked_repo_id: linked_repo_id.trim() }),
    });

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (err) {
    console.error('[code-scans/unlink-repo] proxy error:', err);
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : 'Unlink proxy failed' },
      { status: 500 }
    );
  }
}
