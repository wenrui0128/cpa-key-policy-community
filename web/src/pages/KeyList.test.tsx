import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { KeyPublic } from "../types";
import { _resetLocale } from "../i18n";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
vi.mock("../api/keys", () => ({ listKeys: vi.fn(), patchKey: vi.fn(), deleteKey: vi.fn(), rotateKey: vi.fn(), resetRPM: vi.fn() }));
import KeyList from "./KeyList";
import { listKeys, patchKey } from "../api/keys";

const fixture = (id = "test", used = 40, budget = 100): KeyPublic => ({
  id, name: id, enabled: true, key_preview: "masked", rpm: 60, models: [],
  daily_limit_usd: 20, weekly_limit_usd: budget,
  usage: { daily_usd: 2, daily_limit_usd: 20, weekly_usd: used, weekly_limit_usd: budget, weekly_reset_at: "2026-10-14T10:32:42Z" },
});
let container: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  vi.resetAllMocks();
  _resetLocale("zh-CN");
  vi.mocked(listKeys).mockResolvedValue([fixture()]);
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); });

async function renderList() {
  await act(async () => {
    root.render(<MemoryRouter initialEntries={["/keys"]}>
      <Routes><Route path="/keys" element={<KeyList />} /><Route path="/keys/:id/usage" element={<div>USAGE_PAGE</div>} /></Routes>
    </MemoryRouter>);
    await tick();
  });
}
async function changeBudget(value: string, index = 0) {
  const input = container.querySelectorAll<HTMLInputElement>("input[type=number]")[index];
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  return input;
}
async function submit(index = 0) {
  await act(async () => { container.querySelectorAll("form")[index].dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); await tick(); });
}

describe("Key card weekly budget", () => {
  it("shows weekly spend, remaining amount and progress rather than daily spend", async () => {
    await renderList();
    expect(container.textContent).toContain("$40.00 / $100.00");
    expect(container.textContent).toContain("剩余 $60.00");
    expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("40");
  });
  it("only patches the weekly budget and preserves usage and daily limits", async () => {
    vi.mocked(patchKey).mockResolvedValue({ ...fixture(), weekly_limit_usd: 200, usage: { ...fixture().usage, weekly_limit_usd: 200 } });
    await renderList(); await changeBudget("200"); await submit();
    expect(patchKey).toHaveBeenCalledTimes(1);
    expect(patchKey).toHaveBeenCalledWith({ id: "test", weekly_limit_usd: 200 });
    expect(container.textContent).toContain("$40.00 / $200.00");
    expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("20");
    expect(container.textContent).toContain("周额度已保存");
    expect(listKeys).toHaveBeenCalledTimes(1);
  });
  it("does not navigate or reveal revoke while operating the editor", async () => {
    await renderList(); const input = await changeBudget("200");
    await act(async () => { input.dispatchEvent(new Event("pointerdown", { bubbles: true })); input.click(); });
    expect(container.textContent).not.toContain("USAGE_PAGE");
    expect(container.querySelector<HTMLElement>(".keycard")?.style.transform).toBe("translateX(0px)");
    expect(container.querySelector<HTMLElement>(".kc-revoke")?.style.pointerEvents).toBe("none");
  });
  it("retains another card's unsaved draft after saving one key", async () => {
    vi.mocked(listKeys).mockResolvedValue([fixture("first"), fixture("second")]);
    vi.mocked(patchKey).mockResolvedValue({ ...fixture("first"), weekly_limit_usd: 200, usage: { ...fixture().usage, weekly_limit_usd: 200 } });
    await renderList(); await changeBudget("350", 1); await changeBudget("200"); await submit();
    expect(container.querySelectorAll<HTMLInputElement>("input[type=number]")[1].value).toBe("350");
  });
  it("keeps the draft and original progress on API failure", async () => {
    vi.mocked(patchKey).mockRejectedValue({ response: { data: { error: { message: "保存被拒绝" } } } });
    await renderList(); await changeBudget("200"); await submit();
    expect(container.querySelector<HTMLInputElement>("input")?.value).toBe("200");
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("保存被拒绝");
    expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("40");
  });
  it.each(["", "-1"])("rejects invalid amount %j without an API call", async (value) => {
    await renderList(); await changeBudget(value); await submit();
    expect(patchKey).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("有效金额");
  });
  it("allows zero as unlimited, without clearing spend", async () => {
    vi.mocked(patchKey).mockResolvedValue({ ...fixture(), weekly_limit_usd: 0, usage: { ...fixture().usage, weekly_limit_usd: 0 } });
    await renderList(); await changeBudget("0"); await submit();
    expect(patchKey).toHaveBeenCalledWith({ id: "test", weekly_limit_usd: 0 });
    expect(container.textContent).toContain("$40.00 / 不限");
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
  });
  it("shows a warning for a budget below spend and clamps overspend progress", async () => {
    vi.mocked(listKeys).mockResolvedValue([fixture("test", 120)]);
    await renderList(); await changeBudget("50");
    expect(container.textContent).toContain("停止接收新请求");
    expect(container.textContent).toContain("120.0%");
    expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("100");
    expect(container.querySelector(".keycard.over")).not.toBeNull();
  });
  it("prevents duplicate saves while the API call is pending", async () => {
    let resolve: (key: KeyPublic) => void = () => {};
    vi.mocked(patchKey).mockReturnValue(new Promise((done) => { resolve = done; }));
    await renderList(); await changeBudget("200"); await submit(); await submit();
    expect(patchKey).toHaveBeenCalledTimes(1);
    expect(container.querySelector<HTMLInputElement>("input")?.disabled).toBe(true);
    await act(async () => { resolve({ ...fixture(), weekly_limit_usd: 200, usage: { ...fixture().usage, weekly_limit_usd: 200 } }); await tick(); });
  });
});
