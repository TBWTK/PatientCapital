"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type Asset,
  type Portfolio,
  type Profile,
  type Recommendation,
  request,
} from "./api";

type View = "overview" | "contribution" | "ledger" | "settings";
type Notice = { kind: "error" | "success"; text: string } | null;

const nav: { id: View; label: string; mark: string }[] = [
  { id: "overview", label: "Обзор", mark: "⌁" },
  { id: "contribution", label: "Пополнение", mark: "+" },
  { id: "ledger", label: "Операции", mark: "↕" },
  { id: "settings", label: "Профиль", mark: "○" },
];

const nowLocal = () => {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
};

const errorText = (error: unknown) => {
  if (error instanceof ApiError) {
    const localized: Record<string, string> = {
      STALE_PRICE: "Цена одного из активов устарела. Обновите её в профиле.",
      MISSING_PRICE: "Для одного из активов не задана цена.",
      PROFILE_NOT_CONFIGURED: "Сначала заполните профиль инвестора.",
      ASSET_NOT_FOUND: "Актив не найден.",
      CURRENCY_MISMATCH: "Валюты профиля, актива и операции должны совпадать.",
      VERSION_CONFLICT: "Данные уже изменились. Обновите страницу и повторите.",
      INSUFFICIENT_POSITION: "Для продажи недостаточно бумаг в журнале.",
      IDEMPOTENCY_CONFLICT: "Эта операция уже была записана с другими данными.",
      BUDGET_BELOW_ANY_LOT: "Доступной суммы недостаточно для покупки целого лота.",
    };
    return `${localized[error.code] ?? error.message} · ${error.code}`;
  }
  return "Не удалось связаться с локальным API";
};

const money = (value: string | number, currency = "RUB") =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));

const percent = (value: string | number) =>
  new Intl.NumberFormat("ru-RU", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(Number(value));

const shortDateTime = (value: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));

function EmptyState({ onStart }: { onStart: () => void }) {
  return (
    <section className="empty-state" aria-labelledby="empty-title">
      <div className="empty-orbit" aria-hidden="true">
        <span>01</span>
        <i />
      </div>
      <div>
        <p className="eyebrow">Начало маршрута</p>
        <h2 id="empty-title">Соберите основу портфеля</h2>
        <p>
          Укажите брокера и комиссии, добавьте активы с целевыми долями и
          зафиксируйте актуальные цены. После этого план пополнения станет
          воспроизводимым и проверяемым.
        </p>
        <button className="button primary" onClick={onStart}>
          Настроить профиль <span aria-hidden="true">→</span>
        </button>
      </div>
    </section>
  );
}

