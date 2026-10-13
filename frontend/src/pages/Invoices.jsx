import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ClipboardList,
  Layers,
  ChevronDown,
  ChevronRight as ChevronRightIcon,
  Check,
  Plus,
  Trash2,
  X,
  FileText,
  Filter,
} from "lucide-react";
import Layout from "../components/Layout.jsx";
import InvoiceStatusBadge from "../components/InvoiceStatusBadge.jsx";
import GroupByDropdown, { INVOICE_GROUP_BY_OPTIONS } from "../components/GroupByDropdown.jsx";
import GroupByBar from "../components/GroupByBar.jsx";
import { Card, Button, Input, Select, ErrorBanner, EmptyState } from "../components/ui.jsx";
import SendLogsModal from "../components/SendLogsModal.jsx";
import CreateInvoiceModal from "../components/CreateInvoiceModal.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { downloadPdf, formatDate, formatMoney, isStaff } from "../utils/invoice.js";

const PAGE_SIZES = [10, 25, 50, 100];

const SORTS = {
  newest: { label: "Newest first", sort_by: "invoice_date", order: "desc" },
  oldest: { label: "Oldest first", sort_by: "invoice_date", order: "asc" },
  total_desc: { label: "Total: high to low", sort_by: "total_amount", order: "desc" },
  total_asc: { label: "Total: low to high", sort_by: "total_amount", order: "asc" },
  number: { label: "Invoice number A–Z", sort_by: "invoice_number", order: "asc" },
};

