import React, { useEffect, useState } from "react";
import Layout from "../components/Layout.jsx";
import { Card, Button, Input, ErrorBanner, EmptyState } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";

const emptyForm = { full_name: "", phone: "" };
const emptyLocationForm = { latitude: "", longitude: "" };

export default function Fleet() {
  const { token, role } = useAuth();
  const [drivers, setDrivers] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [locationForms, setLocationForms] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  async function loadDrivers() {
    const data = await api.listDrivers(token);
    const list = Array.isArray(data) ? data : data?.results || [];
    setDrivers(list);
  }

  useEffect(() => {
    loadDrivers()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api.createDriver(token, form);
      setForm(emptyForm);
      await loadDrivers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function updateLocation(driverId) {
    const loc = locationForms[driverId] || emptyLocationForm;
    if (!loc.latitude || !loc.longitude) return;
    setError("");
    try {
      await api.updateDriverLocation(token, driverId, {
        latitude: Number(loc.latitude),
        longitude: Number(loc.longitude),
      });
      await loadDrivers();
    } catch (err) {
      setError(err.message);
    }
  }

  const isAdmin = role === "admin";

  return (
    <Layout eyebrow="Last-mile capacity" title="Fleet">
      <div className={`grid grid-cols-1 ${isAdmin ? "lg:grid-cols-3" : "lg:grid-cols-1"} gap-6`}>
        {isAdmin && (
          <Card className="p-6 lg:col-span-1 h-fit">
            <h3 className="font-display font-semibold text-ink mb-4">New driver</h3>
            <ErrorBanner message={error} />
            <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <Input label="Full name" required value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            <Input label="Phone" required value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <Button type="submit" disabled={submitting} className="mt-2">
              {submitting ? "Adding…" : "Add driver"}
            </Button>
          </form>
        </Card>
        )}

        <div className="lg:col-span-2">
          {loading ? (
            <p className="text-ink-faint text-sm">Loading drivers…</p>
          ) : drivers.length === 0 ? (
            <EmptyState title="No drivers yet" hint="Add your first driver using the form." />
          ) : (
            <div className="flex flex-col gap-4">
              {drivers.map((d) => (
                <Card key={d.id} className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-display font-medium text-ink">{d.full_name}</p>
                      <p className="font-mono text-xs text-ink-faint">{d.phone}</p>
                    </div>
                    <span
                      className={[
                        "font-mono text-[10px] uppercase tracking-wide px-2 py-1 rounded-full",
                        d.is_available ? "bg-freight-soft text-freight-dark" : "bg-paper text-ink-faint",
                      ].join(" ")}
                    >
                      {d.is_available ? "Available" : "On delivery"}
                    </span>
                  </div>
                  <div className="flex items-end gap-2">
                    <Input
                      label="Lat"
                      type="number"
                      step="any"
                      placeholder={d.current_lat?.toFixed(4) ?? "23.03"}
                      value={locationForms[d.id]?.latitude ?? ""}
                      onChange={(e) =>
                        setLocationForms({
                          ...locationForms,
                          [d.id]: { ...(locationForms[d.id] || emptyLocationForm), latitude: e.target.value },
                        })
                      }
                    />
                    <Input
                      label="Lng"
                      type="number"
                      step="any"
                      placeholder={d.current_lng?.toFixed(4) ?? "72.51"}
                      value={locationForms[d.id]?.longitude ?? ""}
                      onChange={(e) =>
                        setLocationForms({
                          ...locationForms,
                          [d.id]: { ...(locationForms[d.id] || emptyLocationForm), longitude: e.target.value },
                        })
                      }
                    />
                    <Button variant="ghost" onClick={() => updateLocation(d.id)}>
                      Update
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
