export const DELIVERY_STATUS_FILTER = [
  { value: "pending", label: "Pending" },
  { value: "delivered", label: "Delivery" },
];

export const PENDING_SHIPMENT_STATUSES = new Set([
  "pickup_requested",
  "picked",
  "in_transit",
  "out_for_delivery",
  "failed",
]);

export const STATUS_LABELS = {
  pickup_requested: "Pickup Requested",
  picked: "Picked",
  in_transit: "In Transit",
  out_for_delivery: "Out For Delivery",
  delivered: "Delivered",
  failed: "Failed",
};

export const EARN_RATE_PER_DELIVERY = 85;
export const EARN_RATE_PER_ITEM = 12;

export function toStatusLabel(status) {
  return STATUS_LABELS[status] || status || "Unknown";
}

export function matchesDeliveryFilter(shipmentStatus, filterValue) {
  if (filterValue === "pending") {
    return PENDING_SHIPMENT_STATUSES.has(shipmentStatus);
  }
  if (filterValue === "delivered") {
    return shipmentStatus === "delivered";
  }
  return true;
}

export function formatINR(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function normalizeItemCount(shipment) {
  const count = Number(shipment?.item_count);
  if (!Number.isFinite(count) || count <= 0) {
    return 1;
  }
  return Math.round(count);
}

export function computeDeliveryEarnings(shipments = []) {
  const delivered = shipments.filter((shipment) => shipment.shipment_status === "delivered");
  const deliveredCount = delivered.length;
  const deliveredItems = delivered.reduce((sum, shipment) => sum + normalizeItemCount(shipment), 0);
  const earnByDelivery = deliveredCount * EARN_RATE_PER_DELIVERY;
  const earnPerItem = deliveredItems * EARN_RATE_PER_ITEM;

  return {
    deliveredCount,
    deliveredItems,
    earnByDelivery,
    earnPerItem,
    totalEarn: earnByDelivery + earnPerItem,
  };
}
