import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";

const COLORS = {
  "First Mile": "#2F6F4E",
  Linehaul: "#C98A2C",
  "Last Mile": "#1E7F8C",
  Closed: "#2F6F4E",
  Exception: "#B23A2E",
};

export default function PhaseChart({ data }) {
  const rows = Object.entries(data || {}).map(([name, value]) => ({ name, value }));
  return (
    <div className="bg-paper-card border border-paper-line rounded-lg p-6">
      <p className="text-xs font-medium tracking-wide uppercase text-ink-faint mb-4">Orders by phase</p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ left: -20 }}>
          <CartesianGrid vertical={false} stroke="#DDE2DC" />
          <XAxis dataKey="name" stroke="#8A968E" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis stroke="#8A968E" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: "rgba(47,111,78,0.06)" }}
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DDE2DC", borderRadius: 8, fontSize: 12 }}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {rows.map((r) => (
              <Cell key={r.name} fill={COLORS[r.name] || "#2F6F4E"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
