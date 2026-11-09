import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  LoaderCircle,
} from "lucide-react";
import {
  ApiError,
  getMarketBenchmarks,
  type MarketBenchmarks as BenchmarkResponse,
} from "./api";
import "./MarketBenchmarks.css";

const points = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function day(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

export default function MarketBenchmarks() {
  const [data, setData] = useState<BenchmarkResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getMarketBenchmarks(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "Market benchmarks could not load. Check the backend connection.",
        );
      });
    return () => controller.abort();
  }, []);

  return (
    <section className="benchmark-section" aria-labelledby="benchmark-title">
      <div className="benchmark-heading">
        <div>
          <span>MARKET PULSE</span>
          <h2 id="benchmark-title">Indian benchmarks</h2>
        </div>
        <p>Latest available daily values · Yahoo Finance</p>
      </div>
      {error ? (
        <div className="benchmark-message" role="alert">
          {error}
        </div>
      ) : !data ? (
        <div className="benchmark-message" role="status">
          <LoaderCircle className="spin" size={18} /> Loading benchmarks…
        </div>
      ) : (
        <div className="benchmark-grid">
          {data.benchmarks.map((benchmark) => {
            const change = Number(benchmark.change_points);
            const rising = change >= 0;
            return (
              <div className="benchmark-card" key={benchmark.symbol}>
                <div className="benchmark-card-top">
                  <span>{benchmark.name}</span>
                  <a
                    href={benchmark.source_url}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`${benchmark.name} source on Yahoo Finance`}
                  >
                    <ExternalLink size={15} />
                  </a>
                </div>
                {benchmark.status === "available" &&
                benchmark.value !== null &&
                benchmark.change_points !== null &&
                benchmark.change_percent !== null &&
                benchmark.as_of_day ? (
                  <>
                    <strong className="benchmark-value">
                      {points.format(Number(benchmark.value))}
                    </strong>
                    <div
                      className={`benchmark-change ${rising ? "up" : "down"}`}
                    >
                      {rising ? (
                        <ArrowUpRight size={17} />
                      ) : (
                        <ArrowDownRight size={17} />
                      )}
                      {rising ? "+" : ""}
                      {points.format(change)} pts
                      <span>
                        {rising ? "+" : ""}
                        {points.format(Number(benchmark.change_percent))}%
                      </span>
                    </div>
                    <small>Daily value · {day(benchmark.as_of_day)}</small>
                  </>
                ) : (
                  <div className="benchmark-unavailable">
                    Value unavailable from source
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <p className="benchmark-note">
        Compared with the previous available daily bar. Today’s bar may change
        during market hours; figures may be delayed.
      </p>
    </section>
  );
}
