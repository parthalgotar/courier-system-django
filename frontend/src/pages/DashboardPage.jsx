import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Truck, AlertTriangle, RotateCcw } from "lucide-react";
import Layout from "../components/Layout.jsx";
import StatCard from "../components/StatCard.jsx";
import PhaseChart from "../components/PhaseChart.jsx";
import StatusTimeline from "../components/StatusTimeline.jsx";
import OrderDrawer from "../components/OrderDrawer.jsx";
import { Card, ErrorBanner } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";

export default function DashboardPage() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [statsData, ordersData] = await Promise.all([
        api.getDashboardStats(token),
        api.listOrders(token),
      ]);
      setStats(statsData);
      // listOrders returns a paginated envelope { results, count, … }
      setOrders(Array.isArray(ordersData) ? ordersData : (ordersData?.results ?? []));
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

  async function openOrder(order) {
    const full = await api.getOrder(token, order.id);
    setSelected(full);
  }

  function handleUpdate(updated) {
    setSelected(updated);
    refresh();
  }

  return (
    <Layout eyebrow="DASHBOARD" title="Dashboard">
      <ErrorBanner message={error} />

      {stats && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard label="Total Orders" value={stats.total_orders} kind="box" color="#2F6F4E" />
          <StatCard label="In Transit" value={stats.in_transit} kind="torus" color="#C98A2C" delay={0.05} />
          <StatCard label="Delivered" value={stats.delivered} kind="octa" color="#1E7F8C" delay={0.1} />
          <StatCard label="Delivery Failed" value={stats.delivery_failed} kind="cone" color="#B23A2E" delay={0.15} />
          <StatCard
            label="COD Pending"
            value={`₹${stats.cod_pending.toLocaleString("en-IN")}`}
            sub={`₹${stats.cod_collected.toLocaleString("en-IN")} collected`}
            kind="box" color="#2F6F4E" delay={0.2}
          />
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-1">{stats && <PhaseChart data={stats.phase_breakdown} />}</div>
        <div className="lg:col-span-2 bg-paper-card border border-paper-line rounded-lg p-6 flex flex-col justify-center">
          <p className="text-xs font-medium tracking-wide uppercase text-ink-faint mb-3">Exception watch</p>
          <div className="grid grid-cols-3 gap-4">
            {[
              { icon: AlertTriangle, label: "Failed", value: stats?.delivery_failed ?? "—", color: "#B23A2E" },
              { icon: RotateCcw, label: "RTO", value: stats?.rto ?? "—", color: "#B23A2E" },
              { icon: Truck, label: "In Transit", value: stats?.in_transit ?? "—", color: "#C98A2C" },
            ].map((x) => (
              <div key={x.label} className="text-center">
                <x.icon size={20} className="mx-auto mb-2" style={{ color: x.color }} />
                <p className="font-display text-xl font-semibold text-ink">{x.value}</p>
                <p className="text-xs text-ink-faint mt-0.5">{x.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="text-xs font-medium tracking-wide uppercase text-ink-faint mt-10 mb-4">Recent orders</p>
      {loading ? (
        <p className="text-ink-faint text-sm">Loading orders…</p>
      ) : orders.length === 0 ? (
        <Card className="p-10 text-center text-ink-faint text-sm">No orders yet — create one on the Orders page.</Card>
      ) : (
        <div className="flex flex-col gap-3">
          {orders.slice(0, 8).map((order, i) => (
            <motion.div
              key={order.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.03 }}
            >
              <Card
                className="p-5 cursor-pointer hover:border-freight/40 hover:shadow-glow transition-all duration-300"
                onClick={() => openOrder(order)}
              >
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <p className="font-mono text-xs text-ink-faint">{order.order_number}</p>
                    <p className="font-display font-medium text-ink">{order.customer_name}</p>
                    <p className="text-sm text-ink-faint">{order.origin_city || "—"} → {order.destination_city || "—"}</p>
                  </div>
                  {order.is_cod && (
                    <span className="text-xs font-medium text-transit whitespace-nowrap">
                      COD ₹{order.cod_amount.toLocaleString("en-IN")}
                    </span>
                  )}
                </div>
                <StatusTimeline status={order.status} />
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      <OrderDrawer order={selected} onClose={() => setSelected(null)} onUpdate={handleUpdate} />
    </Layout>
  );
}
