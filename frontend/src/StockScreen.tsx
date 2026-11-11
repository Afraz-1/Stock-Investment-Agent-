import { useEffect, useState } from "react";
import { getMarketMovers, type MarketMovers, type MarketMover } from "./api";
import "./StockScreen.css";

const questions = [
  "I can explain how this company earns money and what could go wrong.",
  "I checked recent official company filings and the dates behind the figures.",
  "I set a position size and a maximum loss I can accept.",
  "I checked how this position affects concentration across my holdings.",
  "I wrote my time horizon and the conditions that would change my decision.",
];
type Review = { checked: boolean[]; notes: string };
const blank = (): Review => ({
  checked: questions.map(() => false),
  notes: "",
});
const crore = (value: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(
    value / 10_000_000,
  );
const integer = (value: number) => new Intl.NumberFormat("en-IN").format(value);

export default function StockScreen() {
  const [data, setData] = useState<MarketMovers | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [minCap, setMinCap] = useState(10000);
  const [minVolume, setMinVolume] = useState(100000);
  const [minChange, setMinChange] = useState(-100);
  const [maxChange, setMaxChange] = useState(100);
  const [sort, setSort] = useState<"cap" | "change" | "volume">("cap");
  const [selected, setSelected] = useState<MarketMover | null>(null);
  const [review, setReview] = useState<Review>(blank);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getMarketMovers(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "The screened Yahoo sample could not load. Try again later.",
          );
      });
    return () => controller.abort();
  }, [revision]);

  const candidates = (data?.candidates ?? []).filter(
    (item) =>
      item.market_cap_inr >= minCap * 10_000_000 &&
      item.volume >= minVolume &&
      Number(item.change_percent) >= minChange &&
      Number(item.change_percent) <= maxChange,
  );
  candidates.sort((a, b) =>
    sort === "volume"
      ? b.volume - a.volume
      : sort === "change"
        ? Number(b.change_percent) - Number(a.change_percent)
        : b.market_cap_inr - a.market_cap_inr,
  );

  function select(item: MarketMover) {
    setSelected(item);
    setSaved(false);
    try {
      const raw = localStorage.getItem(
        `equityiq:review:${item.security.exchange_code}:${item.security.symbol}`,
      );
      const parsed = raw ? (JSON.parse(raw) as Review) : null;
      setReview(
        parsed &&
          Array.isArray(parsed.checked) &&
          typeof parsed.notes === "string"
          ? parsed
          : blank(),
      );
    } catch {
      setReview(blank());
    }
  }

  function saveReview() {
    if (!selected) return;
    try {
      localStorage.setItem(
        `equityiq:review:${selected.security.exchange_code}:${selected.security.symbol}`,
        JSON.stringify(review),
      );
      setSaved(true);
    } catch {
      setSaved(false);
    }
  }

  return (
    <section className="stock-screen">
      <div className="page-heading">
        <span>DISCOVERY TOOL</span>
        <h1>
          Stock screen<span>.</span>
        </h1>
        <p>
          Filter a bounded Yahoo NSE candidate sample using visible criteria.
          Results are research leads, not ranked investment picks.
        </p>
      </div>
      <div className="screen-controls card">
        <label>
          Minimum market cap (₹ crore)
          <input
            type="number"
            min="10000"
            step="1000"
            value={minCap}
            onChange={(event) => setMinCap(Number(event.target.value))}
          />
        </label>
        <label>
          Minimum daily volume
          <input
            type="number"
            min="100000"
            step="10000"
            value={minVolume}
            onChange={(event) => setMinVolume(Number(event.target.value))}
          />
        </label>
        <label>
          Daily change from (%)
          <input
            type="number"
            min="-100"
            max="100"
            value={minChange}
            onChange={(event) => setMinChange(Number(event.target.value))}
          />
        </label>
        <label>
          Daily change to (%)
          <input
            type="number"
            min="-100"
            max="100"
            value={maxChange}
            onChange={(event) => setMaxChange(Number(event.target.value))}
          />
        </label>
        <label>
          Sort by
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as typeof sort)}
          >
            <option value="cap">Market cap</option>
            <option value="change">Daily change</option>
            <option value="volume">Volume</option>
          </select>
        </label>
      </div>
      <p className="screen-context">
        Yahoo supplies up to 30 rising and 30 falling NSE candidates with market
        cap ≥ ₹10,000 crore and volume ≥ 1 lakh shares. Only quotes from the
        latest date in that response are included. This is not the full NSE
        market.
      </p>
      {error ? (
        <div role="alert" className="inline-alert">
          {error}{" "}
          <button
            type="button"
            onClick={() => {
              setError(null);
              setRevision((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : !data ? (
        <p role="status">Loading screened candidates…</p>
      ) : (
        <>
          <p className="screen-context">
            {candidates.length} of {data.candidates.length} candidates match ·
            quote day {data.as_of_day} · retrieved{" "}
            {new Date(data.retrieved_at).toLocaleString("en-IN", {
              timeZone: "Asia/Kolkata",
            })}
          </p>
          <div className="screen-table-wrap card">
            <table>
              <thead>
                <tr>
                  <th>Listing</th>
                  <th>Market cap</th>
                  <th>Volume</th>
                  <th>Daily change</th>
                  <th>Quote time</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {candidates.map((item) => (
                  <tr key={item.security.symbol}>
                    <td>
                      <strong>{item.company_name}</strong>
                      <small>NSE:{item.security.symbol}</small>
                    </td>
                    <td>₹{crore(item.market_cap_inr)} cr</td>
                    <td>{integer(item.volume)}</td>
                    <td>{Number(item.change_percent).toFixed(2)}%</td>
                    <td>
                      {new Date(item.quote_at).toLocaleString("en-IN", {
                        timeZone: "Asia/Kolkata",
                      })}
                    </td>
                    <td>
                      <button type="button" onClick={() => select(item)}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {candidates.length === 0 && (
              <p>No candidates match these filters in this sample.</p>
            )}
          </div>
        </>
      )}
      {selected && (
        <section className="risk-review card">
          <h2>Risk checklist · NSE:{selected.security.symbol}</h2>
          <p>
            Use this as a prompt for your own research. Ticking a box does not
            verify the underlying fact.
          </p>
          {questions.map((question, index) => (
            <label className="risk-question" key={question}>
              <input
                type="checkbox"
                checked={review.checked[index] ?? false}
                onChange={(event) => {
                  const checked = [...review.checked];
                  checked[index] = event.target.checked;
                  setReview({ ...review, checked });
                  setSaved(false);
                }}
              />
              {question}
            </label>
          ))}
          <label className="risk-notes">
            Open questions and risks
            <textarea
              value={review.notes}
              onChange={(event) => {
                setReview({ ...review, notes: event.target.value });
                setSaved(false);
              }}
              maxLength={4000}
            />
          </label>
          <button type="button" onClick={saveReview}>
            Save checklist on this browser
          </button>
          {saved && <span role="status"> Saved locally</span>}
          <p>
            Checklist data is kept in this browser only. It is not part of your
            PostgreSQL portfolio or synced to another device.
          </p>
        </section>
      )}
    </section>
  );
}
