# EquityIQ frontend

This is the local React and TypeScript stock explorer. It calls the FastAPI
backend through Vite's `/api` development proxy. It does not store credentials
or place trades.

From this directory, run `npm install` once and then `npm run dev`. Open
<http://127.0.0.1:5173/>. Run the backend separately on `127.0.0.1:8000`.

`src/api.ts` defines the responses and fetch calls. `src/App.tsx` handles
stock selection, date ranges, source selection, My stocks actions, and the visible cards.
`src/MarketOverview.tsx` renders timestamped NSE gainers and losers from the
backend; its rows open the research view. `src/theme.css` supplies the page
theme, while `src/MarketOverview.css` styles the market tables.
`src/PriceChart.tsx` is loaded on demand, keeping the chart library out of
the initial JavaScript bundle.
`src/App.css` and `src/index.css` style the page. `vite.config.ts` forwards
`/api` requests to the backend during local development.

Run `npm run lint` and `npm run build` to check the frontend.