function Overview({
  portfolio,
  profile,
  onContribution,
  onSettings,
}: {
  portfolio: Portfolio | null;
  profile: Profile | null;
  onContribution: () => void;
  onSettings: () => void;
}) {
  if (!profile || !portfolio) return <EmptyState onStart={onSettings} />;

  const pnl = Number(portfolio.total_unrealized_pnl);
  return (
    <div className="overview-stack">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow light">Капитал сегодня</p>
          <h1>{money(portfolio.total_market_value, portfolio.currency)}</h1>
          <p className={pnl >= 0 ? "delta positive" : "delta negative"}>
            {pnl >= 0 ? "+" : ""}
            {money(pnl, portfolio.currency)} нереализованного результата
          </p>
        </div>
        <div className="hero-action">
          <span>Следующее действие</span>
          <button className="button cream" onClick={onContribution}>
            Рассчитать пополнение <b aria-hidden="true">↗</b>
          </button>
        </div>
        <div className="hero-line" aria-hidden="true" />
      </section>

      <section className="metric-grid" aria-label="Сводные показатели">
        <article>
          <span>Вложено</span>
          <strong>{money(portfolio.total_cost_basis, portfolio.currency)}</strong>
          <small>по журналу операций</small>
        </article>
        <article>
          <span>Горизонт</span>
          <strong>{profile.investment_horizon_years} лет</strong>
          <small>{profile.risk_level} · версия {profile.version}</small>
        </article>
        <article>
          <span>Резерв</span>
          <strong>{money(profile.cash_buffer, profile.base_currency)}</strong>
          <small>не участвует в покупке</small>
        </article>
      </section>

      <section className="allocation-card">
        <header className="section-heading">
          <div>
            <p className="eyebrow">Структура</p>
            <h2>Портфель и отклонения</h2>
          </div>
          <span className="as-of">По последним сохранённым ценам</span>
        </header>
        {portfolio.assets.length === 0 ? (
          <div className="soft-empty">
            Сделок пока нет. Добавьте первую покупку в разделе «Операции».
          </div>
        ) : (
          <div className="asset-table" role="table" aria-label="Активы портфеля">
            <div className="asset-row asset-head" role="row">
              <span>Актив</span><span>Стоимость</span><span>Доля</span><span>Отклонение</span>
            </div>
            {portfolio.assets.map((asset) => (
              <div className="asset-row" role="row" key={asset.asset_id}>
                <span className="asset-name">
                  <i>{asset.asset_id.slice(0, 2).toUpperCase()}</i>
                  <b>{asset.name}</b>
                  <small>{asset.quantity} шт. · цена на {shortDateTime(asset.price_as_of)}</small>
                </span>
                <strong>{money(asset.market_value, asset.currency)}</strong>
                <span className="weight-cell">
                  <b>{percent(asset.actual_weight)}</b>
                  <i><em style={{ width: `${Math.min(Number(asset.actual_weight) * 100, 100)}%` }} /></i>
                </span>
                <span className={Number(asset.drift) > 0 ? "drift over" : "drift under"}>
                  {Number(asset.drift) > 0 ? "+" : ""}{percent(asset.drift)}
                  <small>цель {percent(asset.target_weight)}</small>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Contribution({
  currency,
  result,
  onResult,
}: {
  currency: string;
  result: Recommendation | null;
  onResult: (value: Recommendation) => void;
}) {
  const [amount, setAmount] = useState("100000");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      onResult(await request<Recommendation>("/v1/recommendations", {
        method: "POST",
        body: JSON.stringify({ contribution: amount }),
      }));
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="workspace-stack">
      <section className="page-intro">
        <p className="eyebrow">Новый взнос</p>
        <h1>Куда направить пополнение</h1>
        <p>Расчёт учитывает текущие позиции, целевые доли, лоты и комиссию брокера.</p>
      </section>
      <form className="contribution-form" onSubmit={submit}>
        <label>
          Сумма пополнения
          <span className="money-input">
            <input
              aria-label="Сумма пополнения"
              type="number"
              min="0"
              step="0.01"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
            <b>{currency}</b>
          </span>
        </label>
        <button className="button primary large" disabled={busy}>
          {busy ? "Считаем…" : "Собрать план"}
        </button>
      </form>
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
      {result && (
        <section className="result-card" aria-live="polite">
          <header className="section-heading">
            <div><p className="eyebrow">План готов</p><h2>{money(result.spent, result.currency)} к покупке</h2></div>
            <span className="status-pill">Предложение · не исполнено</span>
          </header>
          <div className="result-summary">
            <span>Активы <b>{money(result.gross, result.currency)}</b></span>
            <span>Комиссии <b>{money(result.fees, result.currency)}</b></span>
            <span>Остаток <b>{money(result.leftover, result.currency)}</b></span>
          </div>
          {result.lines.length === 0 ? (
            <div className="soft-empty">Лоты не помещаются в доступную сумму. {result.reason}</div>
          ) : (
            <div className="plan-lines">
              {result.lines.map((line, index) => (
                <article key={line.asset_id}>
                  <span className="line-number">{String(index + 1).padStart(2, "0")}</span>
                  <div><h3>{line.asset_id}</h3><p>{line.lots} лот. · {line.quantity} шт. × {money(line.unit_price, result.currency)}</p></div>
                  <div className="drift-change"><span>{percent(line.pre_drift)}</span><i>→</i><b>{percent(line.post_drift)}</b><small>отклонение</small></div>
                  <strong>{money(line.total, result.currency)}</strong>
                </article>
              ))}
            </div>
          )}
          <footer className="audit-line">
            <span>Алгоритм {result.algorithm_version}</span>
            <span>Run {result.id.slice(0, 8)}</span>
            <span>Hash {result.input_hash.slice(0, 10)}</span>
          </footer>
        </section>
      )}
    </div>
  );
}

function Ledger({ assets, onSaved }: { assets: Asset[]; onSaved: () => Promise<void> }) {
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    asset_id: assets[0]?.asset_id ?? "",
    side: "BUY",
    quantity: "1",
    unit_price: "",
    fee: "0",
    currency: assets[0]?.currency ?? "RUB",
    occurred_at: nowLocal(),
    note: "",
  });

  const selectedAssetId = form.asset_id || assets[0]?.asset_id || "";
  const selectedCurrency = form.asset_id ? form.currency : assets[0]?.currency ?? form.currency;

  const updateAsset = (assetId: string) => {
    const asset = assets.find((item) => item.asset_id === assetId);
    setForm((current) => ({ ...current, asset_id: assetId, currency: asset?.currency ?? current.currency }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      await request("/v1/transactions", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          asset_id: selectedAssetId,
          currency: selectedCurrency,
          quantity: Number(form.quantity),
          occurred_at: new Date(form.occurred_at).toISOString(),
          idempotency_key: crypto.randomUUID(),
          note: form.note || null,
        }),
      });
      await onSaved();
      setNotice({ kind: "success", text: "Операция записана в неизменяемый журнал" });
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="workspace-stack narrow">
      <section className="page-intro">
        <p className="eyebrow">Ручной ввод</p>
        <h1>Записать операцию</h1>
        <p>PatientCapital не подключён к брокеру и не исполняет заявки.</p>
      </section>
      <form className="form-card two-column" onSubmit={submit}>
        <label>Актив<select required value={selectedAssetId} onChange={(e) => updateAsset(e.target.value)}><option value="">Выберите актив</option>{assets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.asset_id} · {asset.name}</option>)}</select></label>
        <label>Сторона<select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}><option value="BUY">Покупка</option><option value="SELL">Продажа</option></select></label>
        <label>Количество<input required type="number" min="1" step="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label>
        <label>Цена за единицу<input required type="number" min="0.00000001" step="any" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} /></label>
        <label>Комиссия<input required type="number" min="0" step="0.01" value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} /></label>
        <label>Валюта<input required pattern="[A-Z]{3}" value={selectedCurrency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></label>
        <label>Дата и время<input required type="datetime-local" value={form.occurred_at} onChange={(e) => setForm({ ...form, occurred_at: e.target.value })} /></label>
        <label>Заметка<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Необязательно" /></label>
        <div className="form-actions"><button className="button primary" disabled={busy || assets.length === 0}>{busy ? "Сохраняем…" : "Записать операцию"}</button></div>
      </form>
      {assets.length === 0 && <div className="notice error">Сначала добавьте хотя бы один актив в профиле.</div>}
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
    </div>
  );
}

