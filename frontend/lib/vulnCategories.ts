/**
 * Vulnerability category labels and formatting utilities
 */

export const VULN_CATEGORY_LABELS: Record<string, string> = {
  xss: "XSS",
  sqli: "SQL Injection",
  ssrf: "SSRF",
  ssti: "SSTI",
  xxe: "XXE",
  dir_traversal: "Directory Traversal",
  csrf: "CSRF",
  cors: "CORS Misconfig",
  command_injection: "Command Injection",
  idor: "IDOR",
};

/**
 * Format a category key into a human-readable label
 * @param cat - Category key (e.g., "xss", "sqli")
 * @returns Formatted label (e.g., "XSS", "SQL Injection") or uppercase key if not found
 */
export function formatCategory(cat: string): string {
  return VULN_CATEGORY_LABELS[cat] ?? cat.toUpperCase();
}

/**
 * Get all available category keys
 */
export function getAllCategories(): string[] {
  return Object.keys(VULN_CATEGORY_LABELS);
}

