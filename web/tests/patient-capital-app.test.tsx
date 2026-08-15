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
    expect(await screen.findByRole("heading", { name: "Соберите основу портфеля" })).toBeTruthy();
    const accessibility = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(accessibility.violations.map((violation) => violation.id)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: /Настроить профиль/ }));
    expect(screen.getByRole("heading", { name: "Профиль и модель портфеля" })).toBeTruthy();
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
});
