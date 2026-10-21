import type { ReactNode } from "react";

export function Highlight({ text, query }: { text: string; query: string }): ReactNode {
  const terms = query.trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return text;
  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const parts = text.split(new RegExp(`(${escaped.join("|")})`, "ig"));
  return <>{parts.map((part, index) => terms.some((term) => part.toLocaleLowerCase() === term.toLocaleLowerCase())
    ? <mark className="search-highlight" key={index}>{part}</mark>
    : part)}</>;
}
