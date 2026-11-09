import { useMemo } from "react";
import { LineChart } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceBar } from "./api";

interface PriceChartProps {
  bars: PriceBar[];
  shortDate: (value: string) => string;
  longDate: (value: string) => string;
  money: (value: number) => string;
  integer: (value: number) => string;
}

export default function PriceChart({
  bars,
  shortDate,
  longDate,
  money,
  integer,
}: PriceChartProps) {
  const data = useMemo(
    () =>
      bars.map((bar) => ({
        trading_day: bar.trading_day,
        close: Number(bar.close),
      })),
    [bars],
  );

  if (data.length === 0) {
    return (
      <div className="chart-empty">
        <LineChart size={28} strokeWidth={1.5} />
        <strong>No price bars in this range</strong>
        <span>Try another range or switch the data source.</span>
      </div>
    );
  }

  return (
    <div
      className="chart-wrap"
      role="img"
      aria-label={`Closing price chart with ${data.length} daily observations`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 16, right: 8, left: 0, bottom: 4 }}
        >
          <defs>
            <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5d9b60" stopOpacity={0.24} />
              <stop offset="100%" stopColor="#5d9b60" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#e9eee7"
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="trading_day"
            tickFormatter={shortDate}
            minTickGap={32}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#87938a", fontSize: 11 }}
            dy={10}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={(value: number) => `₹${integer(Math.round(value))}`}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#87938a", fontSize: 11 }}
            width={75}
          />
          <Tooltip
            labelFormatter={(label) => longDate(String(label))}
            formatter={(value) => [money(Number(value)), "Close"]}
            contentStyle={{
              border: "1px solid #e4ebe3",
              borderRadius: 10,
              boxShadow: "0 12px 30px rgba(20,39,28,.1)",
            }}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke="#3f8552"
            strokeWidth={2.5}
            fill="url(#priceFill)"
            dot={false}
            activeDot={{
              r: 5,
              fill: "#3f8552",
              stroke: "#fff",
              strokeWidth: 2,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
