import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  ExternalLink,
  LoaderCircle,
} from "lucide-react";
import {
  ApiError,
  getMarketMovers,
  type MarketMover,
  type MarketMovers,
  type SecurityKey,
} from "./api";
import "./MarketOverview.css";

function money(value: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function quoteTime(value: string): string {
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
    timeZoneName: "short",
  });
}

function MoverList({
  title,
  direction,
  items,
  onSelect,
}: {
  title: string;
  direction: "up" | "down";
  items: MarketMover[];
  onSelect: (security: SecurityKey) => void;
}) {
  return (
    <div className="mover-list">
      <div className="mover-list-head">
        <span className={`mover-direction mover-${direction}`}>
          {direction === "up" ? (
            <ArrowUpRight size={17} />
          ) : (
            <ArrowDownRight size={17} />
          )}
        </span>
        <h3>{title}</h3>
        <span className="mover-list-count">
          {items.length.toString().padStart(2, "0")}
        </span>
      </div>
      {items.length === 0 ? (
        <div className="mover-empty">
          No qualifying {direction === "up" ? "gainers" : "losers"} in this
          session.
        </div>
      ) : (
        <div className="mover-rows">
          {items.map((item, index) => (
            <button
              type="button"
              className="mover-row"
              key={`${item.security.exchange_code}:${item.security.symbol}`}
              onClick={() => onSelect(item.security)}
              aria-label={`Research ${item.company_name}, ${item.change_percent}%`}
            >
              <span className="mover-rank">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="mover-identity">
                <strong>{item.company_name}</strong>
                <small>
                  {item.security.symbol} <span>·</span> NSE
                </small>
              </span>
              <span className="mover-price">
                <strong>{money(item.price)}</strong>
                <small>Prev. {money(item.previous_close)}</small>
              </span>
              <span className={`mover-change mover-change-${direction}`}>
                {direction === "up" ? "+" : ""}
                {Number(item.change_percent).toFixed(2)}%
              </span>
              <ArrowRight className="mover-row-arrow" size={16} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MarketOverview({
  onSelect,
}: {
  onSelect: (security: SecurityKey) => void;
}) {
  const [data, setData] = useState<MarketMovers | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    getMarketMovers(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "The market overview could not load. Check the backend connection.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  return (
    <section
      className="market-overview"
      id="market-overview"
      aria-labelledby="market-title"
    >
      <div className="market-section-heading">
        <div>
          <span className="market-section-index">
            01 <span>/</span> DISCOVER
          </span>
          <h2 id="market-title">
            The market, in motion<span>.</span>
          </h2>
          <p>Top daily gainers and losers among screened NSE equities.</p>
        </div>
        <div className="market-session">
          <span className="market-session-dot" />
          <div>
            <small>LATEST QUOTE</small>
            <strong>
              {data ? quoteTime(data.latest_quote_at) : "Checking market data"}
            </strong>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="market-loading" role="status">
          <LoaderCircle className="spin" size={24} /> Loading market movers…
        </div>
      ) : error ? (
        <div className="market-error" role="alert">
          <strong>Market overview unavailable</strong>
          <span>{error}</span>
        </div>
      ) : data ? (
        <div className="market-lists">
          <MoverList
            title="Top gainers"
            direction="up"
            items={data.gainers}
            onSelect={onSelect}
          />
          <MoverList
            title="Top losers"
            direction="down"
            items={data.losers}
            onSelect={onSelect}
          />
        </div>
      ) : null}

      <div className="market-footnote">
        <span>
          Universe: NSE equities screened by Yahoo with market cap ≥ ₹10,000
          crore and daily volume ≥ 1 lakh shares. Moves are versus previous
          close; quotes may be delayed. A price move is not a recommendation.
        </span>
        <a
          href={data?.source_url ?? "https://finance.yahoo.com/screener/"}
          target="_blank"
          rel="noreferrer"
        >
          Yahoo Finance <ExternalLink size={13} />
        </a>
      </div>
    </section>
  );
}
