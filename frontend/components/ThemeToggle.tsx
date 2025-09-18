'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle() {
  const { theme, setTheme, systemTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = theme === 'system' ? systemTheme : theme;
  const isDark = current === 'dark';

  if (!mounted) {
    // avoid mismatch on first render
    return (
      <button
        className="h-9 w-9 rounded-lg border border-white/10 bg-white/5 grid place-items-center"
        aria-label="Toggle theme"
      />
    );
  }

  return (
    <button
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label="Toggle theme"
      className="h-9 w-9 rounded-lg border border-white/10 bg-white/5 grid place-items-center hover:bg-white/10"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
