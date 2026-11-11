import { useEffect, useState } from "react";
import { ExternalLink, LoaderCircle } from "lucide-react";
import {
  ApiError,
  getFinancialResearch,
  type AnnualFinancialPeriod,
  type FinancialResearch as ResearchResponse,
  type SecurityKey,
} from "./api";
import "./FinancialResearch.css";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const rows: { key: keyof AnnualFinancialPeriod; label: string }[] = [
  { key: "revenue", label: "Revenue" },
  { key: "operating_income", label: "Operating income" },
  { key: "net_income", label: "Net income" },
  { key: "operating_cash_flow", label: "Operating cash flow" },
  { key: "capital_expenditure", label: "Capital expenditure" },
];

function amount(value: string | null, currency: string | null): string {
  if (value === null) return "—";
  if (currency === "INR")
    return `₹${number.format(Number(value) / 10_000_000)} cr`;
  return `${currency ?? ""} ${number.format(Number(value))}`;
}

function date(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

const unavailable = {
  missing_data: "Missing inputs",
  not_meaningful: "Not meaningful",
  sector_not_supported: "Not suited to this sector",
};

export default function FinancialResearch({
  security,
}: {
  security: SecurityKey;
}) {
  const [data, setData] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getFinancialResearch(security, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof ApiError
              ? reason.message
              : "Annual financials could not load.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [security, revision]);

  const statements = data?.statements;
  const periods = statements?.periods.slice(0, 3) ?? [];
  return (
    <section
      className="financial-research card"
      aria-labelledby="financial-research-title"
    >
      <div className="financial-heading">
        <div>
          <span className="section-eyebrow">ANNUAL BUSINESS PERFORMANCE</span>
          <h3 id="financial-research-title">
            Financial statements &amp; ratios
          </h3>
        </div>
        {statements?.source.url && (
          <a href={statements.source.url} target="_blank" rel="noreferrer">
            Yahoo source <ExternalLink size={14} />
          </a>
        )}
      </div>
      {loading ? (
        <div className="financial-message" role="status">
          <LoaderCircle className="spin" size={18} /> Loading annual statements…
        </div>
      ) : error ? (
        <div className="financial-message" role="alert">
          {error}
          <button
            type="button"
            onClick={() => {
              setError(null);
              setLoading(true);
              setRevision((value) => value + 1);
            }}
          >
            Retry annual statements
          </button>
        </div>
      ) : !statements || periods.length === 0 ? (
        <div className="financial-message">
          {statements?.unavailable_reason === "currency_unknown"
            ? "Statement currency is unavailable from the source."
            : "Annual statements are unavailable for this listing."}
        </div>
      ) : (
        <>
          <div className="financial-metrics">
            {data.metrics.map((metric) => (
              <div className="financial-metric" key={metric.key}>
                <span>{metric.label}</span>
                <strong>
                  {metric.status === "available" && metric.value !== null
                    ? metric.unit === "percent"
                      ? `${number.format(Number(metric.value))}%`
                      : amount(metric.value, statements.currency_code)
                    : metric.status === "available"
                      ? "Unavailable"
                      : unavailable[metric.status]}
                </strong>
                <small>
                  {metric.period_end
                    ? `Year ended ${date(metric.period_end)}`
                    : "No annual period"}
                </small>
                <details>
                  <summary>How calculated</summary>
                  <p>
                    {metric.formula} · version {metric.formula_version}
                  </p>
                  {metric.inputs.map((input) => (
                    <p key={`${input.field}-${input.period_end}`}>
                      {input.field.replaceAll("_", " ")} (
                      {date(input.period_end)}):{" "}
                      {amount(input.value, statements.currency_code)}
                    </p>
                  ))}
                </details>
              </div>
            ))}
          </div>
          <div className="financial-table-scroll">
            <table className="financial-table">
              <caption>
                Annual statement values ·{" "}
                {statements.currency_code === "INR"
                  ? "₹ crore"
                  : statements.currency_code}{" "}
                · accounting basis unverified
              </caption>
              <thead>
                <tr>
                  <th scope="col">Statement line</th>
                  {periods.map((period) => (
                    <th scope="col" key={period.period_end}>
                      {date(period.period_end)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{row.label}</th>
                    {periods.map((period) => (
                      <td key={period.period_end}>
                        {amount(
                          period[row.key] as string | null,
                          statements.currency_code,
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="financial-note">
            Annual period ends are supplied by Yahoo. Period starts, publication
            dates, and consolidated versus standalone basis are not verified.
            Capex is shown with Yahoo’s sign; negative means an outflow. Source
            retrieved{" "}
            {new Date(statements.source.retrieved_at).toLocaleString("en-IN", {
              dateStyle: "medium",
              timeStyle: "short",
              timeZone: "Asia/Kolkata",
            })}
            .
          </p>
        </>
      )}
      {statements && (
        <p className="financial-message">
          Yahoo snapshot retrieved{" "}
          {new Date(statements.source.retrieved_at).toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
          })}
          . Latest annual period ended{" "}
          {statements.periods[0]?.period_end ?? "unknown"}; publication date and
          accounting basis are unverified.
        </p>
      )}
    </section>
  );
}
