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

function TopChartCard({ title, rows, valueKey, labelKey = "name", formatter = (value) => value }) {
  const maxValue = useMemo(() => Math.max(...rows.map((row) => Number(row[valueKey] || 0)), 1), [rows, valueKey]);

  return (
    <article className="delivery-card">
      <div className="delivery-card-head">
        <h3>{title}</h3>
        <span>{rows.length} rows</span>
      </div>
      <div className="admin-rank-bars">
        {rows.length === 0 && <p className="delivery-note">No data in selected range.</p>}
        {rows.map((row, index) => {
          const value = Number(row[valueKey] || 0);
          const width = Math.max(6, Math.round((value / maxValue) * 100));
          return (
            <div className="admin-rank-row" key={`${title}-${row[labelKey] || index}`}>
              <div className="admin-rank-label">
                <b>{index + 1}.</b>
                <span>{row[labelKey] || "-"}</span>
              </div>
              <div className="admin-rank-meter">
                <i style={{ width: `${width}%` }} />
              </div>
              <strong>{formatter(value, row)}</strong>
            </div>
          );
        })}
      </div>
    </article>
  );
}

export default function AdminDashboardPage() {
  const { accessToken } = useAuth();
  const [range, setRange] = useState("1m");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [sales, setSales] = useState(null);
  const [ops, setOps] = useState(null);
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
        if (range === "custom") {
          params.from_date = fromDate;
          params.to_date = toDate;
        }
        const [salesReport, operationsReport] = await Promise.all([
          apiClient.salesReport(accessToken),
          apiClient.adminOperationsReport(accessToken, params),
        ]);
        if (!cancelled) {
          setSales(salesReport);
          setOps(operationsReport);
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
  }, [accessToken, range, fromDate, toDate]);

  const trendRows = ops?.revenue_trend || [];
  const trendMax = useMemo(() => Math.max(...trendRows.map((row) => Number(row.revenue || 0)), 1), [trendRows]);

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
      <header className="delivery-page-head split">
        <div>
          <h2>Admin Dashboard</h2>
          <p>Graph view for top 10 vendors, delivery boys, customers, items, and categories.</p>
        </div>
        <div className="delivery-filter-row" style={{ marginTop: 0 }}>
          <label>
            <span>Range</span>
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
                <span>From</span>
                <input onChange={(event) => setFromDate(event.target.value)} type="date" value={fromDate} />
              </label>
              <label>
                <span>To</span>
                <input onChange={(event) => setToDate(event.target.value)} type="date" value={toDate} />
              </label>
            </>
          )}
        </div>
      </header>

      <div className="delivery-summary-grid earned">
        <article className="highlight">
          <p>Total Revenue</p>
          <h3>{formatCurrency(ops?.totals?.revenue || 0)}</h3>
        </article>
        <article>
          <p>Avg Revenue / Item</p>
          <h3>{formatCurrency(ops?.totals?.avg_revenue_per_item || 0)}</h3>
        </article>
        <article>
          <p>Avg Revenue / Delivery</p>
          <h3>{formatCurrency(ops?.totals?.avg_revenue_per_delivery || 0)}</h3>
        </article>
        <article>
          <p>COD Confirmed</p>
          <h3>{sales?.totals?.cod_confirmed_orders || 0}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Revenue Trend</h3>
          <span>{trendRows.length} points</span>
        </div>
        <div className="admin-chart-grid">
          {trendRows.map((row) => {
            const height = Math.max(8, Math.round((Number(row.revenue || 0) / trendMax) * 170));
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

      <div className="admin-ranking-grid">
        <TopChartCard
          formatter={(value) => formatCurrency(value)}
          rows={ops?.top_vendors || []}
          title="Top 10 Vendors"
          valueKey="total_revenue"
        />
        <TopChartCard
          formatter={(value) => value.toLocaleString()}
          rows={ops?.top_delivery_boys || []}
          title="Top 10 Delivery Boys"
          valueKey="delivered"
        />
        <TopChartCard
          formatter={(value) => formatCurrency(value)}
          rows={ops?.top_customers || []}
          title="Top Customers"
          valueKey="total_spend"
        />
        <TopChartCard
          formatter={(value) => value.toLocaleString()}
          rows={ops?.top_items || []}
          title="Top 10 Items"
          valueKey="total_qty"
        />
        <TopChartCard
          formatter={(value) => formatCurrency(value)}
          rows={ops?.top_categories || []}
          title="Top Categories"
          valueKey="total_revenue"
        />
      </div>
    </section>
  );
}
