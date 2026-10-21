import { describe, expect, it } from "vitest";
import { errorMessage, formatDate, formatMoney } from "./api";

describe("api helpers", () => {
  it("formats API dates using the existing product date style", () => {
    expect(formatDate("2026-01-09")).toMatch(/9/);
    expect(formatDate()).toBe("—");
    expect(formatDate("garbage")).toBe("—");
  });
  it("formats rupees with Indian grouping", () => {
    expect(formatMoney(1234567)).toBe("₹12,34,567");
  });
  it("extracts messages from unknown errors", () => {
    expect(errorMessage(new Error("boom"))).toBe("boom");
    expect(errorMessage("x", "fallback")).toBe("fallback");
  });
});
