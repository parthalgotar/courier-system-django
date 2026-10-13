import React, { useEffect, useState } from "react";
import { Mail, Phone, Edit2, X } from "lucide-react";
import Layout from "../components/Layout.jsx";
import { Card, Button, Input, ErrorBanner, EmptyState } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";

const emptyForm = { name: "", email: "", contact_phone: "", address: "", latitude: "", longitude: "" };

export default function Vendors() {
  const { token, role } = useAuth();
  const [vendors, setVendors] = useState([]);
  const [editingVendor, setEditingVendor] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  async function loadVendors() {
    const data = await api.listVendors(token);
    const list = Array.isArray(data) ? data : data?.results || [];
    setVendors(list);
  }

  useEffect(() => {
    loadVendors()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function startEdit(v) {
    setEditingVendor(v);
    setForm({
      name: v.name || "",
      email: v.email || "",
      contact_phone: v.contact_phone || "",
      address: v.address || "",
      latitude: v.latitude != null ? String(v.latitude) : "",
      longitude: v.longitude != null ? String(v.longitude) : "",
    });
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEdit() {
    setEditingVendor(null);
    setForm(emptyForm);
    setError("");
  }

  async function handleSave(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    const payload = {
      name: form.name.trim(),
      email: form.email.trim(),
      contact_phone: form.contact_phone.trim(),
      address: form.address.trim(),
      latitude: form.latitude ? Number(form.latitude) : null,
      longitude: form.longitude ? Number(form.longitude) : null,
    };
    try {
      if (editingVendor) {
        await api.updateVendor(token, editingVendor.id, payload);
      } else {
        await api.createVendor(token, payload);
      }
      setEditingVendor(null);
      setForm(emptyForm);
      await loadVendors();
    } catch (err) {
      setError(err.message || "Failed to save vendor.");
    } finally {
      setSubmitting(false);
    }
  }

  const isAdmin = role === "admin";

  return (
    <Layout eyebrow="First-mile pickup points" title="Vendors">
      <div className={`grid grid-cols-1 ${isAdmin ? "lg:grid-cols-3" : "lg:grid-cols-1"} gap-6`}>
        {isAdmin && (
          <Card className={`p-6 lg:col-span-1 h-fit transition-all duration-200 ${editingVendor ? "border-freight ring-1 ring-freight/30 shadow-md" : ""}`}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display font-semibold text-ink">
                {editingVendor ? `Edit: ${editingVendor.name}` : "New vendor"}
              </h3>
              {editingVendor && (
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="text-xs text-ink-faint hover:text-ink flex items-center gap-1 font-mono uppercase"
                  title="Cancel edit"
                >
                  <X size={14} /> Cancel
                </button>
              )}
            </div>
            <ErrorBanner message={error} />
            <form onSubmit={handleSave} className="flex flex-col gap-3">
              <Input
                label="Name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Fresh Farms"
              />
              <Input
                label="Email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="vendor@example.com"
              />
              <Input
                label="Contact phone"
                required
                value={form.contact_phone}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                placeholder="09104144971"
              />
              <Input
                label="Address"
                required
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="Warehouse 4, Port Area"
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Latitude"
                  type="number"
                  step="any"
                  value={form.latitude}
                  onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                  placeholder="23.02"
                />
                <Input
                  label="Longitude"
                  type="number"
                  step="any"
                  value={form.longitude}
                  onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                  placeholder="72.57"
                />
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Button type="submit" disabled={submitting} className="flex-1">
                  {submitting ? "Saving…" : editingVendor ? "Save changes" : "Add vendor"}
                </Button>
                {editingVendor && (
                  <Button type="button" variant="ghost" onClick={cancelEdit}>
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </Card>
        )}

        <div className="lg:col-span-2">
          {loading ? (
            <p className="text-ink-faint text-sm">Loading vendors…</p>
          ) : vendors.length === 0 ? (
            <EmptyState title="No vendors yet" hint="Add your first pickup point using the form." />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {vendors.map((v) => {
                const isCurrent = editingVendor?.id === v.id;
                return (
                  <Card
                    key={v.id}
                    className={`p-5 relative transition-all duration-200 ${
                      isCurrent ? "border-freight ring-2 ring-freight/30 bg-freight/5" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-display font-medium text-ink text-base">{v.name}</p>
                      {isAdmin && (
                        <button
                          type="button"
                          onClick={() => startEdit(v)}
                          className="text-xs font-medium text-freight hover:text-freight-dark hover:underline inline-flex items-center gap-1 transition-colors px-2 py-0.5 rounded hover:bg-paper"
                          title="Edit this vendor"
                        >
                          <Edit2 size={12} /> Edit
                        </button>
                      )}
                    </div>
                    <p className="font-mono text-xs text-freight-dark/90 mt-1.5 flex items-center gap-1.5">
                      <Mail size={12} className="text-freight shrink-0" />
                      {v.email ? (
                        <span className="truncate">{v.email}</span>
                      ) : (
                        <span className="text-ink-faint italic font-sans text-[11px]">No email address</span>
                      )}
                    </p>
                    <p className="font-mono text-xs text-ink-faint mt-1 flex items-center gap-1.5">
                      <Phone size={12} className="shrink-0" />
                      <span>{v.contact_phone || "—"}</span>
                    </p>
                    <p className="text-sm text-ink-soft mt-2">{v.address}</p>
                    {v.latitude != null && (
                      <p className="font-mono text-[11px] text-ink-faint mt-1">
                        GPS: {v.latitude.toFixed(4)}, {v.longitude.toFixed(4)}
                      </p>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
