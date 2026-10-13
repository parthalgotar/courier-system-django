import React, { useEffect, useState } from "react";
import { X, DollarSign, AlertCircle, Check } from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function PayModal({ invoice, isOpen, onClose, onSuccess }) {
  const { token } = useAuth();
  const [journals, setJournals] = useState([]);
  const [journalId, setJournalId] = useState("");
  const [amount, setAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState("");
  const [memo, setMemo] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Initialize modal fields when opened
  useEffect(() => {
    if (!isOpen || !invoice) return;

    const todayStr = new Date().toISOString().split("T")[0];
    const due = Number(invoice.amount_due || invoice.total_amount || 0);

    setAmount(due > 0 ? due.toFixed(2) : "0.00");
    setPaymentDate(todayStr);
    setMemo(invoice.number || invoice.invoice_number || `Invoice #${invoice.id}`);
    setError("");

    // Fetch journals
    api.listJournals(token)
      .then((res) => {
        const list = Array.isArray(res) ? res : res?.results || [];
        setJournals(list);
        // Default to "Cash" if present, else first journal
        const cashJournal = list.find((j) => (j.name || "").toLowerCase() === "cash" || j.type === "cash");
        if (cashJournal) {
          setJournalId(cashJournal.id.toString());
        } else if (list.length > 0) {
          setJournalId(list[0].id.toString());
        }
      })
      .catch(() => {});
  }, [isOpen, invoice, token]);

  if (!isOpen || !invoice) return null;

  const maxDue = Number(invoice.amount_due || invoice.total_amount || 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount <= 0) {
      setError("Payment amount must be greater than zero.");
      return;
    }
    if (numAmount > maxDue + 0.001) {
      setError(`Payment amount cannot exceed the remaining due amount of $${maxDue.toFixed(2)}.`);
      return;
    }
    if (!paymentDate) {
      setError("Payment date is required.");
      return;
    }
    if (!journalId) {
      setError("Please select a journal.");
      return;
    }

    setBusy(true);
    try {
      await api.payInvoice(token, invoice.id, {
        journal: parseInt(journalId, 10),
        amount: numAmount.toFixed(2),
        payment_date: paymentDate,
        memo: memo.trim(),
      });
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || "Failed to record payment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-paper-card border border-paper-line rounded-xl shadow-2xl max-w-xl w-full overflow-hidden scale-in">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-paper-line bg-paper/60">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">Pay</h3>
            <p className="text-xs text-ink-faint">
              Register payment for {invoice.number || invoice.invoice_number || `Invoice #${invoice.id}`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-ink-faint hover:text-ink hover:bg-paper transition-all"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit}>
          <div className="p-6">
            {error && (
              <div className="mb-4 flex items-start gap-2 p-3 rounded-md bg-alert-soft border border-alert/30 text-xs text-alert animate-in fade-in">
                <AlertCircle size={15} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* 2-Column Layout */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* LEFT COLUMN: Journal */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                    Journal
                  </label>
                  <select
                    value={journalId}
                    onChange={(e) => setJournalId(e.target.value)}
                    required
                    className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight transition-all shadow-xs"
                  >
                    {journals.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.name} ({j.type_display || j.type})
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-ink-faint mt-1.5">
                    Select payment account (Cash or Bank).
                  </p>
                </div>

                <div className="p-3.5 rounded-lg bg-paper/80 border border-paper-line space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-ink-faint">Total Amount:</span>
                    <span className="font-mono font-medium text-ink">
                      ${Number(invoice.amount_total || invoice.total_amount || 0).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-ink-faint">Already Paid:</span>
                    <span className="font-mono text-emerald-600">
                      ${Number(invoice.amount_paid || 0).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs font-semibold pt-1 border-t border-paper-line">
                    <span className="text-ink">Amount Due:</span>
                    <span className="font-mono text-freight">${maxDue.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN: Amount, Payment Date, Memo */}
              <div className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                    Amount
                  </label>
                  <div className="relative flex items-center">
                    <span className="absolute left-3 text-sm font-semibold text-ink-faint">
                      $
                    </span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max={maxDue}
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      required
                      placeholder="0.00"
                      className="w-full pl-7 pr-12 rounded-md border border-paper-line bg-white py-2 text-sm font-mono text-ink outline-none focus:border-freight transition-all shadow-xs"
                    />
                    <span className="absolute right-3 text-xs font-semibold text-ink-faint">
                      USD
                    </span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                    Payment Date
                  </label>
                  <input
                    type="date"
                    value={paymentDate}
                    onChange={(e) => setPaymentDate(e.target.value)}
                    required
                    className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight transition-all shadow-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                    Memo
                  </label>
                  <input
                    type="text"
                    value={memo}
                    onChange={(e) => setMemo(e.target.value)}
                    placeholder="Reference memo or note"
                    className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint outline-none focus:border-freight transition-all shadow-xs"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="flex items-center justify-end gap-2.5 px-6 py-4 border-t border-paper-line bg-paper/30">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="px-4 py-2 rounded-md text-xs font-medium border border-paper-line bg-white hover:bg-paper text-ink transition-all disabled:opacity-50"
            >
              Discard
            </button>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold bg-freight text-white hover:bg-freight-dark transition-all disabled:opacity-50 shadow-xs hover:shadow-glow"
            >
              {busy ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Processing…</span>
                </>
              ) : (
                <>
                  <Check size={14} />
                  <span>Create Payment</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
