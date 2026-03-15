import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { DELIVERY_STATUS_FILTER, matchesDeliveryFilter, toStatusLabel } from "./deliveryMetrics";

function statusTone(status) {
  if (status === "delivered") return "success";
  if (status === "failed") return "danger";
  if (status === "out_for_delivery") return "warning";
  return "neutral";
}

export default function DeliveryShipmentsPage() {
  const { accessToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") || "pending";
  const queryFilter = searchParams.get("q") || "";
  const [queryInput, setQueryInput] = useState(queryFilter);
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setQueryInput(queryFilter);
  }, [queryFilter]);

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

  const filteredShipments = useMemo(() => {
    const needle = queryFilter.trim().toLowerCase();
    return shipments.filter((shipment) => {
      if (!matchesDeliveryFilter(shipment.shipment_status, statusFilter)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      const haystack = [
        shipment.tracking_number,
        shipment.order_id,
        shipment.customer_name,
        shipment.customer_address,
        shipment.customer_phone,
      ]
        .map((value) => String(value || "").toLowerCase())
        .join(" ");
      return haystack.includes(needle);
    });
  }, [queryFilter, shipments, statusFilter]);

  const summary = useMemo(() => {
    const delivered = shipments.filter((shipment) => shipment.shipment_status === "delivered").length;
    const active = shipments.filter((shipment) =>
      ["pickup_requested", "picked", "in_transit", "out_for_delivery"].includes(shipment.shipment_status)
    ).length;
    const failed = shipments.filter((shipment) => shipment.shipment_status === "failed").length;
    return {
      total: shipments.length,
      delivered,
      active,
      failed,
    };
  }, [shipments]);

  const setParam = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setSearchParams(next);
  };

  const onQuerySubmit = (event) => {
    event.preventDefault();
    setParam("q", queryInput.trim());
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading deliveries...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>My Deliveries</h2>
        <p>
          Track your assigned shipments with status filters and quick search for order, customer, or address.
        </p>
      </header>

      <div className="delivery-summary-grid">
        <article>
          <p>Total Deliveries</p>
          <h3>{summary.total}</h3>
        </article>
        <article>
          <p>Active</p>
          <h3>{summary.active}</h3>
        </article>
        <article>
          <p>Delivered</p>
          <h3>{summary.delivered}</h3>
        </article>
        <article>
          <p>Failed</p>
          <h3>{summary.failed}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Delivery List</h3>
          <span>{filteredShipments.length} records</span>
        </div>

        <div className="delivery-filter-row">
          <label>
            <span>Status</span>
            <select value={statusFilter} onChange={(event) => setParam("status", event.target.value)}>
              {DELIVERY_STATUS_FILTER.map((status) => (
                <option key={status.value} value={status.value}>
                  {status.label}
                </option>
              ))}
            </select>
          </label>

          <form onSubmit={onQuerySubmit}>
            <label>
              <span>Search</span>
              <input
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder="Tracking no, order id, customer..."
                value={queryInput}
              />
            </label>
          </form>
        </div>

        {error && <p className="delivery-error">{error}</p>}

        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Tracking</th>
                <th>Order</th>
                <th>Customer</th>
                <th>Status</th>
                <th>Address</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.length === 0 && (
                <tr>
                  <td className="empty" colSpan={6}>
                    No deliveries found for this filter.
                  </td>
                </tr>
              )}
              {filteredShipments.map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.tracking_number || `#${shipment.id}`}</td>
                  <td>#{shipment.order_id}</td>
                  <td>
                    <strong>{shipment.customer_name || "-"}</strong>
                    <small>{shipment.customer_phone || "-"}</small>
                  </td>
                  <td>
                    <span className={`delivery-status-pill ${statusTone(shipment.shipment_status)}`}>
                      {toStatusLabel(shipment.shipment_status)}
                    </span>
                  </td>
                  <td>{shipment.customer_address || "-"}</td>
                  <td>
                    <div className="delivery-row-actions">
                      {shipment.shipment_status !== "delivered" && (
                        <>
                          <a className="delivery-mini-btn" href={`tel:${shipment.customer_phone || ""}`}>
                            Call
                          </a>
                          <a
                            className="delivery-mini-btn muted"
                            href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                              shipment.customer_address || ""
                            )}`}
                            rel="noopener noreferrer"
                            target="_blank"
                          >
                            Navigate
                          </a>
                        </>
                      )}
                      <Link className="delivery-mini-btn strong" to={`/delivery/shipments/${shipment.id}`}>
                        Details
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
