import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { toStatusLabel } from "../delivery/deliveryMetrics";

const ACTIVE_STATUSES = new Set(["pickup_requested", "picked", "in_transit", "out_for_delivery"]);

function statusTone(status) {
  if (status === "delivered") return "success";
  if (status === "failed") return "danger";
  if (status === "out_for_delivery") return "warning";
  return "neutral";
}

export default function LogisticsDashboardPage() {
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
        const [dashboardStats, shipmentRows] = await Promise.all([
          apiClient.getLogisticsDashboard(accessToken),
          apiClient.listShipments(accessToken),
        ]);
        if (cancelled) return;
        setStats(dashboardStats);
        setShipments(shipmentRows || []);
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

  const pendingTasks = useMemo(
    () => shipments.filter((shipment) => shipment.shipment_status !== "delivered").length,
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
          Welcome back, {user?.name || "Dispatcher"}. You have <strong>{pendingTasks} pending tasks</strong> for
          today&apos;s route.
        </p>
      </header>

      <div className="delivery-kpi-grid">
        <article className="delivery-kpi-card primary">
          <p>Total Shipments</p>
          <h3>{stats?.total_shipments || 0}</h3>
          <span>All logistics records</span>
        </article>
        <article className="delivery-kpi-card">
          <p>Unassigned Shipments</p>
          <h3>{stats?.unassigned_shipments || 0}</h3>
          <span>Need delivery boy mapping</span>
        </article>
        <article className="delivery-kpi-card">
          <p>Assigned Shipments</p>
          <h3>{stats?.assigned_shipments || 0}</h3>
          <span>Currently under execution</span>
        </article>
        <article className="delivery-kpi-card danger">
          <p>Failed Attempts</p>
          <h3>{stats?.failed_deliveries || 0}</h3>
          <span>Action required</span>
        </article>
      </div>

      <div className="delivery-dashboard-grid">
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Active Tasks</h3>
            <Link to="/logistics/shipments">View All</Link>
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
                      No active shipments right now.
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
                      <Link className="delivery-action-link" to="/logistics/shipments">
                        Manage
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <div className="delivery-side-stack">
          <article className="delivery-highlight-card">
            <h3>Route Optimization</h3>
            <p>Your current route plan is optimized for this zone&apos;s traffic pattern.</p>
            <Link className="delivery-highlight-btn" to="/logistics/shipments">
              Update Route
            </Link>
          </article>

          <article className="delivery-earnings-card">
            <p>Dispatch Update</p>
            <h3>{stats?.unassigned_shipments || 0}</h3>
            <span>Unassigned shipments waiting for allocation</span>
            <Link className="delivery-earnings-link" to="/logistics/delivery-boys">
              Open Delivery Boys
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}
