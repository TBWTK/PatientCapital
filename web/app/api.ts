import type { components } from "./api-types";

export type Profile = components["schemas"]["ProfileResponse"];
export type Asset = components["schemas"]["AssetResponse"];
export type Portfolio = components["schemas"]["PortfolioResponse"];
export type Recommendation = components["schemas"]["RecommendationResponse"];
export type ProposalSet = components["schemas"]["ProposalSetResponse"];
export type Transaction = components["schemas"]["TransactionResponse"];

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const payload = (await response.json()) as {
    error?: { code?: string; message?: string };
  } & T;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload.error?.code ?? "REQUEST_FAILED",
      payload.error?.message ?? "Не удалось выполнить запрос",
    );
  }
  return payload;
}
