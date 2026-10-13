import { useState } from "react";
import { motion } from "framer-motion";
import { Search, FileCheck2 } from "lucide-react";
import Layout from "../components/Layout.jsx";
import StatusTimeline from "../components/StatusTimeline.jsx";
import { Card, Button, Input, ErrorBanner } from "../components/ui.jsx";
import { api } from "../api/client.js";

export default function Track() {
  const [value, setValue] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    if (!value.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.trackOrder(value.trim().toUpperCase());
      setResult(data);
    } catch (err) {
      setResult(null);
      setError("No shipment found for that tracking number.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout eyebrow="Public tracking · no login required at the API" title="Track Shipment">
      <Card className="p-6 max-w-2xl">
        <form onSubmit={onSubmit} className="flex gap-3 items-end">
          <div className="flex-1">
            <Input
              label="Tracking number"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="e.g. 097915D9D2"
              className="font-mono"
            />
          </div>
          <Button type="submit" disabled={loading}>
            <Search size={14} /> {loading ? "Searching…" : "Track"}
          </Button>
        </form>
        <ErrorBanner message={error} />
      </Card>

      {result && (
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="p-7 max-w-2xl mt-6">
            <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
              <div>
                <p className="font-mono text-xs text-scan">{result.tracking_number}</p>
                <h3 className="font-display text-lg font-semibold text-ink mt-1">{result.order_number}</h3>
              </div>
              <StatusTimeline status={result.status} />
            </div>

            <div className="grid sm:grid-cols-2 gap-4 text-sm mb-6">
              <div>
                <p className="text-xs text-ink-faint mb-1">From</p>
                <p className="text-ink">{result.origin_city || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-ink-faint mb-1">To</p>
                <p className="text-ink">{result.destination_city || "—"}</p>
              </div>
            </div>

            <p className="text-xs font-medium tracking-wide uppercase text-ink-faint mb-3">Milestone trail</p>
            <ol className="relative border-l border-paper-line ml-2 space-y-5">
              {result.events?.map((ev) => (
                <li key={ev.id} className="ml-5">
                  <span className="absolute -left-[7px] mt-1 w-3.5 h-3.5 rounded-full bg-freight border-2 border-paper-card" />
                  <div className="flex items-center gap-2">
                    <FileCheck2 size={13} className="text-scan" />
                    <p className="text-sm text-ink font-medium">{ev.document_name}</p>
                  </div>
                  <p className="text-xs font-mono text-ink-faint/70 mt-0.5">
                    {new Date(ev.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ol>
          </Card>
        </motion.div>
      )}
    </Layout>
  );
}
