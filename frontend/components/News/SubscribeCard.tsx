// components/News/SubscribeCard.tsx
"use client";

import clsx from "clsx";

type Props = { className?: string };

export default function SubscribeCard({ className }: Props) {
  return (
    <section
      className={clsx(
        "rounded-xl bg-[var(--surface)] border card-border shadow-soft p-3",
        className
      )}
    >
      <h3 className="text-sm font-semibold text-[var(--fg)]">Get weekly highlights</h3>
      <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
        A tiny email with the 5 biggest security headlines.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const formData = new FormData(e.currentTarget);
          const email = formData.get('email') as string;
          if (email) {
            alert(`Thank you for subscribing with ${email}! (This is a demo)`);
          }
        }}
        className="mt-3 flex gap-2"
      >
        <input
          name="email"
          type="email"
          placeholder="you@company.com"
          className="min-w-0 flex-1 rounded-lg border card-border bg-transparent px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          required
        />
        <button
          type="submit"
          className="btn-brand whitespace-nowrap px-3 py-2 text-sm"
        >
          Subscribe
        </button>
      </form>
    </section>
  );
}
