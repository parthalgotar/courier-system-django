import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Layers, ChevronDown, Check, RefreshCw, CheckCircle2, Plus } from "lucide-react";
import Layout from "../components/Layout.jsx";
import StatusTimeline from "../components/StatusTimeline.jsx";
import OrderDrawer from "../components/OrderDrawer.jsx";
import NewOrderModal from "../components/orders/NewOrderModal.jsx";
import GroupByDropdown, { ORDER_GROUP_BY_OPTIONS } from "../components/GroupByDropdown.jsx";
import GroupByBar from "../components/GroupByBar.jsx";
import { Card, Button, Input, EmptyState } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";

function OrderCardSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[...Array(4)].map((_, i) => (
        <Card key={i} className="p-5 border border-paper-line bg-paper-card">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="space-y-2">
              <div className="h-3.5 w-24 skeleton-pulse" />
              <div className="h-4.5 w-40 skeleton-pulse" />
              <div className="h-3.5 w-60 skeleton-pulse" />
            </div>
            <div className="h-5 w-24 skeleton-pulse rounded-full" />
          </div>
          <div className="h-6 w-full skeleton-pulse rounded-md mt-2" />
        </Card>
      ))}
    </div>
  );
}

const ORDER_STATUSES = [
  "", "order_received", "booking_planned", "pickup_completed", "label_verified",
  "manifest_created", "at_origin_hub", "sorted_at_origin", "dispatched_linehaul",
  "at_destination_hub", "route_planned", "out_for_delivery", "delivery_attempted",
  "delivery_failed", "reattempt_scheduled", "delivered", "rto_initiated", "returned",
  "closed", "cancelled",
];

const STATUS_LABELS = {
  "": "All statuses",
  order_received: "Order Received",
  booking_planned: "Booking Planned",
  pickup_completed: "Pickup Completed",
  label_verified: "Label Verified",
  manifest_created: "Manifest Created",
  at_origin_hub: "At Origin Hub",
  sorted_at_origin: "Sorted at Origin",
  dispatched_linehaul: "Dispatched (Linehaul)",
  at_destination_hub: "At Destination Hub",
  route_planned: "Route Planned",
  out_for_delivery: "Out for Delivery",
  delivery_attempted: "Delivery Attempted",
  delivery_failed: "Delivery Failed",
  reattempt_scheduled: "Reattempt Scheduled",
  delivered: "Delivered",
  rto_initiated: "RTO Initiated",
  returned: "Returned",
  closed: "Closed",
  cancelled: "Cancelled",
};

