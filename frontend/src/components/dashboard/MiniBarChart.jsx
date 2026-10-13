import React from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, Cell } from "recharts";

function CustomTooltip({ active, payload, label, currency = "USD" }) {
  if (active && payload && payload.length) {
    const val = payload[0].value;
    const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val);
    return (
      <div className="bg-paper-card border border-paper-line rounded-md px-3 py-2 shadow-lg text-xs">
        <p className="font-semibold text-ink">{label}</p>
        <p className="text-freight font-mono mt-0.5">{formatted}</p>
      </div>
    );
  }
  return null;
}

export default function MiniBarChart({ data = [], color = "#8b5cf6", currency = "USD", height = 160 }) {
  // Format month label for x-axis e.g. "2026-05" -> "May"
  const formattedData = data.map((item) => {
    let shortMonth = item.month;
    if (item.month && item.month.includes("-")) {
      const [, m] = item.month.split("-");
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      shortMonth = monthNames[parseInt(m, 10) - 1] || item.month;
    }
    return {
      ...item,
      shortMonth,
    };
  });

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={formattedData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <XAxis
            dataKey="shortMonth"
            stroke="#94a3b8"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: "#e2e8f0" }}
          />
          <Tooltip content={<CustomTooltip currency={currency} />} />
          <Bar dataKey="total" fill={color} radius={[4, 4, 0, 0]} animationDuration={800}>
            {formattedData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={index === formattedData.length - 1 ? "#7c3aed" : color}
                className="hover:opacity-80 transition-opacity"
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
