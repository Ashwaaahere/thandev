'use client';

import { useEffect } from 'react';

interface RedirectHandlerProps {
  url: string;
}

export default function RedirectHandler({ url }: RedirectHandlerProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      window.location.href = url;
    }, 1000);

    return () => clearTimeout(timer);
  }, [url]);

  return null;
}
