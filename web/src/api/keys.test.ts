import { describe, it, expect } from "vitest";
import { buildModelRules } from "./keys";

describe("buildModelRules", () => {
  it("maps alias = target_model and lowercases provider", () => {
    const rules = buildModelRules([
      { provider: "Codex", model: "gpt-5-codex" },
      { provider: "Claude", model: "claude-sonnet-4" },
    ]);
    expect(rules).toEqual([
      { alias: "gpt-5-codex", provider: "codex", target_model: "gpt-5-codex" },
      { alias: "claude-sonnet-4", provider: "claude", target_model: "claude-sonnet-4" },
    ]);
  });

  it("dedupes identical provider/model pairs", () => {
    const rules = buildModelRules([
      { provider: "codex", model: "gpt-5" },
      { provider: "CODEX", model: "GPT-5" },
    ]);
    expect(rules).toHaveLength(1);
  });

  it("skips empty provider or model", () => {
    const rules = buildModelRules([
      { provider: "", model: "x" },
      { provider: "p", model: "" },
      { provider: "p", model: "ok" },
    ]);
    expect(rules).toEqual([
      { alias: "ok", provider: "p", target_model: "ok" },
    ]);
  });

  it("trims whitespace", () => {
    const rules = buildModelRules([{ provider: "  codex  ", model: "  gpt-5  " }]);
    expect(rules).toEqual([
      { alias: "gpt-5", provider: "codex", target_model: "gpt-5" },
    ]);
  });
});
