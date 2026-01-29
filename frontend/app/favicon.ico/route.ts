import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // Read the logo.png file from public directory
    const logoPath = path.join(process.cwd(), 'public', 'logo.png');
    const logoBuffer = fs.readFileSync(logoPath);
    
    // Serve it as favicon.ico with appropriate headers
    return new NextResponse(logoBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/x-icon',
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch (error) {
    // Return 404 if logo not found
    return new NextResponse('Favicon not found', { status: 404 });
  }
}
