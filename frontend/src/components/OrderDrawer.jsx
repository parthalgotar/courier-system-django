import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X, FileCheck2, RefreshCw, CheckCircle2 } from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import StatusTimeline from "./StatusTimeline.jsx";
import { STAGE_ACTIONS } from "../stageActions.js";

export default function OrderDrawer({ order, onClose, onUpdate }) {
  const { token, role } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [navigatingInvoice, setNavigatingInvoice] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [toast, setToast] = useState(null);

  const loadNotifications = async () => {
    if (!order?.id) return;
    try {
      const res = await api.listOrderNotifications(token, order.id);
      const list = Array.isArray(res) ? res : res?.results || [];
      setNotifications(list);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    setErr(null);
    loadNotifications();
  }, [order?.id]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const o = order || {};

  const run = async (fn) => {
    setBusy(true);
    setErr(null);
    try {
      const updated = await fn();
      if (updated) {
        onUpdate(updated);
        await loadNotifications();
        const newStage = STAGE_ACTIONS[updated.status]?.label || updated.status;
        setToast(newStage ? `Advanced to: ${newStage}` : "Order updated");
      }
    } catch (e) {
      setErr(e.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  // Navigate to the invoice detail page for this order's associated invoice
  const viewInvoice = async () => {
    setNavigatingInvoice(true);
    setErr(null);
    try {
      let invoiceId = o.invoice_id;

      if (!invoiceId) {
        // Query the invoice associated with this specific order
        const res = await api.listInvoices(token, { order_id: o.id });
        const list = Array.isArray(res) ? res : res?.results || [];
        // Match specific order ID to guarantee correct order's invoice
        const match =
          list.find((inv) => inv.order_id === o.id && inv.status !== "cancelled") ||
          list.find((inv) => inv.order_id === o.id) ||
          (list.length > 0 && list[0].order_id === o.id ? list[0] : null);
        if (match && match.id) {
          invoiceId = match.id;
        }
      }

      if (invoiceId) {
        if (onClose) onClose();
        navigate(`/invoices/${invoiceId}`);
      } else {
        setErr("No invoice found for this order.");
      }
    } catch (e) {
      setErr(e.message || "No invoice found for this order.");
    } finally {
      setNavigatingInvoice(false);
    }
  };

  // Stage Action from stageActions config
  const currentStageAction = STAGE_ACTIONS[o.status];
  const canExecute = Boolean(
    currentStageAction &&
      (!currentStageAction.canExecute || currentStageAction.canExecute({ role }))
  );
  const ActionIcon = currentStageAction?.icon;

  return (
    <AnimatePresence>
      {order && (
        <>
          {/* Toast Notification */}
          <AnimatePresence>
            {toast && (
              <motion.div
                initial={{ opacity: 0, y: -15, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -15, scale: 0.95 }}
                className="fixed top-4 right-4 z-[70] flex items-center gap-2 px-3.5 py-2.5 bg-ink text-white rounded-lg shadow-xl text-xs sm:text-sm font-medium border border-paper-line"
              >
                <CheckCircle2 size={15} className="text-freight shrink-0" />
                <span>{toast}</span>
              </motion.div>
            )}
          </AnimatePresence>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-ink/40 backdrop-blur-sm z-40"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed top-0 right-0 h-full w-full sm:w-[460px] bg-paper-card border-l border-paper-line z-50 overflow-y-auto"
          >
            {/* Drawer Header: Left = tracking id + order number, Right = [action button] [X] */}
            <div className="sticky top-0 bg-paper-card/95 backdrop-blur border-b border-paper-line px-6 py-4 flex items-center justify-between gap-3 z-10">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-scan truncate">{o.tracking_number}</p>
                <h3 className="font-display text-base sm:text-lg font-semibold text-ink mt-0.5 truncate">
                  {o.order_number}
                </h3>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {canExecute && (
                  <button
                    type="button"
                    onClick={() =>
                      currentStageAction.action({
                        api,
                        token,
                        order: o,
                        run,
                        viewInvoice,
                      })
                    }
                    disabled={busy || navigatingInvoice}
                    title={currentStageAction.label}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-freight text-white hover:bg-freight-dark text-xs sm:text-sm font-medium transition-all shadow-xs hover:shadow disabled:opacity-50 disabled:cursor-not-allowed max-w-[190px] sm:max-w-[260px] whitespace-nowrap"
                  >
                    {busy || navigatingInvoice ? (
                      <RefreshCw size={13} className="animate-spin shrink-0" />
                    ) : ActionIcon ? (
                      <ActionIcon size={13} className="shrink-0" />
                    ) : null}
                    <span className="truncate">
                      {busy || navigatingInvoice ? "Processing…" : currentStageAction.label}
                    </span>
                  </button>
                )}

                <button
                  onClick={onClose}
                  aria-label="Close drawer"
                  className="w-8 h-8 sm:w-9 sm:h-9 rounded-full border border-paper-line grid place-items-center hover:border-freight hover:text-freight hover:rotate-90 hover:scale-105 active:scale-95 transition-all duration-200 shrink-0 text-ink-faint hover:bg-paper"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {err && (
              <div className="mx-6 mt-4 p-3 rounded-md bg-alert-soft border border-alert/30 text-xs text-alert">
                {err}
              </div>
            )}

            <div className="px-6 py-5 space-y-6">
              <StatusTimeline status={o.status} />

              {o.is_cod && (
                <p className="text-xs font-medium text-transit">
                  COD ₹{Number(o.cod_amount || 0).toLocaleString("en-IN")}
                </p>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs text-ink-faint mb-1">Order Date</p>
                  <p className="text-ink">
                    {o.order_date
                      ? new Date(o.order_date + "T00:00:00").toLocaleDateString("en-IN", {
                          day: "2-digit", month: "short", year: "numeric",
                        })
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-ink-faint mb-1">Driver</p>
                  <p className="text-ink">
                    {o.driver_id ? `Driver #${o.driver_id}` : "Unassigned"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-ink-faint mb-1">Customer</p>
                  <p className="text-ink">{o.customer_name}</p>
                </div>
                <div>
                  <p className="text-xs text-ink-faint mb-1">Route</p>
                  <p className="text-ink">
                    {o.origin_city || "—"} → {o.destination_city || "—"}
                  </p>
                </div>
                <div className="col-span-2">
                  <p className="text-xs text-ink-faint mb-1">Delivery Address</p>
                  <p className="text-ink">{o.delivery_address}</p>
                </div>
                <div>
                  <p className="text-xs text-ink-faint mb-1">Commodity</p>
                  <p className="text-ink">
                    {o.commodity} ({o.weight_kg} kg)
                  </p>
                </div>
              </div>

              <div>
                <p className="text-xs font-medium tracking-wide uppercase text-ink-faint mb-3">
                  Milestone trail
                </p>
                <ol className="relative border-l border-paper-line ml-2 space-y-5">
                  {o.events?.map((ev) => (
                    <li key={ev.id} className="ml-5">
                      <span className="absolute -left-[7px] mt-1 w-3.5 h-3.5 rounded-full bg-freight border-2 border-paper-card" />
                      <div className="flex items-center gap-2">
                        <FileCheck2 size={13} className="text-scan" />
                        <p className="text-sm text-ink font-medium">{ev.document_name}</p>
                      </div>
                      {ev.remarks && <p className="text-xs text-ink-faint mt-0.5">{ev.remarks}</p>}
                      <p className="text-xs font-mono text-ink-faint/70 mt-0.5">
                        {new Date(ev.created_at).toLocaleString()}
                      </p>
                    </li>
                  ))}
                </ol>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-medium tracking-wide uppercase text-ink-faint">
                    Milestone Notifications ({notifications.length})
                  </p>
                  <button
                    type="button"
                    onClick={loadNotifications}
                    className="text-[11px] text-freight hover:underline"
                  >
                    Refresh
                  </button>
                </div>
                {notifications.length === 0 ? (
                  <p className="text-xs text-ink-faint italic">
                    No notifications dispatched for this order yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {notifications.map((n) => (
                      <div
                        key={n.id}
                        className="rounded-md border border-paper-line bg-paper/50 p-2.5 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-ink-faint uppercase">
                            {n.channel}
                          </span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${
                              n.status === "sent"
                                ? "bg-freight-soft text-freight-dark"
                                : n.status === "failed"
                                ? "bg-alert-soft text-alert"
                                : "bg-transit-soft text-transit"
                            }`}
                          >
                            {n.status}
                          </span>
                        </div>
                        <p className="text-ink font-medium">{n.recipient}</p>
                        <p className="text-ink-soft text-[11px] line-clamp-2">{n.message_body}</p>
                        <p className="text-[10px] font-mono text-ink-faint">
                          {new Date(n.created_at).toLocaleString()}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