function getGroupValue(order, groupKey, vendorsMap = {}) {
  if (!groupKey) return "All";

  if (groupKey.startsWith("order_date:") || groupKey === "order_date") {
    const sub = groupKey.includes(":") ? groupKey.split(":")[1] : "month";
    const d = order.order_date
      ? new Date(order.order_date + "T00:00:00")
      : (order.created_at ? new Date(order.created_at) : null);
    if (!d || Number.isNaN(d.getTime())) return "No Date";
    if (sub === "year") return d.getFullYear().toString();
    if (sub === "quarter") return `Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
    if (sub === "day") return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
    return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  }

  if (groupKey.startsWith("pickup_date:") || groupKey === "pickup_date") {
    const sub = groupKey.includes(":") ? groupKey.split(":")[1] : "month";
    const d = order.pickup_date ? new Date(order.pickup_date) : (order.created_at ? new Date(order.created_at) : null);
    if (!d || Number.isNaN(d.getTime())) return "No Date";
    if (sub === "year") return d.getFullYear().toString();
    if (sub === "quarter") return `Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
    if (sub === "day") return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
    return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  }

  if (groupKey.startsWith("delivery_date:") || groupKey === "delivery_date") {
    const sub = groupKey.includes(":") ? groupKey.split(":")[1] : "month";
    const d = order.updated_at ? new Date(order.updated_at) : null;
    if (!d || Number.isNaN(d.getTime())) return "No Date";
    if (sub === "year") return d.getFullYear().toString();
    if (sub === "quarter") return `Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
    if (sub === "day") return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
    return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  }

  switch (groupKey) {
    case "vendor":
    case "partner":
    case "custom:vendor": {
      const vName = order.vendor_name || (vendorsMap[order.vendor_id] ? vendorsMap[order.vendor_id].name : null);
      return vName || "Unassigned Vendor";
    }
    case "status":
      return STATUS_LABELS[order.status] || order.status || "Unknown";
    case "driver":
    case "salesperson":
      return order.driver_name || (order.driver_id ? `Driver #${order.driver_id}` : "Unassigned Driver");
    case "customer":
    case "custom:customer":
      return order.customer_name || "Unknown Customer";
    case "route":
    case "journal":
      return order.origin_city && order.destination_city
        ? `${order.origin_city} → ${order.destination_city}`
        : "Direct Logistics Run";
    case "payment_status":
    case "payment_method":
      return order.is_cod ? "Cash on Delivery (COD)" : "Prepaid";
    case "destination":
    case "custom:destination":
      return order.destination_city || "Unknown Destination";
    case "commodity":
    case "custom:commodity":
      return order.commodity || "General Cargo";
    case "amount":
    case "custom:amount": {
      const amt = Number(order.declared_value || order.cod_amount || 0);
      if (amt < 1000) return "Under ₹1,000";
      if (amt < 5000) return "₹1,000 – ₹5,000";
      if (amt < 20000) return "₹5,000 – ₹20,000";
      return "Above ₹20,000";
    }
    case "invoice_date": {
      const d = order.invoice_date ? new Date(order.invoice_date) : null;
      if (!d || Number.isNaN(d.getTime())) return "No Invoice Date";
      return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
    }
    case "sales_team":
      return "Direct Logistics Operations";
    case "peppol_status":
      return order.status === "closed" ? "Billed / Closed" : "In Progress";
    case "company":
      return "Manifest ERP Logistics";
    default:
      return "Other";
  }
}

const emptyFilters = {
  search: "",
  tracking_number: "",
  status: "",
  customer_name: "",
  customer_phone: "",
  is_cod: "",
  created_after: "",
  created_before: "",
};

const PAGE_SIZE = 50;

