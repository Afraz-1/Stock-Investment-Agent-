import type { FormEvent } from "react";
import {
  ArrowRight,
  ChevronRight,
  Info,
  LoaderCircle,
  Search,
} from "lucide-react";
import type { SearchResult, SecurityKey } from "./api";

interface StockSearchProps {
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSelect: (security: SecurityKey) => void;
  results: SearchResult[];
  searching: boolean;
  error: string | null;
  searched: boolean;
}

export default function StockSearch({
  query,
  onQueryChange,
  onSubmit,
  onSelect,
  results,
  searching,
  error,
  searched,
}: StockSearchProps) {
  return (
    <div className="stock-search">
      <form className="search-form" onSubmit={onSubmit}>
        <Search size={20} aria-hidden="true" />
        <label className="sr-only" htmlFor="stock-search">
          Search stocks
        </label>
        <input
          id="stock-search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search an NSE or BSE company, e.g. TCS"
          autoComplete="off"
        />
        <button type="submit" disabled={searching}>
          {searching ? <LoaderCircle className="spin" size={17} /> : "Search"}
          <ArrowRight size={17} />
        </button>
      </form>
      {error && (
        <div className="inline-alert" role="alert">
          {error}
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
              onClick={() => onSelect(result.security)}
            >
              <span className="result-symbol">
                {result.security.symbol.slice(0, 2)}
              </span>
              <span className="result-details">
                <strong>{result.company_name}</strong>
                <small>
                  {result.security.exchange_code} · {result.security.symbol}
                </small>
              </span>
              <ChevronRight size={17} />
            </button>
          ))}
        </div>
      )}
      {!searching && !error && searched && results.length === 0 && (
        <div className="search-hint" role="status">
          <Info size={14} /> No matching NSE or BSE listings. Try a company name
          or another symbol.
        </div>
      )}
      {!searching && !error && !searched && (
        <div className="search-hint">
          <Info size={14} /> NSE and BSE listings stay separate.
        </div>
      )}
    </div>
  );
}
