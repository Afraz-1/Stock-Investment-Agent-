import { createServer } from "vite";
import React from "react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";

const vite = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
});
try {
  const { default: App } = await vite.ssrLoadModule("/src/App.tsx");
  const routes = [
    [
      "/",
      ["Invest with context", "Indian benchmarks", "The market, in motion"],
      ["Research the business", "PERSONAL RESEARCH LIST"],
    ],
    [
      "/research",
      ["Research the business", "Company facts", "Financial statements", "Market performance"],
      ["Invest with context", "PERSONAL RESEARCH LIST"],
    ],
    [
      "/my-stocks",
      ["PERSONAL RESEARCH LIST", "SELECTED LISTING"],
      ["Company facts", "Market performance", "Invest with context"],
    ],
    [
      "/compare",
      ["Compare stocks", "RESEARCH TOOLS", "Compare"],
      ["PERSONAL RESEARCH LIST", "Market performance", "Invest with context"],
    ],
    [
      "/portfolio",
      ["Portfolio &amp; journal", "PERSONAL WORKSPACE"],
      ["Company facts", "Market performance", "Invest with context"],
    ],
    [
      "/screen",
      ["Stock screen", "DISCOVERY TOOL", "Minimum market cap"],
      ["PERSONAL RESEARCH LIST", "Market performance", "Invest with context"],
    ],
  ];
  for (const [path, present, absent] of routes) {
    const html = renderToString(
      React.createElement(
        MemoryRouter,
        { initialEntries: [path] },
        React.createElement(App),
      ),
    );
    for (const marker of present)
      if (!html.includes(marker)) throw new Error(`${path}: missing ${marker}`);
    for (const marker of absent)
      if (html.includes(marker))
        throw new Error(`${path}: unexpected ${marker}`);
    console.log(`${path}: correct page content`);
  }
} finally {
  await vite.close();
}
