import React, { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, Clock, CreditCard, DollarSign, FileText, Landmark, RefreshCw } from "lucide-react";
import Layout from "../components/Layout.jsx";
import { Card, EmptyState } from "../components/ui.jsx";
import { useDashboard } from "../hooks/useDashboard.js";

import KpiCard from "../components/dashboard/KpiCard.jsx";
import SalesCard from "../components/dashboard/SalesCard.jsx";
import CashBankCard from "../components/dashboard/CashBankCard.jsx";
import RecentPaymentsCard from "../components/dashboard/RecentPaymentsCard.jsx";
import TopCustomersCard from "../components/dashboard/TopCustomersCard.jsx";
import StatusDonutChart from "../components/dashboard/StatusDonutChart.jsx";
import DashboardFilters from "../components/dashboard/DashboardFilters.jsx";

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Filters skeleton */}
      <div className="h-14 bg-paper-card border border-paper-line rounded-lg" />
      {/* 5 KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-28 bg-paper-card border border-paper-line rounded-lg p-4 space-y-3">
            <div className="h-3 w-16 bg-paper-line rounded" />
            <div className="h-7 w-24 bg-paper-line rounded" />
            <div className="h-2.5 w-20 bg-paper-line rounded" />
          </div>
        ))}
      </div>
      {/* Middle row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-80 bg-paper-card border border-paper-line rounded-lg" />
        <div className="lg:col-span-1 h-80 bg-paper-card border border-paper-line rounded-lg" />
      </div>
      {/* Bottom row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-64 bg-paper-card border border-paper-line rounded-lg" />
        <div className="h-64 bg-paper-card border border-paper-line rounded-lg" />
      </div>
    </div>
  );
}

export default function AccountingPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Extract filters from URL query parameters
  const filters = useMemo(() => {
    return {
      date_from: searchParams.get("date_from") || undefined,
      date_to: searchParams.get("date_to") || undefined,
      customer: searchParams.get("customer") || undefined,
      journal: searchParams.get("journal") || undefined,
    };
  }, [searchParams]);

  const { data, loading, error, refetch } = useDashboard(filters);

  // Sync filters to URL query string
  const handleFiltersChange = (newFilters) => {
    const params = new URLSearchParams();
    Object.entries(newFilters).forEach(([k, v]) => {
      if (v !== undefined && v !== "") {
        params.set(k, v);
      }
    });
    setSearchParams(params);
  };

  const currency = data?.currency || "USD";
  const formatMoney = (val) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val || 0);

  // Navigate to invoices list with query filters
  const handleNavigateInvoices = (queryParams) => {
    const params = new URLSearchParams(queryParams);
    navigate(`/invoices?${params.toString()}`);
  };

  const topCards = data?.top_cards || {
    invoices_total: 0,
    receivable: 0,
    cash_received: 0,
    bank_received: 0,
    draft_total: 0,
    overdue_total: 0,
  };

  return (
    <Layout
      eyebrow="ACCOUNTING"
      title="Accounting"
    >
      {/* Filters Bar */}
      <DashboardFilters
        filters={filters}
        onChange={handleFiltersChange}
        onRefresh={refetch}
        loading={loading}
      />

      {error ? (
        <Card className="p-8 text-center border-alert/30 bg-alert-soft/30">
          <AlertCircle size={36} className="mx-auto text-alert mb-2" />
          <h4 className="font-display text-base font-bold text-ink">Failed to load dashboard</h4>
          <p className="text-xs text-ink-faint mt-1 mb-4">{error}</p>
          <button
            onClick={refetch}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold bg-freight text-white hover:bg-freight-dark transition-all shadow-xs"
          >
            <RefreshCw size={13} />
            <span>Retry</span>
          </button>
        </Card>
      ) : loading && !data ? (
        <DashboardSkeleton />
      ) : (
        <div className="space-y-6">
          {/* A) TOP ROW - 5 Small KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <KpiCard
              title="Invoices"
              amount={formatMoney(topCards.invoices_total)}
              subtitle="Posted + Paid totals"
              icon={FileText}
              color="#6366f1"
              onClick={() => handleNavigateInvoices({ status: "posted" })}
            />
            <KpiCard
              title="Receivable"
              amount={formatMoney(topCards.receivable)}
              subtitle="Pending customer due"
              icon={Clock}
              color="#f59e0b"
              onClick={() => handleNavigateInvoices({ status: "posted", unpaid: "true" })}
            />
            <KpiCard
              title="Cash"
              amount={formatMoney(topCards.cash_received)}
              subtitle="Cash collections"
              icon={DollarSign}
              color="#10b981"
              onClick={() => handleNavigateInvoices({ journal: "cash" })}
            />
            <KpiCard
              title="Bank"
              amount={formatMoney(topCards.bank_received)}
              subtitle="Bank transfers"
              icon={Landmark}
              color="#0284c7"
              onClick={() => handleNavigateInvoices({ journal: "bank" })}
            />
            <KpiCard
              title="Overdue"
              amount={formatMoney(topCards.overdue_total)}
              subtitle="Past payment due date"
              icon={CreditCard}
              color="#ef4444"
              onClick={() => handleNavigateInvoices({ status: "posted", overdue: "true" })}
            />
          </div>

          {/* B & E) SALES CARD & INVOICE STATUS DONUT */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <SalesCard
                salesData={data?.sales}
                onNavigateFilter={handleNavigateInvoices}
                onNewInvoice={() => navigate("/invoices")}
                currency={currency}
              />
            </div>
            <div className="lg:col-span-1">
              <StatusDonutChart
                statusBreakdown={data?.status_breakdown}
                currency={currency}
              />
            </div>
          </div>

          {/* C & D) CASH & BANK JOURNALS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <CashBankCard
              type="cash"
              title="Cash Journal"
              balance={data?.cash?.balance}
              monthly={data?.cash?.monthly}
              currency={currency}
              onViewTransactions={() => handleNavigateInvoices({ journal: "cash" })}
            />
            <CashBankCard
              type="bank"
              title="Bank Journal"
              balance={data?.bank?.balance}
              monthly={data?.bank?.monthly}
              currency={currency}
              onViewTransactions={() => handleNavigateInvoices({ journal: "bank" })}
            />
          </div>

          {/* E) EXTRA CARDS: RECENT PAYMENTS & TOP CUSTOMERS */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <RecentPaymentsCard
              payments={data?.recent_payments}
              currency={currency}
            />
            <TopCustomersCard
              customers={data?.top_customers}
              currency={currency}
            />
          </div>
        </div>
      )}
    </Layout>
  );
}
