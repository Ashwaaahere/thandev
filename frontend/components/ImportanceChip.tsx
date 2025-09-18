// components/ImportanceChip.tsx
export default function ImportanceChip({ level }: { level: "High" | "Medium" | "Low" }) {
  const cfg =
    level === "High"
      ? { text: "🔥 High",  cls: "bg-red-500/10 text-red-600 dark:text-red-300" }
      : level === "Medium"
      ? { text: "⚡ Medium", cls: "bg-amber-500/10 text-amber-700 dark:text-amber-300" }
      : { text: "• Low", cls: "bg-slate-500/10 text-slate-700 dark:text-slate-300" };

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cfg.cls}`}>
      {cfg.text}
    </span>
  );
}
