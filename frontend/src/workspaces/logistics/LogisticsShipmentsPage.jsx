import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { toStatusLabel } from "../delivery/deliveryMetrics";

const STATUS_OPTIONS = ["picked", "in_transit", "out_for_delivery", "failed"];
const STATUS_FILTER = ["", "pickup_requested", "picked", "in_transit", "out_for_delivery", "delivered", "failed"];

function statusTone(status) {
  if (status === "delivered") return "success";
  if (status === "failed") return "danger";
  if (status === "out_for_delivery") return "warning";
  return "neutral";
}

export default function LogisticsShipmentsPage() {
  const { accessToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") || "";
  const queryFilter = searchParams.get("q") || "";
  const [queryInput, setQueryInput] = useState(queryFilter);
  const [shipments, setShipments] = useState([]);
  const [deliveryBoys, setDeliveryBoys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setQueryInput(queryFilter);
  }, [queryFilter]);

  const load = async () => {
    const [shipmentRows, deliveryRows] = await Promise.all([
      apiClient.listShipments(accessToken),
      apiClient.listDeliveryBoys(accessToken),
    ]);
    setShipments(shipmentRows || []);
    setDeliveryBoys((deliveryRows || []).filter((deliveryBoy) => deliveryBoy.is_active));
  };

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      setLoading(true);
      setError("");
      try {
        await load();
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
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  const filteredShipments = useMemo(() => {
    const needle = queryFilter.trim().toLowerCase();
    return shipments.filter((shipment) => {
      if (statusFilter && shipment.shipment_status !== statusFilter) {
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
        shipment.assigned_delivery_boy_name,
      ]
        .map((value) => String(value || "").toLowerCase())
        .join(" ");
      return haystack.includes(needle);
    });
  }, [queryFilter, shipments, statusFilter]);

  const summary = useMemo(() => {
    const total = shipments.length;
    const unassigned = shipments.filter((shipment) => !shipment.assigned_delivery_boy_id).length;
    const assigned = shipments.filter((shipment) => Boolean(shipment.assigned_delivery_boy_id)).length;
    const delivered = shipments.filter((shipment) => shipment.shipment_status === "delivered").length;
    return { total, unassigned, assigned, delivered };
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

  const assign = async (shipmentId, deliveryBoyId) => {
    if (!deliveryBoyId) return;
    setError("");
    try {
      await apiClient.assignDeliveryBoy(accessToken, shipmentId, { delivery_boy_id: Number(deliveryBoyId) });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const update = async (shipmentId, status) => {
    const payload = { status };
    if (status === "failed") {
      const reason = window.prompt("Failure reason (optional)");
      if (reason !== null) payload.failure_reason = reason;
    }
    setError("");
    try {
      await apiClient.updateShipmentStatus(accessToken, shipmentId, payload);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading shipments...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>Shipments</h2>
        <p>Assign delivery boys, track shipment statuses, and manage dispatch operations.</p>
      </header>

      <div className="delivery-summary-grid">
        <article>
          <p>Total Shipments</p>
          <h3>{summary.total}</h3>
        </article>
        <article>
          <p>Unassigned</p>
          <h3>{summary.unassigned}</h3>
        </article>
        <article>
          <p>Assigned</p>
          <h3>{summary.assigned}</h3>
        </article>
        <article>
          <p>Delivered</p>
          <h3>{summary.delivered}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Shipment List</h3>
          <span>{filteredShipments.length} records</span>
        </div>

        <div className="delivery-filter-row">
          <label>
            <span>Status</span>
            <select value={statusFilter} onChange={(event) => setParam("status", event.target.value)}>
              {STATUS_FILTER.map((status) => (
                <option key={status || "all"} value={status}>
                  {status ? toStatusLabel(status) : "All Status"}
                </option>
              ))}
            </select>
          </label>

          <form onSubmit={onQuerySubmit}>
            <label>
              <span>Search</span>
              <input
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder="Tracking, customer, order, driver..."
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
                <th>Driver</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.length === 0 && (
                <tr>
                  <td className="empty" colSpan={7}>
                    No shipments found for this filter.
                  </td>
                </tr>
              )}
              {filteredShipments.map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.tracking_number || `#${shipment.id}`}</td>
                  <td>#{shipment.order_id}</td>
                  <td>{shipment.customer_name || "-"}</td>
                  <td>
                    <span className={`delivery-status-pill ${statusTone(shipment.shipment_status)}`}>
                      {toStatusLabel(shipment.shipment_status)}
                    </span>
                  </td>
                  <td>{shipment.customer_address || "-"}</td>
                  <td>{shipment.assigned_delivery_boy_name || "-"}</td>
                  <td>
                    <div className="delivery-row-actions">
                      {!shipment.assigned_delivery_boy_id && shipment.shipment_status !== "delivered" && (
                        <select
                          className="delivery-inline-select"
                          onChange={(event) => assign(shipment.id, event.target.value)}
                          value=""
                        >
                          <option value="" disabled>
                            Assign driver
                          </option>
                          {deliveryBoys.map((deliveryBoy) => (
                            <option key={deliveryBoy.id} value={deliveryBoy.id}>
                              {deliveryBoy.name}
                            </option>
                          ))}
                        </select>
                      )}
                      {shipment.shipment_status === "delivered" ? (
                        <span className="delivery-inline-note">Finalized by delivery OTP</span>
                      ) : (
                        <select
                          className="delivery-inline-select"
                          defaultValue=""
                          onChange={(event) => update(shipment.id, event.target.value)}
                        >
                          <option value="" disabled>
                            Update status
                          </option>
                          {STATUS_OPTIONS.map((status) => (
                            <option key={status} value={status}>
                              {toStatusLabel(status)}
                            </option>
                          ))}
                        </select>
                      )}
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