function InvoiceTableSkeleton() {
  return (
    <Card className="overflow-hidden border border-paper-line shadow-xs">
      <div className="p-4 border-b border-paper-line/60 bg-paper/30 flex items-center justify-between">
        <div className="h-4 w-32 skeleton-pulse" />
        <div className="h-4 w-20 skeleton-pulse" />
      </div>
      <div className="divide-y divide-paper-line/50">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3.5 gap-4">
            <div className="h-4 w-24 skeleton-pulse" />
            <div className="space-y-1.5 flex-1 max-w-[140px]">
              <div className="h-3.5 w-20 skeleton-pulse" />
              <div className="h-2.5 w-28 skeleton-pulse" />
            </div>
            <div className="h-4 w-24 skeleton-pulse hidden sm:block" />
            <div className="h-4 w-24 skeleton-pulse hidden md:block" />
            <div className="h-4 w-20 skeleton-pulse hidden lg:block" />
            <div className="h-4 w-16 skeleton-pulse ml-auto" />
            <div className="h-5 w-16 skeleton-pulse rounded-full" />
            <div className="h-8 w-8 skeleton-pulse rounded-md" />
            <div className="h-8 w-8 skeleton-pulse rounded-md" />
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function Invoices() {
  const { token, role } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial states from URL query string
  const initialGroupBy = useMemo(() => {
    const raw = searchParams.get("group_by");
    if (!raw) return [];
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
  }, [searchParams]);

  const [activeGroupBys, setActiveGroupBys] = useState(initialGroupBy);

  const [searchInput, setSearchInput] = useState(searchParams.get("search") || "");
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "");
  const [unpaidOnly, setUnpaidOnly] = useState(searchParams.get("unpaid") === "true");
  const [overdueOnly, setOverdueOnly] = useState(searchParams.get("overdue") === "true");
  const [dateFrom, setDateFrom] = useState(searchParams.get("date_from") || "");
  const [dateTo, setDateTo] = useState(searchParams.get("date_to") || "");
  const [sortKey, setSortKey] = useState("newest");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);
  const [pageSize, setPageSize] = useState(50);

  // Data states
  const [data, setData] = useState({ count: 0, next: null, previous: null, results: [] });
  const [groupedTree, setGroupedTree] = useState([]);
  const [collapsedNodes, setCollapsedNodes] = useState({}); // { [nodeKey]: boolean }

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [downloadingId, setDownloadingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [selectedLogInv, setSelectedLogInv] = useState(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Sync state to URL search parameters
  useEffect(() => {
    const params = new URLSearchParams();
    if (activeGroupBys.length > 0) params.set("group_by", activeGroupBys.join(","));
    if (statusFilter) params.set("status", statusFilter);
    if (unpaidOnly) params.set("unpaid", "true");
    if (overdueOnly) params.set("overdue", "true");
    if (search) params.set("search", search);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (page > 1) params.set("page", String(page));

    setSearchParams(params, { replace: true });
  }, [activeGroupBys, statusFilter, unpaidOnly, overdueOnly, search, dateFrom, dateTo, page, setSearchParams]);

  // Toggle group by field in selection order (multi-select, unlimited levels)
  function toggleGroupBy(id) {
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
    setCollapsedNodes({});
  }

  function removeGroupBy(id) {
    setActiveGroupBys((prev) => prev.filter((item) => item !== id));
    setCollapsedNodes({});
  }

  function handleExpandAllGroups() {
    setCollapsedNodes({});
  }

  function handleCollapseAllGroups() {
    const allPaths = {};
    function collectPaths(nodes, prefix = "") {
      for (const n of nodes) {
        const p = `${prefix}/${n.field}:${n.key}`;
        allPaths[p] = true;
        if (n.children && n.children.length > 0 && !("number" in n.children[0])) {
          collectPaths(n.children, p);
        }
      }
    }
    if (groupedTree) {
      collectPaths(groupedTree);
    }
    setCollapsedNodes(allPaths);
  }

  function toggleNodeCollapse(nodePath) {
    setCollapsedNodes((prev) => ({
      ...prev,
      [nodePath]: !prev[nodePath],
    }));
  }

  function clearAllFiltersAndGrouping() {
    setActiveGroupBys([]);
    setStatusFilter("");
    setUnpaidOnly(false);
    setOverdueOnly(false);
    setSearchInput("");
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
    setCollapsedNodes({});
  }

  // Fetch data (either grouped tree or standard paginated list)
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const filterParams = {
      search,
      status: statusFilter,
      unpaid: unpaidOnly ? "true" : undefined,
      overdue: overdueOnly ? "true" : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };

    if (activeGroupBys.length > 0) {
      // Multi-level Grouped API call
      api
        .getGroupedInvoices(
          token,
          {
            group_by: activeGroupBys.join(","),
            ...filterParams,
          },
          controller.signal
        )
        .then((tree) => {
          setGroupedTree(Array.isArray(tree) ? tree : []);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          setError({ message: err.message || "Failed to load grouped invoices.", status: err.status });
          setLoading(false);
        });
    } else {
      // Normal paginated list API call
      const query = {
        page,
        page_size: pageSize,
        ...filterParams,
        sort_by: SORTS[sortKey].sort_by,
        order: SORTS[sortKey].order,
      };

      api
        .listInvoices(token, query, controller.signal)
        .then((res) => {
          const safeData =
            res && Array.isArray(res.results)
              ? res
              : { count: Array.isArray(res) ? res.length : 0, next: null, previous: null, results: Array.isArray(res) ? res : [] };
          setData(safeData);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          if (err.status === 404 && page > 1) {
            setPage(1);
            return;
          }
          setError({ message: err.message || "Could not load invoices.", status: err.status });
          setLoading(false);
        });
    }

    return () => controller.abort();
  }, [
    token,
    activeGroupBys,
    search,
    statusFilter,
    unpaidOnly,
    overdueOnly,
    dateFrom,
    dateTo,
    sortKey,
    page,
    pageSize,
    reloadKey,
  ]);

  const totalPages = Math.max(1, Math.ceil(data.count / pageSize));
  const hasActiveFilters = Boolean(
    search || statusFilter || unpaidOnly || overdueOnly || dateFrom || dateTo || activeGroupBys.length > 0
  );
  const hasActiveFilterChips = Boolean(
    search || statusFilter || unpaidOnly || overdueOnly || dateFrom || dateTo
  );

  async function handleDownload(e, inv) {
    e.stopPropagation();
    const invId = inv.id;
    const invNum = inv.number || inv.invoice_number || `INV-${invId}`;
    setNotice("");
    setDownloadingId(invId);
    try {
      await downloadPdf(() => api.fetchInvoicePdf(token, invId), `${invNum}.pdf`);
      setNotice(`Downloaded ${invNum}.pdf`);
    } catch (err) {
      setError({ message: err.message || "Download failed.", status: err.status });
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(e, inv) {
    e.stopPropagation();
    if (inv.status === "paid" || inv.status === "posted") {
      setError({ message: "Only draft invoices can be deleted.", status: 400 });
      return;
    }
    const invNum = inv.number || inv.invoice_number || `INV-${inv.id}`;
    const confirmed = window.confirm(
      `Are you sure you want to delete invoice ${invNum}? This action cannot be undone.`
    );
    if (!confirmed) return;

    setNotice("");
    setError(null);
    setDeletingId(inv.id);
    try {
      await api.deleteInvoice(token, inv.id);
      setNotice(`Invoice ${invNum} has been deleted.`);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError({ message: err.message || "Failed to delete invoice.", status: err.status });
    } finally {
      setDeletingId(null);
    }
  }

  const forbidden = error?.status === 403;

  function renderInvoiceRow(inv, isNested = false, depth = 0) {
    const isPaid = inv.status === "paid";
    const invNum = inv.number || inv.invoice_number || `INV-${inv.id}`;
    const custName = inv.customer_name || inv.customer || "—";
    const total = inv.amount_total !== undefined ? inv.amount_total : inv.total_amount;
    const due = inv.amount_due !== undefined ? inv.amount_due : (isPaid ? 0 : total);

    return (
      <tr
        key={inv.id}
        onClick={() => navigate(`/invoices/${inv.id}`)}
        className="table-row-premium group border-b border-paper-line last:border-0 cursor-pointer hover:bg-paper/40 transition-colors"
      >
        <td
          className="px-4 py-3 font-mono text-xs text-scan font-semibold group-hover:text-scan-dark group-hover:underline transition-colors whitespace-nowrap"
          style={isNested ? { paddingLeft: `${(depth + 1) * 1.5}rem` } : undefined}
        >
          {invNum}
        </td>
        <td className="px-4 py-3 text-ink font-medium">{custName}</td>
        <td className="px-4 py-3 text-ink-soft whitespace-nowrap text-xs">{formatDate(inv.invoice_date)}</td>
        <td className="px-4 py-3 text-ink-soft whitespace-nowrap text-xs">
          {inv.due_date ? formatDate(inv.due_date) : "—"}
        </td>
        <td className="px-4 py-3 text-right font-medium text-ink whitespace-nowrap font-mono text-sm">
          {formatMoney(total)}
        </td>
        <td className="px-4 py-3 text-right font-medium text-amber-700 whitespace-nowrap font-mono text-sm">
          {formatMoney(due)}
        </td>
        <td className="px-4 py-3">
          <InvoiceStatusBadge status={inv.status} />
        </td>
        <td className="px-4 py-3 text-center">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSelectedLogInv({ id: inv.id, invoice_number: invNum });
            }}
            title="View send logs"
            className="action-btn-pill inline-grid place-items-center w-8 h-8 rounded-md border border-paper-line text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <ClipboardList size={14} />
          </button>
        </td>
        <td className="px-4 py-3 text-center">
          <button
            onClick={(e) => handleDownload(e, inv)}
            disabled={downloadingId === inv.id}
            title="Download PDF"
            className="action-btn-pill inline-grid place-items-center w-8 h-8 rounded-md border border-paper-line text-freight-dark hover:bg-freight-soft transition-colors disabled:opacity-40"
          >
            <Download size={14} className={downloadingId === inv.id ? "spin" : ""} />
          </button>
        </td>
        <td className="px-4 py-3 text-center">
          {!isPaid && inv.status === "draft" && (
            <button
              onClick={(e) => handleDelete(e, inv)}
              disabled={deletingId === inv.id}
              title="Delete draft invoice"
              className="action-btn-pill inline-grid place-items-center w-8 h-8 rounded-md border border-paper-line text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40"
            >
              <Trash2 size={14} className={deletingId === inv.id ? "spin" : ""} />
            </button>
          )}
        </td>
      </tr>
    );
  }

  // Recursive renderer for nested group-by tree
  function renderGroupNode(node, depth = 0, pathPrefix = "") {
    const nodePath = `${pathPrefix}/${node.field}:${node.key}`;
    const isCollapsed = Boolean(collapsedNodes[nodePath]);
    const children = node.children || [];
    const isLeafList = children.length > 0 && "number" in children[0]; // Children are raw invoice objects

    const depthIndent = depth * 1.5; // rem indentation

    return (
      <React.Fragment key={nodePath}>
        <tr
          onClick={() => toggleNodeCollapse(nodePath)}
          className="bg-paper/90 hover:bg-paper border-b border-paper-line font-medium text-ink cursor-pointer select-none transition-colors"
        >
          <td colSpan={10} className="py-2.5 pr-4" style={{ paddingLeft: `${depthIndent + 1}rem` }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[#714B67] transition-transform duration-150">
                  {isCollapsed ? <ChevronRightIcon size={16} /> : <ChevronDown size={16} />}
                </span>
                <span className="font-semibold text-ink text-sm capitalize">
                  {node.key || "—"}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#714B67]/10 text-[#714B67] uppercase font-bold tracking-wider">
                  {node.field}
                </span>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono bg-paper-line text-ink-soft">
                  {node.count} {node.count === 1 ? "invoice" : "invoices"}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs font-medium font-mono">
                <div>
                  <span className="text-ink-faint">Total: </span>
                  <span className="font-semibold text-ink">{formatMoney(node.total)}</span>
                </div>
                {node.due !== undefined && (
                  <div>
                    <span className="text-ink-faint">Due: </span>
                    <span className="font-semibold text-amber-700">{formatMoney(node.due)}</span>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>

        {!isCollapsed && (
          <>
            {isLeafList
              ? children.map((inv) => renderInvoiceRow(inv, true, depth + 1))
              : children.map((childNode) => renderGroupNode(childNode, depth + 1, nodePath))}
          </>
        )}
      </React.Fragment>
    );
  }

  return (
    <Layout
      eyebrow="Accounting"
      title="Invoices"
      action={
        <div className="flex items-center gap-2">
          {/* New Invoice Button */}
          <Button
            variant="primary"
            onClick={() => setCreateModalOpen(true)}
            className="shadow-sm"
          >
            <Plus size={15} /> New Invoice
          </Button>

          {/* Multi-Level Group By Dropdown */}
          <GroupByDropdown
            options={INVOICE_GROUP_BY_OPTIONS}
            activeGroupBys={activeGroupBys}
            onToggleGroupBy={toggleGroupBy}
            onClear={() => {
              setActiveGroupBys([]);
              setCollapsedNodes({});
            }}
          />

          <Button variant="ghost" onClick={() => setReloadKey((k) => k + 1)} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </Button>
        </div>
      }
    >
      {/* ------------------------------------------------------------ Filters & Search Bar */}
      <Card className="p-4 mb-4">
        {/* Quick status tabs */}
        <div className="flex flex-wrap items-center gap-2 mb-3 pb-3 border-b border-paper-line text-xs">
          <span className="font-semibold text-ink-soft uppercase tracking-wider text-[11px] mr-1">
            Status:
          </span>
          {[
            { label: "All", status: "", unpaid: false, overdue: false },
            { label: "Draft", status: "draft", unpaid: false, overdue: false },
            { label: "Posted", status: "posted", unpaid: false, overdue: false },
            { label: "Paid", status: "paid", unpaid: false, overdue: false },
            { label: "Unpaid Only", status: "posted", unpaid: true, overdue: false },
            { label: "Overdue", status: "posted", unpaid: false, overdue: true },
          ].map((tab) => {
            const isActive =
              statusFilter === tab.status &&
              unpaidOnly === tab.unpaid &&
              overdueOnly === tab.overdue;
            return (
              <button
                key={tab.label}
                type="button"
                onClick={() => {
                  setStatusFilter(tab.status);
                  setUnpaidOnly(tab.unpaid);
                  setOverdueOnly(tab.overdue);
                  setPage(1);
                }}
                className={`px-3 py-1 rounded-md transition-all font-medium ${
                  isActive
                    ? "bg-freight text-white shadow-xs"
                    : "bg-paper text-ink-soft hover:bg-paper-line/60 hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div className="md:col-span-2 relative">
            <Input
              label="Search"
              placeholder="Invoice #, customer, order #..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9 w-full"
            />
            <Search size={14} className="absolute left-3 bottom-3 text-ink-faint pointer-events-none" />
          </div>

          <Input
            label="From Date"
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          />

          <Input
            label="To Date"
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          />

          {activeGroupBys.length === 0 && (
            <Select
              label="Sort by"
              value={sortKey}
              onChange={(e) => { setSortKey(e.target.value); setPage(1); }}
            >
              {Object.entries(SORTS).map(([k, s]) => (
                <option key={k} value={k}>
                  {s.label}
                </option>
              ))}
            </Select>
          )}
        </div>
      </Card>

      {/* ------------------------------------------------------------ Group By Bar */}
      {activeGroupBys.length > 0 && (
        <GroupByBar
          activeGroupBys={activeGroupBys}
          options={INVOICE_GROUP_BY_OPTIONS}
          onRemoveGroup={removeGroupBy}
          onClear={() => {
            setActiveGroupBys([]);
            setCollapsedNodes({});
          }}
          onExpandAll={handleExpandAllGroups}
          onCollapseAll={handleCollapseAllGroups}
          groupCount={groupedTree?.length || 0}
          itemLabel="group"
        />
      )}

      {/* ------------------------------------------------------------ Active Filter Chips Bar */}
      {hasActiveFilterChips && (
        <div className="flex flex-wrap items-center gap-2 mb-4 px-3 py-2 bg-paper/60 border border-paper-line rounded-lg text-xs">
          <span className="text-ink-soft flex items-center gap-1 font-medium">
            <Filter size={12} /> Active Filters:
          </span>

          {/* Filter chips */}
          {statusFilter && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-paper border border-paper-line text-ink">
              Status: <span className="font-semibold uppercase text-freight-dark">{statusFilter}</span>
              <button type="button" onClick={() => setStatusFilter("")} className="hover:text-red-500 font-bold">×</button>
            </span>
          )}
          {unpaidOnly && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800">
              Unpaid
              <button type="button" onClick={() => setUnpaidOnly(false)} className="hover:text-red-500 font-bold">×</button>
            </span>
          )}
          {overdueOnly && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-red-50 border border-red-200 text-red-800">
              Overdue
              <button type="button" onClick={() => setOverdueOnly(false)} className="hover:text-red-500 font-bold">×</button>
            </span>
          )}
          {search && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-paper border border-paper-line text-ink">
              Search: "{search}"
              <button
                type="button"
                onClick={() => { setSearchInput(""); setSearch(""); }}
                className="hover:text-red-500 font-bold"
              >
                ×
              </button>
            </span>
          )}
          {dateFrom && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-paper border border-paper-line text-ink">
              From: {dateFrom}
              <button type="button" onClick={() => setDateFrom("")} className="hover:text-red-500 font-bold">×</button>
            </span>
          )}
          {dateTo && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-paper border border-paper-line text-ink">
              To: {dateTo}
              <button type="button" onClick={() => setDateTo("")} className="hover:text-red-500 font-bold">×</button>
            </span>
          )}

          <button
            type="button"
            onClick={clearAllFiltersAndGrouping}
            className="ml-auto text-xs font-mono uppercase tracking-wide text-freight hover:text-freight-dark hover:underline font-semibold"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Notice alert */}
      <AnimatePresence>
        {notice && !error && (
          <motion.div
            initial={{ opacity: 0, y: -6, height: 0 }}
            animate={{ opacity: 1, y: 0, height: "auto" }}
            exit={{ opacity: 0, y: -6, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden mb-4"
          >
            <div className="rounded-md border border-freight/30 bg-freight-soft px-4 py-3 text-sm text-freight-dark flex items-center justify-between shadow-xs">
              <span>{notice}</span>
              <button
                type="button"
                onClick={() => setNotice("")}
                className="text-freight-dark/60 hover:text-freight-dark font-bold text-sm ml-2"
              >
                ×
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ------------------------------------------------------------- Content States */}
      {forbidden ? (
        <EmptyState title="Access Denied" hint="Your account role does not have permission to view invoices." />
      ) : error ? (
        <div className="space-y-3">
          <ErrorBanner message={error.message} />
          <Button variant="ghost" onClick={() => setReloadKey((k) => k + 1)}>
            Try again
          </Button>
        </div>
      ) : loading && ((activeGroupBys.length === 0 && data.results.length === 0) || (activeGroupBys.length > 0 && groupedTree.length === 0)) ? (
        <InvoiceTableSkeleton />
      ) : (
        <>
          {activeGroupBys.length > 0 ? (
            /* ======================================================= Multi-Level Grouped Table */
            <Card className="overflow-x-auto shadow-xs border border-paper-line">
              {groupedTree.length === 0 ? (
                <div className="p-8 text-center text-ink-soft text-sm">
                  No invoices found for the current filters and grouping.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-ink-faint border-b border-paper-line bg-paper/50">
                      <th className="px-4 py-3 font-semibold">Invoice #</th>
                      <th className="px-4 py-3 font-semibold">Customer</th>
                      <th className="px-4 py-3 font-semibold">Invoice Date</th>
                      <th className="px-4 py-3 font-semibold">Due Date</th>
                      <th className="px-4 py-3 font-semibold text-right">Total</th>
                      <th className="px-4 py-3 font-semibold text-right">Due</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold text-center">Logs</th>
                      <th className="px-4 py-3 font-semibold text-center">PDF</th>
                      <th className="px-4 py-3 font-semibold text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedTree.map((node) => renderGroupNode(node, 0, ""))}
                  </tbody>
                </table>
              )}
            </Card>
          ) : (
            /* ======================================================= Normal Paginated Table */
            <>
              {data.count === 0 ? (
                <EmptyState
                  title={hasActiveFilters ? "No invoices match filters" : "No invoices yet"}
                  hint={hasActiveFilters ? "Try clearing filters to see all invoices." : "Click '+ New Invoice' to create your first draft invoice."}
                />
              ) : (
                <Card className={`overflow-x-auto shadow-xs border border-paper-line transition-opacity ${loading ? "opacity-60" : ""}`}>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wider text-ink-faint border-b border-paper-line bg-paper/50">
                        <th className="px-4 py-3 font-semibold">Invoice #</th>
                        <th className="px-4 py-3 font-semibold">Customer</th>
                        <th className="px-4 py-3 font-semibold">Date</th>
                        <th className="px-4 py-3 font-semibold">Due Date</th>
                        <th className="px-4 py-3 font-semibold text-right">Total</th>
                        <th className="px-4 py-3 font-semibold text-right">Due</th>
                        <th className="px-4 py-3 font-semibold">Status</th>
                        <th className="px-4 py-3 font-semibold text-center">Logs</th>
                        <th className="px-4 py-3 font-semibold text-center">PDF</th>
                        <th className="px-4 py-3 font-semibold text-center">Delete</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.results.map((inv) => renderInvoiceRow(inv))}
                    </tbody>
                  </table>
                </Card>
              )}

              {/* Pagination controls */}
              {!error && data.count > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 mt-4 text-sm text-ink-soft">
                  <p>
                    Page <span className="font-medium text-ink">{page}</span> of{" "}
                    <span className="font-medium text-ink">{totalPages}</span> ·{" "}
                    <span className="font-medium text-ink">{data.count}</span> {data.count === 1 ? "invoice" : "invoices"}
                  </p>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-xs">
                      Per page
                      <select
                        value={pageSize}
                        onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                        className="rounded-md border border-paper-line bg-white px-2 py-1 text-sm outline-none"
                      >
                        {PAGE_SIZES.map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                    </label>
                    <Button variant="ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={!data.previous || loading}>
                      <ChevronLeft size={14} /> Previous
                    </Button>
                    <Button variant="ghost" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={!data.next || loading}>
                      Next <ChevronRight size={14} />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ------------------------------------------------------------- Create Invoice Modal */}
      <CreateInvoiceModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={(newInv) => {
          setNotice(`Draft invoice ${newInv.number || "created"} successfully.`);
          setReloadKey((k) => k + 1);
          if (newInv?.id) {
            navigate(`/invoices/${newInv.id}`);
          }
        }}
      />

      {/* ------------------------------------------------------------- Send Logs Modal */}
      <AnimatePresence>
        {selectedLogInv && (
          <SendLogsModal
            invoiceId={selectedLogInv.id}
            invoiceNumber={selectedLogInv.invoice_number}
            onClose={() => setSelectedLogInv(null)}
          />
        )}
      </AnimatePresence>
    </Layout>
  );
}
