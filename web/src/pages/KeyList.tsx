import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listKeys, patchKey, deleteKey, rotateKey, resetRPM } from "../api/keys";
import type { KeyPublic } from "../types";
import PlainKeyModal from "../components/PlainKeyModal";
import { useT } from "../i18n";

// Renders a key's daily/weekly dollar usage against its limits. Empty limits
// (0) show as "不限"; usage at/over a limit is flagged in the danger color so an
// admin can spot a throttled key at a glance.
//
// When the backend reports cache stats (cache-read tokens + non-cache input
// tokens), a third line shows cache spend and hit-rate per window. Hit-rate =
// cacheRead / (cacheRead + input); cache-creation tokens are excluded by the
// backend so this stays a clean "of the input we read, how much was cached".
export default function KeyList() {
  const t = useT();
  const [keys, setKeys] = useState<KeyPublic[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [plain, setPlain] = useState<string | null>(null);
  const [plainTitle, setPlainTitle] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setKeys(await listKeys());
    } catch (e) {
      const err = e as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setError(err.response?.data?.error?.message ?? err.message ?? t("keys.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const onRotate = async (id: string) => {
    if (!confirm(t("keys.rotateConfirm", { id }))) return;
    try {
      const r = await rotateKey(id);
      setPlain(r.plain_key);
      setPlainTitle(t("keys.rotated"));
      void load();
    } catch (e) {
      alert((e as Error).message ?? t("keys.rotateFailed"));
    }
  };

  const onReset = async (id: string) => {
    try {
      await resetRPM(id);
      void load();
    } catch (e) {
      alert((e as Error).message ?? t("keys.resetFailed"));
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm(t("keys.deleteConfirm", { id }))) return;
    try {
      await deleteKey(id);
      void load();
    } catch (e) {
      alert((e as Error).message ?? t("keys.deleteFailed"));
    }
  };

  return (
    <div>
      {/* Desktop: page toolbar (h1 + refresh). Nav/new-key live in the topnav. */}
      <div className="fp-head mobile-hidden" style={{ margin: "0 0 16px" }}>
        <h1>{t("header.keyList")}</h1>
        <div className="fp-actions">
          <button className="btn sm" onClick={load}>{t("keys.refresh")}</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <div className="muted">{t("keys.loading")}</div>
      ) : keys.length === 0 ? (
        <div className="card muted">{t("keys.empty")}</div>
      ) : (
        /* Unified card grid: mobile stack + desktop grid (CSS switches). */
        <div className="card-stack">
          {keys.map((k) => (
            <KeyCard
              key={k.id}
              k={k}
              onDelete={onDelete}
              onRotate={onRotate}
              onReset={onReset}
              onBudgetSaved={(updated) => setKeys((current) => current.map((key) => key.id === updated.id ? updated : key))}
            />
          ))}
        </div>
      )}

      {/* Mobile: FAB + bottom tab bar */}
      <Link to="/keys/new" className="fab" aria-label={t("keys.newKey")}>+</Link>
      <MobileTabBar active="keys" />

      {plain && (
        <PlainKeyModal
          plainKey={plain}
          title={plainTitle}
          onClose={() => setPlain(null)}
        />
      )}
    </div>
  );
}

