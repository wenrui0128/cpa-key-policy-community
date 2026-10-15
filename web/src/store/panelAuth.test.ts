import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  _resetKeyCache,
  obfuscateData,
  deobfuscateData,
  readPanelAuth,
  type PanelAuth,
} from "./panelAuth";

const STORAGE_KEY = "cli-proxy-auth";

// Build a panel-style persisted auth blob: zustand persist envelope
// {state, version} serialized to JSON, then obfuscated with the shared algo.
function storePanelAuth(auth: PanelAuth): void {
  const envelope = JSON.stringify({
    state: {
      apiBase: auth.apiBase,
      managementKey: auth.managementKey,
      rememberPassword: true,
    },
    version: 0,
  });
  localStorage.setItem(STORAGE_KEY, obfuscateData(envelope));
}

describe("panelAuth obfuscation", () => {
  it("round-trips through obfuscate/deobfuscate", () => {
    const original = JSON.stringify({ state: { apiBase: "http://localhost:1", managementKey: "k" } });
    expect(deobfuscateData(obfuscateData(original))).toBe(original);
  });
});

describe("readPanelAuth", () => {
  const realSelf = window.self;
  const realTop = window.top;

  beforeEach(() => {
    localStorage.clear();
    _resetKeyCache();
  });

  afterEach(() => {
    localStorage.clear();
    _resetKeyCache();
    // Restore embedded state.
    Object.defineProperty(window, "self", { value: realSelf, configurable: true });
    Object.defineProperty(window, "top", { value: realTop, configurable: true });
  });

  function setEmbedded(embedded: boolean) {
    // window.self !== window.top → embedded
    Object.defineProperty(window, "self", { value: window, configurable: true });
    Object.defineProperty(window, "top", {
      value: embedded ? ({} as Window) : window,
      configurable: true,
    });
  }

  it("returns null when not embedded (direct page open)", () => {
    setEmbedded(false);
    storePanelAuth({ apiBase: window.location.origin, managementKey: "secret-xyz" });
    expect(readPanelAuth()).toBeNull();
  });

  it("reads apiBase + managementKey when embedded and remember-password was set", () => {
    setEmbedded(true);
    storePanelAuth({ apiBase: window.location.origin, managementKey: "secret-xyz" });
    expect(readPanelAuth()).toEqual({
      apiBase: window.location.origin,
      managementKey: "secret-xyz",
    });
  });

  it("returns null when managementKey is empty (remember password unchecked)", () => {
    setEmbedded(true);
    const envelope = JSON.stringify({
      state: { apiBase: "http://localhost:1", managementKey: "", rememberPassword: false },
      version: 0,
    });
    localStorage.setItem(STORAGE_KEY, obfuscateData(envelope));
    expect(readPanelAuth()).toBeNull();
  });

  it("returns null when nothing is stored", () => {
    setEmbedded(true);
    expect(readPanelAuth()).toBeNull();
  });

  it("returns null when the stored value is garbage", () => {
    setEmbedded(true);
    localStorage.setItem(STORAGE_KEY, "not-valid-json-or-obfuscated");
    expect(readPanelAuth()).toBeNull();
  });
  it("does not reuse the management key for an external API origin", () => {
    setEmbedded(true);
    storePanelAuth({ apiBase: "https://other.example.invalid", managementKey: "test-only" });
    expect(readPanelAuth()).toBeNull();
  });

  it("rejects embedded credentials, query strings and fragments in the saved URL", () => {
    setEmbedded(true);
    for (const apiBase of [
      window.location.origin.replace("://", "://user:password@"),
      window.location.origin + "?redirect=other",
      window.location.origin + "#other",
    ]) {
      storePanelAuth({ apiBase, managementKey: "test-only" });
      expect(readPanelAuth()).toBeNull();
    }
  });

  it("does not reuse saved authentication inside an unreadable cross-origin parent", () => {
    setEmbedded(true);
    const parent = window.parent;
    Object.defineProperty(window, "parent", { configurable: true, get: () => { throw new Error("cross origin"); } });
    try {
      storePanelAuth({ apiBase: window.location.origin, managementKey: "test-only" });
      expect(readPanelAuth()).toBeNull();
    } finally {
      Object.defineProperty(window, "parent", { configurable: true, value: parent });
    }
  });

});
