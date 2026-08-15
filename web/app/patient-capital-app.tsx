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
      UNSUPPORTED_DISCOVERY_HORIZON: "Автоподбор сейчас рассчитан на горизонт ровно 5 лет. Измените горизонт в профиле.",
      UNSUPPORTED_DISCOVERY_CURRENCY: "Автоподбор сейчас работает только для рублёвого профиля.",
      UNSUPPORTED_MARKET_HOLDING: "Один из купленных инструментов нельзя обновить через текущий источник MOEX.",
      NO_AFFORDABLE_MARKET_CANDIDATE: "В проверенном списке MOEX нет целого лота, который помещается в сумму.",
      MOEX_UNAVAILABLE: "MOEX ISS сейчас недоступен. Предложение не создано и старая цена не подставлена.",
      MOEX_INVALID_RESPONSE: "MOEX вернул неполные данные. Предложение остановлено.",
      MOEX_INSTRUMENT_UNAVAILABLE: "Один из проверяемых инструментов сейчас недоступен на MOEX.",
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
        <h2 id="empty-title">Настройте профиль инвестора</h2>
        <p>
          Укажите брокера, комиссии и риск-профиль. Активы, цены, лоты и
          целевые доли PatientCapital подберёт сам, когда вы введёте сумму.
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
  onSaved,
}: {
  currency: string;
  result: Recommendation | null;
  onResult: (value: Recommendation) => void;
  onSaved: () => Promise<void>;
}) {
  const [amount, setAmount] = useState("8000");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const candidates = result?.candidates ?? [];

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const run = await request<Recommendation>("/v1/discovery/recommendations", {
        method: "POST",
        body: JSON.stringify({ contribution: amount }),
      });
      onResult(run);
      await onSaved();
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="workspace-stack">
      <section className="page-intro">
        <p className="eyebrow">Автоподбор · 5 лет</p>
        <h1>Скажите только сумму</h1>
        <p>PatientCapital сам проверит доступные ОФЗ и фонд акций на MOEX, а затем рассчитает целые лоты, комиссию и остаток.</p>
      </section>
      <section className="chat-panel" aria-label="Диалог подбора">
        <div className="chat-avatar" aria-hidden="true">PC</div>
        <div className="chat-bubble assistant">
          <b>PatientCapital</b>
          <p>Сколько рублей вы готовы направить сейчас? Я использую ваш риск-профиль и горизонт 5 лет. Предложение не совершит сделку.</p>
        </div>
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
          {busy ? "Ищу и считаю…" : "Подобрать активы"}
        </button>
      </form>
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
      {result && (
        <section className="result-card" aria-live="polite">
          <div className="user-query"><span>Вы</span><p>У меня есть {money(result.contribution, result.currency)}. Что можно купить на {result.horizon_years ?? 5} лет?</p></div>
          <header className="section-heading">
            <div><p className="eyebrow">Проверяемое предложение</p><h2>{money(result.spent, result.currency)} к покупке</h2></div>
            <span className="status-pill">Предложение · не исполнено</span>
          </header>
          {candidates.length > 0 && (
            <div className="candidate-grid" aria-label="Подобранные инструменты">
              {candidates.map((candidate) => (
                <article key={candidate.asset_id}>
                  <header><i>{candidate.instrument_type === "ofz" ? "ОФЗ" : "ФОНД"}</i><b>{percent(candidate.target_weight)}</b></header>
                  <h3>{candidate.name}</h3>
                  <p>{candidate.rationale}</p>
                  <dl>
                    <div><dt>Код</dt><dd>{candidate.asset_id}</dd></div>
                    <div><dt>Цена / пай</dt><dd>{money(candidate.unit_price, result.currency)}</dd></div>
                    <div><dt>Лот</dt><dd>{candidate.lot_size} · {money(candidate.lot_cost, result.currency)}</dd></div>
                    {candidate.maturity_date && <div><dt>Погашение</dt><dd>{new Intl.DateTimeFormat("ru-RU").format(new Date(`${candidate.maturity_date}T00:00:00Z`))}</dd></div>}
                    {candidate.yield_percent != null && <div><dt>Доходность MOEX</dt><dd>{candidate.yield_percent}%</dd></div>}
                    <div><dt>Цена на</dt><dd>{shortDateTime(candidate.price_as_of)}</dd></div>
                  </dl>
                  <footer><a href={candidate.source_url} target="_blank" rel="noreferrer">Котировка MOEX ↗</a><a href={candidate.classification_url} target="_blank" rel="noreferrer">Класс инструмента ↗</a></footer>
                </article>
              ))}
            </div>
          )}
          <div className="market-warning">Данные MOEX задержанные. Перед фактической покупкой проверьте цену у брокера. Это предложение, не заявка и не обещание доходности.</div>
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
                  <div><h3>{candidates.find((item) => item.asset_id === line.asset_id)?.name ?? line.asset_id}</h3><p>{line.asset_id} · {line.lots} лот. · {line.quantity} шт. × {money(line.unit_price, result.currency)}</p></div>
                  <div className="drift-change"><span>{money(line.pre_drift, result.currency)}</span><i>→</i><b>{money(line.post_drift, result.currency)}</b><small>отклонение от цели</small></div>
                  <strong>{money(line.total, result.currency)}</strong>
                </article>
              ))}
            </div>
          )}
          <footer className="audit-line">
            <span>Алгоритм {result.algorithm_version}</span>
            {result.policy_version && <span>Policy {result.policy_version}</span>}
            <span>Run {result.id.slice(0, 8)}</span>
            <span>Hash {result.input_hash.slice(0, 10)}</span>
          </footer>
        </section>
      )}
    </div>
  );
}

