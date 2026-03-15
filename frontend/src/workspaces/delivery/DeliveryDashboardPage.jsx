import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { toStatusLabel } from "./deliveryMetrics";

const ACTIVE_STATUSES = new Set(["pickup_requested", "picked", "in_transit", "out_for_delivery"]);

function statusTone(status) {
  if (status === "delivered") return "success";
  if (status === "failed") return "danger";
  if (status === "out_for_delivery") return "warning";
  return "neutral";
}

export default function DeliveryDashboardPage() {
  const { accessToken, user } = useAuth();
  const [stats, setStats] = useState(null);
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [dashboardData, assignedShipments] = await Promise.all([
          apiClient.getDeliveryDashboard(accessToken),
          apiClient.listMyDeliveries(accessToken),
        ]);
        if (cancelled) return;
        setStats(dashboardData);
        setShipments(assignedShipments || []);
      } catch (err) {
        if (cancelled) return;
        setError(err.message);
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

  const activeTasks = useMemo(
    () => shipments.filter((shipment) => ACTIVE_STATUSES.has(shipment.shipment_status)).slice(0, 6),
    [shipments]
  );

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading dashboard...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="delivery-page">
        <p className="delivery-error">{error}</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>Dashboard Overview</h2>
        <p>
          Welcome back, {user?.name || "Courier"}. You have <strong>{stats?.pending_deliveries || 0} pending tasks</strong>{" "}
          for today&apos;s route.
        </p>
      </header>

      <div className="delivery-kpi-grid">
        <article className="delivery-kpi-card primary">
          <p>Total Deliveries Today</p>
          <h3>{stats?.today_deliveries || 0}</h3>
          <span>Assigned for current shift</span>
        </article>
        <article className="delivery-kpi-card">
          <p>Pending Deliveries</p>
          <h3>{stats?.pending_deliveries || 0}</h3>
          <span>Priority: high level urgent</span>
        </article>
        <article className="delivery-kpi-card">
          <p>Completed Tasks</p>
          <h3>{stats?.completed_deliveries || 0}</h3>
          <span>Success rate tracked daily</span>
        </article>
        <article className="delivery-kpi-card danger">
          <p>Failed Attempts</p>
          <h3>{stats?.failed_deliveries || 0}</h3>
          <span>Action required</span>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Active Tasks</h3>
          <Link to="/delivery/shipments">View All</Link>
        </div>

        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Customer</th>
                <th>Address</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {activeTasks.length === 0 && (
                <tr>
                  <td className="empty" colSpan={5}>
                    No active tasks right now.
                  </td>
                </tr>
              )}
              {activeTasks.map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.tracking_number || `#${shipment.id}`}</td>
                  <td>{shipment.customer_name || "-"}</td>
                  <td>{shipment.customer_address || "-"}</td>
                  <td>
                    <span className={`delivery-status-pill ${statusTone(shipment.shipment_status)}`}>
                      {toStatusLabel(shipment.shipment_status)}
                    </span>
                  </td>
                  <td>
                    <Link className="delivery-action-link" to={`/delivery/shipments/${shipment.id}`}>
                      Details
                    </Link>
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
