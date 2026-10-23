const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, token, auth = true, query, signal } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;

  const qs = query
    ? "?" + Object.entries(query).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&")
    : "";

  const res = await fetch(`${API_URL}${path}${qs}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;

  if (!res.ok) {
    const message = data?.detail
      ? typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail)
      : `Request failed (${res.status})`;
    throw new ApiError(message, res.status, data?.detail);
  }
  return data;
}

// Binary download with auth. Invoice PDFs are now protected, so they cannot be
// opened with a plain link: fetch them with the token and hand back a Blob.
async function requestBlob(path, { token, query } = {}) {
  const qs = query ? "?" + new URLSearchParams(query).toString() : "";
  const res = await fetch(`${API_URL}${path}${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail || "";
    } catch {
      /* not JSON */
    }
    const message =
      detail || (res.status === 403 ? "You do not have access to this invoice." : `Request failed (${res.status})`);
    throw new ApiError(message, res.status, detail);
  }
  return res.blob();
}

// Drop empty filter values so they are not sent as "?status=".
function cleanQuery(query = {}) {
  return Object.fromEntries(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== ""));
}

export const api = {
  me: (token) => request("/auth/me", { token }),
  register: (payload) => request("/auth/register", { method: "POST", body: payload, auth: false }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload, auth: false }),

  listVendors: (token, query) => request("/vendors/", { token, query: cleanQuery(query) }),
  createVendor: (token, payload) => request("/vendors/", { method: "POST", body: payload, token }),
  updateVendor: (token, vendorId, payload) =>
    request(`/vendors/${vendorId}/`, { method: "PATCH", body: payload, token }),
  deleteVendor: (token, vendorId) =>
    request(`/vendors/${vendorId}/`, { method: "DELETE", token }),
  linkVendorUser: (token, vendorId, userId) =>
    request(`/vendors/${vendorId}/link_user/`, { method: "POST", body: { user_id: userId }, token }),

  /**
   * List orders. Supports rich filtering:
   * query: { status, customer_name, customer_phone, tracking_number, is_cod,
   *          vendor, driver, created_after, created_before,
   *          search, sort_by, order, page, page_size }
   */
  listOrders: (token, query, signal) =>
    request("/orders/", { token, query: cleanQuery(query || {}), signal }),
  createOrder: (token, payload) => request("/orders/", { method: "POST", body: payload, token }),
  getOrder: (token, orderId) => request(`/orders/${orderId}`, { token }),
  trackOrder: (trackingNumber) => request(`/orders/track/${trackingNumber}`, { auth: false }),
  bookOrder: (token, orderId, payload) => request(`/orders/${orderId}/book`, { method: "POST", body: payload, token }),
  advanceOrder: (token, orderId, remarks) =>
    request(`/orders/${orderId}/advance`, { method: "POST", token, query: { remarks } }),
  deliveryAttempt: (token, orderId, payload) =>
    request(`/orders/${orderId}/delivery-attempt`, { method: "POST", body: payload, token }),
  reattempt: (token, orderId, remarks) =>
    request(`/orders/${orderId}/reattempt`, { method: "POST", token, query: { remarks } }),
  initiateRto: (token, orderId, remarks) =>
    request(`/orders/${orderId}/rto`, { method: "POST", token, query: { remarks } }),
  closeBilling: (token, orderId, freightCharge) =>
    request(`/orders/${orderId}/close-billing`, { method: "POST", token, query: { freight_charge: freightCharge } }),
  listOrderNotifications: (token, orderId, signal) =>
    request(`/orders/${orderId}/notifications`, { token, signal }),
  retryNotification: (token, notificationId) =>
    request(`/notifications/${notificationId}/retry/`, { method: "POST", token }),
  listNotifications: (token, query, signal) =>
    request("/notifications/", { token, query: cleanQuery(query), signal }),
  // Kept for backwards compatibility; the endpoint now requires a token, so
  // use fetchOrderInvoicePdf() instead of linking to this URL directly.
  invoiceUrl: (orderId) => `${API_URL}/orders/${orderId}/invoice.pdf`,

  // ---- Invoices (Accounting module) ----
  listInvoices: (token, query, signal) => request("/invoices/", { token, query: cleanQuery(query), signal }),
  getOrderInvoice: (token, orderId, signal) => request("/invoices/", { token, query: { order_id: orderId }, signal }),
  getInvoice: (token, invoiceId, signal) => request(`/invoices/${invoiceId}/`, { token, signal }),
  fetchInvoicePdf: (token, invoiceId) => requestBlob(`/invoices/${invoiceId}/pdf/`, { token }),
  fetchOrderInvoicePdf: (token, orderId) => requestBlob(`/orders/${orderId}/invoice.pdf`, { token }),
  sendInvoiceEmail: (token, invoiceId, recipientEmail) =>
    request(`/invoices/${invoiceId}/send-email/`, {
      method: "POST",
      token,
      body: recipientEmail ? { recipient_email: recipientEmail } : undefined,
    }),
  listInvoiceSendLogs: (token, invoiceId, signal) => request(`/invoices/${invoiceId}/send-logs/`, { token, signal }),
  createSendLog: (token, invoiceId, payload) =>
    request(`/invoices/${invoiceId}/create-send-log/`, { method: "POST", body: payload, token }),
  /** Admin only: transition invoice status (draft→issued→paid→cancelled). */
  updateInvoiceStatus: (token, invoiceId, newStatus) =>
    request(`/invoices/${invoiceId}/update-status/`, { method: "PATCH", body: { status: newStatus }, token }),
  /** Admin only: delete an unpaid invoice. */
  deleteInvoice: (token, invoiceId) => request(`/invoices/${invoiceId}/`, { method: "DELETE", token }),
  updateInvoice: (token, invoiceId, payload) =>
    request(`/invoices/${invoiceId}/`, { method: "PATCH", body: payload, token }),

  // ---- Accounting Enhancements (State, Pay, Group By, Master Data) ----
  confirmInvoice: (token, invoiceId) =>
    request(`/invoices/${invoiceId}/confirm/`, { method: "POST", token }),
  resetInvoiceToDraft: (token, invoiceId) =>
    request(`/invoices/${invoiceId}/reset-to-draft/`, { method: "POST", token }),
  payInvoice: (token, invoiceId, payload) =>
    request(`/invoices/${invoiceId}/pay/`, { method: "POST", body: payload, token }),
  createInvoice: (token, payload) =>
    request("/invoices/", { method: "POST", body: payload, token }),
  getGroupedInvoices: (token, query, signal) =>
    request("/invoices/grouped/", { token, query: cleanQuery(query), signal }),

  listJournals: (token) => request("/journals/", { token }),
  listCustomers: (token) => request("/customers/", { token }),
  listTags: (token) => request("/tags/", { token }),
  createTag: (token, payload) => request("/tags/", { method: "POST", body: payload, token }),
  seedDefaultTags: (token) => request("/tags/seed_defaults/", { method: "POST", token }),
  listPayments: (token, query, signal) =>
    request("/payments/", { token, query: cleanQuery(query), signal }),
  getGroupedPayments: (token, query, signal) =>
    request("/payments/grouped/", { token, query: cleanQuery(query), signal }),

  // Accounting Dashboard Summary API
  getDashboardSummary: (token, query, signal) =>
    request("/dashboard/summary/", { token, query: cleanQuery(query), signal }),

  getDashboardStats: (token) => request("/dashboard/stats", { token }),

  listDrivers: (token) => request("/fleet/drivers", { token }),
  createDriver: (token, payload) => request("/fleet/drivers", { method: "POST", body: payload, token }),
  updateDriverLocation: (token, driverId, payload) =>
    request(`/fleet/drivers/${driverId}/location`, { method: "PATCH", body: payload, token }),

  assignDriver: (token, orderId) =>
    request(`/dispatch/orders/${orderId}/assign`, { method: "POST", token }),
};


export { ApiError };
