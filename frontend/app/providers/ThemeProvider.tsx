'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';
import type { ThemeProviderProps } from 'next-themes';

export default function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"          // sets class on <html> → "light" | "dark" | "system"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange  // avoids flicker
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
