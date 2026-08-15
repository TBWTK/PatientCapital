import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PatientCapitalApp } from "../app/patient-capital-app";

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  }));

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

  it("starts the primary flow from 8000 rubles and renders sourced automatic candidates", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/v1/profile")) return json({ version: 3, base_currency: "RUB", investment_horizon_years: 5, risk_level: "balanced", cash_buffer: "0.00", broker_name: "Demo Broker", fee_rate: "0.001", minimum_fee: "1.00", created_at: "2026-08-15T00:00:00Z" });
      if (path.endsWith("/v1/assets")) return json({ assets: [] });
      if (path.endsWith("/v1/portfolio")) return json({ currency: "RUB", total_market_value: "0.00", total_cost_basis: "0.00", total_unrealized_pnl: "0.00", assets: [] });
      if (path.endsWith("/v1/discovery/recommendations") && init?.method === "POST") return json({
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
        lines: [{ asset_id: "SU26218RMFS6", lots: 9, lot_size: 1, quantity: 9, unit_price: "818.21000000", current_value: "0.00", target_value: "4800.00", pre_drift: "-4800.00", post_drift: "2563.89", gross: "7363.89", fee: "7.36", total: "7371.25" }],
      }, 201);
      return json({ error: { code: "UNEXPECTED", message: path } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<PatientCapitalApp />);
    await screen.findByText("Demo Broker");
    fireEvent.click(screen.getAllByRole("button", { name: /Пополнение/ })[0]);
    expect((screen.getByLabelText("Сумма пополнения") as HTMLInputElement).value).toBe("8000");
    fireEvent.click(screen.getByRole("button", { name: "Подобрать активы" }));

    expect((await screen.findAllByRole("heading", { name: "ОФЗ 26218" })).length).toBe(2);
    expect(screen.getByRole("link", { name: "Котировка MOEX ↗" }).getAttribute("href")).toBe("https://iss.moex.com/ofz");
    const discoveryCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/discovery/recommendations"));
    expect(discoveryCall?.[1]?.body).toBe(JSON.stringify({ contribution: "8000" }));
  });
});
