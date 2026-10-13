import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { X, Mail, RefreshCw } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { formatDate, isStaff } from "../utils/invoice.js";

/**
 * STATUS_STYLES maps each InvoiceSendLog status to a tailwind badge.
 * Matches the same statuses defined by InvoiceSendStatus in models.py:
 *   pending | sent | failed | bounced
 */
const STATUS_STYLES = {
  sent:    "bg-green-100 text-green-700 border-green-200",
  failed:  "bg-red-100 text-red-700 border-red-200",
  bounced: "bg-orange-100 text-orange-700 border-orange-200",
  pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
};

function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {status}
    </span>
  );
}

/**
 * SendLogsModal
 * Props:
 *   invoiceId      – ID of the Invoice whose logs to fetch
 *   invoiceNumber  – Human-readable invoice number shown in the modal title
 *   onClose        – Callback to close/unmount the modal
 */
export default function SendLogsModal({ invoiceId, invoiceNumber, onClose }) {
  const { token, role } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const overlayRef = useRef(null);

  const staff = isStaff(role);

  function fetchLogs(signal) {
    setLoading(true);
    setError("");
    api
      .listInvoiceSendLogs(token, invoiceId, signal)
      .then((data) => {
        setLogs(Array.isArray(data) ? data : data?.results || []);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === "AbortError") return;
        setError(err.message || "Could not load send logs.");
        setLoading(false);
      });
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchLogs(controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  // Close on backdrop click
  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose();
  }

  // Close on Escape key
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      ref={overlayRef}
      onClick={handleOverlayClick}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Send logs for ${invoiceNumber}`}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ type: "spring", damping: 26, stiffness: 320 }}
        className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-100">
          <Mail size={18} className="text-blue-600 shrink-0 transition-transform hover:scale-110" />
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-gray-900 text-base truncate">
              Send Logs
            </h2>
            <p className="text-xs text-gray-400 font-mono truncate">{invoiceNumber}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close send logs"
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-all duration-200 hover:rotate-90 hover:scale-110 active:scale-95"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
              <RefreshCw size={14} className="animate-spin" />
              Loading send logs…
            </div>
          ) : error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 mb-2">
              {error}
              <button
                onClick={() => fetchLogs()}
                className="ml-3 underline hover:no-underline text-red-700"
              >
                Retry
              </button>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12">
              <Mail size={32} className="text-gray-200 mx-auto mb-3" />
              <p className="text-sm font-medium text-gray-500">No send logs yet</p>
              <p className="text-xs text-gray-400 mt-1">
                This invoice has not been e-mailed yet.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-400 border-b border-gray-100">
                    <th className="pb-2 pr-4 font-medium">Recipient</th>
                    <th className="pb-2 pr-4 font-medium">Type</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Date / Time</th>
                    {staff && <th className="pb-2 font-medium">Error</th>}
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/60">
                      <td className="py-2.5 pr-4 text-gray-800 font-mono text-xs break-all">
                        {log.recipient_email || "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-gray-500 text-xs">
                        Email
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={log.status} />
                      </td>
                      <td className="py-2.5 pr-4 text-gray-500 text-xs whitespace-nowrap">
                        {formatDate(log.sent_at ?? log.created_at, true)}
                      </td>
                      {staff && (
                        <td className="py-2.5 text-xs text-red-500 max-w-xs break-words">
                          {log.error_message || "—"}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
          <span>{logs.length} {logs.length === 1 ? "entry" : "entries"}</span>
          <button
            onClick={() => fetchLogs()}
            disabled={loading}
            className="flex items-center gap-1.5 text-blue-600 hover:text-blue-800 disabled:opacity-40 transition-colors"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