function Settings({
  profile,
  assets,
  onRefresh,
}: {
  profile: Profile | null;
  assets: Asset[];
  onRefresh: () => Promise<void>;
}) {
  const [notice, setNotice] = useState<Notice>(null);
  const [profileForm, setProfileForm] = useState({
    base_currency: profile?.base_currency ?? "RUB",
    investment_horizon_years: String(profile?.investment_horizon_years ?? 15),
    risk_level: profile?.risk_level ?? "balanced",
    cash_buffer: profile?.cash_buffer ?? "0",
    broker_name: profile?.broker_name ?? "",
    fee_rate: profile?.fee_rate ?? "0.0005",
    minimum_fee: profile?.minimum_fee ?? "0",
  });
  const [assetForm, setAssetForm] = useState({ asset_id: "", name: "", currency: profile?.base_currency ?? "RUB", lot_size: "1", target_weight: "", price: "", source: "manual" });

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setNotice(null);
    try {
      await request("/v1/profile", { method: "PUT", body: JSON.stringify({ ...profileForm, expected_version: profile?.version ?? null, investment_horizon_years: Number(profileForm.investment_horizon_years) }) });
      await onRefresh();
      setNotice({ kind: "success", text: "Новая версия профиля сохранена" });
    } catch (error) { setNotice({ kind: "error", text: errorText(error) }); }
  };

  const saveAsset = async (event: FormEvent) => {
    event.preventDefault();
    setNotice(null);
    const assetId = assetForm.asset_id.trim().toUpperCase();
    const existing = assets.find((asset) => asset.asset_id === assetId);
    try {
      await request(`/v1/assets/${encodeURIComponent(assetId)}`, { method: "PUT", body: JSON.stringify({ expected_version: existing?.version ?? null, name: assetForm.name, currency: assetForm.currency, lot_size: Number(assetForm.lot_size), target_weight: assetForm.target_weight, is_active: true }) });
      if (assetForm.price) await request(`/v1/assets/${encodeURIComponent(assetId)}/prices`, { method: "POST", body: JSON.stringify({ price: assetForm.price, currency: assetForm.currency, as_of: new Date().toISOString(), max_age_seconds: 604800, source: assetForm.source }) });
      await onRefresh();
      setAssetForm({ ...assetForm, asset_id: "", name: "", target_weight: "", price: "" });
      setNotice({ kind: "success", text: existing ? "Новая версия актива сохранена" : "Актив и цена сохранены" });
    } catch (error) { setNotice({ kind: "error", text: errorText(error) }); }
  };

  return (
    <div className="workspace-stack">
      <section className="page-intro"><p className="eyebrow">Параметры</p><h1>Профиль и модель портфеля</h1><p>Все изменения версионируются. Старые рекомендации сохраняют исходный контекст.</p></section>
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
      <div className="settings-grid">
        <form className="form-card two-column" onSubmit={saveProfile}>
          <div className="form-title"><span>01</span><div><h2>Инвестор</h2><p>Брокер, горизонт и издержки</p></div></div>
          <label>Базовая валюта<input required pattern="[A-Z]{3}" value={profileForm.base_currency} onChange={(e) => setProfileForm({ ...profileForm, base_currency: e.target.value.toUpperCase() })} /></label>
          <label>Горизонт, лет<input required type="number" min="1" max="100" value={profileForm.investment_horizon_years} onChange={(e) => setProfileForm({ ...profileForm, investment_horizon_years: e.target.value })} /></label>
          <label>Риск-профиль<select value={profileForm.risk_level} onChange={(e) => setProfileForm({ ...profileForm, risk_level: e.target.value })}><option value="conservative">Консервативный</option><option value="balanced">Сбалансированный</option><option value="growth">Рост</option></select></label>
          <label>Денежный резерв<input required type="number" min="0" step="0.01" value={profileForm.cash_buffer} onChange={(e) => setProfileForm({ ...profileForm, cash_buffer: e.target.value })} /></label>
          <label>Брокер<input required value={profileForm.broker_name} onChange={(e) => setProfileForm({ ...profileForm, broker_name: e.target.value })} /></label>
          <label>Комиссия, доля<input required type="number" min="0" max="1" step="0.00000001" value={profileForm.fee_rate} onChange={(e) => setProfileForm({ ...profileForm, fee_rate: e.target.value })} /></label>
          <label>Минимальная комиссия<input required type="number" min="0" step="0.01" value={profileForm.minimum_fee} onChange={(e) => setProfileForm({ ...profileForm, minimum_fee: e.target.value })} /></label>
          <div className="form-actions"><button className="button primary">Сохранить профиль</button>{profile && <small>Текущая версия: {profile.version}</small>}</div>
        </form>

        <form className="form-card two-column" onSubmit={saveAsset}>
          <div className="form-title"><span>02</span><div><h2>Актив и цена</h2><p>Целевая доля от 0 до 1</p></div></div>
          <label>Код актива<input required maxLength={64} value={assetForm.asset_id} onChange={(e) => setAssetForm({ ...assetForm, asset_id: e.target.value.toUpperCase() })} placeholder="Например, BOND" /></label>
          <label>Название<input required value={assetForm.name} onChange={(e) => setAssetForm({ ...assetForm, name: e.target.value })} /></label>
          <label>Валюта<input required pattern="[A-Z]{3}" value={assetForm.currency} onChange={(e) => setAssetForm({ ...assetForm, currency: e.target.value.toUpperCase() })} /></label>
          <label>Размер лота<input required type="number" min="1" step="1" value={assetForm.lot_size} onChange={(e) => setAssetForm({ ...assetForm, lot_size: e.target.value })} /></label>
          <label>Целевая доля<input required type="number" min="0" max="1" step="0.00000001" value={assetForm.target_weight} onChange={(e) => setAssetForm({ ...assetForm, target_weight: e.target.value })} placeholder="0.40" /></label>
          <label>Текущая цена<input type="number" min="0.00000001" step="any" value={assetForm.price} onChange={(e) => setAssetForm({ ...assetForm, price: e.target.value })} /></label>
          <label>Источник цены<input required value={assetForm.source} onChange={(e) => setAssetForm({ ...assetForm, source: e.target.value })} /></label>
          <div className="form-actions"><button className="button primary">Сохранить актив</button></div>
        </form>
      </div>
      {assets.length > 0 && <section className="configured-assets"><header className="section-heading"><div><p className="eyebrow">Модель</p><h2>Настроенные активы</h2></div><span>Сумма целей должна быть 100%</span></header><div>{assets.map((asset) => <article key={asset.asset_id}><i>{asset.asset_id.slice(0, 2)}</i><span><b>{asset.asset_id} · {asset.name}</b><small>лот {asset.lot_size} · версия {asset.version}</small></span><strong>{percent(asset.target_weight)}</strong></article>)}</div></section>}
    </div>
  );
}

