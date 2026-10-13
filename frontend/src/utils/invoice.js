// Shared helpers for the Accounting / Invoice module.

// Which roles may see invoices. Mirrors the backend rules (admin: all,
// dispatcher: all read-only, vendor: own, driver: none). This only controls
// what is SHOWN — the API enforces it for real.
export const INVOICE_ROLES = ["admin", "dispatcher", "vendor"];
export const canViewInvoices = (role) => INVOICE_ROLES.includes(role);
export const canResendInvoice = (role) => role === "admin";
export const canBillOrders = (role) => role === "admin" || role === "dispatcher";
export const isStaff = (role) => role === "admin" || role === "dispatcher";

export function formatMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatDate(iso, withTime = false) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return withTime
    ? d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// Opens a PDF in a new tab. The PDF endpoints need the Bearer token, so we
// fetch a Blob first. The tab is opened synchronously (before the await) so
// browsers don't treat it as a blocked pop-up; if it is blocked anyway we fall
// back to a normal download.
export async function openPdf(getBlob, filename = "invoice.pdf") {
  const tab = window.open("", "_blank");
  try {
    const blob = await getBlob();
    const url = URL.createObjectURL(blob);
    if (tab) {
      tab.location.href = url;
    } else {
      triggerDownload(url, filename);
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    if (tab) tab.close();
    throw err;
  }
}

export async function downloadPdf(getBlob, filename = "invoice.pdf") {
  const blob = await getBlob();
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