export default function Orders() {
  const { token, role } = useAuth();
  const [orders, setOrders] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [filters, setFilters] = useState(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState(emptyFilters);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null, page: 1 });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const [isNewOrderOpen, setIsNewOrderOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const abortRef = useRef(null);

  // Multi-level Group By states
  const [activeGroupBys, setActiveGroupBys] = useState([]);
  const [collapsedGroups, setCollapsedGroups] = useState({});

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const vendorsMap = useMemo(() => {
    const map = {};
    for (const v of vendors) {
      map[v.id] = v;
    }
    return map;
  }, [vendors]);

  // Nested multi-level grouped tree builder
  const groupedOrdersTree = useMemo(() => {
    if (!activeGroupBys || activeGroupBys.length === 0) return null;

    function buildTree(items, depth = 0) {
      if (depth >= activeGroupBys.length) {
        return items;
      }
      const groupKey = activeGroupBys[depth];
      const opt = ORDER_GROUP_BY_OPTIONS.find(
        (o) => o.id === groupKey || groupKey.startsWith(`${o.id}:`)
      );
      const fieldLabel = opt?.label || groupKey;
      const groups = {};

      for (const order of items) {
        const val = getGroupValue(order, groupKey, vendorsMap);
        if (!groups[val]) {
          groups[val] = {
            name: val,
            field: groupKey,
            fieldLabel,
            items: [],
            totalAmount: 0,
          };
        }
        groups[val].items.push(order);
        groups[val].totalAmount += Number(
          order.declared_value || order.cod_amount || order.invoice_amount || 0
        );
      }

      return Object.values(groups).map((g) => ({
        ...g,
        children: buildTree(g.items, depth + 1),
      }));
    }

    return buildTree(orders, 0);
  }, [activeGroupBys, orders, vendorsMap]);

  function handleToggleGroupBy(id) {
    setActiveGroupBys((prev) => {
      if (prev.includes(id)) {
        return prev.filter((item) => item !== id);
      }
      const base = id.split(":")[0];
      const existingIdx = prev.findIndex((item) => item === base || item.startsWith(`${base}:`));
      if (existingIdx !== -1) {
        const next = [...prev];
        next[existingIdx] = id;
        return next;
      }
      return [...prev, id];
    });
    setCollapsedGroups({});
  }

  function handleRemoveGroupBy(id) {
    setActiveGroupBys((prev) => prev.filter((item) => item !== id));
    setCollapsedGroups({});
  }

  function handleClearGroupBy() {
    setActiveGroupBys([]);
    setCollapsedGroups({});
  }

  function handleExpandAllGroups() {
    setCollapsedGroups({});
  }

  function handleCollapseAllGroups() {
    const allPaths = {};
    function collectPaths(nodes, prefix = "") {
      for (const n of nodes) {
        const p = `${prefix}/${n.field}:${n.name}`;
        allPaths[p] = true;
        if (n.children && n.children.length > 0 && !("id" in n.children[0])) {
          collectPaths(n.children, p);
        }
      }
    }
    if (groupedOrdersTree) {
      collectPaths(groupedOrdersTree);
    }
    setCollapsedGroups(allPaths);
  }

  function toggleGroupCollapse(nodePath) {
    setCollapsedGroups((prev) => ({
      ...prev,
      [nodePath]: !prev[nodePath],
    }));
  }

  const canCreate = role === "admin" || role === "dispatcher" || role === "vendor";

  const loadOrders = useCallback(async (page = 1, filtersToApply = appliedFilters, currentSort = sortBy, currentOrder = sortOrder) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const query = {
        page,
        page_size: PAGE_SIZE,
        ...(filtersToApply.search ? { search: filtersToApply.search } : {}),
        ...(filtersToApply.tracking_number ? { tracking_number: filtersToApply.tracking_number } : {}),
        ...(filtersToApply.status ? { status: filtersToApply.status } : {}),
        ...(filtersToApply.customer_name ? { customer_name: filtersToApply.customer_name } : {}),
        ...(filtersToApply.customer_phone ? { customer_phone: filtersToApply.customer_phone } : {}),
        ...(filtersToApply.is_cod !== "" ? { is_cod: filtersToApply.is_cod } : {}),
        ...(filtersToApply.created_after ? { created_after: filtersToApply.created_after } : {}),
        ...(filtersToApply.created_before ? { created_before: filtersToApply.created_before } : {}),
        sort_by: currentSort,
        order: currentOrder,
      };
      const data = await api.listOrders(token, query, controller.signal);
      // Handle both paginated { results, count, next, previous } and plain arrays
      if (Array.isArray(data)) {
        setOrders(data);
        setPagination({ count: data.length, next: null, previous: null, page: 1 });
      } else {
        setOrders(data.results || []);
        setPagination({ count: data.count || 0, next: data.next, previous: data.previous, page });
      }
      setError("");
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, appliedFilters, sortBy, sortOrder]);

  useEffect(() => {
    async function load() {
      try {
        const vendorsData = await api.listVendors(token);
        const vList = Array.isArray(vendorsData) ? vendorsData : vendorsData?.results || [];
        setVendors(vList);
      } catch (err) {
        if (err.status !== 403) setError(err.message);
      }
      await loadOrders(1, emptyFilters, "created_at", "desc");
    }
    load();
  }, [token, role]); // eslint-disable-line react-hooks/exhaustive-deps

  function applyFilters(e) {
    if (e && e.preventDefault) e.preventDefault();
    setAppliedFilters({ ...filters });
    loadOrders(1, filters, sortBy, sortOrder);
  }

  function clearFilters() {
    setFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    loadOrders(1, emptyFilters, sortBy, sortOrder);
  }

  function handleSortChange(newSort, newOrder) {
    setSortBy(newSort);
    setSortOrder(newOrder);
    loadOrders(1, appliedFilters, newSort, newOrder);
  }

  const hasActiveFilters = Object.values(appliedFilters).some(Boolean);
  const totalPages = Math.ceil(pagination.count / PAGE_SIZE);

  async function openOrder(order) {
    const full = await api.getOrder(token, order.id);
    setSelected(full);
  }

  function handleUpdate(updated) {
    setSelected(updated);
    loadOrders(pagination.page);
  }

  function handleOrderCreated() {
    setToast("Order created");
    loadOrders(1, appliedFilters, "created_at", "desc");
  }

  function renderOrderCard(order) {
    const vName = order.vendor_name || (vendorsMap[order.vendor_id] ? vendorsMap[order.vendor_id].name : null);
    return (
      <Card
        key={order.id}
        className="p-5 cursor-pointer order-card-interactive border border-paper-line bg-paper-card rounded-lg hover:border-freight/50 hover:shadow-md group relative overflow-hidden"
        onClick={() => openOrder(order)}
      >
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-freight opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <p className="font-mono text-xs text-ink-faint group-hover:text-freight transition-colors duration-150">{order.order_number}</p>
            <p className="font-display font-medium text-ink group-hover:text-freight-dark transition-colors duration-150">{order.customer_name}</p>
            <p className="text-sm text-ink-faint">{order.delivery_address}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            {order.is_cod && (
              <span className="text-xs font-medium text-transit whitespace-nowrap bg-transit-soft/60 px-2 py-0.5 rounded border border-transit/20 transition-transform group-hover:scale-105">
                COD ₹{Number(order.cod_amount).toLocaleString("en-IN")}
              </span>
            )}
            {vName && (
              <span className="text-xs text-ink-faint">{vName}</span>
            )}
          </div>
        </div>
        <StatusTimeline status={order.status} />
      </Card>
    );
  }

  function renderOrderGroupNode(node, depth = 0, pathPrefix = "") {
    const nodePath = `${pathPrefix}/${node.field}:${node.name}`;
    const isCollapsed = Boolean(collapsedGroups[nodePath]);
    const isLeafGroup = node.children && node.children.length > 0 && "id" in node.children[0];
    const orderCount = node.items ? node.items.length : 0;

    return (
      <div
        key={nodePath}
        className="flex flex-col gap-2 rounded-lg transition-all"
        style={{ marginLeft: depth > 0 ? `${Math.min(depth * 16, 48)}px` : undefined }}
      >
        <button
          type="button"
          onClick={() => toggleGroupCollapse(nodePath)}
          className={`flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-lg border text-left transition-all group ${
            depth === 0
              ? "bg-paper-card border-paper-line shadow-xs hover:border-freight/40"
              : "bg-paper/70 border-paper-line/80 hover:border-freight/30"
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className={`p-1 rounded text-ink-soft group-hover:text-freight transition-transform duration-200 ${
                isCollapsed ? "-rotate-90" : "rotate-0"
              }`}
            >
              <ChevronDown size={15} />
            </span>
            <span className="text-xs font-mono font-medium text-ink-faint uppercase tracking-wider px-1.5 py-0.5 rounded bg-paper-line/40">
              {node.fieldLabel || node.field}
            </span>
            <span className="font-display font-semibold text-ink truncate text-sm">
              {node.name}
            </span>
            <span className="text-xs text-ink-soft bg-paper px-2 py-0.5 rounded-full border border-paper-line/60 font-mono">
              {orderCount} {orderCount === 1 ? "order" : "orders"}
            </span>
          </div>
          {node.totalAmount > 0 && (
            <span className="text-xs font-mono font-medium text-transit shrink-0">
              ₹{Math.round(node.totalAmount).toLocaleString("en-IN")}
            </span>
          )}
        </button>

        <AnimatePresence initial={false}>
          {!isCollapsed && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden flex flex-col gap-2 pt-1"
            >
              {isLeafGroup ? (
                <div className="flex flex-col gap-2 pl-2">
                  {node.children.map((order) => renderOrderCard(order))}
                </div>
              ) : (
                node.children.map((childNode) =>
                  renderOrderGroupNode(childNode, depth + 1, nodePath)
                )
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <Layout
      eyebrow="First mile → linehaul → last mile"
      title="Orders"
      action={
        <div className="flex items-center gap-2">
          <GroupByDropdown
            options={ORDER_GROUP_BY_OPTIONS}
            activeGroupBys={activeGroupBys}
            onToggleGroupBy={handleToggleGroupBy}
            onClear={handleClearGroupBy}
          />

          <Button variant="ghost" onClick={() => loadOrders(pagination.page)} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </Button>

          {canCreate && (
            <Button
              type="button"
              onClick={() => setIsNewOrderOpen(true)}
              className="px-4 py-2 text-sm shrink-0 shadow-xs hover:shadow transition-all"
            >
              + New Order
            </Button>
          )}
        </div>
      }
    >
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="fixed top-5 right-5 z-[100] flex items-center gap-2.5 px-4 py-3 bg-[#111827] text-white rounded-lg shadow-xl border border-paper-line/30 text-sm font-medium"
          >
            <CheckCircle2 size={16} className="text-freight shrink-0" />
            <span>{toast}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Full-width Orders List */}
      <div className="w-full">
        {/* Search + Filter toolbar */}
        <div className="mb-4 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              placeholder="Search orders, customer, tracking…"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") applyFilters(e); }}
              className="flex-1 min-w-[200px] rounded-md border border-paper-line bg-white px-3 py-2 text-sm focus:border-freight outline-none transition-all duration-150 focus:ring-2 focus:ring-freight/15 shadow-xs"
            />
            <Button type="button" onClick={applyFilters} className="px-4 py-2 text-sm shrink-0 shadow-xs hover:shadow transition-all">
              Search
            </Button>
            <div className="flex items-center gap-1 shrink-0 bg-white border border-paper-line rounded-md px-2 py-1 shadow-xs">
              <span className="text-xs text-ink-faint">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => handleSortChange(e.target.value, sortOrder)}
                className="text-xs bg-transparent border-none text-ink font-medium focus:outline-none cursor-pointer pr-1"
              >
                <option value="created_at">Date Created</option>
                <option value="order_number">Order #</option>
                <option value="customer_name">Customer</option>
                <option value="weight_kg">Weight</option>
                <option value="declared_value">Declared Value</option>
              </select>
              <button
                type="button"
                onClick={() => handleSortChange(sortBy, sortOrder === "asc" ? "desc" : "asc")}
                className="px-1.5 py-0.5 rounded text-[11px] font-mono font-semibold text-freight hover:bg-freight-soft transition-colors"
                title="Toggle sort direction"
              >
                {sortOrder === "asc" ? "ASC ↑" : "DESC ↓"}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className={`px-3 py-2 rounded-md border text-sm transition-all duration-150 shrink-0 shadow-xs active:scale-98 ${showFilters ? "bg-freight text-white border-freight shadow-sm" : "border-paper-line text-ink-soft hover:border-freight hover:text-ink bg-white hover:bg-paper/50"}`}
            >
              Filters {hasActiveFilters && "●"}
            </button>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="px-3 py-2 rounded-md text-sm text-red-500 hover:bg-red-50 transition-all duration-150 active:scale-95 shrink-0"
              >
                Clear
              </button>
            )}
          </div>

          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ opacity: 0, height: 0, y: -6 }}
                animate={{ opacity: 1, height: "auto", y: 0 }}
                exit={{ opacity: 0, height: 0, y: -6 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <Card className="p-4 border border-paper-line shadow-xs">
                  <form onSubmit={applyFilters} className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <Input label="Tracking number" value={filters.tracking_number}
                      onChange={(e) => setFilters({ ...filters, tracking_number: e.target.value })} placeholder="TRK-..." />
                    <label className="flex flex-col gap-1 text-xs text-ink-soft">
                      Status
                      <select
                        value={filters.status}
                        onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                        className="rounded border border-paper-line px-2 py-1.5 text-sm bg-white focus:border-freight outline-none transition-all"
                      >
                        {ORDER_STATUSES.map((s) => (
                          <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                        ))}
                      </select>
                    </label>
                    <Input label="Customer name" value={filters.customer_name}
                      onChange={(e) => setFilters({ ...filters, customer_name: e.target.value })} />
                    <Input label="Customer phone" value={filters.customer_phone}
                      onChange={(e) => setFilters({ ...filters, customer_phone: e.target.value })} />
                    <label className="flex flex-col gap-1 text-xs text-ink-soft">
                      COD only
                      <select
                        value={filters.is_cod}
                        onChange={(e) => setFilters({ ...filters, is_cod: e.target.value })}
                        className="rounded border border-paper-line px-2 py-1.5 text-sm bg-white focus:border-freight outline-none transition-all"
                      >
                        <option value="">Any</option>
                        <option value="true">COD orders</option>
                        <option value="false">Non-COD orders</option>
                      </select>
                    </label>
                    <Input label="Created after" type="date" value={filters.created_after}
                      onChange={(e) => setFilters({ ...filters, created_after: e.target.value })} />
                    <Input label="Created before" type="date" value={filters.created_before}
                      onChange={(e) => setFilters({ ...filters, created_before: e.target.value })} />
                    <div className="col-span-full flex gap-2 mt-1">
                      <Button type="submit" className="px-4 py-1.5 text-sm">Apply filters</Button>
                      <button type="button" onClick={clearFilters}
                        className="px-4 py-1.5 rounded text-sm text-ink-soft hover:text-red-500 transition-colors">
                        Clear all
                      </button>
                    </div>
                  </form>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results summary */}
          {!loading && (
            <p className="text-xs text-ink-faint">
              {pagination.count === 0
                ? "No orders found"
                : `${pagination.count} order${pagination.count === 1 ? "" : "s"} found`
                  + (totalPages > 1 ? ` · Page ${pagination.page} of ${totalPages}` : "")}
            </p>
          )}
        </div>

        {/* Orders list */}
        {loading && orders.length === 0 ? (
          <OrderCardSkeleton />
        ) : orders.length === 0 ? (
          <EmptyState title="No orders found" hint={hasActiveFilters ? "Try adjusting your search filters." : "Create your first order using the + New Order button."} />
        ) : (
          <>
            {activeGroupBys.length > 0 && (
              <GroupByBar
                activeGroupBys={activeGroupBys}
                options={ORDER_GROUP_BY_OPTIONS}
                onRemoveGroup={handleRemoveGroupBy}
                onClear={handleClearGroupBy}
                onExpandAll={handleExpandAllGroups}
                onCollapseAll={handleCollapseAllGroups}
                groupCount={groupedOrdersTree?.length || 0}
                itemLabel="group"
              />
            )}

            {activeGroupBys.length === 0 ? (
              <div className="flex flex-col gap-3">
                {orders.map((order) => renderOrderCard(order))}
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {groupedOrdersTree.map((group) => renderOrderGroupNode(group, 0, ""))}
              </div>
            )}
          </>
        )}

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => loadOrders(pagination.page - 1)}
              className="px-3 py-1.5 rounded border border-paper-line text-sm text-ink-soft hover:border-freight hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              ← Previous
            </button>
            <span className="text-sm text-ink-faint px-2">
              Page {pagination.page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={pagination.page >= totalPages}
              onClick={() => loadOrders(pagination.page + 1)}
              className="px-3 py-1.5 rounded border border-paper-line text-sm text-ink-soft hover:border-freight hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {/* New Order Modal */}
      <NewOrderModal
        isOpen={isNewOrderOpen}
        onClose={() => setIsNewOrderOpen(false)}
        onSuccess={handleOrderCreated}
        vendors={vendors}
        role={role}
        token={token}
      />

      {/* Order Detail Drawer */}
      <OrderDrawer order={selected} onClose={() => setSelected(null)} onUpdate={handleUpdate} />
    </Layout>
  );
}
