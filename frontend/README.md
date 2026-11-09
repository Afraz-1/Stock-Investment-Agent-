# EquityIQ frontend

This is the local React and TypeScript stock explorer. It calls the FastAPI
backend through Vite's `/api` development proxy. It does not store credentials
or place trades.

From this directory, run `npm install` once and then `npm run dev`. Open
<http://127.0.0.1:5173/>. Run the backend separately on `127.0.0.1:8000`.

The top navigation opens three separate routes: `/` for Market overview,
`/research` for Stock research, and `/my-stocks` for My stocks. Direct links and
browser Back/Forward work through React Router. `src/main.tsx` provides the
router, `src/App.tsx` handles route content and stock state, and
`src/StockSearch.tsx` shares the listing search between the latter two pages.
`src/navigation.css` styles the horizontal navigation and page layout.

`src/api.ts` defines the responses and fetch calls. `src/App.tsx` also handles
stock selection, date ranges, source selection, and My stocks actions.
`src/MarketOverview.tsx` renders timestamped NSE gainers and losers from the
backend; its rows open the research view. `src/theme.css` supplies the page
theme, while `src/MarketOverview.css` styles the market tables.
`src/MarketBenchmarks.tsx` displays NIFTY 50 and SENSEX daily values from
`GET /api/v1/market/benchmarks`, including the prior-bar move and date.
`src/PriceChart.tsx` is loaded on demand, keeping the chart library out of
the initial JavaScript bundle.
`src/App.css` and `src/index.css` style the page. `vite.config.ts` forwards
`/api` requests to the backend during local development.

Run `npm run lint`, `npm run build`, and `npm run test:routes` to check the frontend.
