import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const RANGE_OPTIONS = [
  { value: "1d", label: "Last 1 Day" },
  { value: "7d", label: "Last 7 Days" },
  { value: "14d", label: "Last 14 Days" },
  { value: "1m", label: "Last 1 Month" },
  { value: "3m", label: "Last 3 Months" },
  { value: "6m", label: "Last 6 Months" },
  { value: "12m", label: "Last 12 Months" },
  { value: "custom", label: "Custom Range" },
];

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function AdminOperationsPage() {
  const { accessToken } = useAuth();
  const [range, setRange] = useState("1m");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (range === "custom" && (!fromDate || !toDate)) {
      return;
    }

    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const params = { range };
        if (appliedQuery) {
          params.q = appliedQuery;
        }
        if (range === "custom") {
          params.from_date = fromDate;
          params.to_date = toDate;
        }
        const payload = await apiClient.adminOperationsReport(accessToken, params);
        if (!cancelled) {
          setReport(payload);
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
  }, [accessToken, appliedQuery, fromDate, range, toDate]);

  const trendRows = report?.revenue_trend || [];
  const maxRevenue = useMemo(
    () => Math.max(...trendRows.map((row) => Number(row.revenue || 0)), 1),
    [trendRows]
  );

  const onSearchSubmit = (event) => {
    event.preventDefault();
    setAppliedQuery(queryInput.trim());
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading operations report...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>Operations A to Z</h2>
        <p>
          End-to-end delivery intelligence: vendor, logistics approval, delivery boy, customer, payment, and item level
          tracking.
        </p>
      </header>

      <article className="delivery-card">
        <div className="delivery-filter-row">
          <label>
            <span>Revenue Range</span>
            <select onChange={(event) => setRange(event.target.value)} value={range}>
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {range === "custom" && (
            <>
              <label>
                <span>From Date</span>
                <input onChange={(event) => setFromDate(event.target.value)} type="date" value={fromDate} />
              </label>
              <label>
                <span>To Date</span>
                <input onChange={(event) => setToDate(event.target.value)} type="date" value={toDate} />
              </label>
            </>
          )}

          <form onSubmit={onSearchSubmit}>
            <label>
              <span>Search Delivery Detail</span>
              <input
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder="Tracking, customer, vendor, item..."
                value={queryInput}
              />
            </label>
          </form>
        </div>

        {error && <p className="delivery-error">{error}</p>}
      </article>

      <div className="delivery-summary-grid earned">
        <article className="highlight">
          <p>Total Revenue</p>
          <h3>{formatCurrency(report?.totals?.revenue || 0)}</h3>
        </article>
        <article>
          <p>Avg Revenue / Item</p>
          <h3>{formatCurrency(report?.totals?.avg_revenue_per_item || 0)}</h3>
        </article>
        <article>
          <p>Avg Revenue / Delivery</p>
          <h3>{formatCurrency(report?.totals?.avg_revenue_per_delivery || 0)}</h3>
        </article>
        <article>
          <p>Total Deliveries</p>
          <h3>{report?.totals?.deliveries || 0}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Revenue Trend</h3>
          <span>{trendRows.length} buckets</span>
        </div>
        <div className="admin-chart-grid">
          {trendRows.map((row) => {
            const height = Math.max(8, Math.round((Number(row.revenue || 0) / maxRevenue) * 170));
            return (
              <div className="admin-chart-col" key={row.label}>
                <div className="admin-chart-bar-wrap">
                  <i className="admin-chart-bar" style={{ height: `${height}px` }} />
                </div>
                <small>{row.label}</small>
                <span>{formatCurrency(row.revenue)}</span>
              </div>
            );
          })}
        </div>
      </article>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Delivery Detail A to Z</h3>
          <span>{(report?.deliveries || []).length} rows</span>
        </div>
        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Tracking</th>
                <th>Status</th>
                <th>Order</th>
                <th>Customer</th>
                <th>Vendors</th>
                <th>Items</th>
                <th>Logistics</th>
                <th>Approved By</th>
                <th>Delivery Boy</th>
                <th>Payment</th>
                <th>Order Total</th>
              </tr>
            </thead>
            <tbody>
              {(report?.deliveries || []).length === 0 && (
                <tr>
                  <td className="empty" colSpan={11}>
                    No delivery rows in this filter.
                  </td>
                </tr>
              )}
              {(report?.deliveries || []).map((delivery) => (
                <tr key={delivery.shipment_id}>
                  <td>{delivery.tracking_number || `#${delivery.shipment_id}`}</td>
                  <td>
                    <span className="delivery-status-pill neutral">{delivery.shipment_status}</span>
                  </td>
                  <td>#{delivery.order_id}</td>
                  <td>{delivery.customer_name || "-"}</td>
                  <td>{delivery.vendors || "-"}</td>
                  <td>{delivery.items || "-"}</td>
                  <td>{delivery.logistics_owner || "-"}</td>
                  <td>{delivery.approved_by_logistics || "-"}</td>
                  <td>{delivery.delivery_boy || "-"}</td>
                  <td>{delivery.payment_status || "-"}</td>
                  <td>{formatCurrency(delivery.order_total || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
