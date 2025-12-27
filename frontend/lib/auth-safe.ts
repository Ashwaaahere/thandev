import { getServerSession } from 'next-auth';
import { authOptions } from './auth';

/**
 * Safely get server session with error handling.
 * Returns null if auth is misconfigured or unavailable.
 */
export async function getSafeServerSession() {
  try {
    return await getServerSession(authOptions);
  } catch (error) {
    // Log error but don't crash the page
    console.error('[Auth] Failed to get server session:', error);
    return null;
  }
}

