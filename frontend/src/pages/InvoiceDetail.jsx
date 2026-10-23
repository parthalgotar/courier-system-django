import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  CreditCard,
  Download,
  FileText,
  Mail,
  Plus,
  RefreshCw,
  RotateCcw,
  Tag,
  X,
} from "lucide-react";
import Layout from "../components/Layout.jsx";
import InvoiceStatusBadge from "../components/InvoiceStatusBadge.jsx";
import { Card, Button, Input, Select, ErrorBanner, EmptyState } from "../components/ui.jsx";
import PayModal from "../components/PayModal.jsx";
import LinkedOrderSection from "../components/LinkedOrderSection.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { canResendInvoice, downloadPdf, formatDate, formatMoney, isStaff, openPdf } from "../utils/invoice.js";

// ─── InvoiceSendLog status choices ───
const SEND_STATUS_CHOICES = [
  { value: "pending", label: "Pending" },
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
  { value: "bounced", label: "Bounced" },
];

const SEND_STATUS_STYLES = {
  sent: "bg-green-100 text-green-700 border-green-200",
  failed: "bg-red-100 text-red-700 border-red-200",
  bounced: "bg-orange-100 text-orange-700 border-orange-200",
  pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
};

function SendStatusBadge({ status }) {
  const cls = SEND_STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {status ?? "—"}
    </span>
  );
}

// ─── Generic layout helpers ───
function Field({ label, children }) {
  return (
    <div>
      <p className="text-xs text-ink-faint mb-1">{label}</p>
      <div className="text-sm text-ink">{children || "—"}</div>
    </div>
  );
}

function AmountRow({ label, value, strong, highlight }) {
  return (
    <div className={`flex items-center justify-between py-2 ${strong ? "border-t border-paper-line mt-1 pt-3" : ""}`}>
      <span className={strong ? "font-display font-semibold text-ink" : "text-sm text-ink-soft"}>{label}</span>
      <span
        className={
          highlight
            ? "font-display text-lg font-bold text-freight"
            : strong
            ? "font-display text-base font-semibold text-ink"
            : "text-sm text-ink font-mono"
        }
      >
        {formatMoney(value)}
      </span>
    </div>
  );
}

