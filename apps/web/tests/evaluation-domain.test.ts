import { describe, expect, it } from "vitest";

import { evaluateMetric } from "@/types/domain";

describe("evaluation metric gating", () => {
  it("uses the configured comparison direction and leaves missing thresholds ungated", () => {
    expect(evaluateMetric({ value: 0.84, threshold: 0.85, operator: ">=" })).toBe("fail");
    expect(evaluateMetric({ value: 0.03, threshold: 0.05, operator: "<=" })).toBe("pass");
    expect(evaluateMetric({ value: 0.84 })).toBe("not_gated");
  });
});
