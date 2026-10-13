// Signature element: a checkpoint-style transit line showing where an order
// sits in the FRD's First Mile -> Linehaul -> Last Mile -> Closed flow.
// Condensed to 4 phases (instead of all 14 raw milestones) so it reads at a
// glance, like a shipping manifest scan log.

const PHASES = ["First Mile", "Linehaul", "Last Mile", "Closed"];

const PHASE_OF = {
  order_received: 0,
  booking_planned: 0,
  pickup_completed: 0,
  label_verified: 0,
  manifest_created: 0,
  at_origin_hub: 0,
  sorted_at_origin: 1,
  dispatched_linehaul: 1,
  at_destination_hub: 1,
  route_planned: 1,
  out_for_delivery: 2,
  delivery_attempted: 2,
  delivered: 2,
  closed: 3,
};

const EXCEPTION_LABELS = {
  delivery_failed: "Delivery Failed",
  reattempt_scheduled: "Reattempt Scheduled",
  rto_initiated: "RTO Initiated",
  returned: "Returned",
  cancelled: "Cancelled",
};

export default function StatusTimeline({ status }) {
  if (status in EXCEPTION_LABELS) {
    return (
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-alert animate-pulse" aria-hidden="true" />
        <span className="font-mono text-xs uppercase tracking-wide text-alert">
          {EXCEPTION_LABELS[status]}
        </span>
      </div>
    );
  }

  const currentIndex = PHASE_OF[status] ?? 0;

  return (
    <div className="flex items-center" role="img" aria-label={`Order phase: ${PHASES[currentIndex]}`}>
      {PHASES.map((stage, i) => {
        const reached = i <= currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <div key={stage} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <span
                className={[
                  "h-2.5 w-2.5 rounded-full border transition-colors duration-300",
                  reached ? "bg-freight border-freight" : "bg-transparent border-paper-line",
                  isCurrent ? "ring-2 ring-freight-soft" : "",
                ].join(" ")}
                aria-hidden="true"
              />
              <span
                className={[
                  "font-mono text-[10px] uppercase tracking-wide whitespace-nowrap",
                  isCurrent ? "text-freight-dark font-semibold" : "text-ink-faint",
                ].join(" ")}
              >
                {stage}
              </span>
            </div>
            {i < PHASES.length - 1 && (
              <span
                className={["h-px w-6 md:w-8 -mt-4 transition-colors duration-300", i < currentIndex ? "bg-freight" : "bg-paper-line"].join(" ")}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
