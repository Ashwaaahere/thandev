import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

export async function GET(request: NextRequest) {
  try {
    // Read from public directory for reliable access in all environments
    const filePath = path.join(process.cwd(), 'public', 'THIRD_PARTY_NOTICES.md');
    
    const fileContent = await readFile(filePath, 'utf-8');
    
    return new NextResponse(fileContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/markdown; charset=utf-8',
        'Content-Disposition': 'attachment; filename="THIRD_PARTY_NOTICES.md"',
        'Cache-Control': 'public, max-age=3600, s-maxage=3600',
      },
    });
  } catch (error) {
    console.error('Error serving THIRD_PARTY_NOTICES.md:', error);
    return new NextResponse('File not found', { status: 404 });
  }
}

