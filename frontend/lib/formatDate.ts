/**
 * Format a date/time value for display in the user's local timezone.
 * 
 * @param value - Date string, Date object, or null/undefined
 * @returns Formatted date string or "—" for invalid/null values
 */
export function formatDateTime(value?: string | Date | null): string {
  if (!value) {
    return "—";
  }

  try {
    const date = typeof value === "string" ? new Date(value) : value;
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return "—";
    }

    // Use browser's local timezone (no hard-coded timezone)
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch (error) {
    console.warn("Failed to format date:", value, error);
    return "—";
  }
}

