import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  Info,
  Layers3,
  LineChart as LineChartIcon,
  LoaderCircle,
  Menu,
  Search,
  Star,
  ShieldCheck,
  TrendingUp,
  Trash2,
  X,
} from "lucide-react";
import {
  ApiError,
  addToWatchlist,
  getPrices,
  getProfile,
  getWatchlist,
  refreshWatchlistPrices,
  removeFromWatchlist,
  searchStocks,
  type CompanyProfile,
  type PriceHistory,
  type SearchResult,
  type SecurityKey,
  type StoredPriceHistory,
  type WatchlistEntry,
} from "./api";
import MarketOverview from "./MarketOverview";
import "./App.css";
import "./theme.css";

const PriceChart = lazy(() => import("./PriceChart"));

type PriceSource = "live" | "saved";
const initialSecurity: SecurityKey = { exchange_code: "NSE", symbol: "TCS" };
const ranges = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "1Y", days: 365 },
];

function indiaToday(): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function dateWindow(days: number): { start: string; end: string } {
  const end = indiaToday();
  const startDate = new Date(`${end}T00:00:00Z`);
  startDate.setUTCDate(startDate.getUTCDate() - days);
  return { start: startDate.toISOString().slice(0, 10), end };
}

const money = (value: number, digits = 2) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: digits,
  }).format(value);
const integer = (value: number) => new Intl.NumberFormat("en-IN").format(value);

function shortDate(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}

function longDate(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

function retrievedAt(value: string | null | undefined): string {
  if (!value) return "Not available";
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
    timeZoneName: "short",
  });
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Could not reach the API. Check that the backend is running.";
}

