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

export interface WatchlistEntry {
  id: number;
  security: SecurityKey;
  legal_name: string;
  isin: string | null;
  saved_price_count: number;
  latest_saved_day: string | null;
  added_at: string;
}

export interface RefreshResult {
  security: SecurityKey;
  start: string;
  end: string;
  bars_received: number;
}

export interface MarketMover {
  security: SecurityKey;
  company_name: string;
  price: string;
  previous_close: string;
  change_percent: string;
  volume: number;
  quote_at: string;
  source_url: string;
}

export interface MarketMovers {
  as_of_day: string;
  latest_quote_at: string;
  retrieved_at: string;
  min_market_cap_inr: number;
  min_day_volume: number;
  gainers: MarketMover[];
  losers: MarketMover[];
  source_url: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, { ...init, signal });
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

async function sendJson<T>(path: string, body?: object): Promise<T> {
  return getJson<T>(path, undefined, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
}

function listingPath(security: SecurityKey): string {
  return `/api/v1/stocks/${encodeURIComponent(security.exchange_code)}/${encodeURIComponent(security.symbol)}`;
}

function watchlistPath(security: SecurityKey): string {
  return `/api/v1/watchlist/${encodeURIComponent(security.exchange_code)}/${encodeURIComponent(security.symbol)}`;
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

export function getWatchlist(signal?: AbortSignal): Promise<WatchlistEntry[]> {
  return getJson("/api/v1/watchlist", signal);
}

export function getMarketMovers(signal?: AbortSignal): Promise<MarketMovers> {
  return getJson("/api/v1/market/movers", signal);
}

export function addToWatchlist(
  security: SecurityKey,
  legalName: string,
  isin: string | null,
): Promise<WatchlistEntry> {
  return sendJson("/api/v1/watchlist", {
    ...security,
    legal_name: legalName,
    isin,
  });
}

export async function removeFromWatchlist(
  security: SecurityKey,
): Promise<void> {
  const response = await fetch(watchlistPath(security), {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }
}

export function refreshWatchlistPrices(
  security: SecurityKey,
  start: string,
  end: string,
): Promise<RefreshResult> {
  return sendJson(
    `${watchlistPath(security)}/refresh-prices?start=${start}&end=${end}`,
  );
}
