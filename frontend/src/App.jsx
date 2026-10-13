import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AccountingPage from "./pages/AccountingPage.jsx";
import Orders from "./pages/Orders.jsx";
import Vendors from "./pages/Vendors.jsx";
import Fleet from "./pages/Fleet.jsx";
import Track from "./pages/Track.jsx";
import Invoices from "./pages/Invoices.jsx";
import InvoiceDetail from "./pages/InvoiceDetail.jsx";
import Layout from "./components/Layout.jsx";
import { EmptyState } from "./components/ui.jsx";
import { INVOICE_ROLES } from "./utils/invoice.js";

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

// Shows a page only to the given roles. This is a UX guard: the API rejects
// unauthorised requests on its own (drivers get 403 from /invoices/).
function RoleRoute({ roles, title, children }) {
  const { role } = useAuth();
  if (!role) {
    return (
      <Layout title={title}>
        <p className="text-ink-faint text-sm" role="status">Loading…</p>
      </Layout>
    );
  }
  if (!roles.includes(role)) {
    return (
      <Layout eyebrow="Access denied" title={title}>
        <EmptyState title="You don't have access to this page" hint="Your account role is not permitted to view it." />
      </Layout>
    );
  }
  return children;
}

const VENDOR_ROLES = ["admin", "dispatcher", "vendor"];
const FLEET_ROLES = ["admin", "dispatcher", "driver"];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/operations" element={<Navigate to="/dashboard" replace />} />
      <Route path="/accounting" element={<ProtectedRoute><RoleRoute roles={INVOICE_ROLES} title="Accounting"><AccountingPage /></RoleRoute></ProtectedRoute>} />
      <Route path="/orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
      <Route path="/vendors" element={<ProtectedRoute><RoleRoute roles={VENDOR_ROLES} title="Vendors"><Vendors /></RoleRoute></ProtectedRoute>} />
      <Route path="/fleet" element={<ProtectedRoute><RoleRoute roles={FLEET_ROLES} title="Fleet"><Fleet /></RoleRoute></ProtectedRoute>} />
      <Route path="/track" element={<ProtectedRoute><Track /></ProtectedRoute>} />
      <Route path="/invoices" element={<ProtectedRoute><RoleRoute roles={INVOICE_ROLES} title="Invoices"><Invoices /></RoleRoute></ProtectedRoute>} />
      <Route path="/invoices/:id" element={<ProtectedRoute><RoleRoute roles={INVOICE_ROLES} title="Invoice"><InvoiceDetail /></RoleRoute></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