function Ledger({ assets, onSaved }: { assets: Asset[]; onSaved: () => Promise<void> }) {
  const activeAssets = assets.filter((asset) => asset.is_active);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    asset_id: activeAssets[0]?.asset_id ?? "",
    side: "BUY",
    quantity: "1",
    unit_price: "",
    accrued_interest_total: "0",
    fee: "0",
    currency: activeAssets[0]?.currency ?? "RUB",
    occurred_at: nowLocal(),
    note: "",
  });

  const selectedAssetId = form.asset_id || activeAssets[0]?.asset_id || "";
  const selectedCurrency = form.asset_id
    ? form.currency
    : activeAssets[0]?.currency ?? form.currency;

  const updateAsset = (assetId: string) => {
    const asset = activeAssets.find((item) => item.asset_id === assetId);
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
        <label>Актив<select required value={selectedAssetId} onChange={(e) => updateAsset(e.target.value)}><option value="">Выберите актив</option>{activeAssets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.asset_id} · {asset.name}</option>)}</select></label>
        <label>Сторона<select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}><option value="BUY">Покупка</option><option value="SELL">Продажа</option></select></label>
        <label>Количество<input required type="number" min="1" step="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label>
        <label>Цена за единицу<input required type="number" min="0.00000001" step="any" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} /></label>
        <label>НКД всего<input required type="number" min="0" step="0.01" value={form.accrued_interest_total} onChange={(e) => setForm({ ...form, accrued_interest_total: e.target.value })} /></label>
        <label>Комиссия<input required type="number" min="0" step="0.01" value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} /></label>
        <label>Валюта<input required pattern="[A-Z]{3}" value={selectedCurrency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></label>
        <label>Дата и время<input required type="datetime-local" value={form.occurred_at} onChange={(e) => setForm({ ...form, occurred_at: e.target.value })} /></label>
        <label>Заметка<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Необязательно" /></label>
        <div className="form-actions"><button className="button primary" disabled={busy || activeAssets.length === 0}>{busy ? "Сохраняем…" : "Записать операцию"}</button></div>
      </form>
      {activeAssets.length === 0 && <div className="notice error">Сначала создайте автоматическое предложение в разделе «Пополнение» — выбранные инструменты появятся здесь.</div>}
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
    investment_horizon_years: "5",
    risk_level: profile?.risk_level ?? "balanced",
    cash_buffer: profile?.cash_buffer ?? "0",
    broker_name: profile?.broker_name ?? "",
    fee_rate: profile?.fee_rate ?? "0.0005",
    minimum_fee: profile?.minimum_fee ?? "0",
  });

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setNotice(null);
    try {
      await request("/v1/profile", { method: "PUT", body: JSON.stringify({ ...profileForm, expected_version: profile?.version ?? null, investment_horizon_years: Number(profileForm.investment_horizon_years) }) });
      await onRefresh();
      setNotice({ kind: "success", text: "Новая версия профиля сохранена" });
    } catch (error) { setNotice({ kind: "error", text: errorText(error) }); }
  };

  return (
    <div className="workspace-stack">
      <section className="page-intro"><p className="eyebrow">Параметры</p><h1>Профиль инвестора</h1><p>Вы задаёте риск и реальные издержки. Активы, цены и лоты подбираются автоматически и сохраняются вместе с источниками.</p></section>
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
      <div className="settings-grid">
        <form className="form-card two-column" onSubmit={saveProfile}>
          <div className="form-title"><span>01</span><div><h2>Инвестор</h2><p>Брокер, горизонт и издержки</p></div></div>
          <label>Базовая валюта<input required pattern="[A-Z]{3}" value={profileForm.base_currency} onChange={(e) => setProfileForm({ ...profileForm, base_currency: e.target.value.toUpperCase() })} /></label>
          <label>Горизонт, лет<input required readOnly type="number" min="5" max="5" value={profileForm.investment_horizon_years} /><small className="field-note">Текущая policy поддерживает 5 лет</small></label>
          <label>Риск-профиль<select value={profileForm.risk_level} onChange={(e) => setProfileForm({ ...profileForm, risk_level: e.target.value })}><option value="conservative">Консервативный</option><option value="balanced">Сбалансированный</option><option value="growth">Рост</option></select></label>
          <label>Денежный резерв<input required type="number" min="0" step="0.01" value={profileForm.cash_buffer} onChange={(e) => setProfileForm({ ...profileForm, cash_buffer: e.target.value })} /></label>
          <label>Брокер<input required value={profileForm.broker_name} onChange={(e) => setProfileForm({ ...profileForm, broker_name: e.target.value })} /></label>
          <label>Комиссия, доля<input required type="number" min="0" max="1" step="0.00000001" value={profileForm.fee_rate} onChange={(e) => setProfileForm({ ...profileForm, fee_rate: e.target.value })} /></label>
          <label>Минимальная комиссия<input required type="number" min="0" step="0.01" value={profileForm.minimum_fee} onChange={(e) => setProfileForm({ ...profileForm, minimum_fee: e.target.value })} /></label>
          <div className="form-actions"><button className="button primary">Сохранить профиль</button>{profile && <small>Текущая версия: {profile.version}</small>}</div>
        </form>

        <section className="form-card discovery-info">
          <div className="form-title"><span>02</span><div><h2>Автоматический подбор</h2><p>MOEX ISS + deterministic policy</p></div></div>
          <ol>
            <li><b>Поиск.</b><span>Проверяем активные рублёвые ОФЗ и фонды широкого индекса.</span></li>
            <li><b>Контроль.</b><span>Цена, лот, валюта, дата и источник проходят строгую валидацию.</span></li>
            <li><b>Расчёт.</b><span>Движок учитывает риск, бюджет, резерв, комиссии и текущие позиции.</span></li>
          </ol>
          <p className="advanced-note">Ручное редактирование universe больше не требуется в основном интерфейсе. Legacy API сохранён для диагностики и миграции старых данных.</p>
        </section>
      </div>
      {assets.length > 0 && <section className="configured-assets"><header className="section-heading"><div><p className="eyebrow">Каталог</p><h2>Инструменты из последних подборов</h2></div><span>Проверенные данные сохранены локально</span></header><div>{assets.filter((asset) => asset.is_active).map((asset) => <article key={asset.asset_id}><i>{asset.asset_id.slice(0, 2)}</i><span><b>{asset.asset_id} · {asset.name}</b><small>лот {asset.lot_size} · версия {asset.version}</small></span><strong>{percent(asset.target_weight)}</strong></article>)}</div></section>}
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
              {view === "contribution" && <Contribution currency={profile?.base_currency ?? "RUB"} result={recommendation} onResult={setRecommendation} onSaved={refresh} />}
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