// Mobile key card with swipe-to-revoke. Renders the weekly usage as an
// ink-drop progress bar and the first few model aliases as chips. Tapping
// the card navigates to the detail/usage page; swiping left reveals a
// destructive Revoke action that calls onDelete.
function KeyCard({
  k,
  onDelete,
  onRotate,
  onReset,
  onBudgetSaved,
}: {
  k: KeyPublic;
  onDelete: (id: string) => void;
  onRotate?: (id: string) => void;
  onReset?: (id: string) => void;
  onBudgetSaved: (key: KeyPublic) => void;
}) {
  const t = useT();
  const nav = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  const [dx, setDx] = useState(0);          // current swipe translate
  const [revoking, setRevoking] = useState(false);
  const budgetId = useId();
  const [budgetDraft, setBudgetDraft] = useState(String(k.weekly_limit_usd));
  const [budgetError, setBudgetError] = useState("");
  const [budgetSaved, setBudgetSaved] = useState(false);
  const [budgetSaving, setBudgetSaving] = useState(false);
  const savingRef = useRef(false);
  const startX = useRef(0); const startY = useRef(0); const dragging = useRef(false); const horizontal = useRef(false); const moved = useRef(false);

  const limit = k.usage.weekly_limit_usd > 0 ? k.usage.weekly_limit_usd : 0;
  const usagePct = limit > 0 ? (k.usage.weekly_usd / limit) * 100 : 0;
  const pct = Math.max(0, Math.min(100, usagePct));
  const over = limit > 0 && k.usage.weekly_usd >= limit;
  const nearLimit = limit > 0 && usagePct >= 80 && !over;
  const draftValue = Number(budgetDraft);
  const validDraft = budgetDraft.trim() !== "" && Number.isFinite(draftValue) && draftValue >= 0;
  const unchanged = validDraft && draftValue === k.weekly_limit_usd;
  const belowSpend = validDraft && draftValue > 0 && draftValue < k.usage.weekly_usd;

  useEffect(() => {
    setBudgetDraft(String(k.weekly_limit_usd));
  }, [k.weekly_limit_usd]);

  const saveBudget = async (event: React.FormEvent) => {
    event.preventDefault();
    if (savingRef.current) return;
    if (!validDraft) {
      setBudgetError(t("keys.budget.invalid"));
      return;
    }
    if (unchanged) return;
    savingRef.current = true;
    setBudgetSaving(true);
    setBudgetError("");
    setBudgetSaved(false);
    try {
      const updated = await patchKey({ id: k.id, weekly_limit_usd: draftValue });
      onBudgetSaved(updated);
      setBudgetDraft(String(updated.weekly_limit_usd));
      setBudgetSaved(true);
    } catch (e) {
      const err = e as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setBudgetError(err.response?.data?.error?.message ?? err.message ?? t("keys.budget.saveFailed"));
    } finally {
      savingRef.current = false;
      setBudgetSaving(false);
    }
  };
  const models = k.models ?? [];
  // Deduplicate by alias name for display: a multi-target alias resolves
  // to multiple ModelRules sharing one alias, but the key list should show
  // each alias once (not 'test' twice for a 2-target alias).
  const uniqueAliases: string[] = [];
  const seenAlias = new Set<string>();
  for (const m of models) {
    const key = (m.alias ?? "").toLowerCase();
    if (key && !seenAlias.has(key)) {
      seenAlias.add(key);
      uniqueAliases.push(m.alias);
    }
  }
  const shownChips = uniqueAliases.slice(0, 2);
  const moreCount = Math.max(0, uniqueAliases.length - 2);

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("input, button, a, form, label")) return;
    dragging.current = true; horizontal.current = false; moved.current = false;
    startX.current = e.clientX; startY.current = e.clientY;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    const ddx = e.clientX - startX.current;
    const ddy = e.clientY - startY.current;
    if (!horizontal.current && Math.abs(ddx) > 8 && Math.abs(ddx) > Math.abs(ddy)) {
      horizontal.current = true; // lock to horizontal swipe
    }
    if (horizontal.current) {
      e.preventDefault();
      moved.current = true;
      setDx(Math.max(-96, Math.min(0, ddx))); // only allow left swipe
    }
  };
  const onPointerUp = () => {
    if (!dragging.current) return;
    dragging.current = false;
    if (horizontal.current) {
      if (dx <= -64) { setRevoking(true); setDx(-88); }
      else { setDx(0); }
    }
  };

  // Click handles tap-to-open. Skipped when the pointer turned into a swipe
  // (moved.current) or the revoke panel is revealed, so a swipe doesn't also
  // navigate. Using onClick (instead of navigating from pointerup) is more
  // reliable on mobile browsers where pointerup can be swallowed by touch
  // handling.
  const onClick = () => {
    if (moved.current || revoking) return;
    nav(`/keys/${encodeURIComponent(k.id)}/usage`);
  };

  const doRevoke = () => { setDx(0); setRevoking(false); onDelete(k.id); };

  return (
    <div
      ref={ref}
      className={"keycard" + (k.enabled ? "" : " disabled") + (over ? " over" : "") + (nearLimit ? " near-limit" : "")}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onClick={onClick}
      style={{ transform: `translateX(${dx}px)`, touchAction: "pan-y" }}
    >
      <div className="kc-revoke" style={{ opacity: revoking || dx < -8 ? 1 : 0, transition: "opacity 150ms", pointerEvents: revoking ? "auto" : "none" }}
           onClick={(e) => { e.stopPropagation(); if (revoking) doRevoke(); }}>
        <span className="revoke-icon">⊘</span>
        <span>{t("keys.mobile.revoke")}</span>
      </div>
      <div className="kc-head">
        <span className="kc-dot" />
        <span className="kc-name">{k.name || k.id}</span>
        <span className="kc-chevron">›</span>
      </div>
      <div className="kc-preview">{k.key_preview}</div>
      <div className="kc-usage-heading">
        <span>{t("keys.budget.weeklyUsage")}</span>
        <strong>{limit > 0 ? `${usagePct.toFixed(1)}%` : t("keys.mobile.noLimit")}</strong>
      </div>
      <div
        className="kc-bar"
        role={limit > 0 ? "progressbar" : undefined}
        aria-label={limit > 0 ? t("keys.budget.progressLabel", { name: k.name || k.id }) : undefined}
        aria-valuemin={limit > 0 ? 0 : undefined}
        aria-valuemax={limit > 0 ? 100 : undefined}
        aria-valuenow={limit > 0 ? pct : undefined}
        aria-valuetext={limit > 0 ? t("keys.budget.progressText", { used: k.usage.weekly_usd.toFixed(2), limit: limit.toFixed(2), percent: usagePct.toFixed(1) }) : undefined}
        aria-hidden={limit === 0 ? true : undefined}
      ><span style={{ transform: `scaleX(${pct / 100})` }} /></div>
      <div className="kc-meta">
        <span>${k.usage.weekly_usd.toFixed(2)} / {limit > 0 ? `$${limit.toFixed(2)}` : t("keys.mobile.noLimit")}</span>
        <span>{limit > 0 ? t("keys.budget.remaining", { amount: Math.max(0, limit - k.usage.weekly_usd).toFixed(2) }) : `${uniqueAliases.length} ${t("keys.mobile.modelsSuffix")}`}</span>
      </div>
      <form className="kc-budget" onSubmit={saveBudget} noValidate onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()}>
        <label htmlFor={budgetId}>{t("keys.budget.label")}</label>
        <div className="kc-budget-row">
          <input
            id={budgetId}
            className="input"
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={budgetDraft}
            disabled={budgetSaving}
            aria-invalid={!!budgetError}
            aria-describedby={`${budgetId}-hint${budgetError ? ` ${budgetId}-error` : ""}`}
            onChange={(e) => { setBudgetDraft(e.target.value); setBudgetError(""); setBudgetSaved(false); }}
            onBlur={() => { if (!validDraft) setBudgetError(t("keys.budget.invalid")); }}
          />
          <button className="btn primary" type="submit" disabled={budgetSaving || unchanged}>
            {budgetSaving ? t("keys.budget.saving") : t("keys.budget.save")}
          </button>
        </div>
        <div id={`${budgetId}-hint`} className={"kc-budget-hint" + (belowSpend ? " warning" : "")}>
          {belowSpend ? t("keys.budget.belowSpend") : t("keys.budget.hint")}
        </div>
        {budgetError && <div id={`${budgetId}-error`} className="kc-budget-error" role="alert">{budgetError}</div>}
        {budgetSaved && <div className="kc-budget-saved" role="status">{t("keys.budget.saved")}</div>}
      </form>
      {shownChips.length > 0 && (
        <div className="kc-chips">
          {shownChips.map((a) => <span key={a} className="chip">{a}</span>)}
          {moreCount > 0 && <span className="chip more">+{moreCount}</span>}
        </div>
      )}

      {/* Desktop: hover/focus action row. Not an overlay — sits at the card
       * footer and expands on hover/focus-within so card info stays visible.
       * Hidden on mobile (CSS .kc-actions display:none under 641px). The
       * swipe-to-revoke layer above handles mobile delete. */}
      <div className="kc-actions">
        <Link to={`/keys/${encodeURIComponent(k.id)}/usage`}>
          <button className="btn sm" onClick={(e) => e.stopPropagation()}>{t("keys.detail")}</button>
        </Link>
        <Link to={`/keys/${encodeURIComponent(k.id)}/edit`}>
          <button className="btn sm" onClick={(e) => e.stopPropagation()}>{t("keys.edit")}</button>
        </Link>
        {onReset && <button className="btn sm" onClick={(e) => { e.stopPropagation(); onReset(k.id); }}>{t("keys.resetRpm")}</button>}
        {onRotate && <button className="btn sm" onClick={(e) => { e.stopPropagation(); onRotate(k.id); }}>{t("keys.rotate")}</button>}
        <button className="btn sm danger" onClick={(e) => { e.stopPropagation(); onDelete(k.id); }}>{t("keys.delete")}</button>
      </div>
    </div>
  );
}

