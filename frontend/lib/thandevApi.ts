/**
 * Thandev API client helper
 * 
 * Provides authenticated fetch functions that automatically include
 * X-Thandev-User-Id and X-Thandev-Tenant-Id headers from NextAuth session.
 * 
 * For now, uses 1:1 mapping: tenant_id = user_id
 * (Future: will support org accounts with multiple users per tenant)
 */

import { Session } from 'next-auth';

// Backend API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Get authentication headers from NextAuth session
 * 
 * @param session - NextAuth session object
 * @returns Headers object with X-Thandev-User-Id and X-Thandev-Tenant-Id
 * @throws Error if session or user.id is missing
 */
export function getAuthHeaders(session: Session | null): Record<string, string> {
  if (!session || !session.user || !session.user.id) {
    throw new Error('Session required: getAuthHeaders() called without valid NextAuth session');
  }

  const userId = session.user.id;
  
  // For now, use 1:1 mapping: tenant_id = user_id
  // Future: will support org accounts where multiple users share a tenant
  return {
    'X-Thandev-User-Id': userId,
    'X-Thandev-Tenant-Id': userId,
  };
}

/**
 * Authenticated fetch for JSON responses
 * 
 * Automatically includes auth headers and handles errors.
 * 
 * @param url - API endpoint path (e.g., '/api/projects')
 * @param session - NextAuth session (required for authenticated routes)
 * @param init - Optional fetch init options (headers will be merged)
 * @returns Parsed JSON response
 * @throws Error if request fails or response is not ok
 */
export async function thandevFetchJSON<T>(
  url: string,
  session: Session | null,
  init?: RequestInit
): Promise<T> {
  const authHeaders = getAuthHeaders(session);
  
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  
  const response = await fetch(fullUrl, {
    ...init,
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...authHeaders,
      ...init?.headers,
    },
    mode: 'cors',
    credentials: 'omit',
  });

  if (!response.ok) {
    let errorMessage = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      // FastAPI validation errors (422) return detail as an array
      if (Array.isArray(errorData.detail)) {
        const validationErrors = errorData.detail.map((err: any) => {
          const loc = Array.isArray(err.loc) ? err.loc.slice(1).join('.') : '';
          const msg = err.msg || '';
          return loc ? `${loc}: ${msg}` : msg;
        }).join('; ');
        errorMessage = validationErrors || errorMessage;
      } else {
        // Single error message
        errorMessage = errorData.detail || errorData.message || errorData.error || errorMessage;
      }
    } catch {
      try {
        const errorText = await response.text();
        if (errorText) errorMessage = errorText;
      } catch {
        // Use default error message
      }
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

/**
 * Authenticated fetch for PDF downloads
 * 
 * Automatically includes auth headers and returns Blob for PDF files.
 * 
 * @param url - API endpoint path (e.g., '/api/scans/{id}/report.pdf')
 * @param session - NextAuth session (required for authenticated routes)
 * @param init - Optional fetch init options (headers will be merged)
 * @returns Blob for PDF file
 * @throws Error if request fails or response is not ok
 */
export async function thandevFetchPDF(
  url: string,
  session: Session | null,
  init?: RequestInit
): Promise<Blob> {
  const authHeaders = getAuthHeaders(session);
  
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  
  const response = await fetch(fullUrl, {
    ...init,
    headers: {
      'Accept': 'application/pdf',
      ...authHeaders,
      ...init?.headers,
    },
    mode: 'cors',
    credentials: 'omit',
  });

  if (!response.ok) {
    let errorMessage = `PDF download failed: ${response.status} ${response.statusText}`;
    try {
      const errorText = await response.text();
      if (errorText) errorMessage = errorText;
    } catch {
      // Use default error message
    }
    throw new Error(errorMessage);
  }

  return response.blob();
}
