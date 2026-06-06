import type { ReactNode } from "react";

export function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="glass-panel overflow-hidden rounded-2xl">
      <div className="flex min-h-12 items-center justify-between border-b border-amber-200/10 px-4">
        <h2 className="text-sm font-semibold text-amber-100">{title}</h2>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
