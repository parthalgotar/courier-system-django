import {
  ArrowRightCircle,
  CalendarCheck,
  PackageCheck,
  CheckCircle2,
  FileText,
  Warehouse,
  Boxes,
  Truck,
  Navigation,
  Receipt,
  Download,
} from "lucide-react";
import { canBillOrders, canViewInvoices } from "./utils/invoice.js";

/**
 * 14 Canonical Stages & Functionalities from FRD / Milestone Backbone:
 * Keyed by stageKey with exact functionality display names from MILESTONE_DOCUMENTS.
 */
export const STAGE_ACTIONS = {
  order_received: {
    label: "Customer Order / Shipping Request",
    icon: ArrowRightCircle,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  booking_planned: {
    label: "Booking Confirmation",
    icon: CalendarCheck,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  pickup_completed: {
    label: "Pickup Acknowledgement",
    icon: PackageCheck,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  label_verified: {
    label: "Shipping Label / Barcode Verification",
    icon: CheckCircle2,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  manifest_created: {
    label: "Consignment Note / LR / Waybill",
    icon: FileText,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  at_origin_hub: {
    label: "Inbound Scan / Goods Receipt Record",
    icon: Warehouse,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  sorted_at_origin: {
    label: "Sorting Sheet / Load Planning Sheet",
    icon: Boxes,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  dispatched_linehaul: {
    label: "Manifest / Trip Sheet",
    icon: Truck,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  at_destination_hub: {
    label: "Arrival Confirmation / Inbound Manifest",
    icon: Warehouse,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  route_planned: {
    label: "Delivery Run Sheet / Delivery Manifest",
    icon: Navigation,
    action: ({ api, token, order, run }) => run(() => api.advanceOrder(token, order.id)),
  },
  out_for_delivery: {
    label: "Delivery Dispatch Record",
    icon: CheckCircle2,
    action: ({ api, token, order, run }) =>
      run(() =>
        api.deliveryAttempt(token, order.id, {
          success: true,
          proof_type: "otp",
          recipient_name: order.customer_name,
        })
      ),
  },
  delivery_attempted: {
    label: "Delivery Attempt Record",
    icon: CheckCircle2,
    action: ({ api, token, order, run }) =>
      run(() =>
        api.deliveryAttempt(token, order.id, {
          success: true,
          proof_type: "otp",
          recipient_name: order.customer_name,
        })
      ),
  },
  delivered: {
    label: "Proof of Delivery (POD)",
    icon: Receipt,
    canExecute: ({ role }) => canBillOrders(role),
    action: ({ api, token, order, run }) => {
      const charge = Math.round(order.weight_kg * 12.5) || 500;
      return run(() => api.closeBilling(token, order.id, charge));
    },
  },
  closed: {
    label: "Freight Invoice / Shipment Closure Record",
    icon: Download,
    canExecute: ({ role }) => canViewInvoices(role),
    action: ({ viewInvoice }) => viewInvoice(),
  },
};
