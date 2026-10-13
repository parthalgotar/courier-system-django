import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Receipt,
  FileText,
  ShoppingCart,
  Users,
  Truck,
  MapPin,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { INVOICE_ROLES } from "../utils/invoice.js";

const VENDOR_ROLES = ["admin", "dispatcher", "vendor"];
const FLEET_ROLES = ["admin", "dispatcher", "driver"];

export const NAV_ITEMS = [
  { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { label: "Accounting", path: "/accounting", icon: Receipt, roles: INVOICE_ROLES },
  { label: "Invoices", path: "/invoices", icon: FileText, roles: INVOICE_ROLES },
  { label: "Orders", path: "/orders", icon: ShoppingCart },
  { label: "Vendors", path: "/vendors", icon: Users, roles: VENDOR_ROLES },
  { label: "Fleet", path: "/fleet", icon: Truck, roles: FLEET_ROLES },
  { label: "Track Shipment", path: "/track", icon: MapPin },
];

export default function Sidebar() {
  const { email, role, logout } = useAuth();
  const visibleItems = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role));

  return (
    <aside className="w-60 shrink-0 bg-console-bg text-white flex flex-col h-screen sticky top-0">
      <div className="px-6 py-6 border-b border-console-line">
        <p className="font-mono text-[11px] tracking-[0.2em] text-freight uppercase">
          Manifest
        </p>
        <h1 className="font-display font-semibold text-lg leading-tight mt-1">
          ERP Console
        </h1>
      </div>

      <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
        {visibleItems.map((item, idx) => {
          const number = String(idx + 1).padStart(2, "0");
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                [
                  "nav-item flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-200",
                  isActive
                    ? "nav-active bg-console-bgSoft text-white font-medium shadow-sm"
                    : "text-white/60 hover:bg-console-bgSoft hover:text-white hover:translate-x-1",
                ].join(" ")
              }
            >
              <span className="font-mono text-[10px] text-freight">{number}</span>
              <span className="font-display">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-console-line">
        <p className="text-xs text-white/50 truncate">{email}</p>
        <button
          onClick={logout}
          className="mt-2 text-xs font-mono uppercase tracking-wide text-white/70 hover:text-white transition-all hover:translate-x-1 inline-flex items-center gap-1"
        >
          Sign out →
        </button>
      </div>
    </aside>
  );
}
