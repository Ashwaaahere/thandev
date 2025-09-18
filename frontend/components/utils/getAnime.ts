
export async function getAnime() {
  try {
    // only import from the package root – the exports field is reliable
    const mod: any = await import('animejs');

    // normalize: sometimes it's the function itself, sometimes at .default
    const fn = typeof mod === 'function'
      ? mod
      : (typeof mod?.default === 'function' ? mod.default : null);

    if (typeof fn === 'function') return fn as any;
  } catch {
    // ignore – we'll return a no-op below
  }

  // fallback: no-op function so callers can still "call" anime(...)
  const noop = ((_: any) => {}) as unknown as (args: any) => void;
  // tiny helpers so code like anime.timeline?.(...) won’t explode
  (noop as any).timeline = () => ({ add: () => (noop as any).timeline() });
  (noop as any).set = () => {};
  return noop as any;
}