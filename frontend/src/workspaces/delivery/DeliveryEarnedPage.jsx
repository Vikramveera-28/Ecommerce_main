import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  computeDeliveryEarnings,
  EARN_RATE_PER_DELIVERY,
  EARN_RATE_PER_ITEM,
  formatINR,
  normalizeItemCount,
} from "./deliveryMetrics";

const RANGE_OPTIONS = [
  { value: "all", label: "All Time" },
  { value: "30d", label: "Last 30 Days" },
  { value: "7d", label: "Last 7 Days" },
];

function filterByRange(shipments, range) {
  if (range === "all") return shipments;
  const days = range === "7d" ? 7 : 30;
  const threshold = new Date();
  threshold.setDate(threshold.getDate() - days);
  return shipments.filter((shipment) => {
    const stamp = shipment.delivery_time || shipment.assigned_time || shipment.created_at;
    if (!stamp) return false;
    const date = new Date(stamp);
    if (Number.isNaN(date.getTime())) return false;
    return date >= threshold;
  });
}

function formatDate(dateValue) {
  if (!dateValue) return "-";
  const parsed = new Date(dateValue);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleString();
}

export default function DeliveryEarnedPage() {
  const { accessToken } = useAuth();
  const [shipments, setShipments] = useState([]);
  const [range, setRange] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const rows = await apiClient.listMyDeliveries(accessToken);
        if (!cancelled) {
          setShipments(rows || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  const scopedShipments = useMemo(() => filterByRange(shipments, range), [range, shipments]);
  const earnings = useMemo(() => computeDeliveryEarnings(scopedShipments), [scopedShipments]);
  const deliveredShipments = useMemo(
    () =>
      scopedShipments
        .filter((shipment) => shipment.shipment_status === "delivered")
        .sort((a, b) => new Date(b.delivery_time || b.created_at) - new Date(a.delivery_time || a.created_at)),
    [scopedShipments]
  );

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading earnings...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head split">
        <div>
          <h2>Earned</h2>
          <p>Track your delivery performance and earnings by delivery and per delivered item.</p>
        </div>
        <label className="delivery-range-filter">
          <span>Range</span>
          <select onChange={(event) => setRange(event.target.value)} value={range}>
            {RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      <div className="delivery-summary-grid earned">
        <article>
          <p>Total Delivery</p>
          <h3>{scopedShipments.length}</h3>
        </article>
        <article className="highlight">
          <p>Total Earn</p>
          <h3>{formatINR(earnings.totalEarn)}</h3>
        </article>
        <article>
          <p>Earn By Delivery</p>
          <h3>{formatINR(earnings.earnByDelivery)}</h3>
        </article>
        <article>
          <p>Earn Per Item</p>
          <h3>{formatINR(earnings.earnPerItem)}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Earnings Logic</h3>
          <span>
            {formatINR(EARN_RATE_PER_DELIVERY)} per delivery, {formatINR(EARN_RATE_PER_ITEM)} per item
          </span>
        </div>
        <p className="delivery-note">
          Total earn = (Delivered shipments x {formatINR(EARN_RATE_PER_DELIVERY)}) + (Delivered items x{" "}
          {formatINR(EARN_RATE_PER_ITEM)}).
        </p>
        <p className="delivery-note">
          Delivered shipments: {earnings.deliveredCount} | Delivered items: {earnings.deliveredItems}
        </p>
      </article>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Delivered Shipments Breakdown</h3>
          <span>{deliveredShipments.length} rows</span>
        </div>
        {error && <p className="delivery-error">{error}</p>}
        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Tracking</th>
                <th>Delivered At</th>
                <th>Items</th>
                <th>Earn By Delivery</th>
                <th>Earn Per Item</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {deliveredShipments.length === 0 && (
                <tr>
                  <td className="empty" colSpan={6}>
                    No delivered shipments in selected range.
                  </td>
                </tr>
              )}
              {deliveredShipments.map((shipment) => {
                const itemCount = normalizeItemCount(shipment);
                const deliveryEarn = EARN_RATE_PER_DELIVERY;
                const itemEarn = itemCount * EARN_RATE_PER_ITEM;
                return (
                  <tr key={shipment.id}>
                    <td>{shipment.tracking_number || `#${shipment.id}`}</td>
                    <td>{formatDate(shipment.delivery_time || shipment.created_at)}</td>
                    <td>{itemCount}</td>
                    <td>{formatINR(deliveryEarn)}</td>
                    <td>{formatINR(itemEarn)}</td>
                    <td>{formatINR(deliveryEarn + itemEarn)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
