import React, { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { formatMoney } from "../utils/invoice.js";

export default function CreateInvoiceModal({ isOpen, onClose, onSuccess }) {
  const { token } = useAuth();

  const [customers, setCustomers] = useState([]);
  const [tagsList, setTagsList] = useState([]);
  const [loadingLookups, setLoadingLookups] = useState(true);

  const [customer, setCustomer] = useState("");
  const [newCustomerName, setNewCustomerName] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split("T")[0];
  });
  const [selectedTags, setSelectedTags] = useState([]);
  const [lines, setLines] = useState([
    { description: "", quantity: 1, unit_price: 100.0, tax_percent: 10.0 },
  ]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoadingLookups(true);
    Promise.all([api.listCustomers(token), api.listTags(token)])
      .then(([custRes, tagRes]) => {
        const custs = Array.isArray(custRes) ? custRes : custRes?.results || [];
        const tags = Array.isArray(tagRes) ? tagRes : tagRes?.results || [];
        setCustomers(custs);
        setTagsList(tags);
        if (custs.length > 0) setCustomer(String(custs[0].id));
      })
      .catch((err) => {
        console.error("Lookup error:", err);
      })
      .finally(() => setLoadingLookups(false));
  }, [isOpen, token]);

  if (!isOpen) return null;

  function handleLineChange(idx, field, val) {
    setLines((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [field]: val };
      return copy;
    });
  }

  function addLine() {
    setLines((prev) => [
      ...prev,
      { description: "", quantity: 1, unit_price: 0, tax_percent: 0 },
    ]);
  }

  function removeLine(idx) {
    if (lines.length === 1) return;
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  function toggleTag(tagId) {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  }

  const computedTotals = lines.reduce(
    (acc, line) => {
      const qty = Number(line.quantity) || 0;
      const price = Number(line.unit_price) || 0;
      const taxPct = Number(line.tax_percent) || 0;
      const untaxed = qty * price;
      const tax = untaxed * (taxPct / 100);
      acc.untaxed += untaxed;
      acc.tax += tax;
      acc.total += untaxed + tax;
      return acc;
    },
    { untaxed: 0, tax: 0, total: 0 }
  );

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!customer && !newCustomerName.trim()) {
      setError("Please select or enter a customer name.");
      return;
    }

    if (lines.length === 0) {
      setError("Please add at least one line item.");
      return;
    }

    setSubmitting(true);
    try {
      let customerId = customer ? Number(customer) : null;
      let customerName = "";

      if (!customerId && newCustomerName.trim()) {
        customerName = newCustomerName.trim();
      }

      const payload = {
        customer: customerId,
        customer_name: customerName,
        invoice_date: invoiceDate,
        due_date: dueDate || null,
        tags: selectedTags,
        lines: lines.map((l) => ({
          product: l.description,
          description: l.description,
          quantity: Number(l.quantity) || 1,
          unit_price: Number(l.unit_price) || 0,
          tax_percent: Number(l.tax_percent) || 0,
        })),
      };

      const newInv = await api.createInvoice(token, payload);
      onSuccess?.(newInv);
      onClose();
    } catch (err) {
      setError(err.message || "Failed to create invoice.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-3xl rounded-xl bg-white shadow-2xl border border-paper-line overflow-hidden flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-paper-line px-6 py-4 bg-paper/40">
          <div>
            <h2 className="text-lg font-semibold text-ink font-display">New Draft Invoice</h2>
            <p className="text-xs text-ink-faint">Create a new customer invoice with line items</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-faint hover:bg-paper hover:text-ink transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="rounded-md border border-alert/30 bg-alert-soft px-4 py-3 text-sm text-alert">
              {error}
            </div>
          )}

          {/* Top metadata grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                Customer *
              </label>
              {customers.length > 0 ? (
                <div className="space-y-1.5">
                  <select
                    value={customer}
                    onChange={(e) => setCustomer(e.target.value)}
                    className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                  >
                    <option value="">-- Or enter new customer name below --</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} {c.email ? `(${c.email})` : ""}
                      </option>
                    ))}
                  </select>
                  {!customer && (
                    <input
                      type="text"
                      placeholder="Enter new customer name..."
                      value={newCustomerName}
                      onChange={(e) => setNewCustomerName(e.target.value)}
                      className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                    />
                  )}
                </div>
              ) : (
                <input
                  type="text"
                  placeholder="Enter customer name..."
                  value={newCustomerName}
                  onChange={(e) => setNewCustomerName(e.target.value)}
                  className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                  Invoice Date
                </label>
                <input
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                  Due Date
                </label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full rounded-md border border-paper-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-freight"
                />
              </div>
            </div>
          </div>

          {/* Tags */}
          {tagsList.length > 0 && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5">
                Tags
              </label>
              <div className="flex flex-wrap gap-2">
                {tagsList.map((tag) => {
                  const isChecked = selectedTags.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => toggleTag(tag.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                        isChecked
                          ? "bg-freight text-white border-freight"
                          : "bg-paper text-ink-soft border-paper-line hover:border-freight"
                      }`}
                    >
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: tag.color || "#888" }}
                      />
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Lines Table */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
                Invoice Lines *
              </label>
              <button
                type="button"
                onClick={addLine}
                className="inline-flex items-center gap-1 text-xs text-freight hover:text-freight-dark font-medium"
              >
                <Plus size={14} /> Add Line
              </button>
            </div>

            <div className="rounded-lg border border-paper-line overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-paper/80 text-ink-faint text-xs uppercase tracking-wider border-b border-paper-line">
                  <tr>
                    <th className="px-3 py-2.5 text-left font-medium">Description / Product</th>
                    <th className="px-3 py-2.5 text-right font-medium w-24">Qty</th>
                    <th className="px-3 py-2.5 text-right font-medium w-28">Unit Price</th>
                    <th className="px-3 py-2.5 text-right font-medium w-24">Tax %</th>
                    <th className="px-3 py-2.5 text-right font-medium w-28">Subtotal</th>
                    <th className="px-3 py-2.5 text-center w-12" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-paper-line">
                  {lines.map((l, idx) => {
                    const subtotal =
                      (Number(l.quantity) || 0) *
                      (Number(l.unit_price) || 0) *
                      (1 + (Number(l.tax_percent) || 0) / 100);
                    return (
                      <tr key={idx} className="hover:bg-paper/40">
                        <td className="p-2">
                          <input
                            type="text"
                            placeholder="e.g. Consulting Services, Freight..."
                            value={l.description}
                            onChange={(e) => handleLineChange(idx, "description", e.target.value)}
                            required
                            className="w-full rounded border border-paper-line px-2.5 py-1.5 text-sm text-ink outline-none focus:border-freight"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            step="any"
                            min="1"
                            value={l.quantity}
                            onChange={(e) => handleLineChange(idx, "quantity", e.target.value)}
                            className="w-full text-right rounded border border-paper-line px-2.5 py-1.5 text-sm text-ink outline-none focus:border-freight font-mono"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            step="any"
                            min="0"
                            value={l.unit_price}
                            onChange={(e) => handleLineChange(idx, "unit_price", e.target.value)}
                            className="w-full text-right rounded border border-paper-line px-2.5 py-1.5 text-sm text-ink outline-none focus:border-freight font-mono"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            step="any"
                            min="0"
                            max="100"
                            value={l.tax_percent}
                            onChange={(e) => handleLineChange(idx, "tax_percent", e.target.value)}
                            className="w-full text-right rounded border border-paper-line px-2.5 py-1.5 text-sm text-ink outline-none focus:border-freight font-mono"
                          />
                        </td>
                        <td className="p-2 text-right font-mono font-medium text-ink">
                          {formatMoney(subtotal)}
                        </td>
                        <td className="p-2 text-center">
                          <button
                            type="button"
                            onClick={() => removeLine(idx)}
                            disabled={lines.length === 1}
                            className="text-ink-faint hover:text-red-500 disabled:opacity-30 p-1 rounded"
                            title="Remove line"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Totals Summary */}
          <div className="flex justify-end pt-2">
            <div className="w-64 space-y-1.5 text-sm bg-paper/50 p-3.5 rounded-lg border border-paper-line">
              <div className="flex justify-between text-ink-soft">
                <span>Untaxed Amount:</span>
                <span className="font-mono">{formatMoney(computedTotals.untaxed)}</span>
              </div>
              <div className="flex justify-between text-ink-soft">
                <span>Taxes:</span>
                <span className="font-mono">{formatMoney(computedTotals.tax)}</span>
              </div>
              <div className="flex justify-between text-base font-semibold text-ink pt-1.5 border-t border-paper-line">
                <span>Total:</span>
                <span className="font-mono text-freight-dark">{formatMoney(computedTotals.total)}</span>
              </div>
            </div>
          </div>

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-paper-line">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-ink-soft hover:text-ink rounded-md border border-paper-line hover:bg-paper transition-colors"
            >
              Discard
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 text-sm font-medium text-white bg-freight hover:bg-freight-dark rounded-md shadow-sm transition-colors disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Save Draft"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
