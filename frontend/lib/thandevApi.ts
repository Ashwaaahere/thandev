/**
 * Thandev API client helper
 *
 * FINDINGS:
 * - Previously, we sent GitHub numeric ids in X-Thandev-User-Id / X-Thandev-Tenant-Id.
 * - Backend now requires UUIDs, so requests were failing with "Invalid tenant_id".
 * - Fix: after GitHub login we bootstrap to internal UUIDs and always send those here.
 */

import { Session } from 'next-auth';

export const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isUuid = (value?: string | null) => !!value && UUID_REGEX.test(String(value));

// Backend API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Get authentication headers from NextAuth session with UUID validation
 * 
 * @param session - NextAuth session object
 * @returns UUID tuple for headers
 * @throws Error if session or UUIDs are missing/invalid (includes bootstrap error if present)
 */
export function ensureUuidSession(session: Session | null): { userId: string; tenantId: string } {
  if (!session || !session.user || !session.user.id) {
    throw new Error('Session required: getAuthHeaders() called without valid NextAuth session');
  }

  const userId = session.user.id;
  const tenantId = session.user.tenantId || session.user.id;
  
  // UUID validation - never send non-UUIDs
  const isUserIdUuid = isUuid(userId);
  const isTenantIdUuid = isUuid(tenantId);
  
  if (!isUserIdUuid || !isTenantIdUuid) {
    const baseError = `Invalid UUIDs in session: userId=${userId} (${isUserIdUuid ? 'valid' : 'INVALID'}), tenantId=${tenantId} (${isTenantIdUuid ? 'valid' : 'INVALID'})`;
    const bootstrapNote = session.bootstrapError ? ` Bootstrap error: ${session.bootstrapError}` : ' Account provisioning required.';
    const error = baseError + bootstrapNote;
    console.error('[ThandevAPI]', error);
    throw new Error(error);
  }

  return { userId, tenantId }
}

/**
 * Get authentication headers from NextAuth session with UUID validation
 */
export function getAuthHeaders(session: Session | null): Record<string, string> {
  const { userId, tenantId } = ensureUuidSession(session);
  return {
    'X-Thandev-User-Id': userId,
    'X-Thandev-Tenant-Id': tenantId,
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
  let authHeaders: Record<string, string>
  try {
    authHeaders = getAuthHeaders(session);
  } catch (err) {
    console.error('[ThandevAPI] Failed to get auth headers:', err);
    
    // UUID validation failed - trigger session refresh and retry once
    if (err instanceof Error && err.message.includes('Invalid UUIDs')) {
      // Trigger session refresh (this will call JWT callback which bootstraps)
      const { useSession } = await import('next-auth/react')
      // Can't use hooks here - instead, wait a bit and retry with fresh session
      // For now, throw and let the component handle refresh
      throw new Error('Session refresh required: UUIDs missing. Please refresh the page.')
    }
    throw err
  }
  
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  
  let response: Response;
  try {
    response = await fetch(fullUrl, {
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
  } catch (fetchError) {
    // Network error (CORS, connection refused, etc.)
    const errorMsg = fetchError instanceof Error ? fetchError.message : String(fetchError);
    console.error('[ThandevAPI] Network error:', {
      url: fullUrl,
      error: errorMsg,
      apiBase: API_BASE
    });
    throw new Error(`Failed to fetch: ${errorMsg}. Check if backend is running at ${API_BASE}`);
  }

  if (!response.ok) {
    let errorMessage = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      
      // Check for UUID validation error from backend
      const isUuidError = errorData.detail && (
        typeof errorData.detail === 'string' && (
          errorData.detail.includes('Invalid tenant_id') ||
          errorData.detail.includes('Must be a valid UUID') ||
          errorData.detail.includes('Invalid user_id')
        )
      )
      
      if (isUuidError && response.status === 400) {
        throw new Error('Session refresh required: Backend rejected non-UUID headers. Please refresh the page.')
      }

      if (response.status === 403 && typeof errorData.detail === 'string' && errorData.detail.includes('Private beta')) {
        const err = new Error('PRIVATE_BETA_FORBIDDEN')
        ;(err as any).code = 'PRIVATE_BETA_FORBIDDEN'
        throw err
      }
      
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
