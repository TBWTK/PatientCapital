import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PatientCapitalApp } from "../app/patient-capital-app";

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  }));

const transactionDraft = (
  sourceKind: "text" | "image" | "manual" = "text",
  status: "unconfirmed" | "confirmed" | "rejected" = "unconfirmed",
) => ({
  id: "00000000-0000-0000-0000-000000000020",
  version: 1,
  status,
  source_kind: sourceKind,
  source_sha256: "b".repeat(64),
  source_metadata: sourceKind === "image" ? { media_type: "image/jpeg", width: 1178, height: 2560 } : {},
  extractor_version: sourceKind === "image" ? "tesseract-rus-eng-v1" : sourceKind === "manual" ? "manual-exact-v1" : "transaction-text-ru-v1",
  fields: {
    side: "BUY",
    asset_id: "SU26226RMFS9",
    asset_name: "ОФЗ 26226",
    quantity: 7,
    unit_price: "992.04",
    accrued_interest_total: "195.16",
    fee: "3.47",
    currency: "RUB",
    occurred_at: "2026-08-13T13:34:00Z",
  },
  unknown_fields: [],
  conflicts: [],
  field_confidence: { side: "1.00", asset_id: "1.00" },
  created_at: "2026-08-16T00:00:00Z",
  expires_at: "2026-08-17T00:00:00Z",
  decision: status === "confirmed" ? {
    decision: "confirm",
    decided_at: "2026-08-16T00:01:00Z",
    transaction: {
      id: "00000000-0000-0000-0000-000000000002",
      idempotency_key: "transaction-draft-00000000-0000-0000-0000-000000000020",
      asset_id: "SU26226RMFS9",
      side: "BUY",
      quantity: 7,
      unit_price: "992.04",
      accrued_interest_total: "195.16",
      fee: "3.47",
      currency: "RUB",
      occurred_at: "2026-08-13T13:34:00Z",
      note: null,
      created_at: "2026-08-16T00:01:00Z",
    },
  } : null,
});

afterEach(() => vi.restoreAllMocks());

