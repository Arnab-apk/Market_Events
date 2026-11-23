"use client";

// Three-up summary strip (label, value, detail) shown under each section heading. Numeric values count up
// with React Bits CountUp and always land on the exact figure. Pure display; no API calls.
import type { ReactNode } from "react";
import { Count } from "./ui";
import { format } from "./types";

type SummaryItem = { label: string; value: ReactNode | number; detail: string };

/** A shared, factual snapshot keeps every workspace on the same visual rhythm. */
export function WorkspaceSummary({ items }: { items: SummaryItem[] }) {
  return <dl className="workspace-summary" aria-label="Workspace snapshot">
    {items.map(item => <div className="workspace-summary-item" key={item.label}>
      <dt className="workspace-summary-label">{item.label}</dt>
      <dd className="workspace-summary-value">{typeof item.value === "number" ? <Count value={item.value} format={value => format(value, 0)} /> : item.value}</dd>
      <dd className="workspace-summary-detail">{item.detail}</dd>
    </div>)}
  </dl>;
}
