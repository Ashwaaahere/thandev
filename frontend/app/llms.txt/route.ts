import { NextResponse } from 'next/server';

export async function GET() {
  const content = `User-agent: *
Allow: /`;

  return new NextResponse(content, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
}