describe("PatientCapitalApp", () => {
  it("guides a new user to configure the portfolio", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ error: { code: "PROFILE_NOT_CONFIGURED", message: "not configured" } }, 404);
      if (path.endsWith("/v1/assets")) return json({ assets: [] });
      return json({ error: { code: "PROFILE_NOT_CONFIGURED", message: "not configured" } }, 404);
    }));

    const { container } = render(<PatientCapitalApp />);
    expect(await screen.findByRole("heading", { name: "Настройте профиль инвестора" })).toBeTruthy();
    const accessibility = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(accessibility.violations.map((violation) => violation.id)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: /Настроить профиль/ }));
    expect(screen.getByRole("heading", { name: "Профиль инвестора" })).toBeTruthy();
  });

  it("renders backend portfolio analytics without recalculating them", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 2, base_currency: "RUB", investment_horizon_years: 15, risk_level: "balanced", cash_buffer: "10000.00", broker_name: "Demo Broker", fee_rate: "0.0005", minimum_fee: "1.00", created_at: "2026-08-15T00:00:00Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [] });
      return json({ currency: "RUB", total_market_value: "125000.00", total_cost_basis: "120000.00", total_unrealized_pnl: "5000.00", assets: [] });
    }));

    render(<PatientCapitalApp />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("125"));
    expect(screen.getByText((_, node) => node?.classList.contains("delta") === true && node.textContent?.includes("нереализованного результата") === true)).toBeTruthy();
    expect(screen.getByText("Demo Broker")).toBeTruthy();
  });

  it("renders one recommended strategy card and progressively discloses exact evidence", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 3, base_currency: "RUB", investment_horizon_years: 5, risk_level: "balanced", cash_buffer: "0.00", broker_name: "Demo Broker", fee_rate: "0.001", minimum_fee: "1.00", created_at: "2026-08-15T00:00:00Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [] });
      if (path.endsWith("/v1/portfolio")) return json({ currency: "RUB", total_market_value: "0.00", total_cost_basis: "0.00", total_unrealized_pnl: "0.00", assets: [] });
      if (path.endsWith("/v1/proposal-sets") && init?.method === "POST") return json({
        id: "00000000-0000-0000-0000-000000000010",
        contribution: "8000.00",
        currency: "RUB",
        profile_version: 3,
        recommended_strategy_id: "five_year_core",
        created_at: "2026-08-15T09:00:01Z",
        strategies: [{
          strategy_id: "five_year_core",
          name: "Основной план",
          summary: "Вернуть портфель ближе к целевой структуре.",
          why: "Учитывает ваш профиль, текущие позиции и комиссии.",
          risk_note: "Стоимость активов может снижаться.",
          tradeoffs: ["Следует долгосрочной структуре.", "Не исполняет заявку."],
          recommended: true,
          recommendation: {
          id: "00000000-0000-0000-0000-000000000001",
        algorithm_version: "contribution-greedy-v1",
        input_hash: "a".repeat(64),
        calculated_at: "2026-08-15T09:00:00Z",
        currency: "RUB",
        contribution: "8000.00",
        cash_buffer: "0.00",
        investable: "8000.00",
        gross: "7890.00",
        fees: "7.89",
        spent: "7897.89",
        leftover: "102.11",
        reason: "ALLOCATED",
        mode: "automatic",
        policy_version: "five-year-moex-v1",
        horizon_years: 5,
        risk_level: "balanced",
        candidates: [{
          asset_id: "SU26218RMFS6",
          name: "ОФЗ 26218",
          instrument_type: "ofz",
          target_weight: "0.60000000",
          rationale: "Ликвидный рублёвый выпуск ОФЗ около пятилетней даты.",
          unit_price: "818.21000000",
          lot_size: 1,
          lot_cost: "818.21",
          price_as_of: "2026-08-14T20:50:44Z",
          quote_kind: "last_dirty",
          turnover: "742285912",
          maturity_date: "2031-09-17",
          yield_percent: "15.19",
          source_url: "https://iss.moex.com/ofz",
          classification_url: "https://www.moex.com/ru/marketdata/",
        }],
        rejected_candidates: [{
          asset_id: "FUNDALT",
          name: "Альтернативный фонд",
          instrument_type: "equity_index_fund",
          reason: "Инструмент уступил выбранному кандидату в детерминированном ranking policy.",
          unit_price: "120.00000000",
          lot_size: 1,
          lot_cost: "120.00",
          price_as_of: "2026-08-14T20:50:44Z",
          source_url: "https://iss.moex.com/fundalt",
        }],
        lines: [{ asset_id: "SU26218RMFS6", lots: 9, lot_size: 1, quantity: 9, unit_price: "818.21000000", current_value: "0.00", target_value: "4800.00", pre_drift: "-4800.00", post_drift: "2563.89", gross: "7363.89", fee: "7.36", total: "7371.25" }],
        profile_version: 3,
      }}],
      }, 201);
      return json({ error: { code: "UNEXPECTED", message: path } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<PatientCapitalApp />);
    await screen.findByText("Demo Broker");
    fireEvent.click(screen.getAllByRole("button", { name: /Пополн/ })[0]);
    expect((screen.getByLabelText("Сумма пополнения") as HTMLInputElement).value).toBe("8000");
    fireEvent.click(screen.getByRole("button", { name: "Подобрать активы" }));

    expect(await screen.findByRole("heading", { name: "Основной план" })).toBeTruthy();
    expect(screen.getByText("Рекомендуется")).toBeTruthy();
    const evidence = screen.getByText("Расчёт и источники").closest("details");
    expect(evidence?.open).toBe(false);
    fireEvent.click(screen.getByText("Расчёт и источники"));
    expect(evidence?.open).toBe(true);
    expect(screen.getAllByRole("heading", { name: "ОФЗ 26218" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/Не выбранные policy кандидаты/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Котировка MOEX ↗" }).getAttribute("href")).toBe("https://iss.moex.com/ofz");
    const accessibility = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(accessibility.violations.map((violation) => violation.id)).toEqual([]);
    const discoveryCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/proposal-sets"));
    expect(discoveryCall?.[1]?.body).toBe(JSON.stringify({ contribution: "8000" }));
  });

  it("keeps advanced bond input as a draft until exact confirmation", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 4, base_currency: "RUB", investment_horizon_years: 5, risk_level: "growth", cash_buffer: "1000.00", broker_name: "Т-Инвестиции", fee_rate: "0.0005", minimum_fee: "1.00", created_at: "2026-08-15T22:03:40Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [
        { asset_id: "AAA", version: 2, name: "Asset A", currency: "RUB", lot_size: 1, target_weight: "0.00000000", is_active: false, created_at: "2026-08-15T22:04:47Z" },
        { asset_id: "SU26226RMFS9", version: 1, name: "ОФЗ 26226", currency: "RUB", lot_size: 1, target_weight: "0.00000000", is_active: true, created_at: "2026-08-15T22:04:48Z" },
      ] });
      if (path.endsWith("/v1/portfolio")) return json({ currency: "RUB", total_market_value: "0.00", total_cost_basis: "0.00", total_unrealized_pnl: "0.00", assets: [] });
      if (path.endsWith("/v1/transaction-drafts/manual") && init?.method === "POST") return json(transactionDraft("manual"), 201);
      if (path.endsWith("/v1/transaction-drafts/00000000-0000-0000-0000-000000000020/decisions") && init?.method === "POST") return json(transactionDraft("manual", "confirmed"), 201);
      return json({ error: { code: "UNEXPECTED", message: path } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<PatientCapitalApp />);
    await screen.findByText("Т-Инвестиции");
    fireEvent.click(screen.getAllByRole("button", { name: /Ассистент/ })[0]);
    fireEvent.click(screen.getByText("Расширенный ввод операции"));
    expect(screen.getByRole("option", { name: /Asset A/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Количество"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Цена за единицу"), { target: { value: "992.04" } });
    fireEvent.change(screen.getByLabelText("НКД всего"), { target: { value: "195.16" } });
    fireEvent.change(screen.getByLabelText("Комиссия"), { target: { value: "3.47" } });
    fireEvent.change(screen.getByLabelText("Дата и время"), { target: { value: "2026-08-13T16:34" } });
    const advanced = screen.getByText("Расширенный ввод операции").closest("details");
    expect(advanced).toBeTruthy();
    fireEvent.click(within(advanced!).getByRole("button", { name: "Подготовить черновик" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/v1/transaction-drafts/manual") && init?.method === "POST");
      expect(call).toBeTruthy();
      const payload = JSON.parse(String(call?.[1]?.body));
      expect(payload).toMatchObject({
        asset_id: "SU26226RMFS9",
        quantity: 7,
        unit_price: "992.04",
        accrued_interest_total: "195.16",
        fee: "3.47",
        occurred_at: new Date("2026-08-13T16:34").toISOString(),
      });
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/v1/transactions"))).toBe(false);

    expect(await screen.findByRole("heading", { name: "Черновик операции" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить и записать" }));
    await screen.findByText("Операция подтверждена");
    const decisionCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/decisions") && init?.method === "POST");
    expect(decisionCall).toBeTruthy();
    expect(JSON.parse(String(decisionCall?.[1]?.body))).toMatchObject({
      expected_version: 1,
      decision: "confirm",
      transaction: {
        asset_id: "SU26226RMFS9",
        quantity: 7,
        unit_price: "992.04",
        accrued_interest_total: "195.16",
        fee: "3.47",
      },
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/v1/transactions"))).toBe(false);
  });

  it("turns free text into a reviewable draft and shows unknown fields", async () => {
    const incomplete = {
      ...transactionDraft("text"),
      fields: { side: "BUY", asset_id: "SU26226RMFS9", asset_name: "ОФЗ 26226", quantity: null, unit_price: null, accrued_interest_total: null, fee: null, currency: "RUB", occurred_at: null },
      unknown_fields: ["quantity", "unit_price", "accrued_interest_total", "fee", "occurred_at"],
    };
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 4, base_currency: "RUB", investment_horizon_years: 5, risk_level: "growth", cash_buffer: "0.00", broker_name: "Т-Инвестиции", fee_rate: "0.0005", minimum_fee: "0.00", created_at: "2026-08-15T22:03:40Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [{ asset_id: "SU26226RMFS9", version: 1, name: "ОФЗ 26226", currency: "RUB", lot_size: 1, target_weight: "1.00000000", is_active: true, created_at: "2026-08-15T22:04:48Z" }] });
      if (path.endsWith("/v1/portfolio")) return json({ currency: "RUB", total_market_value: "0.00", total_cost_basis: "0.00", total_unrealized_pnl: "0.00", assets: [] });
      if (path.endsWith("/v1/transaction-drafts/text") && init?.method === "POST") return json(incomplete, 201);
      return json({ error: { code: "UNEXPECTED", message: path } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<PatientCapitalApp />);
    await screen.findByText("Т-Инвестиции");
    fireEvent.click(screen.getAllByRole("button", { name: /Ассистент/ })[0]);
    fireEvent.change(screen.getByLabelText("Что произошло"), { target: { value: "Купил ОФЗ 26226" } });
    const composer = screen.getByLabelText("Что произошло").closest("form");
    expect(composer).toBeTruthy();
    fireEvent.click(within(composer!).getByRole("button", { name: "Подготовить черновик" }));

    expect(await screen.findByText(/Не удалось определить:/)).toBeTruthy();
    expect(screen.getByText(/количество, чистая цена за единицу/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Подтвердить и записать" }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/v1/transactions"))).toBe(false);
  });

  it("uploads a receipt as multipart without forcing a JSON content type", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 4, base_currency: "RUB", investment_horizon_years: 5, risk_level: "growth", cash_buffer: "0.00", broker_name: "Т-Инвестиции", fee_rate: "0.0005", minimum_fee: "0.00", created_at: "2026-08-15T22:03:40Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [{ asset_id: "SU26226RMFS9", version: 1, name: "ОФЗ 26226", currency: "RUB", lot_size: 1, target_weight: "1.00000000", is_active: true, created_at: "2026-08-15T22:04:48Z" }] });
      if (path.endsWith("/v1/portfolio")) return json({ currency: "RUB", total_market_value: "0.00", total_cost_basis: "0.00", total_unrealized_pnl: "0.00", assets: [] });
      if (path.endsWith("/v1/transaction-drafts/image") && init?.method === "POST") return json(transactionDraft("image"), 201);
      return json({ error: { code: "UNEXPECTED", message: path } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<PatientCapitalApp />);
    await screen.findByText("Т-Инвестиции");
    fireEvent.click(screen.getAllByRole("button", { name: /Ассистент/ })[0]);
    const file = new File(["receipt"], "receipt.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("Скриншот операции"), { target: { files: [file] } });

    expect(await screen.findByRole("heading", { name: "Черновик операции" })).toBeTruthy();
    const uploadCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/transaction-drafts/image"));
    expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData);
    expect(new Headers(uploadCall?.[1]?.headers).has("Content-Type")).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/v1/transactions"))).toBe(false);
  });
});
