import { motion } from "framer-motion";
import Icon3D from "./Icon3D.jsx";

export default function StatCard({ label, value, sub, kind, color = "#2F6F4E", delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay }}
      whileHover={{ y: -4 }}
      className="relative bg-paper-card border border-paper-line rounded-lg p-5 flex items-center gap-4 overflow-hidden transition-shadow duration-300 hover:shadow-glow"
    >
      <div
        className="absolute -right-6 -top-6 w-24 h-24 rounded-full blur-2xl opacity-20 pointer-events-none"
        style={{ background: color }}
      />
      <Icon3D kind={kind} color={color} />
      <div className="relative z-10">
        <p className="text-xs font-medium tracking-wide uppercase text-ink-faint">{label}</p>
        <p className="font-display text-2xl font-semibold text-ink mt-0.5">{value}</p>
        {sub && <p className="text-xs text-ink-faint mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  );
}
