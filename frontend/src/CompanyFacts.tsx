import { ExternalLink } from "lucide-react";
import type { CompanyProfile } from "./api";
import "./CompanyFacts.css";

const decimal = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

function marketCap(value: string | null, currency: string | null): string {
  if (value === null) return "Unavailable";
  const amount = Number(value);
  if (currency === "INR") {
    return `₹${decimal.format(amount / 10_000_000)} crore`;
  }
  return `${currency ?? "Currency unknown"} ${decimal.format(amount)}`;
}

function price(value: string, currency: string | null): string {
  return `${currency === "INR" ? "₹" : `${currency ?? ""} `}${decimal.format(Number(value))}`;
}

export default function CompanyFacts({
  profile,
  loading,
}: {
  profile: CompanyProfile | null;
  loading: boolean;
}) {
  const facts = profile?.facts;
  const currency = profile?.currency_code ?? null;
  const range =
    facts?.fifty_two_week_low && facts.fifty_two_week_high
      ? `${price(facts.fifty_two_week_low, currency)} – ${price(facts.fifty_two_week_high, currency)}`
      : "Unavailable";

  return (
    <section
      className="company-facts card"
      aria-labelledby="company-facts-title"
    >
      <div className="company-facts-heading">
        <div>
          <span className="section-eyebrow">VALUATION & PRICE CONTEXT</span>
          <h3 id="company-facts-title">Company facts</h3>
        </div>
        {profile?.source.url && (
          <a href={profile.source.url} target="_blank" rel="noreferrer">
            Source <ExternalLink size={14} />
          </a>
        )}
      </div>
      <div className="company-facts-grid">
        <div>
          <span>Market cap</span>
          <strong>
            {loading
              ? "Loading…"
              : marketCap(
                  facts?.market_cap ?? null,
                  profile?.currency_code ?? null,
                )}
          </strong>
          <small>Provider reported value</small>
        </div>
        <div>
          <span>Trailing P/E</span>
          <strong>
            {loading
              ? "Loading…"
              : facts?.trailing_pe
                ? `${decimal.format(Number(facts.trailing_pe))}×`
                : "Unavailable"}
          </strong>
          <small>Price ÷ trailing earnings</small>
        </div>
        <div>
          <span>Price to book</span>
          <strong>
            {loading
              ? "Loading…"
              : facts?.price_to_book
                ? `${decimal.format(Number(facts.price_to_book))}×`
                : "Unavailable"}
          </strong>
          <small>Price ÷ book value</small>
        </div>
        <div>
          <span>52-week range</span>
          <strong>{loading ? "Loading…" : range}</strong>
          <small>Provider reported low to high</small>
        </div>
      </div>
      <p>
        Yahoo Finance snapshot retrieved{" "}
        {profile
          ? new Date(profile.source.retrieved_at).toLocaleString("en-IN", {
              dateStyle: "medium",
              timeStyle: "short",
              timeZone: "Asia/Kolkata",
            })
          : "when available"}
        . Financial reporting periods are not supplied for these values; check
        company filings before relying on them.
      </p>
    </section>
  );
}
