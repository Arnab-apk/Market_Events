// Three-up summary strip (label, value, detail) shown under each section heading. Pure display; no API calls.
import type { ReactNode } from "react";

type SummaryItem = { label: string; value: ReactNode; detail: string };

/** A shared, factual snapshot keeps every workspace on the same visual rhythm. */
export function WorkspaceSummary({ items }: { items: SummaryItem[] }) {
  return <dl className="workspace-summary" aria-label="Workspace snapshot">
    {items.map(item => <div className="workspace-summary-item" key={item.label}>
      <dt className="workspace-summary-label">{item.label}</dt>
      <dd className="workspace-summary-value">{item.value}</dd>
      <dd className="workspace-summary-detail">{item.detail}</dd>
    </div>)}
  </dl>;
}