// ─── Log detail row (expandable) ───
function LogRow({ log, staff }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className="border-b border-paper-line last:border-0 hover:bg-paper/80 cursor-pointer transition-all duration-150"
        onClick={() => setExpanded((v) => !v)}
        title="Click to expand details"
      >
        <td className="py-2.5 pr-3 font-mono text-xs text-ink break-all">{log.recipient_email || "—"}</td>
        <td className="py-2.5 pr-3"><SendStatusBadge status={log.status} /></td>
        <td className="py-2.5 pr-3 text-xs text-ink-soft whitespace-nowrap">{formatDate(log.sent_at, true)}</td>
        <td className="py-2.5 pr-3 text-xs text-ink-soft text-center">{log.attempts ?? 0}</td>
        <td className="py-2.5 pr-3 text-xs text-ink-faint whitespace-nowrap">{formatDate(log.created_at, true)}</td>
        {staff && (
          <td className="py-2.5 pr-3 text-xs text-alert max-w-[160px] truncate" title={log.error_message}>
            {log.error_message || "—"}
          </td>
        )}
        <td className="py-2.5 text-ink-faint transition-transform duration-200 hover:scale-125">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-paper border-b border-paper-line">
          <td colSpan={staff ? 7 : 6} className="px-3 py-3">
            <div className="scale-in grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
              <div>
                <p className="text-ink-faint mb-0.5">Log ID</p>
                <p className="font-mono text-ink">{log.id}</p>
              </div>
              <div>
                <p className="text-ink-faint mb-0.5">Recipient Email</p>
                <p className="font-mono text-ink break-all">{log.recipient_email || "—"}</p>
              </div>
              <div>
                <p className="text-ink-faint mb-0.5">Status</p>
                <SendStatusBadge status={log.status} />
              </div>
              <div>
                <p className="text-ink-faint mb-0.5">Sent At</p>
                <p className="text-ink">{formatDate(log.sent_at, true)}</p>
              </div>
              <div>
                <p className="text-ink-faint mb-0.5">Attempts</p>
                <p className="text-ink">{log.attempts ?? 0}</p>
              </div>
              {staff && log.error_message && (
                <div className="col-span-2 md:col-span-3">
                  <p className="text-ink-faint mb-0.5">Error Details</p>
                  <p className="font-mono text-alert bg-alert-soft p-2 rounded border border-alert/20 break-all">
                    {log.error_message}
                  </p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Add Send Log Form ───
function AddSendLogForm({ invoiceId, invoiceNumber, token, onCreated, onCancel }) {
  const [form, setForm] = useState({
    recipient_email: "",
    status: "pending",
    sent_at: "",
    attempts: 0,
    error_message: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        recipient_email: form.recipient_email.trim(),
        status: form.status,
        sent_at: form.sent_at ? new Date(form.sent_at).toISOString() : null,
        attempts: parseInt(form.attempts, 10) || 0,
        error_message: form.error_message.trim(),
      };
      const log = await api.createSendLog(token, invoiceId, payload);
      onCreated(log);
    } catch (err) {
      setError(err.message || "Failed to create log entry.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="scale-in mt-4 border border-freight/30 rounded-lg bg-freight-soft/20 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-ink">Add Send Log Entry</h4>
        <button
          type="button"
          onClick={onCancel}
          className="p-1 rounded text-ink-faint hover:text-ink hover:bg-paper-line transition-all"
          aria-label="Cancel"
        >
          <X size={14} />
        </button>
      </div>
      {error && (
        <div className="rounded-md border border-alert/30 bg-alert-soft px-3 py-2 text-xs text-alert mb-3 scale-in">
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <p className="text-xs font-medium text-ink-soft mb-1">Invoice</p>
          <p className="text-sm text-ink font-mono">{invoiceNumber}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft text-xs">Recipient Email</span>
              <input
                type="email"
                name="recipient_email"
                value={form.recipient_email}
                onChange={handleChange}
                placeholder="vendor@example.com"
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-freight outline-none transition-all"
              />
            </label>
          </div>

          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft text-xs">Status</span>
              <select
                name="status"
                value={form.status}
                onChange={handleChange}
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink focus:border-freight outline-none transition-all"
              >
                {SEND_STATUS_CHOICES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </label>
          </div>

          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft text-xs">Sent At</span>
              <input
                type="datetime-local"
                name="sent_at"
                value={form.sent_at}
                onChange={handleChange}
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink focus:border-freight outline-none transition-all"
              />
            </label>
          </div>

          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft text-xs">Attempts</span>
              <input
                type="number"
                name="attempts"
                min="0"
                value={form.attempts}
                onChange={handleChange}
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink focus:border-freight outline-none transition-all"
              />
            </label>
          </div>
        </div>

        <div className="mb-3">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-ink-soft text-xs">Error Message</span>
            <textarea
              name="error_message"
              value={form.error_message}
              onChange={handleChange}
              rows={2}
              placeholder="Optional error or notes…"
              className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-freight outline-none resize-none transition-all"
            />
          </label>
        </div>

        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="btn-ghost inline-flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-xs font-medium border border-paper-line text-ink hover:bg-paper transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="btn-primary inline-flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-xs font-medium bg-freight text-white hover:bg-freight-dark disabled:opacity-50 transition-all shadow-sm"
          >
            {busy ? "Saving…" : "Save Log Entry"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Main page ───
export default function InvoiceDetail() {
  const { id } = useParams();
  const { token, role } = useAuth();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(""); // "view" | "download" | "email" | "confirm" | "reset" | ""
  const timers = useRef([]);

  // Pay Modal State
  const [showPayModal, setShowPayModal] = useState(false);

  // Email send state
  const [recipientEmail, setRecipientEmail] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [emailNotice, setEmailNotice] = useState("");

  // Send logs
  const [sendLogs, setSendLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState("");
  const [showAddLog, setShowAddLog] = useState(false);

  // Active tab on invoice page: "lines", "payments", "logs"
  const [activeTab, setActiveTab] = useState("lines");

  const staff = isStaff(role);

  const load = useCallback(
    (signal, { silent = false } = {}) => {
      if (!silent) setLoading(true);
      return api
        .getInvoice(token, id, signal)
        .then((data) => {
          setInvoice(data);
          if (data.send_logs) setSendLogs(data.send_logs);
          setError(null);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          if (!silent) setError({ message: err.message, status: err.status });
        })
        .finally(() => {
          if (!silent && !signal?.aborted) setLoading(false);
        });
    },
    [token, id]
  );

  const refreshLogs = useCallback(
    (signal) => {
      setLogsLoading(true);
      setLogsError("");
      api
        .listInvoiceSendLogs(token, id, signal)
        .then((data) => {
          setSendLogs(Array.isArray(data) ? data : data?.results || []);
          setLogsLoading(false);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          setLogsError(err.message || "Could not load send logs.");
          setLogsLoading(false);
        });
    },
    [token, id]
  );

  useEffect(() => {
    const controller = new AbortController();
    setInvoice(null);
    setSendLogs([]);
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!invoice) return;
    const controller = new AbortController();
    refreshLogs(controller.signal);
    return () => controller.abort();
  }, [invoice?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => timers.current.forEach((t) => { clearTimeout(t); clearInterval(t); }), []);

  // ── State Actions ──
  const handleConfirm = async () => {
    setBusy("confirm");
    setActionError("");
    setNotice("");
    try {
      await api.confirmInvoice(token, invoice.id);
      setNotice("Invoice confirmed and posted successfully.");
      await load(undefined, { silent: true });
    } catch (err) {
      setActionError(err.message || "Failed to confirm invoice.");
    } finally {
      setBusy("");
    }
  };

  const handleResetToDraft = async () => {
    setBusy("reset");
    setActionError("");
    setNotice("");
    try {
      await api.resetInvoiceToDraft(token, invoice.id);
      setNotice("Invoice reset to draft status.");
      await load(undefined, { silent: true });
    } catch (err) {
      setActionError(err.message || "Failed to reset invoice to draft.");
    } finally {
      setBusy("");
    }
  };

  const handlePaymentSuccess = () => {
    setNotice("Payment created successfully! Invoice balances and status updated.");
    load(undefined, { silent: true });
  };

  const run = async (kind, fn, successMsg) => {
    setBusy(kind);
    setActionError("");
    setNotice("");
    try {
      await fn();
      if (successMsg) setNotice(successMsg);
    } catch (err) {
      setActionError(err.message || "Action failed.");
    } finally {
      setBusy("");
    }
  };

  const filename = `${invoice?.number || invoice?.invoice_number || "invoice"}.pdf`;

  const handleResend = async () => {
    setBusy("email");
    setActionError("");
    setNotice("");
    try {
      const res = await api.sendInvoiceEmail(token, invoice.id);
      const recipient = res?.recipient_email || invoice.vendor?.billing_email || "recipient";
      setNotice(`Invoice email queued for ${recipient}.`);
      await refreshLogs();
      await load(undefined, { silent: true });
    } catch (err) {
      setActionError(err.message || "Failed to send email.");
    } finally {
      setBusy("");
    }
  };

  const handleSendEmail = async (e) => {
    e.preventDefault();
    setEmailBusy(true);
    setEmailError("");
    setEmailNotice("");
    try {
      const res = await api.sendInvoiceEmail(token, invoice.id, recipientEmail.trim());
      setEmailNotice(`Invoice sent to ${res.recipient_email || recipientEmail}.`);
      setRecipientEmail("");
      await refreshLogs();
      await load(undefined, { silent: true });
    } catch (err) {
      setEmailError(err.message || "Failed to send invoice email.");
    } finally {
      setEmailBusy(false);
    }
  };

  const handleLogCreated = (log) => {
    setSendLogs((prev) => [log, ...prev]);
    setShowAddLog(false);
    setNotice("Send log entry added.");
  };

  const back = (
    <Link to="/invoices" className="btn-ghost inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink">
      <ArrowLeft size={14} /> Back to Invoices
    </Link>
  );

  if (loading && !invoice) {
    return (
      <Layout eyebrow="Accounting" title="Invoice" action={back}>
        <div className="p-8 text-center text-ink-faint text-sm">Loading invoice…</div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout eyebrow="Accounting" title="Invoice" action={back}>
        <EmptyState title="Could not load invoice" hint={error.message} />
      </Layout>
    );
  }

  if (!invoice) return null;

  const isDraft = invoice.status === "draft";
  const isPosted = ["posted", "issued"].includes(invoice.status);
  const isPaid = invoice.status === "paid";
  const amountDue = Number(invoice.amount_due || invoice.total_amount || 0);
  const paymentsList = invoice.payments || [];
  const linesList = invoice.lines || [];
  const canSendEmail = canResendInvoice(role) && isPosted;

  return (
    <Layout eyebrow="Accounting" title={invoice.number || invoice.invoice_number || `Invoice #${invoice.id}`} action={back}>
      <ErrorBanner message={actionError} />
      {notice && (
        <div className="rounded-md border border-freight/30 bg-freight-soft px-4 py-3 text-sm text-freight-dark mb-4 flex items-center justify-between">
          <span>{notice}</span>
          <button onClick={() => setNotice("")} className="text-freight-dark/60 hover:text-freight-dark"><X size={14} /></button>
        </div>
      )}

      {/* ── SECTION 3: STATUS BAR & STEPPER (Draft > Posted > Paid) ── */}
      <div className="bg-paper-card border border-paper-line rounded-xl p-4 mb-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        {/* State Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {isDraft && (
            <button
              onClick={handleConfirm}
              disabled={busy === "confirm"}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold bg-freight text-white hover:bg-freight-dark transition-all disabled:opacity-50 shadow-xs hover:shadow-glow"
            >
              {busy === "confirm" ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Confirming…</span>
                </>
              ) : (
                <>
                  <Check size={14} />
                  <span>Confirm</span>
                </>
              )}
            </button>
          )}

          {isPosted && amountDue > 0 && (
            <button
              onClick={() => setShowPayModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 transition-all shadow-xs hover:shadow-glow"
            >
              <CreditCard size={14} />
              <span>Pay</span>
            </button>
          )}

          {isPosted && paymentsList.length === 0 && (
            <button
              onClick={handleResetToDraft}
              disabled={busy === "reset"}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-paper-line text-ink hover:bg-paper transition-all disabled:opacity-50"
            >
              <RotateCcw size={13} />
              <span>{busy === "reset" ? "Resetting…" : "Reset to Draft"}</span>
            </button>
          )}

          {isPaid && (
            <span className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 shadow-xs">
              <Check size={14} /> PAID
            </span>
          )}

          <div className="h-4 w-px bg-paper-line mx-1 hidden sm:block" />

          <Button
            variant="ghost"
            disabled={busy === "view"}
            onClick={() => run("view", () => openPdf(() => api.fetchInvoicePdf(token, invoice.id), filename))}
          >
            <FileText size={14} /> {busy === "view" ? "Opening…" : "View PDF"}
          </Button>
          <Button
            disabled={busy === "download"}
            onClick={() => run("download", () => downloadPdf(() => api.fetchInvoicePdf(token, invoice.id), filename), `Downloaded ${filename}`)}
          >
            <Download size={14} /> {busy === "download" ? "Preparing…" : "Download PDF"}
          </Button>

          {canSendEmail && (
            <Button
              variant="ghost"
              disabled={busy === "email"}
              onClick={handleResend}
              title="Re-send invoice email to vendor or customer"
            >
              <Mail size={14} /> {busy === "email" ? "Sending…" : "Send Email"}
            </Button>
          )}
        </div>

        {/* Stepper Showing: Draft > Posted > Paid */}
        <div className="flex items-center gap-1.5 text-xs font-semibold">
          <div
            className={`px-3 py-1 rounded-md transition-colors ${
              isDraft ? "bg-slate-700 text-white shadow-xs" : "bg-paper text-ink-faint"
            }`}
          >
            Draft
          </div>
          <span className="text-ink-faint">›</span>
          <div
            className={`px-3 py-1 rounded-md transition-colors ${
              isPosted ? "bg-blue-600 text-white shadow-xs" : isPaid ? "bg-blue-100 text-blue-700" : "bg-paper text-ink-faint"
            }`}
          >
            Posted
          </div>
          <span className="text-ink-faint">›</span>
          <div
            className={`px-3 py-1 rounded-md transition-colors ${
              isPaid ? "bg-emerald-600 text-white shadow-xs" : "bg-paper text-ink-faint"
            }`}
          >
            Paid
          </div>
        </div>
      </div>

      {/* ── Metadata card ── */}
      <Card className="p-6 mb-6 border border-paper-line shadow-xs">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Customer">
            <span className="font-semibold text-ink">
              {invoice.customer_name || invoice.order?.customer_name || "—"}
            </span>
          </Field>
          <Field label="Invoice Date">
            {formatDate(invoice.invoice_date, false)}
          </Field>
          <Field label="Due Date">
            {invoice.due_date ? formatDate(invoice.due_date, false) : "Immediate / On Delivery"}
          </Field>
          <Field label="Status">
            <InvoiceStatusBadge status={invoice.status} />
          </Field>
        </div>

        {((invoice.tag_details && invoice.tag_details.length > 0) || (Array.isArray(invoice.tags) && invoice.tags.length > 0 && typeof invoice.tags[0] === "object")) && (
          <div className="mt-4 pt-4 border-t border-paper-line flex items-center gap-2 flex-wrap">
            <Tag size={13} className="text-ink-faint" />
            <span className="text-xs text-ink-faint">Tags:</span>
            {(invoice.tag_details && invoice.tag_details.length > 0 ? invoice.tag_details : invoice.tags).map((t) => (
              <span
                key={t.id}
                className="px-2 py-0.5 rounded text-[11px] font-medium text-white shadow-xs"
                style={{ backgroundColor: t.color || "#6366f1" }}
              >
                {t.name}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* ── Tabbed View: Lines vs Payments vs Email History ── */}
      <div className="flex border-b border-paper-line mb-4">
        <button
          onClick={() => setActiveTab("lines")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "lines"
              ? "border-freight text-freight"
              : "border-transparent text-ink-faint hover:text-ink"
          }`}
        >
          Invoice
        </button>

        <button
          onClick={() => setActiveTab("payments")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 ${
            activeTab === "payments"
              ? "border-freight text-freight"
              : "border-transparent text-ink-faint hover:text-ink"
          }`}
        >
          <span>Payments</span>
          <span
            className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
              paymentsList.length > 0 ? "bg-emerald-100 text-emerald-800" : "bg-paper text-ink-faint"
            }`}
          >
            {paymentsList.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("logs")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "logs"
              ? "border-freight text-freight"
              : "border-transparent text-ink-faint hover:text-ink"
          }`}
        >
          Delivery History ({sendLogs.length})
        </button>
      </div>

      {/* ── TAB 1: INVOICE LINES ── */}
      {activeTab === "lines" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <Card className="p-6 lg:col-span-2 border border-paper-line shadow-xs">
            {!((invoice.order || invoice.order_id) && linesList.length === 0) && (
              <>
                <h3 className="font-display font-semibold text-ink mb-4">Line Items</h3>
                {linesList.length === 0 ? (
                  <p className="text-xs text-ink-faint py-4">No lines attached to this invoice.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead>
                        <tr className="border-b border-paper-line text-ink-faint uppercase tracking-wider font-semibold">
                          <th className="py-2.5 pr-2">Product / Description</th>
                          <th className="py-2.5 pr-2 text-right">Quantity</th>
                          <th className="py-2.5 pr-2 text-right">Unit Price</th>
                          <th className="py-2.5 pr-2 text-right">Tax %</th>
                          <th className="py-2.5 text-right">Subtotal</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-paper-line">
                        {linesList.map((line, idx) => (
                          <tr key={line.id || idx} className="hover:bg-paper/50">
                            <td className="py-2.5 pr-2">
                              <p className="font-semibold text-ink">{line.product || "Item"}</p>
                              {line.description && <p className="text-[11px] text-ink-faint">{line.description}</p>}
                            </td>
                            <td className="py-2.5 pr-2 text-right font-mono">{Number(line.quantity).toFixed(2)}</td>
                            <td className="py-2.5 pr-2 text-right font-mono">{formatMoney(line.unit_price)}</td>
                            <td className="py-2.5 pr-2 text-right font-mono">{Number(line.tax_percent || 0).toFixed(0)}%</td>
                            <td className="py-2.5 text-right font-mono font-semibold text-ink">
                              {formatMoney(line.subtotal)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}

            {invoice.order && <LinkedOrderSection invoice={invoice} />}
          </Card>

          {/* Charges and Totals Breakdown */}
          <Card className="p-6 lg:col-span-1 h-fit border border-paper-line shadow-xs">
            <h3 className="font-display font-semibold text-ink mb-4">Financial Summary</h3>
            <AmountRow label="Untaxed Amount" value={invoice.amount_untaxed || invoice.freight_charge} />
            <AmountRow label="Tax Amount" value={invoice.amount_tax || invoice.tax_amount} />
            {Number(invoice.cod_amount) > 0 && <AmountRow label="COD Amount" value={invoice.cod_amount} />}
            <AmountRow label="Total Amount" value={invoice.amount_total || invoice.total_amount} strong />
            <div className="my-2 border-t border-dashed border-paper-line" />
            <AmountRow label="Amount Paid" value={invoice.amount_paid} />
            <AmountRow label="Amount Due" value={invoice.amount_due} strong highlight />

            {isPosted && amountDue > 0 && (
              <button
                onClick={() => setShowPayModal(true)}
                className="w-full mt-4 py-2 px-3 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-xs"
              >
                <CreditCard size={14} />
                <span>Record Payment ({formatMoney(amountDue)})</span>
              </button>
            )}
          </Card>
        </div>
      )}

      {/* ── TAB 2: PAYMENTS LIST (Section 3 Requirement) ── */}
      {activeTab === "payments" && (
        <Card className="p-6 mb-6 border border-paper-line shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-display font-semibold text-ink">Recorded Payments</h3>
              <p className="text-xs text-ink-faint">
                All transactions settled against this invoice
              </p>
            </div>
            {isPosted && amountDue > 0 && (
              <button
                onClick={() => setShowPayModal(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-all shadow-xs"
              >
                <Plus size={13} />
                <span>Pay Now</span>
              </button>
            )}
          </div>

          {paymentsList.length === 0 ? (
            <div className="py-8 text-center text-xs text-ink-faint">
              No payments have been recorded for this invoice yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-paper-line text-ink-faint uppercase tracking-wider font-semibold">
                    <th className="py-2.5 pr-3">Payment #</th>
                    <th className="py-2.5 pr-3">Date</th>
                    <th className="py-2.5 pr-3">Journal</th>
                    <th className="py-2.5 pr-3">Memo</th>
                    <th className="py-2.5 pr-3">Status</th>
                    <th className="py-2.5 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-paper-line">
                  {paymentsList.map((p) => {
                    const isCash = (p.journal_type || "").toLowerCase() === "cash";
                    return (
                      <tr key={p.id} className="hover:bg-paper/50">
                        <td className="py-2.5 pr-3 font-mono font-medium text-ink">{p.payment_number || p.number}</td>
                        <td className="py-2.5 pr-3 text-ink-soft">{p.payment_date}</td>
                        <td className="py-2.5 pr-3">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                              isCash ? "bg-emerald-100 text-emerald-800" : "bg-sky-100 text-sky-800"
                            }`}
                          >
                            {p.journal_name || p.journal}
                          </span>
                        </td>
                        <td className="py-2.5 pr-3 text-ink-soft max-w-[200px] truncate">{p.memo || "—"}</td>
                        <td className="py-2.5 pr-3">
                          <span className="capitalize text-emerald-700 font-semibold">{p.status}</span>
                        </td>
                        <td className="py-2.5 text-right font-mono font-bold text-ink">
                          {formatMoney(p.amount)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* ── TAB 3: EMAIL DELIVERY LOGS ── */}
      {activeTab === "logs" && (
        <Card className="p-6 mb-6 border border-paper-line shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-semibold text-ink">E-mail Delivery History</h3>
            <div className="flex items-center gap-2">
              {staff && (
                <button
                  type="button"
                  onClick={() => setShowAddLog((v) => !v)}
                  className="btn-ghost inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border border-freight/30 text-freight hover:bg-freight-soft transition-all"
                >
                  <Plus size={12} /> Add Log Entry
                </button>
              )}
              <button
                type="button"
                onClick={() => refreshLogs()}
                disabled={logsLoading}
                className="btn-ghost inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium border border-paper-line text-ink-soft hover:bg-paper transition-all disabled:opacity-40"
              >
                <RefreshCw size={12} className={logsLoading ? "spin" : ""} />
                Refresh
              </button>
            </div>
          </div>

          {canSendEmail && (
            <form onSubmit={handleSendEmail} className="mb-5 flex flex-wrap items-end gap-3 p-4 border border-paper-line rounded-lg bg-paper/50">
              <div className="flex-1 min-w-[200px]">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-xs font-medium text-ink-soft">Recipient Email</span>
                  <input
                    type="email"
                    value={recipientEmail}
                    onChange={(e) => setRecipientEmail(e.target.value)}
                    placeholder="Enter recipient email address…"
                    required
                    className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                  />
                </label>
              </div>
              <button
                type="submit"
                disabled={emailBusy}
                className="btn-primary inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-sm font-medium bg-freight text-white hover:bg-freight-dark disabled:opacity-50 transition-all shadow-sm"
              >
                <Mail size={14} />
                {emailBusy ? "Sending…" : "Send Invoice Email"}
              </button>
            </form>
          )}

          {staff && showAddLog && (
            <AddSendLogForm
              invoiceId={invoice.id}
              invoiceNumber={invoice.number || invoice.invoice_number}
              token={token}
              onCreated={handleLogCreated}
              onCancel={() => setShowAddLog(false)}
            />
          )}

          {sendLogs.length === 0 ? (
            <p className="text-sm text-ink-faint py-4 text-center">This invoice has not been e-mailed yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-ink-faint border-b border-paper-line">
                    <th className="py-2 pr-3 font-medium">Recipient Email</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Sent At</th>
                    <th className="py-2 pr-3 font-medium text-center">Attempts</th>
                    <th className="py-2 pr-3 font-medium">Created At</th>
                    {staff && <th className="py-2 pr-3 font-medium">Error Message</th>}
                    <th className="py-2 w-6" />
                  </tr>
                </thead>
                <tbody>
                  {sendLogs.map((log) => (
                    <LogRow key={log.id} log={log} staff={staff} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* ── Section 3: Pay Popup Modal ── */}
      <PayModal
        invoice={invoice}
        isOpen={showPayModal}
        onClose={() => setShowPayModal(false)}
        onSuccess={handlePaymentSuccess}
      />
    </Layout>
  );
}
