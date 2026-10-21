import type { PropsWithChildren } from "react";
export function Badge({ children, tone = "default" }: PropsWithChildren<{ tone?: "default" | "soft" | "danger" }>) { return <span className={`tag ${tone === "soft" ? "tag-soft" : tone === "danger" ? "tag-danger" : ""}`}>{children}</span>; }
