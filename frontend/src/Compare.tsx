import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  getFinancialResearch,
  getPrices,
  getProfile,
  type CompanyProfile,
  type FinancialResearch,
  type PriceHistory,
  type SecurityKey,
} from "./api";
import "./Compare.css";

type Snapshot = {
  profile: CompanyProfile | null;
  financials: FinancialResearch | null;
  prices: PriceHistory | null;
  errors: string[];
};

const empty: Snapshot = {
  profile: null,
  financials: null,
  prices: null,
  errors: [],
};
const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

function message(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Provider or API unavailable";
}

function dateWindow(): { start: string; end: string } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? "";
  const today = `${part("year")}-${part("month")}-${part("day")}`;
  const start = new Date(`${today}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - 90);
  return { start: start.toISOString().slice(0, 10), end: today };
}

async function snapshot(
  key: SecurityKey,
  signal: AbortSignal,
): Promise<Snapshot> {
  const { start, end } = dateWindow();
  const [profile, financials, prices] = await Promise.allSettled([
    getProfile(key, signal),
    getFinancialResearch(key, signal),
    getPrices(key, start, end, false, signal) as Promise<PriceHistory>,
  ]);
  return {
    profile: profile.status === "fulfilled" ? profile.value : null,
    financials: financials.status === "fulfilled" ? financials.value : null,
    prices: prices.status === "fulfilled" ? prices.value : null,
    errors: [
      profile.status === "rejected"
        ? `Profile: ${message(profile.reason)}`
        : "",
      financials.status === "rejected"
        ? `Financials: ${message(financials.reason)}`
        : "",
      prices.status === "rejected" ? `Prices: ${message(prices.reason)}` : "",
    ].filter(Boolean),
  };
}

function metric(data: Snapshot, key: string): string {
  const item = data.financials?.metrics.find((value) => value.key === key);
  return item?.status === "available" && item.value !== null
    ? `${number.format(Number(item.value))}% · FY ended ${item.period_end ?? "unknown"}`
    : (item?.status.replaceAll("_", " ") ?? "Unavailable");
}

function performance(data: Snapshot): string {
  const bars = data.prices?.bars ?? [];
  const first = bars[0];
  const last = bars.at(-1);
  if (!first || !last || Number(first.close) <= 0) return "Unavailable";
  return `${number.format((Number(last.close) / Number(first.close) - 1) * 100)}% · ${first.trading_day} to ${last.trading_day}`;
}

export default function Compare() {
  const [left, setLeft] = useState<SecurityKey>({
    exchange_code: "NSE",
    symbol: "TCS",
  });
  const [right, setRight] = useState<SecurityKey>({
    exchange_code: "NSE",
    symbol: "INFY",
  });
  const [draftLeft, setDraftLeft] = useState("TCS");
  const [draftRight, setDraftRight] = useState("INFY");
  const [data, setData] = useState<[Snapshot, Snapshot]>([empty, empty]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      snapshot(left, controller.signal),
      snapshot(right, controller.signal),
    ])
      .then((result) => {
        if (!controller.signal.aborted) setData(result as [Snapshot, Snapshot]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [left, right]);

  function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setLeft({
      exchange_code: left.exchange_code,
      symbol: draftLeft.trim().toUpperCase(),
    });
    setRight({
      exchange_code: right.exchange_code,
      symbol: draftRight.trim().toUpperCase(),
    });
  }

  const rows: [string, (item: Snapshot) => string][] = [
    ["Sector", (item) => item.profile?.sector ?? "Unavailable"],
    ["90-day closing-price change", performance],
    [
      "Trailing P/E",
      (item) => item.profile?.facts.trailing_pe ?? "Unavailable",
    ],
    ["Operating margin", (item) => metric(item, "operating_margin")],
    ["Net margin", (item) => metric(item, "net_margin")],
    [
      "Operating cash flow margin",
      (item) => metric(item, "operating_cash_flow_margin"),
    ],
    ["Revenue growth", (item) => metric(item, "revenue_growth")],
  ];

  return (
    <section className="compare-page">
      <div className="page-heading">
        <span>RESEARCH TOOLS</span>
        <h1>
          Compare stocks<span>.</span>
        </h1>
        <p>
          View the same fields side by side. Periods and source dates can
          differ; missing values stay visible.
        </p>
      </div>
      <form className="compare-form card" onSubmit={compare}>
        {([0, 1] as const).map((index) => (
          <label key={index}>
            Listing {index + 1}
            <select
              value={index === 0 ? left.exchange_code : right.exchange_code}
              onChange={(event) => {
                const code = event.target.value as SecurityKey["exchange_code"];
                setLoading(true);
                if (index === 0) setLeft({ ...left, exchange_code: code });
                else setRight({ ...right, exchange_code: code });
              }}
            >
              <option>NSE</option>
              <option>BSE</option>
            </select>
            <input
              aria-label={`Symbol ${index + 1}`}
              required
              pattern="[A-Za-z0-9][A-Za-z0-9&_.-]{0,31}"
              maxLength={32}
              value={index === 0 ? draftLeft : draftRight}
              onChange={(event) =>
                index === 0
                  ? setDraftLeft(event.target.value)
                  : setDraftRight(event.target.value)
              }
            />
          </label>
        ))}
        <button type="submit">Compare</button>
      </form>
      {loading ? (
        <p role="status">Loading both listings…</p>
      ) : (
        <div className="compare-table-wrap card">
          <table className="compare-table">
            <thead>
              <tr>
                <th>Measure</th>
                {[left, right].map((key) => (
                  <th key={`${key.exchange_code}:${key.symbol}`}>
                    {key.exchange_code}:{key.symbol}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, value]) => (
                <tr key={label}>
                  <th>{label}</th>
                  <td>{value(data[0])}</td>
                  <td>{value(data[1])}</td>
                </tr>
              ))}
              <tr>
                <th>Profile retrieved</th>
                {data.map((item, index) => (
                  <td key={index}>
                    {item.profile?.source.retrieved_at
                      ? new Date(
                          item.profile.source.retrieved_at,
                        ).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
                      : "Unavailable"}
                  </td>
                ))}
              </tr>
              <tr>
                <th>Financials retrieved</th>
                {data.map((item, index) => (
                  <td key={index}>
                    {item.financials?.statements.source.retrieved_at
                      ? new Date(
                          item.financials.statements.source.retrieved_at,
                        ).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
                      : "Unavailable"}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
          {data.map(
            (item, index) =>
              item.errors.length > 0 && (
                <p className="compare-error" role="alert" key={index}>
                  {index === 0 ? left.symbol : right.symbol}:{" "}
                  {item.errors.join(" · ")}
                </p>
              ),
          )}
        </div>
      )}
      <p className="compare-note">
        Yahoo Finance data may be delayed or incomplete. These are historical
        observations, not a ranking or recommendation. Check reporting periods
        and official company filings before comparing fundamentals.
      </p>
    </section>
  );
}