function App() {
  const [selected, setSelected] = useState<SecurityKey>(initialSecurity);
  const [query, setQuery] = useState("TCS");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [live, setLive] = useState<PriceHistory | null>(null);
  const [saved, setSaved] = useState<StoredPriceHistory | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rangeDays, setRangeDays] = useState(90);
  const [priceSource, setPriceSource] = useState<PriceSource>("live");
  const [showDescription, setShowDescription] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [watchlistLoading, setWatchlistLoading] = useState(true);
  const [watchlistBusy, setWatchlistBusy] = useState<string | null>(null);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [watchlistMessage, setWatchlistMessage] = useState<string | null>(null);
  const [legalName, setLegalName] = useState("");
  const [isin, setIsin] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getWatchlist(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setWatchlist(items);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setWatchlistError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setWatchlistLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const { start, end } = dateWindow(rangeDays);
    Promise.allSettled([
      getProfile(selected, controller.signal),
      getPrices(selected, start, end, false, controller.signal),
      getPrices(selected, start, end, true, controller.signal),
    ]).then(([profileResult, liveResult, savedResult]) => {
      if (controller.signal.aborted) return;
      if (profileResult.status === "fulfilled") {
        setProfile(profileResult.value);
        setLegalName((current) => current || profileResult.value.company_name);
        setIsin((current) => current || profileResult.value.isin || "");
      }
      if (liveResult.status === "fulfilled")
        setLive(liveResult.value as PriceHistory);
      else setLiveError(errorMessage(liveResult.reason));
      if (savedResult.status === "fulfilled") {
        setSaved(savedResult.value as StoredPriceHistory);
        if (
          liveResult.status === "rejected" &&
          savedResult.value.bars.length > 0
        )
          setPriceSource("saved");
      } else if (!(
        savedResult.reason instanceof ApiError &&
        savedResult.reason.status === 404
      )) {
        setSavedError(errorMessage(savedResult.reason));
      }
      setLoading(false);
    });
    return () => controller.abort();
  }, [selected, rangeDays]);

  async function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setSearchError("Enter a company name or symbol.");
      return;
    }
    setSearching(true);
    setSearchError(null);
    setResults([]);
    try {
      setResults(await searchStocks(trimmed));
    } catch (error) {
      setSearchError(errorMessage(error));
    } finally {
      setSearching(false);
    }
  }

  function chooseStock(security: SecurityKey) {
    setSelected(security);
    setLoading(true);
    setLiveError(null);
    setSavedError(null);
    setProfile(null);
    setLive(null);
    setSaved(null);
    setQuery(security.symbol);
    setResults([]);
    setPriceSource("live");
    setShowDescription(false);
    setLegalName("");
    setIsin("");
    setWatchlistMessage(null);
    setWatchlistError(null);
    setMobileMenu(false);
    document.getElementById("research")?.scrollIntoView({ behavior: "smooth" });
  }

  async function addCurrentStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!legalName.trim()) {
      setWatchlistError("Enter the confirmed legal name.");
      return;
    }
    setWatchlistBusy("add");
    setWatchlistError(null);
    setWatchlistMessage(null);
    try {
      await addToWatchlist(selected, legalName.trim(), isin.trim() || null);
      setWatchlist(await getWatchlist());
      setWatchlistMessage(
        `${selected.exchange_code}:${selected.symbol} added to My stocks.`,
      );
    } catch (error) {
      setWatchlistError(errorMessage(error));
    } finally {
      setWatchlistBusy(null);
    }
  }

  async function removeTrackedStock(security: SecurityKey) {
    setWatchlistBusy(`remove:${security.exchange_code}:${security.symbol}`);
    setWatchlistError(null);
    setWatchlistMessage(null);
    try {
      await removeFromWatchlist(security);
      setWatchlist(await getWatchlist());
      setWatchlistMessage(
        `${security.exchange_code}:${security.symbol} removed from My stocks. Saved prices remain in PostgreSQL.`,
      );
    } catch (error) {
      setWatchlistError(errorMessage(error));
    } finally {
      setWatchlistBusy(null);
    }
  }

  async function refreshCurrentStock() {
    setWatchlistBusy("refresh");
    setWatchlistError(null);
    setWatchlistMessage(null);
    const { start, end } = dateWindow(rangeDays);
    try {
      const result = await refreshWatchlistPrices(selected, start, end);
      const updated = await getPrices(selected, start, end, true);
      setSaved(updated as StoredPriceHistory);
      setSavedError(null);
      setPriceSource("saved");
      setWatchlist(await getWatchlist());
      setWatchlistMessage(
        `Received ${result.bars_received} daily bars for ${selected.exchange_code}:${selected.symbol}. The saved chart is updated.`,
      );
    } catch (error) {
      setWatchlistError(errorMessage(error));
    } finally {
      setWatchlistBusy(null);
    }
  }

  function chooseRange(days: number) {
    if (days === rangeDays) return;
    setRangeDays(days);
    setLoading(true);
    setLiveError(null);
    setSavedError(null);
    setLive(null);
    setSaved(null);
  }

  const activeBars =
    priceSource === "live" ? (live?.bars ?? []) : (saved?.bars ?? []);
  const first = activeBars[0];
  const latest = activeBars.at(-1);
  const change =
    first && latest && Number(first.close) > 0
      ? (Number(latest.close) / Number(first.close) - 1) * 100
      : null;
  const positive = change !== null && change >= 0;
  const rangeLabel =
    ranges.find((range) => range.days === rangeDays)?.label ?? "3M";
  const companyName =
    profile?.company_name ?? `${selected.symbol} on ${selected.exchange_code}`;
  const activeError = priceSource === "live" ? liveError : savedError;
  const selectedTracked = watchlist.find(
    (item) =>
      item.security.exchange_code === selected.exchange_code &&
      item.security.symbol === selected.symbol,
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <TrendingUp size={23} strokeWidth={2.6} />
          </div>
          <div>
            <strong>EquityIQ</strong>
            <span>Research workspace</span>
          </div>
          <button
            className="mobile-close icon-button"
            aria-label="Close menu"
            onClick={() => setMobileMenu(false)}
          >
            <X size={19} />
          </button>
        </div>
        <div className="sidebar-section-label">YOUR WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          <a
            className="nav-item nav-active"
            href="#market-overview"
            onClick={() => setMobileMenu(false)}
          >
            <BarChart3 size={18} /> Market overview{" "}
            <span className="nav-active-dot" />
          </a>
          <a
            className="nav-item nav-link"
            href="#research"
            onClick={() => setMobileMenu(false)}
          >
            <LineChartIcon size={18} /> Stock research
          </a>
          <a
            className="nav-item nav-link"
            href="#my-stocks"
            onClick={() => setMobileMenu(false)}
          >
            <Star size={18} /> My stocks <span>{watchlist.length}</span>
          </a>
          <div className="nav-item nav-future">
            <BookOpen size={18} /> Research reports <span>Later</span>
          </div>
          <div className="nav-item nav-future">
            <BarChart3 size={18} /> Portfolio <span>Later</span>
          </div>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <div className="sidebar-note-icon">
              <ShieldCheck size={18} />
            </div>
            <strong>Context for better decisions</strong>
            <p>
              Real data, clear sources, and room to think. This workspace does
              not place trades.
            </p>
          </div>
          <div className="sidebar-version">
            <span className="status-dot" /> Personal workspace <span>v0.1</span>
          </div>
        </div>
      </aside>

      <div className="content-shell">
        <header className="topbar">
          <button
            className="mobile-menu icon-button"
            aria-label="Open menu"
            onClick={() => setMobileMenu(true)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            EquityIQ <ChevronRight size={14} /> <strong>Market overview</strong>
          </div>
          <div className="topbar-right">
            <span className="topbar-local">
              <span className="status-dot" /> Local mode
            </span>
            <span className="topbar-date">
              <CalendarDays size={15} /> {longDate(indiaToday())}
            </span>
          </div>
        </header>
        <main className="main-content">
          <section className="intro-section premium-hero" id="top">
            <div className="eyebrow">
              <span /> INDIA EQUITIES · NSE & BSE
            </div>
            <div className="intro-heading-row">
              <div>
                <h1>
                  Invest with context.
                  <br />
                  <em>Move with clarity.</em>
                </h1>
                <p>
                  A considered view of the Indian market. Discover daily movers,
                  explore businesses, and keep your own research close.
                </p>
                <div className="hero-links">
                  <a href="#market-overview">
                    Explore the market <ArrowRight size={16} />
                  </a>
                  <a href="#research">Research a stock</a>
                </div>
              </div>
              <div className="intro-illustration" aria-hidden="true">
                <span className="hero-visual-top">EQUITY / INTELLIGENCE</span>
                <span className="hero-visual-mark">
                  IQ<span>.</span>
                </span>
                <span className="hero-visual-bottom">
                  RESEARCH FIRST. DECIDE YOURSELF.
                </span>
              </div>
            </div>
            <div className="hero-search-label">FIND A COMPANY</div>
            <form className="search-form" onSubmit={onSearch}>
              <Search size={20} aria-hidden="true" />
              <label className="sr-only" htmlFor="stock-search">
                Search stocks
              </label>
              <input
                id="stock-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search an NSE or BSE company, e.g. TCS"
                autoComplete="off"
              />
              <button type="submit" disabled={searching}>
                {searching ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  "Explore"
                )}
                <ArrowRight size={17} />
              </button>
            </form>
            {searchError && (
              <div className="inline-alert" role="alert">
                {searchError}
              </div>
            )}
            {results.length > 0 && (
              <div className="search-results" aria-label="Stock search results">
                <div className="search-results-title">
                  MATCHING LISTINGS <span>{results.length} found</span>
                </div>
                {results.map((result) => (
                  <button
                    key={`${result.security.exchange_code}:${result.security.symbol}`}
                    type="button"
                    onClick={() => chooseStock(result.security)}
                  >
                    <span className="result-symbol">
                      {result.security.symbol.slice(0, 2)}
                    </span>
                    <span className="result-details">
                      <strong>{result.company_name}</strong>
                      <small>
                        {result.security.exchange_code} ·{" "}
                        {result.security.symbol}
                      </small>
                    </span>
                    <ChevronRight size={17} />
                  </button>
                ))}
              </div>
            )}
            {!searching && !searchError && results.length === 0 && (
              <div className="search-hint">
                <Info size={14} /> Search results keep NSE and BSE listings
                separate.
              </div>
            )}
          </section>

          <MarketOverview onSelect={chooseStock} />

          <div className="research-section-heading">
            <span>02 / DEEP DIVE</span>
            <h2>
              Research the business<span>.</span>
            </h2>
            <p>Price history and company context for the listing you select.</p>
          </div>

          <section
            className="company-heading"
            id="research"
            aria-label="Selected stock"
          >
            <div className="company-heading-main">
              <div className="company-avatar">
                {selected.symbol.slice(0, 2)}
              </div>
              <div>
                <div className="company-kicker">
                  CURRENTLY EXPLORING <span>{selected.exchange_code}</span>
                </div>
                <h2>{companyName}</h2>
                <div className="company-subtitle">
                  {selected.exchange_code}:{selected.symbol} <span>·</span>{" "}
                  {profile?.sector ?? "Company profile"}{" "}
                  {profile?.industry ? `· ${profile.industry}` : ""}
                </div>
              </div>
            </div>
            {profile?.source.url && (
              <a
                className="source-link"
                href={profile.source.url}
                target="_blank"
                rel="noreferrer"
              >
                View source <ExternalLink size={15} />
              </a>
            )}
          </section>

          <section
            id="my-stocks"
            className="watchlist-card card"
            aria-label="My stocks"
          >
            <div className="watchlist-header">
              <div>
                <span className="section-eyebrow">PERSONAL RESEARCH LIST</span>
                <h3>
                  My stocks <span>{watchlist.length}</span>
                </h3>
                <p>
                  Keep the listings you want to follow and choose when to save
                  their daily prices.
                </p>
              </div>
              <Star size={21} strokeWidth={1.6} />
            </div>
            <div className="watchlist-layout">
              <div className="watchlist-items">
                {watchlistLoading ? (
                  <div className="watchlist-empty">Loading your stocks...</div>
                ) : watchlist.length === 0 ? (
                  <div className="watchlist-empty">
                    No tracked stocks yet. Search for a listing above, then add
                    it here.
                  </div>
                ) : (
                  watchlist.map((item) => (
                    <div className="watchlist-row" key={item.id}>
                      <button
                        type="button"
                        className="watchlist-select"
                        onClick={() => chooseStock(item.security)}
                        aria-label={`Explore ${item.security.exchange_code}:${item.security.symbol}`}
                      >
                        <span className="watchlist-symbol">
                          {item.security.symbol.slice(0, 2)}
                        </span>
                        <span className="watchlist-company">
                          <strong>{item.legal_name}</strong>
                          <small>
                            {item.security.exchange_code}:{item.security.symbol}{" "}
                            · {item.saved_price_count} saved days
                            {item.latest_saved_day
                              ? ` · through ${shortDate(item.latest_saved_day)}`
                              : ""}
                          </small>
                        </span>
                      </button>
                      <button
                        type="button"
                        className="watchlist-remove icon-button"
                        onClick={() => removeTrackedStock(item.security)}
                        disabled={watchlistBusy !== null}
                        aria-label={`Remove ${item.security.exchange_code}:${item.security.symbol} from My stocks`}
                        title="Remove from My stocks; saved prices stay in PostgreSQL"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))
                )}
              </div>
              <div className="watchlist-action">
                <span className="section-eyebrow">SELECTED LISTING</span>
                <strong>
                  {selected.exchange_code}:{selected.symbol}
                </strong>
                {watchlistLoading ? (
                  <p>Checking your saved list...</p>
                ) : selectedTracked ? (
                  <>
                    <p>
                      Save or update up to one year of daily prices for the
                      selected chart range. Existing rows are refreshed safely.
                    </p>
                    <button
                      type="button"
                      className="watchlist-primary"
                      onClick={refreshCurrentStock}
                      disabled={watchlistBusy !== null}
                    >
                      {watchlistBusy === "refresh" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <Database size={15} />
                      )}
                      Save {rangeLabel} price history
                    </button>
                  </>
                ) : profile ? (
                  <form onSubmit={addCurrentStock}>
                    <label htmlFor="legal-name">
                      Confirm legal company name
                    </label>
                    <input
                      id="legal-name"
                      value={legalName}
                      onChange={(event) => setLegalName(event.target.value)}
                      maxLength={255}
                      required
                    />
                    <label htmlFor="listing-isin">ISIN (optional)</label>
                    <input
                      id="listing-isin"
                      value={isin}
                      onChange={(event) =>
                        setIsin(event.target.value.toUpperCase())
                      }
                      maxLength={12}
                      pattern="[A-Z0-9]{12}"
                      placeholder="12-character ISIN"
                    />
                    <p>
                      Check the legal name and ISIN against the NSE or BSE
                      listing. Yahoo values are only a starting point.
                    </p>
                    <button
                      type="submit"
                      className="watchlist-primary"
                      disabled={watchlistBusy !== null}
                    >
                      {watchlistBusy === "add" ? (
                        <LoaderCircle className="spin" size={15} />
                      ) : (
                        <Star size={15} />
                      )}
                      Add to My stocks
                    </button>
                  </form>
                ) : (
                  <p>Choose a valid listing from search to add it.</p>
                )}
              </div>
            </div>
            {watchlistError && (
              <div className="inline-alert" role="alert">
                {watchlistError}
              </div>
            )}
            {watchlistMessage && (
              <div className="watchlist-message" role="status">
                {watchlistMessage}
              </div>
            )}
          </section>

          <div className="dashboard-grid">
            <section className="price-card card">
              <div className="section-heading">
                <div>
                  <span className="section-eyebrow">PRICE HISTORY</span>
                  <h3>Market performance</h3>
                </div>
                <div className="range-tabs" aria-label="Price date range">
                  {ranges.map((range) => (
                    <button
                      key={range.label}
                      type="button"
                      className={rangeDays === range.days ? "active" : ""}
                      onClick={() => chooseRange(range.days)}
                    >
                      {range.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="price-summary">
                <div>
                  <div className="price-label">
                    Latest close{" "}
                    <span>· {latest ? longDate(latest.trading_day) : "—"}</span>
                  </div>
                  <div className="big-price">
                    {latest ? money(Number(latest.close)) : "—"}
                  </div>
                </div>
                {change !== null && (
                  <div
                    className={`change-badge ${positive ? "change-positive" : "change-negative"}`}
                  >
                    {positive ? (
                      <ArrowUpRight size={18} />
                    ) : (
                      <ArrowDownRight size={18} />
                    )}
                    {positive ? "+" : ""}
                    {change.toFixed(2)}% <small>in {rangeLabel}</small>
                  </div>
                )}
              </div>
              <div className="source-tabs" aria-label="Price data source">
                <button
                  type="button"
                  className={priceSource === "live" ? "selected" : ""}
                  onClick={() => setPriceSource("live")}
                >
                  <Activity size={15} /> Live provider
                </button>
                <button
                  type="button"
                  className={priceSource === "saved" ? "selected" : ""}
                  onClick={() => setPriceSource("saved")}
                >
                  <Database size={15} /> Saved in PostgreSQL{" "}
                  {saved?.bars.length ? <span>{saved.bars.length}</span> : null}
                </button>
              </div>
              {loading ? (
                <div className="chart-loading">
                  <LoaderCircle className="spin" size={25} /> Loading stock
                  data…
                </div>
              ) : activeError ? (
                <div className="chart-empty" role="alert">
                  <Info size={27} />
                  <strong>Price data unavailable</strong>
                  <span>{activeError}</span>
                </div>
              ) : (
                <Suspense
                  fallback={<div className="chart-loading">Loading chart…</div>}
                >
                  <PriceChart
                    bars={activeBars}
                    shortDate={shortDate}
                    longDate={longDate}
                    money={money}
                    integer={integer}
                  />
                </Suspense>
              )}
              <div className="chart-footer">
                <span>
                  <span className="legend-dot" /> Daily closing price ·{" "}
                  {priceSource === "saved" ? "saved snapshot" : "Yahoo Finance"}
                </span>
                <span>{activeBars.length} trading days shown</span>
              </div>
            </section>

            <aside className="side-column">
              <section className="snapshot-card card">
                <div className="side-card-title">
                  <span className="side-icon teal">
                    <Database size={17} />
                  </span>
                  <div>
                    <span className="section-eyebrow">YOUR DATA</span>
                    <h3>Saved snapshot</h3>
                  </div>
                </div>
                <div className="snapshot-count">
                  {saved?.bars.length ?? 0}
                  <span>stored trading days in this range</span>
                </div>
                <div className="snapshot-details">
                  <div>
                    <span>Listing</span>
                    <strong>
                      {selected.exchange_code}:{selected.symbol}
                    </strong>
                  </div>
                  <div>
                    <span>Last retrieved</span>
                    <strong>{retrievedAt(saved?.newest_retrieved_at)}</strong>
                  </div>
                  <div>
                    <span>Price basis</span>
                    <strong>
                      {saved?.adjustment?.replaceAll("_", " ") ??
                        "No saved bars"}
                    </strong>
                  </div>
                </div>
                <p className="small-note">
                  These rows are stored in your local PostgreSQL database. They
                  are separate from your live provider request.
                </p>
              </section>
              <section className="guide-card card">
                <div className="side-card-title">
                  <span className="side-icon amber">
                    <BookOpen size={17} />
                  </span>
                  <div>
                    <span className="section-eyebrow">LEARN AS YOU GO</span>
                    <h3>Reading the chart</h3>
                  </div>
                </div>
                <p>
                  Each point is one trading day’s closing price. A rising line
                  shows what happened during the selected period; it does not
                  tell us what happens next.
                </p>
                <div className="guide-foot">
                  <CheckCircle2 size={16} /> Historical data, clearly labelled
                </div>
              </section>
            </aside>

            <section className="metrics-card card">
              <div className="section-heading">
                <div>
                  <span className="section-eyebrow">AT A GLANCE</span>
                  <h3>Price context</h3>
                </div>
                <span className="muted-caption">
                  Based on the selected source and range
                </span>
              </div>
              <div className="metrics-grid">
                <div className="metric">
                  <span>
                    <TrendingUp size={16} /> Period high
                  </span>
                  <strong>
                    {activeBars.length
                      ? money(
                          Math.max(
                            ...activeBars.map((bar) => Number(bar.high)),
                          ),
                        )
                      : "—"}
                  </strong>
                  <small>Highest daily high</small>
                </div>
                <div className="metric">
                  <span>
                    <ArrowDownRight size={16} /> Period low
                  </span>
                  <strong>
                    {activeBars.length
                      ? money(
                          Math.min(...activeBars.map((bar) => Number(bar.low))),
                        )
                      : "—"}
                  </strong>
                  <small>Lowest daily low</small>
                </div>
                <div className="metric">
                  <span>
                    <BarChart3 size={16} /> Latest volume
                  </span>
                  <strong>
                    {latest?.volume == null ? "—" : integer(latest.volume)}
                  </strong>
                  <small>Shares reported</small>
                </div>
                <div className="metric">
                  <span>
                    <Clock3 size={16} /> Retrieved
                  </span>
                  <strong className="metric-date">
                    {retrievedAt(
                      priceSource === "live"
                        ? live?.source.retrieved_at
                        : saved?.newest_retrieved_at,
                    )}
                  </strong>
                  <small>India time</small>
                </div>
              </div>
            </section>
            <section className="profile-card card">
              <div className="section-heading">
                <div>
                  <span className="section-eyebrow">THE BUSINESS</span>
                  <h3>Company overview</h3>
                </div>
                <span className="profile-icon">
                  <Layers3 size={19} />
                </span>
              </div>
              {profile ? (
                <>
                  <div className="profile-tags">
                    {profile.sector && <span>{profile.sector}</span>}
                    {profile.industry && <span>{profile.industry}</span>}
                    {profile.country_code && (
                      <span>{profile.country_code}</span>
                    )}
                  </div>
                  <p
                    className={
                      showDescription ? "description expanded" : "description"
                    }
                  >
                    {profile.description ||
                      "No business description is available from this provider."}
                  </p>
                  {profile.description && profile.description.length > 280 && (
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => setShowDescription(!showDescription)}
                    >
                      {showDescription ? "Show less" : "Read more"}{" "}
                      <ArrowRight size={15} />
                    </button>
                  )}
                </>
              ) : (
                <p className="description">
                  {loading
                    ? "Loading company details…"
                    : "Company details are unavailable right now."}
                </p>
              )}
            </section>
          </div>
          <div className="data-note">
            <Info size={16} />
            <span>
              EquityIQ is a research workspace. This screen shows historical
              market data and company context; it does not make a buy or sell
              recommendation.
            </span>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