export function PatientCapitalApp() {
  const [view, setView] = useState<View>("overview");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const refresh = async () => {
    setConnectionError(null);
    const [profileResult, assetsResult, portfolioResult] = await Promise.allSettled([
      request<Profile>("/v1/profile"),
      request<{ assets: Asset[] }>("/v1/assets"),
      request<Portfolio>("/v1/portfolio"),
    ]);
    if (profileResult.status === "fulfilled") setProfile(profileResult.value);
    else if (!(profileResult.reason instanceof ApiError && profileResult.reason.status === 404)) setConnectionError(errorText(profileResult.reason));
    if (assetsResult.status === "fulfilled") setAssets(assetsResult.value.assets);
    else setConnectionError(errorText(assetsResult.reason));
    if (portfolioResult.status === "fulfilled") setPortfolio(portfolioResult.value);
    else if (!(portfolioResult.reason instanceof ApiError && [404, 422].includes(portfolioResult.reason.status))) setConnectionError(errorText(portfolioResult.reason));
    setLoading(false);
  };

  useEffect(() => {
    const timeout = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timeout);
  }, []);

  const title = useMemo(() => nav.find((item) => item.id === view)?.label ?? "Обзор", [view]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView("overview")} aria-label="PatientCapital, на главную"><span>PC</span><b>Patient<br />Capital</b></button>
        <nav aria-label="Основная навигация">{nav.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)} aria-current={view === item.id ? "page" : undefined}><i>{item.mark}</i><span>{item.label}</span></button>)}</nav>
        <div className="sidebar-foot"><span className={connectionError ? "health bad" : "health"} /><div><b>{connectionError ? "API недоступен" : "Локальный контур"}</b><small>{profile?.broker_name ?? "Данные остаются у вас"}</small></div></div>
      </aside>
      <main>
        <header className="topbar"><div><span className="mobile-brand">PC</span><p>PatientCapital / <b>{title}</b></p></div><div className="top-actions"><span className="privacy">● private</span><button onClick={() => setView("settings")} aria-label="Открыть профиль">{profile?.broker_name.slice(0, 2).toUpperCase() || "PC"}</button></div></header>
        <nav className="mobile-nav" aria-label="Мобильная навигация">{nav.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><i>{item.mark}</i><span>{item.label}</span></button>)}</nav>
        <div className="content">
          {connectionError && <div className="connection-banner"><b>Нет связи с API.</b> {connectionError}<button onClick={() => void refresh()}>Повторить</button></div>}
          {loading ? <div className="loading-state" role="status"><span />Загружаем ваш капитал…</div> : (
            <>
              {view === "overview" && <Overview portfolio={portfolio} profile={profile} onContribution={() => setView("contribution")} onSettings={() => setView("settings")} />}
              {view === "contribution" && <Contribution currency={profile?.base_currency ?? "RUB"} result={recommendation} onResult={setRecommendation} />}
              {view === "ledger" && <Ledger assets={assets} onSaved={refresh} />}
              {view === "settings" && <Settings profile={profile} assets={assets} onRefresh={refresh} />}
            </>
          )}
        </div>
      </main>
      <footer className="disclaimer">Информационный инструмент · не является индивидуальной инвестиционной рекомендацией · заявки не исполняются</footer>
    </div>
  );
}