// Mobile bottom tab bar. Active tab is highlighted with a 2px primary
// underline. Shown only on narrow screens via .tabbar CSS. The "usage" tab
// is hidden on the key list / new / edit screens (usage is per-key); it only
// appears once the user has opened a specific key's usage page.
// Compact top bar for mobile create/edit screens (desktop keeps the h2).
export function MobileFormHeader({ title, backTo }: { title: string; backTo: string }) {
  const t = useT();
  return (
    <div className="mobile-form-header mobile-only">
      <Link to={backTo} className="mfb-back">
        {t("keyUsage.back")}
      </Link>
      <h2 className="mfb-title">{title}</h2>
    </div>
  );
}

export function MobileTabBar({
  active,
  showUsage = false,
  usagePath = "/keys",
}: {
  active: "keys" | "usage" | "new";
  showUsage?: boolean;
  usagePath?: string;
}) {
  const t = useT();
  const nav = useNavigate();
  const tab = (id: "keys" | "usage" | "new", label: string, icon: string, target: string) => (
    <button
      className={"tab" + (active === id ? " active" : "")}
      onClick={() => nav(target)}
    >
      <span className="tab-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
  return (
    <nav className={"tabbar" + (showUsage ? "" : " tabbar--no-usage")}>
      {tab("keys", t("keys.mobile.tabKeys"), "#", "/keys")}
      {showUsage && tab("usage", t("keys.mobile.tabUsage"), "#", usagePath)}
      {tab("new", t("keys.mobile.tabNew"), "+", "/keys/new")}
    </nav>
  );
}
