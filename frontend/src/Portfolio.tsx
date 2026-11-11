import { useEffect, useState, type FormEvent } from "react";
import {
  addJournal,
  getPortfolio,
  getWatchlist,
  recordTrade,
  removeTrade,
  updateJournalOutcome,
  type PortfolioData,
  type SecurityKey,
  type WatchlistEntry,
} from "./api";
import "./Portfolio.css";

const money = (value: string) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
const listing = (key: SecurityKey) => `${key.exchange_code}:${key.symbol}`;

export default function Portfolio() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [selected, setSelected] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [day, setDay] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("0");
  const [note, setNote] = useState("");
  const [thesis, setThesis] = useState("");
  const [outcomes, setOutcomes] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getPortfolio(controller.signal),
      getWatchlist(controller.signal),
    ])
      .then(([portfolio, stocks]) => {
        if (controller.signal.aborted) return;
        setData(portfolio);
        setWatchlist(stocks);
        if (stocks[0]) setSelected(listing(stocks[0].security));
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Portfolio could not load. Check the database and backend.");
      });
    return () => controller.abort();
  }, []);

  async function reload() {
    setData(await getPortfolio());
  }
  const security = watchlist.find(
    (item) => listing(item.security) === selected,
  )?.security;

  async function submitTrade(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!security) return;
    setBusy(true);
    setError(null);
    try {
      await recordTrade({
        security,
        trade_day: day,
        side,
        quantity,
        price,
        fees,
        note,
      });
      await reload();
      setQuantity("");
      setPrice("");
      setNote("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Trade could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitThesis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!security) return;
    setBusy(true);
    setError(null);
    try {
      await addJournal(security, thesis.trim());
      await reload();
      setThesis("");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Journal entry could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveOutcome(id: number) {
    setBusy(true);
    setError(null);
    try {
      await updateJournalOutcome(id, outcomes[id].trim());
      await reload();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Outcome could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }

  async function deleteTrade(id: number) {
    if (!window.confirm("Remove this recorded trade? This cannot be undone."))
      return;
    setBusy(true);
    setError(null);
    try {
      await removeTrade(id);
      await reload();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Trade could not be removed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="portfolio-page">
      <div className="page-heading">
        <span>PERSONAL WORKSPACE</span>
        <h1>
          Portfolio &amp; journal<span>.</span>
        </h1>
        <p>
          Record trades manually and write down your reasoning. This page does
          not connect to your broker or place orders.
        </p>
      </div>
      {error && (
        <div className="inline-alert" role="alert">
          {error}
        </div>
      )}
      {!data ? (
        <p role="status">Loading portfolio…</p>
      ) : (
        <>
          <div className="portfolio-summary card">
            <div>
              <small>OPEN HOLDINGS</small>
              <strong>{data.holdings.length}</strong>
            </div>
            <div>
              <small>REALIZED P/L</small>
              <strong>{money(data.realized_pnl)}</strong>
            </div>
            <p>
              Average cost includes recorded buy fees. Realized P/L deducts
              recorded sell fees. Open positions have no live valuation here.
            </p>
          </div>
          <div className="portfolio-grid">
            <section className="card portfolio-panel">
              <h2>Holdings</h2>
              {data.holdings.length === 0 ? (
                <p>No holdings recorded yet.</p>
              ) : (
                <div className="portfolio-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Listing</th>
                        <th>Quantity</th>
                        <th>Average cost</th>
                        <th>Cost basis</th>
                        <th>Realized P/L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.holdings.map((item) => (
                        <tr key={listing(item.security)}>
                          <td>{listing(item.security)}</td>
                          <td>{Number(item.quantity)}</td>
                          <td>{money(item.average_cost)}</td>
                          <td>{money(item.cost_basis)}</td>
                          <td>{money(item.realized_pnl)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            <section className="card portfolio-panel">
              <h2>Record a trade</h2>
              {watchlist.length === 0 ? (
                <p>Add a listing to My stocks before recording a trade.</p>
              ) : (
                <form onSubmit={submitTrade} className="portfolio-form">
                  <label>
                    Listing
                    <select
                      value={selected}
                      onChange={(event) => setSelected(event.target.value)}
                    >
                      {watchlist.map((item) => (
                        <option key={item.id} value={listing(item.security)}>
                          {listing(item.security)} · {item.legal_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Side
                    <select
                      value={side}
                      onChange={(event) =>
                        setSide(event.target.value as "buy" | "sell")
                      }
                    >
                      <option value="buy">Buy</option>
                      <option value="sell">Sell</option>
                    </select>
                  </label>
                  <label>
                    Trade date
                    <input
                      type="date"
                      required
                      value={day}
                      onChange={(event) => setDay(event.target.value)}
                    />
                  </label>
                  <label>
                    Quantity
                    <input
                      type="number"
                      min="0.000001"
                      step="0.000001"
                      required
                      value={quantity}
                      onChange={(event) => setQuantity(event.target.value)}
                    />
                  </label>
                  <label>
                    Price per share (₹)
                    <input
                      type="number"
                      min="0.0001"
                      step="0.0001"
                      required
                      value={price}
                      onChange={(event) => setPrice(event.target.value)}
                    />
                  </label>
                  <label>
                    Fees (₹)
                    <input
                      type="number"
                      min="0"
                      step="0.0001"
                      required
                      value={fees}
                      onChange={(event) => setFees(event.target.value)}
                    />
                  </label>
                  <label className="wide">
                    Trade note (optional)
                    <textarea
                      maxLength={2000}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                    />
                  </label>
                  <button disabled={busy}>Save trade</button>
                </form>
              )}
            </section>
          </div>
          <section className="card portfolio-panel">
            <h2>Trade history</h2>
            {data.trades.length === 0 ? (
              <p>No trades recorded yet.</p>
            ) : (
              <div className="portfolio-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Listing</th>
                      <th>Side</th>
                      <th>Quantity</th>
                      <th>Price</th>
                      <th>Fees</th>
                      <th>Note</th>
                      <th>Correction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trades.map((item) => (
                      <tr key={item.id}>
                        <td>{item.trade_day}</td>
                        <td>{listing(item.security)}</td>
                        <td>{item.side}</td>
                        <td>{Number(item.quantity)}</td>
                        <td>{money(item.price)}</td>
                        <td>{money(item.fees)}</td>
                        <td>{item.note || "—"}</td>
                        <td>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => deleteTrade(item.id)}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section className="card portfolio-panel">
            <h2>Investment journal</h2>
            {watchlist.length > 0 && (
              <form className="portfolio-form" onSubmit={submitThesis}>
                <label>
                  Listing
                  <select
                    value={selected}
                    onChange={(event) => setSelected(event.target.value)}
                  >
                    {watchlist.map((item) => (
                      <option key={item.id} value={listing(item.security)}>
                        {listing(item.security)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="wide">
                  Your thesis
                  <textarea
                    required
                    maxLength={4000}
                    value={thesis}
                    onChange={(event) => setThesis(event.target.value)}
                    placeholder="Why are you considering this company? What would change your mind?"
                  />
                </label>
                <button disabled={busy}>Save thesis</button>
              </form>
            )}
            <div className="journal-list">
              {data.journal.map((entry) => (
                <article key={entry.id}>
                  <small>
                    {listing(entry.security)} ·{" "}
                    {new Date(entry.created_at).toLocaleDateString("en-IN", {
                      timeZone: "Asia/Kolkata",
                    })}
                  </small>
                  <p>{entry.thesis}</p>
                  <label>
                    Outcome
                    <textarea
                      maxLength={4000}
                      value={outcomes[entry.id] ?? entry.outcome ?? ""}
                      onChange={(event) =>
                        setOutcomes({
                          ...outcomes,
                          [entry.id]: event.target.value,
                        })
                      }
                      placeholder="What happened later? What did you learn?"
                    />
                  </label>
                  <button
                    disabled={busy || !(outcomes[entry.id] ?? "").trim()}
                    onClick={() => saveOutcome(entry.id)}
                  >
                    Save outcome
                  </button>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
