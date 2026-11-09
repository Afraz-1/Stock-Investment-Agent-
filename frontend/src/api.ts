export interface SecurityKey {
  exchange_code: "NSE" | "BSE";
  symbol: string;
}

export interface DataSource {
  provider: string;
  retrieved_at: string;
  published_at: string | null;
  url: string | null;
}

export interface SearchResult {
  security: SecurityKey;
  company_name: string;
  isin: string | null;
  currency_code: string | null;
  source: DataSource;
}

export interface CompanyProfile extends SearchResult {
  country_code: string | null;
  sector: string | null;
  industry: string | null;
  description: string | null;
}

export interface PriceBar {
  trading_day: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number | null;
}

export interface PriceHistory {
  security: SecurityKey;
  currency_code: string | null;
  adjustment: "raw" | "split_adjusted" | "dividend_adjusted" | "unknown";
  bars: PriceBar[];
  unavailable_reason: "no_data" | "unsupported" | null;
  warnings: string[];
  source: DataSource;
}

export interface StoredPriceHistory {
  security: SecurityKey;
  currency_code: string;
  provider: string;
  adjustment: PriceHistory["adjustment"];
  bars: PriceBar[];
  oldest_retrieved_at: string | null;
  newest_retrieved_at: string | null;
  unavailable_reason: "no_data" | null;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

function listingPath(security: SecurityKey): string {
  return `/api/v1/stocks/${encodeURIComponent(security.exchange_code)}/${encodeURIComponent(security.symbol)}`;
}

export function searchStocks(
  query: string,
  signal?: AbortSignal,
): Promise<SearchResult[]> {
  return getJson(
    `/api/v1/stocks/search?q=${encodeURIComponent(query)}&limit=12`,
    signal,
  );
}

export function getProfile(
  security: SecurityKey,
  signal?: AbortSignal,
): Promise<CompanyProfile> {
  return getJson(`${listingPath(security)}/profile`, signal);
}

export function getPrices(
  security: SecurityKey,
  start: string,
  end: string,
  saved: boolean,
  signal?: AbortSignal,
): Promise<PriceHistory | StoredPriceHistory> {
  const kind = saved ? "saved-prices" : "prices";
  return getJson(
    `${listingPath(security)}/${kind}?start=${start}&end=${end}`,
    signal,
  );
}
