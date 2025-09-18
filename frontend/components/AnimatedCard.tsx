'use client';

import { useEffect, useRef } from 'react';
import { getAnime } from './utils/getAnime';

type Props = React.HTMLAttributes<HTMLDivElement>;

export default function AnimatedCard({ className = '', children, ...rest }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    Object.assign(el.style, {
      transform: 'translateZ(0) scale(1) rotateX(0deg) rotateY(0deg)',
      willChange: 'transform, box-shadow, filter',
      transition: 'box-shadow .25s ease, filter .25s ease',
    });

    let cleanup = () => {};

    (async () => {
      const anime = await getAnime();

      const onEnter = () => {
        anime({
            targets: el,
            scale: 1.015,
            translateY: -4,
            easing: 'spring(1, 80, 12, 0)',
            duration: 500,
        });
        };


      const onLeave = () => {
        anime({
          targets: el,
          scale: 1,
          translateY: 0,
          rotateX: 0,
          rotateY: 0,
          easing: 'easeOutQuart',
          duration: 280,
        });
        el.style.boxShadow = '';
        el.style.filter = '';
      };

      const onMove = (e: MouseEvent) => {
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = (e.clientX - cx) / (r.width / 2);
        const dy = (e.clientY - cy) / (r.height / 2);
        // use anime.set only if available; fallback to style transform
        try {
          (anime as any).set?.(el, { rotateY: dx * 6, rotateX: -dy * 6 });
        } catch {
          el.style.transform = `translateZ(0) scale(1.015) rotateX(${-dy * 6}deg) rotateY(${dx * 6}deg)`;
        }
      };

      el.addEventListener('mouseenter', onEnter);
      el.addEventListener('mousemove', onMove);
      el.addEventListener('mouseleave', onLeave);
      cleanup = () => {
        el.removeEventListener('mouseenter', onEnter);
        el.removeEventListener('mousemove', onMove);
        el.removeEventListener('mouseleave', onLeave);
      };
    })();

    return () => cleanup();
  }, []);

  return (
    <div
      ref={ref}
      className={`rounded-2xl border bg-white p-6 shadow-sm transition-colors
                  border-slate-200 dark:bg-white/5 dark:border-white/10 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
