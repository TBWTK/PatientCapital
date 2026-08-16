"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type AlertAcknowledgement,
  type AnalyticsOverview,
  type Asset,
  type MonitorAlert,
  type Portfolio,
  type Profile,
  type ProposalSet,
  type Recommendation,
  type TransactionDraft,
  request,
} from "./api";

type View = "overview" | "contribution" | "assistant" | "settings";
type Notice = { kind: "error" | "success"; text: string } | null;

const nav: { id: View; label: string; mark: string }[] = [
  { id: "overview", label: "Обзор", mark: "⌁" },
  { id: "contribution", label: "Пополнить", mark: "+" },
  { id: "assistant", label: "Ассистент", mark: "↕" },
  { id: "settings", label: "Профиль", mark: "○" },
];

const toLocalDateTimeInput = (value: string | null | undefined) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  parsed.setMinutes(parsed.getMinutes() - parsed.getTimezoneOffset());
  return parsed.toISOString().slice(0, 16);
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
  analytics,
  profile,
  onContribution,
  onSettings,
}: {
  portfolio: Portfolio | null;
  analytics: AnalyticsOverview | null;
  profile: Profile | null;
  onContribution: () => void;
  onSettings: () => void;
}) {
  if (!profile || !portfolio) return <EmptyState onStart={onSettings} />;

  const pnlValue = analytics?.unrealized_result.status === "available"
    ? analytics.unrealized_result.value
    : portfolio.total_unrealized_pnl;
  const pnl = Number(pnlValue);
  const allocation = analytics?.allocation ?? portfolio.assets;
  const unavailableReason: Record<string, string> = {
    "DEPOSIT/WITHDRAWAL events are not configured in the ledger": "Журнал пока не различает пополнения и выводы денег",
    "COUPON/DIVIDEND events are not configured in the ledger": "Купоны и дивиденды пока не записываются отдельными событиями",
  };
  const metric = (
    title: string,
    item: AnalyticsOverview["market_value"] | undefined,
    availableHint: string,
  ) => (
    <article>
      <span>{title}</span>
      <strong>{item?.status === "available" && item.value != null ? money(item.value, portfolio.currency) : item?.status === "not_configured" ? "Не настроено" : "Неизвестно"}</strong>
      <small>{item?.status === "available" ? availableHint : unavailableReason[item?.reason ?? ""] ?? item?.reason ?? "Источник данных отсутствует"}</small>
    </article>
  );
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
        {metric("Себестоимость", analytics?.cost_basis, "по подтверждённому журналу")}
        {metric("Реализованный результат", analytics?.realized_result, "по закрытой части позиций")}
        {metric("Нереализованный результат", analytics?.unrealized_result, "по последним сохранённым ценам")}
        {metric("Чистые пополнения", analytics?.net_contributions, "отдельные денежные потоки")}
        {metric("Купоны и дивиденды", analytics?.income, "подтверждённый инвестиционный доход")}
        <article>
          <span>Свежесть цен</span>
          <strong>{analytics?.price_freshness.status === "fresh" ? "Актуальны" : analytics?.price_freshness.status === "stale" ? "Есть устаревшие" : "Неизвестно"}</strong>
          <small>{analytics?.price_freshness.oldest_as_of ? `старейшая: ${shortDateTime(analytics.price_freshness.oldest_as_of)}` : analytics?.price_freshness.reason ?? "нет ценовых данных"}</small>
        </article>
      </section>

      <section className="allocation-card">
        <header className="section-heading">
          <div>
            <p className="eyebrow">Структура</p>
            <h2>Портфель и отклонения</h2>
          </div>
          <span className="as-of">{analytics ? `Расчёт ${shortDateTime(analytics.calculated_at)} · ${analytics.algorithm_version}` : "По последним сохранённым ценам"}</span>
        </header>
        {allocation.length === 0 ? (
          <div className="soft-empty">
            Сделок пока нет. Запишите первую покупку через «Ассистент».
          </div>
        ) : (
          <div className="asset-table" role="table" aria-label="Активы портфеля">
            <div className="asset-row asset-head" role="row">
              <span>Актив</span><span>Стоимость</span><span>Доля</span><span>Отклонение</span>
            </div>
            {allocation.map((asset) => (
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

      <section className="activity-card">
        <header className="section-heading">
          <div><p className="eyebrow">Журнал</p><h2>Последние операции</h2></div>
          <span>{analytics?.recent_activity.length ?? 0} из последних 10</span>
        </header>
        {!analytics || analytics.recent_activity.length === 0 ? <div className="soft-empty">Подтверждённых операций пока нет.</div> : (
          <div className="activity-list">
            {analytics.recent_activity.map((event) => (
              <article key={event.id}>
                <i className={event.side === "BUY" ? "buy" : "sell"}>{event.side === "BUY" ? "BUY" : "SELL"}</i>
                <span><b>{event.side === "BUY" ? "Покупка" : "Продажа"} · {event.asset_id}</b><small>{shortDateTime(event.occurred_at)} · {event.quantity} шт. по {money(event.unit_price, event.currency)}</small></span>
                <span><b>Комиссия {money(event.fee, event.currency)}</b><small>НКД {money(event.accrued_interest_total, event.currency)}</small></span>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function RecommendationEvidence({ result }: { result: Recommendation }) {
  const candidates = result.candidates ?? [];
  const rejectedCandidates = result.rejected_candidates ?? [];
  return (
    <div className="evidence-body">
      {result.search && (
        <section className="search-trace" aria-label="Охват исследования рынка">
          <div>
            <i>{result.search.mode === "live" ? "LIVE SEARCH" : "FRESH CACHE"}</i>
            <b>Просмотрено {result.search.universe_size} инструментов</b>
            <span>
              Допущено {result.search.candidate_count} · углублённо проверено {result.search.enriched_count}
            </span>
          </div>
          <div>
            <span>Снимок {shortDateTime(result.search.observed_at)}</span>
            <small>{result.search.scan_policy_version} · {result.search.snapshot_id.slice(0, 8)}</small>
          </div>
        </section>
      )}
      {candidates.length > 0 && (
        <div className="candidate-grid" aria-label="Подобранные инструменты">
          {candidates.map((candidate) => (
            <article key={candidate.asset_id}>
              <header><i>{candidate.instrument_type === "ofz" ? "ОФЗ" : candidate.instrument_type === "dividend_stock" ? "АКЦИЯ" : "ФОНД"}</i><b>{percent(candidate.target_weight)}</b></header>
              <h3>{candidate.name}</h3>
              <p>{candidate.rationale}</p>
              <dl>
                <div><dt>Код</dt><dd>{candidate.asset_id}</dd></div>
                <div><dt>Цена / пай</dt><dd>{money(candidate.unit_price, result.currency)}</dd></div>
                <div><dt>Лот</dt><dd>{candidate.lot_size} · {money(candidate.lot_cost, result.currency)}</dd></div>
                {candidate.maturity_date && <div><dt>Погашение</dt><dd>{new Intl.DateTimeFormat("ru-RU").format(new Date(`${candidate.maturity_date}T00:00:00Z`))}</dd></div>}
                {candidate.yield_percent != null && <div><dt>Доходность MOEX</dt><dd>{candidate.yield_percent}%</dd></div>}
                {candidate.next_coupon_date && <div><dt>Следующий купон</dt><dd>{new Intl.DateTimeFormat("ru-RU").format(new Date(`${candidate.next_coupon_date}T00:00:00Z`))}</dd></div>}
                {candidate.coupon_percent != null && <div><dt>Ставка купона</dt><dd>{candidate.coupon_percent}%</dd></div>}
                <div><dt>Цена на</dt><dd>{shortDateTime(candidate.price_as_of)}</dd></div>
                {candidate.score != null && <div><dt>Ranking score</dt><dd>{candidate.score}</dd></div>}
              </dl>
              {candidate.research && (
                <details className="research-details">
                  <summary>{candidate.research.scope === "market_screen" ? "Что проверил market screen" : "Почему акция прошла полную проверку"}</summary>
                  <p>{candidate.research.summary}</p>
                  <dl>
                    {candidate.research.profitable_years != null && <div><dt>Прибыльные периоды</dt><dd>{candidate.research.profitable_years}</dd></div>}
                    <div><dt>Дивидендные периоды</dt><dd>{candidate.research.dividend_years}</dd></div>
                    {candidate.research.payout_ratio_percent != null && <div><dt>Выплата от прибыли</dt><dd>{candidate.research.payout_ratio_percent}%</dd></div>}
                    {candidate.research.annual_dividend_per_share != null && <div><dt>Последний год истории</dt><dd>{money(candidate.research.annual_dividend_per_share, result.currency)} на акцию</dd></div>}
                    {candidate.research.historical_dividend_yield_percent != null && <div><dt>Историческая доходность</dt><dd>{candidate.research.historical_dividend_yield_percent}%</dd></div>}
                    <div><dt>Scope</dt><dd>{candidate.research.scope === "market_screen" ? "Рыночный скрининг" : "Полная quality-проверка"}</dd></div>
                    <div><dt>Research на</dt><dd>{shortDateTime(candidate.research.observed_at)}</dd></div>
                  </dl>
                  {(candidate.research.unknown_facts ?? []).length > 0 && (
                    <p className="research-unknown">Не проверено этим источником: {(candidate.research.unknown_facts ?? []).join(", ")}.</p>
                  )}
                  <nav aria-label={`Первичные источники ${candidate.asset_id}`}>
                    {candidate.research.citations.map((citation) => (
                      <a key={citation.kind} href={citation.url} target="_blank" rel="noreferrer">{citation.title} ↗</a>
                    ))}
                  </nav>
                  <small>Policy {candidate.research.policy_version} · прошлая выплата не является прогнозом · dividend capture не используется</small>
                </details>
              )}
              <footer><a href={candidate.source_url} target="_blank" rel="noreferrer">Котировка MOEX ↗</a><a href={candidate.classification_url} target="_blank" rel="noreferrer">Класс инструмента ↗</a></footer>
            </article>
          ))}
        </div>
      )}
      {rejectedCandidates.length > 0 && (
        <details className="rejected-details">
          <summary>Не выбранные policy кандидаты · {rejectedCandidates.length}</summary>
          <div>
            {rejectedCandidates.map((candidate) => (
              <article key={candidate.asset_id}>
                <span><b>{candidate.name}</b><small>{candidate.asset_id} · лот {candidate.lot_size} · {money(candidate.lot_cost, result.currency)}</small></span>
                <p>{candidate.reason}</p>
                {candidate.score != null && <small>Score {candidate.score}</small>}
                <a href={candidate.source_url} target="_blank" rel="noreferrer">Источник ↗</a>
              </article>
            ))}
          </div>
        </details>
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
    </div>
  );
}

function Contribution({
  currency,
  result,
  onResult,
  onSaved,
  onAssistant,
}: {
  currency: string;
  result: ProposalSet | null;
  onResult: (value: ProposalSet) => void;
  onSaved: () => Promise<void>;
  onAssistant: () => void;
}) {
  const [amount, setAmount] = useState("8000");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    setSelectedStrategy(null);
    try {
      const proposalSet = await request<ProposalSet>("/v1/proposal-sets", {
        method: "POST",
        body: JSON.stringify({ contribution: amount }),
      });
      onResult(proposalSet);
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
        <p>PatientCapital проверит свежий снимок рынка или запустит новый поиск по MOEX, затем покажет до трёх понятных стратегий. Источники, охват, котировки и причины отсева останутся внутри карточки.</p>
      </section>
      <section className="chat-panel" aria-label="Диалог подбора">
        <div className="chat-avatar" aria-hidden="true">PC</div>
        <div className="chat-bubble assistant">
          <b>PatientCapital</b>
          <p>Сколько рублей вы готовы направить сейчас? Я использую ваш риск-профиль и горизонт 5 лет. Ни одно предложение не совершит сделку.</p>
        </div>
      </section>
      <form className="contribution-form" onSubmit={submit}>
        <label>
          Сумма пополнения
          <span className="money-input">
            <input aria-label="Сумма пополнения" type="number" min="0" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} />
            <b>{currency}</b>
          </span>
        </label>
        <button className="button primary large" disabled={busy}>
          {busy ? "Изучаю рынок и считаю…" : "Исследовать рынок и подобрать"}
        </button>
      </form>
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
      {result && (
        <section className="proposal-set" aria-live="polite">
          <div className="user-query"><span>Вы</span><p>У меня есть {money(result.contribution, result.currency)}. Что можно купить на 5 лет?</p></div>
          <header className="section-heading">
            <div><p className="eyebrow">Варианты действий</p><h2>Выберите подход</h2></div>
            <span className="status-pill">Предложения · не исполнены</span>
          </header>
          <div className="strategy-grid">
            {result.strategies.map((strategy, index) => {
              const recommendation = strategy.recommendation;
              const selected = selectedStrategy === strategy.strategy_id;
              return (
                <article className={`strategy-card${selected ? " selected" : ""}`} key={strategy.strategy_id}>
                  <header>
                    <span className="strategy-number">Вариант {index + 1}</span>
                    {strategy.recommended && <span className="recommended-pill">Рекомендуется</span>}
                  </header>
                  <h2>{strategy.name}</h2>
                  <p className="strategy-summary">{strategy.summary}</p>
                  <div className="strategy-why"><b>Почему</b><p>{strategy.why}</p></div>
                  <div className="strategy-money">
                    <span>К покупке <b>{money(recommendation.spent, recommendation.currency)}</b></span>
                    <span>Остаток <b>{money(recommendation.leftover, recommendation.currency)}</b></span>
                  </div>
                  <p className="risk-note">{strategy.risk_note}</p>
                  <ul>{strategy.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}</ul>
                  <button className="button primary" type="button" onClick={() => setSelectedStrategy(strategy.strategy_id)}>
                    {selected ? "Вариант выбран" : "Выбрать этот вариант"}
                  </button>
                  <details className="evidence-details">
                    <summary>Расчёт и источники</summary>
                    <RecommendationEvidence result={recommendation} />
                  </details>
                  {selected && <div className="selection-next"><span>После покупки пришлите чек или опишите сделку Ассистенту.</span><button type="button" onClick={onAssistant}>Открыть Ассистент →</button></div>}
                </article>
              );
            })}
          </div>
          <footer className="proposal-audit">Набор {result.id.slice(0, 8)} · профиль v{result.profile_version} · создан {shortDateTime(result.created_at)}</footer>
        </section>
      )}
    </div>
  );
}

function Assistant({
  assets,
  alerts,
  onSaved,
  onAcknowledge,
}: {
  assets: Asset[];
  alerts: MonitorAlert[];
  onSaved: () => Promise<void>;
  onAcknowledge: (alertId: string) => Promise<void>;
}) {
  const knownAssets = assets;
  const defaultAsset = knownAssets.find((asset) => asset.is_active) ?? knownAssets[0];
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [draft, setDraft] = useState<TransactionDraft | null>(null);
  const [review, setReview] = useState({
    asset_id: "",
    side: "",
    quantity: "",
    unit_price: "",
    accrued_interest_total: "",
    fee: "",
    currency: "",
    occurred_at: "",
    note: "",
  });
  const [manual, setManual] = useState({
    asset_id: defaultAsset?.asset_id ?? "",
    side: "BUY",
    quantity: "",
    unit_price: "",
    accrued_interest_total: "",
    fee: "",
    currency: defaultAsset?.currency ?? "RUB",
    occurred_at: "",
    note: "",
  });

  const openDraft = (next: TransactionDraft) => {
    setDraft(next);
    setReview({
      asset_id: next.fields.asset_id ?? "",
      side: next.fields.side ?? "",
      quantity: next.fields.quantity?.toString() ?? "",
      unit_price: next.fields.unit_price ?? "",
      accrued_interest_total: next.fields.accrued_interest_total ?? "",
      fee: next.fields.fee ?? "",
      currency: next.fields.currency ?? "",
      occurred_at: toLocalDateTimeInput(next.fields.occurred_at),
      note: next.source_kind === "image" ? "Подтверждено по загруженному брокерскому чеку" : "",
    });
    setNotice(null);
  };

  const createTextDraft = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      openDraft(await request<TransactionDraft>("/v1/transaction-drafts/text", {
        method: "POST",
        body: JSON.stringify({ text: sourceText }),
      }));
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  const createImageDraft = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setNotice(null);
    try {
      const body = new FormData();
      body.append("file", file);
      openDraft(await request<TransactionDraft>("/v1/transaction-drafts/image", {
        method: "POST",
        body,
      }));
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  const createManualDraft = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      openDraft(await request<TransactionDraft>("/v1/transaction-drafts/manual", {
        method: "POST",
        body: JSON.stringify({
          ...manual,
          quantity: Number(manual.quantity),
          occurred_at: new Date(manual.occurred_at).toISOString(),
          note: manual.note || null,
        }),
      }));
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  const confirmDraft = async (event: FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setNotice(null);
    try {
      const confirmed = await request<TransactionDraft>(`/v1/transaction-drafts/${draft.id}/decisions`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: draft.version,
          decision: "confirm",
          transaction: {
            idempotency_key: `transaction-draft-${draft.id}`,
            asset_id: review.asset_id,
            side: review.side,
            quantity: Number(review.quantity),
            unit_price: review.unit_price,
            accrued_interest_total: review.accrued_interest_total,
            fee: review.fee,
            currency: review.currency,
            occurred_at: new Date(review.occurred_at).toISOString(),
            note: review.note || null,
          },
        }),
      });
      setDraft(confirmed);
      await onSaved();
      setNotice({ kind: "success", text: "Подтверждённая операция записана в неизменяемый журнал" });
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  const rejectDraft = async () => {
    if (!draft) return;
    setBusy(true);
    setNotice(null);
    try {
      const rejected = await request<TransactionDraft>(`/v1/transaction-drafts/${draft.id}/decisions`, {
        method: "POST",
        body: JSON.stringify({ expected_version: draft.version, decision: "reject", transaction: null }),
      });
      setDraft(rejected);
      setNotice({ kind: "success", text: "Черновик отклонён. Журнал операций не изменён" });
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };

  const chooseManualAsset = (assetId: string) => {
    const asset = knownAssets.find((item) => item.asset_id === assetId);
    setManual((current) => ({ ...current, asset_id: assetId, currency: asset?.currency ?? "" }));
  };

  const chooseReviewAsset = (assetId: string) => {
    const asset = knownAssets.find((item) => item.asset_id === assetId);
    setReview((current) => ({ ...current, asset_id: assetId, currency: asset?.currency ?? current.currency }));
  };

  const reviewComplete = Boolean(
    review.asset_id && review.side && review.quantity && review.unit_price &&
    review.accrued_interest_total !== "" && review.fee !== "" &&
    review.currency && review.occurred_at,
  );

  const fieldNames: Record<string, string> = {
    side: "покупка или продажа",
    asset_id: "инструмент",
    quantity: "количество",
    unit_price: "чистая цена за единицу",
    accrued_interest_total: "НКД всей сделки",
    fee: "комиссия",
    currency: "валюта",
    occurred_at: "дата, время и часовой пояс",
  };

  const acknowledgeMonitor = async (alertId: string) => {
    setNotice(null);
    try {
      await onAcknowledge(alertId);
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    }
  };

  return (
    <div className="workspace-stack narrow">
      <section className="page-intro">
        <p className="eyebrow">Операции через диалог</p>
        <h1>Ассистент операций</h1>
        <p>Опишите фактическую покупку или загрузите брокерский чек. Ассистент подготовит черновик, но запишет операцию только после вашей проверки и подтверждения.</p>
      </section>
      <section className="monitor-panel" aria-labelledby="monitor-title">
        <header className="section-heading">
          <div>
            <p className="eyebrow">4 проверки в день</p>
            <h2 id="monitor-title">Наблюдение портфеля</h2>
          </div>
          <span>{alerts.length ? `${alerts.length} требуют внимания` : "Новых сигналов нет"}</span>
        </header>
        {alerts.length === 0 ? (
          <p className="monitor-empty">PatientCapital проверяет цены, отклонения и срок действия research evidence. Наблюдение не создаёт операций и не отправляет заявки брокеру.</p>
        ) : (
          <div className="monitor-alerts">
            {alerts.map((alert) => (
              <article className={alert.severity} key={alert.id}>
                <header><span>{alert.asset_id}</span><time dateTime={alert.created_at}>{shortDateTime(alert.created_at)}</time></header>
                <h3>{alert.title}</h3>
                <p>{alert.message}</p>
                <footer>
                  <details><summary>Проверенные факты</summary><pre>{JSON.stringify(alert.evidence, null, 2)}</pre></details>
                  {alert.acknowledgement == null ? (
                    <button type="button" onClick={() => void acknowledgeMonitor(alert.id)}>Принять к сведению</button>
                  ) : <span>Принято {shortDateTime(alert.acknowledgement.created_at)}</span>}
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="assistant-composer" aria-label="Диалог записи операции">
        <div className="chat-panel">
          <div className="chat-avatar" aria-hidden="true">PC</div>
          <div className="chat-bubble assistant"><b>PatientCapital</b><p>Пришлите текст или скриншот операции. Я извлеку факты в черновик и отдельно попрошу всё подтвердить.</p></div>
        </div>
        <form className="assistant-input" onSubmit={createTextDraft}>
          <label htmlFor="operation-text">Что произошло</label>
          <textarea id="operation-text" required minLength={2} value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder="Например: Купил 7 ОФЗ 26226 по 992,04 ₽, НКД 195,16 ₽, комиссия 3,47 ₽, 13 августа 2026 в 16:34" />
          <div className="composer-actions">
            <button className="button primary" disabled={busy}>{busy ? "Разбираю…" : "Подготовить черновик"}</button>
            <label className="upload-button">
              <span>{busy ? "Обработка…" : "Загрузить скриншот"}</span>
              <input aria-label="Скриншот операции" type="file" accept="image/jpeg,image/png" disabled={busy} onChange={(event) => void createImageDraft(event.target.files?.[0])} />
            </label>
          </div>
          <small>JPEG или PNG до 8 МБ. OCR выполняется локально; исходное изображение удаляется сразу после распознавания.</small>
        </form>
      </section>

      {draft && (
        <section className="draft-review" aria-labelledby="draft-title" aria-live="polite">
          <header className="section-heading">
            <div><p className="eyebrow">Проверка перед записью</p><h2 id="draft-title">Черновик операции</h2></div>
            <span className={`status-pill ${draft.status}`}>{draft.status === "unconfirmed" ? "Не подтверждён" : draft.status === "confirmed" ? "Записан" : "Отклонён"}</span>
          </header>
          <p className="draft-source">Источник: {draft.source_kind === "image" ? "скриншот" : draft.source_kind === "manual" ? "расширенный ввод" : "текст"} · extractor {draft.extractor_version} · draft {draft.id.slice(0, 8)}</p>
          {draft.unknown_fields.length > 0 && <div className="draft-warning"><b>Не удалось определить:</b> {draft.unknown_fields.map((field) => fieldNames[field] ?? field).join(", ")}. Заполните эти поля вручную.</div>}
          {draft.conflicts.length > 0 && <div className="draft-warning conflict"><b>Найдены противоречия:</b><ul>{draft.conflicts.map((conflict) => <li key={conflict}>{conflict}</li>)}</ul></div>}
          {draft.status === "unconfirmed" ? (
            <form className="form-card two-column review-form" onSubmit={confirmDraft}>
              <label>Актив<select required value={review.asset_id} onChange={(event) => chooseReviewAsset(event.target.value)}><option value="">Выберите распознанный актив</option>{knownAssets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.asset_id} · {asset.name}</option>)}</select></label>
              <label>Сторона<select required value={review.side} onChange={(event) => setReview({ ...review, side: event.target.value })}><option value="">Уточните</option><option value="BUY">Покупка</option><option value="SELL">Продажа</option></select></label>
              <label>Количество<input required type="number" min="1" step="1" value={review.quantity} onChange={(event) => setReview({ ...review, quantity: event.target.value })} /></label>
              <label>Чистая цена за единицу<input required type="number" min="0.00000001" step="any" value={review.unit_price} onChange={(event) => setReview({ ...review, unit_price: event.target.value })} /></label>
              <label>НКД всего<input required type="number" min="0" step="0.01" value={review.accrued_interest_total} onChange={(event) => setReview({ ...review, accrued_interest_total: event.target.value })} /></label>
              <label>Комиссия<input required type="number" min="0" step="0.01" value={review.fee} onChange={(event) => setReview({ ...review, fee: event.target.value })} /></label>
              <label>Валюта<input required pattern="[A-Z]{3}" value={review.currency} onChange={(event) => setReview({ ...review, currency: event.target.value.toUpperCase() })} /></label>
              <label>Дата и время<input required type="datetime-local" value={review.occurred_at} onChange={(event) => setReview({ ...review, occurred_at: event.target.value })} /></label>
              <label className="wide-field">Заметка<input value={review.note} onChange={(event) => setReview({ ...review, note: event.target.value })} placeholder="Необязательно" /></label>
              <div className="draft-confirmation-note wide-field">Проверьте данные по брокерскому отчёту. Подтверждение создаст ровно одну фактическую запись; заявка брокеру не отправляется.</div>
              <div className="form-actions wide-field"><button className="button primary" disabled={busy || !reviewComplete}>{busy ? "Записываю…" : "Подтвердить и записать"}</button><button className="button secondary" type="button" disabled={busy} onClick={() => void rejectDraft()}>Отклонить черновик</button></div>
            </form>
          ) : (
            <div className="draft-decision"><b>{draft.status === "confirmed" ? "Операция подтверждена" : "Черновик отклонён"}</b><p>{draft.status === "confirmed" ? `Запись ${draft.decision?.transaction?.id.slice(0, 8)} добавлена в журнал.` : "Позиции и капитал не изменились."}</p></div>
          )}
          <details className="draft-evidence"><summary>Технические данные распознавания</summary><dl><div><dt>SHA-256</dt><dd>{draft.source_sha256}</dd></div><div><dt>Создан</dt><dd>{shortDateTime(draft.created_at)}</dd></div><div><dt>Истекает</dt><dd>{shortDateTime(draft.expires_at)}</dd></div></dl></details>
        </section>
      )}

      <details className="advanced-ledger">
        <summary>Расширенный ввод операции</summary>
        <form className="form-card two-column" onSubmit={createManualDraft}>
          <label>Актив<select required value={manual.asset_id} onChange={(event) => chooseManualAsset(event.target.value)}><option value="">Выберите актив</option>{knownAssets.map((asset) => <option key={asset.asset_id} value={asset.asset_id}>{asset.asset_id} · {asset.name}</option>)}</select></label>
          <label>Сторона<select value={manual.side} onChange={(event) => setManual({ ...manual, side: event.target.value })}><option value="BUY">Покупка</option><option value="SELL">Продажа</option></select></label>
          <label>Количество<input required type="number" min="1" step="1" value={manual.quantity} onChange={(event) => setManual({ ...manual, quantity: event.target.value })} /></label>
          <label>Цена за единицу<input required type="number" min="0.00000001" step="any" value={manual.unit_price} onChange={(event) => setManual({ ...manual, unit_price: event.target.value })} /></label>
          <label>НКД всего<input required type="number" min="0" step="0.01" value={manual.accrued_interest_total} onChange={(event) => setManual({ ...manual, accrued_interest_total: event.target.value })} /></label>
          <label>Комиссия<input required type="number" min="0" step="0.01" value={manual.fee} onChange={(event) => setManual({ ...manual, fee: event.target.value })} /></label>
          <label>Валюта<input required pattern="[A-Z]{3}" value={manual.currency} onChange={(event) => setManual({ ...manual, currency: event.target.value.toUpperCase() })} /></label>
          <label>Дата и время<input required type="datetime-local" value={manual.occurred_at} onChange={(event) => setManual({ ...manual, occurred_at: event.target.value })} /></label>
          <label>Заметка<input value={manual.note} onChange={(event) => setManual({ ...manual, note: event.target.value })} placeholder="Необязательно" /></label>
          <div className="form-actions"><button className="button primary" disabled={busy || knownAssets.length === 0}>{busy ? "Готовлю…" : "Подготовить черновик"}</button></div>
        </form>
      </details>
      {knownAssets.length === 0 && <div className="notice error">Пока нет проверенных инструментов. Создайте автоматическое предложение в разделе «Пополнение» — допущенные активы появятся здесь.</div>}
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
            <li><b>Поиск.</b><span>Проверяем рублёвые ОФЗ, фонды широкого индекса и допущенные research-policy дивидендные акции.</span></li>
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
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [proposalSet, setProposalSet] = useState<ProposalSet | null>(null);
  const [alerts, setAlerts] = useState<MonitorAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const refresh = async () => {
    setConnectionError(null);
    const [profileResult, assetsResult, portfolioResult, analyticsResult, alertsResult] = await Promise.allSettled([
      request<Profile>("/v1/profile"),
      request<{ assets: Asset[] }>("/v1/assets"),
      request<Portfolio>("/v1/portfolio"),
      request<AnalyticsOverview>("/v1/analytics/overview"),
      request<{ alerts: MonitorAlert[] }>("/v1/alerts?include_acknowledged=false"),
    ]);
    if (profileResult.status === "fulfilled") setProfile(profileResult.value);
    else if (!(profileResult.reason instanceof ApiError && profileResult.reason.status === 404)) setConnectionError(errorText(profileResult.reason));
    if (assetsResult.status === "fulfilled") setAssets(assetsResult.value.assets);
    else setConnectionError(errorText(assetsResult.reason));
    if (portfolioResult.status === "fulfilled") setPortfolio(portfolioResult.value);
    else if (!(portfolioResult.reason instanceof ApiError && [404, 422].includes(portfolioResult.reason.status))) setConnectionError(errorText(portfolioResult.reason));
    if (analyticsResult.status === "fulfilled") setAnalytics(analyticsResult.value);
    else if (!(analyticsResult.reason instanceof ApiError && [404, 422].includes(analyticsResult.reason.status))) setConnectionError(errorText(analyticsResult.reason));
    if (alertsResult.status === "fulfilled") setAlerts(alertsResult.value.alerts ?? []);
    else setConnectionError(errorText(alertsResult.reason));
    setLoading(false);
  };

  const acknowledge = async (alertId: string) => {
    const acknowledgement = await request<AlertAcknowledgement>(`/v1/alerts/${alertId}/acknowledgements`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    setAlerts((current) => current.map((alert) => (
      alert.id === alertId ? { ...alert, acknowledgement } : alert
    )));
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
              {view === "overview" && <Overview portfolio={portfolio} analytics={analytics} profile={profile} onContribution={() => setView("contribution")} onSettings={() => setView("settings")} />}
              {view === "contribution" && <Contribution currency={profile?.base_currency ?? "RUB"} result={proposalSet} onResult={setProposalSet} onSaved={refresh} onAssistant={() => setView("assistant")} />}
              {view === "assistant" && <Assistant assets={assets} alerts={alerts} onSaved={refresh} onAcknowledge={acknowledge} />}
              {view === "settings" && <Settings profile={profile} assets={assets} onRefresh={refresh} />}
            </>
          )}
        </div>
      </main>
      <footer className="disclaimer">Информационный инструмент · не является индивидуальной инвестиционной рекомендацией · заявки не исполняются</footer>
    </div>
  );
}
