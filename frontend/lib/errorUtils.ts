/**
 * Error message parser utility
 * 
 * Extracts readable error messages from various error types:
 * - Fetch Response objects
 * - Error instances
 * - Plain objects
 * - Strings
 * 
 * Never returns "[object Object]" - always returns a readable string.
 */

export async function getErrorMessage(err: unknown): Promise<string> {
  // If it's a Response object (from fetch)
  if (err instanceof Response) {
    try {
      const json = await err.json();
      return json.message || json.detail || json.error || JSON.stringify(json);
    } catch {
      try {
        const text = await err.text();
        return text || `Request failed: ${err.status} ${err.statusText}`;
      } catch {
        return `Request failed: ${err.status} ${err.statusText}`;
      }
    }
  }
  
  // If it's an Error instance
  if (err instanceof Error) {
    return err.message;
  }
  
  // If it's a string
  if (typeof err === 'string') {
    return err;
  }
  
  // If it's an object with common error fields
  if (err && typeof err === 'object') {
    const obj = err as any;
    if (obj.message && typeof obj.message === 'string') {
      return obj.message;
    }
    if (obj.detail && typeof obj.detail === 'string') {
      return obj.detail;
    }
    if (obj.error && typeof obj.error === 'string') {
      return obj.error;
    }
    if (obj.detail && typeof obj.detail === 'object') {
      // FastAPI validation errors
      if (Array.isArray(obj.detail)) {
        return obj.detail.map((e: any) => {
          const loc = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : '';
          const msg = e.msg || '';
          return loc ? `${loc}: ${msg}` : msg;
        }).join('; ');
      }
      if (obj.detail.message && typeof obj.detail.message === 'string') {
        return obj.detail.message;
      }
    }
    // Last resort: try to stringify, but with a fallback
    try {
      const str = JSON.stringify(err);
      // If it's just "{}", return a generic message
      if (str === '{}' || str === 'null') {
        return 'An unknown error occurred';
      }
      return str;
    } catch {
      return 'An unknown error occurred';
    }
  }
  
  // Fallback
  return String(err) || 'An unknown error occurred';
}

/**
 * Synchronous version for cases where we already have the error message
 */
export function getErrorMessageSync(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  if (err && typeof err === 'object') {
    const obj = err as any;
    if (obj.message && typeof obj.message === 'string') {
      return obj.message;
    }
    if (obj.detail && typeof obj.detail === 'string') {
      return obj.detail;
    }
    if (obj.error && typeof obj.error === 'string') {
      return obj.error;
    }
    try {
      const str = JSON.stringify(err);
      if (str === '{}' || str === 'null') {
        return 'An unknown error occurred';
      }
      return str;
    } catch {
      return 'An unknown error occurred';
    }
  }
  return String(err) || 'An unknown error occurred';
}

