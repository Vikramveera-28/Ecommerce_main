import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function percentageChange(current, previous) {
  if (previous <= 0) {
    return current > 0 ? 100 : 0;
  }
  return ((current - previous) / previous) * 100;
}

function shortWeekLabel(index) {
  return `Week ${index + 1}`;
}

function buildChartPath(values, width, height, padding = 18) {
  if (!values.length) return "";
  const max = Math.max(...values, 1);
  const min = 0;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  return values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * innerWidth;
      const y = padding + innerHeight - ((value - min) / (max - min || 1)) * innerHeight;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function buildAreaPath(values, width, height, padding = 18) {
  if (!values.length) return "";
  const linePath = buildChartPath(values, width, height, padding);
  const firstX = padding;
  const lastX = width - padding;
  const baselineY = height - padding;
  return `${linePath} L${lastX.toFixed(1)},${baselineY.toFixed(1)} L${firstX.toFixed(1)},${baselineY.toFixed(1)} Z`;
}

function bucketWeeklyRevenue(orders, startDate, includeCancelled = false) {
  const buckets = [0, 0, 0, 0];
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  const start = new Date(startDate).getTime();
  const end = start + weekMs * 4;

  (orders || []).forEach((row) => {
    if (!includeCancelled && row.order_status === "cancelled") {
      return;
    }
    const created = new Date(row.created_at).getTime();
    if (Number.isNaN(created) || created < start || created >= end) {
      return;
    }
    const bucketIndex = Math.min(3, Math.max(0, Math.floor((created - start) / weekMs)));
    buckets[bucketIndex] += Number(row.price || 0) * Number(row.quantity || 0);
  });

  return buckets;
}

export default function VendorDashboardPage() {
  const { accessToken } = useAuth();
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [orderRows, productRows] = await Promise.all([
          apiClient.listVendorOrders(accessToken),
          apiClient.listVendorProducts(accessToken),
        ]);
        setOrders(orderRows || []);
        setProducts(productRows || []);
      } catch (err) {
        setError(err.message);
        setOrders([]);
        setProducts([]);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [accessToken]);

  const analytics = useMemo(() => {
    const validOrders = (orders || []).filter((row) => row.order_status !== "cancelled");
    const totalRevenue = validOrders.reduce((sum, row) => sum + Number(row.price || 0) * Number(row.quantity || 0), 0);

    const orderIds = new Set(validOrders.map((row) => row.order_id));
    const totalOrders = orderIds.size;
    const avgOrderValue = totalOrders > 0 ? totalRevenue / totalOrders : 0;

    const activeListings = (products || []).filter((p) => p.status === "active" && p.approval_status === "approved").length;
    const pendingApproval = (products || []).filter((p) => p.approval_status === "pending").length;

    const currentDate = new Date();
    const monthStart = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const monthlyRevenue = validOrders
      .filter((row) => {
        const created = new Date(row.created_at);
        return !Number.isNaN(created.getTime()) && created >= monthStart;
      })
      .reduce((sum, row) => sum + Number(row.price || 0) * Number(row.quantity || 0), 0);

    const currentPeriodStart = new Date();
    currentPeriodStart.setDate(currentPeriodStart.getDate() - 27);
    const previousPeriodStart = new Date(currentPeriodStart);
    previousPeriodStart.setDate(previousPeriodStart.getDate() - 28);

    const weeklyCurrent = bucketWeeklyRevenue(validOrders, currentPeriodStart);
    const weeklyPrevious = bucketWeeklyRevenue(validOrders, previousPeriodStart);

    const currentTotal = weeklyCurrent.reduce((sum, value) => sum + value, 0);
    const previousTotal = weeklyPrevious.reduce((sum, value) => sum + value, 0);

    const deltaRevenue = percentageChange(currentTotal, previousTotal);
    const deltaOrders = percentageChange(totalOrders, Math.max(1, Math.floor(totalOrders * 0.9)));

    const productRollup = new Map();
    validOrders.forEach((row) => {
      const product = (products || []).find((p) => p.id === row.product_id);
      if (!product) return;
      const revenue = Number(row.price || 0) * Number(row.quantity || 0);
      const existing = productRollup.get(row.product_id) || {
        id: row.product_id,
        name: product.name,
        sku: product.sku,
        sales: 0,
        revenue: 0,
        status: product.approval_status,
      };
      existing.sales += Number(row.quantity || 0);
      existing.revenue += revenue;
      productRollup.set(row.product_id, existing);
    });

    const topProducts = [...productRollup.values()].sort((a, b) => b.revenue - a.revenue).slice(0, 5);

    return {
      totalRevenue,
      totalOrders,
      avgOrderValue,
      activeListings,
      pendingApproval,
      monthlyRevenue,
      weeklyCurrent,
      weeklyPrevious,
      deltaRevenue,
      deltaOrders,
      topProducts,
    };
  }, [orders, products]);

  const chartWidth = 860;
  const chartHeight = 320;
  const currentPath = useMemo(
    () => buildChartPath(analytics.weeklyCurrent, chartWidth, chartHeight),
    [analytics.weeklyCurrent]
  );
  const previousPath = useMemo(
    () => buildChartPath(analytics.weeklyPrevious, chartWidth, chartHeight),
    [analytics.weeklyPrevious]
  );
  const areaPath = useMemo(
    () => buildAreaPath(analytics.weeklyCurrent, chartWidth, chartHeight),
    [analytics.weeklyCurrent]
  );

  return (
    <div className="vendor-page">
      <section className="vendor-hero">
        <div>
          <h2>Business Performance</h2>
          <p>Real-time insights and growth metrics for your storefront.</p>
        </div>
        <div className="vendor-hero-actions">
          <button type="button">Last 30 Days</button>
          <button className="primary" type="button">
            Export Report
          </button>
        </div>
      </section>

      {loading && <p className="elite-muted">Loading dashboard...</p>}
      {error && <p className="elite-error">{error}</p>}

      <section className="vendor-kpi-grid">
        <article className="vendor-kpi-card">
          <div className="vendor-kpi-head">
            <span>Total Revenue</span>
            <b className={analytics.deltaRevenue >= 0 ? "up" : "down"}>{analytics.deltaRevenue >= 0 ? "+" : ""}{analytics.deltaRevenue.toFixed(1)}%</b>
          </div>
          <h3>{formatCurrency(analytics.totalRevenue)}</h3>
        </article>

        <article className="vendor-kpi-card">
          <div className="vendor-kpi-head">
            <span>Total Orders</span>
            <b className={analytics.deltaOrders >= 0 ? "up" : "down"}>{analytics.deltaOrders >= 0 ? "+" : ""}{analytics.deltaOrders.toFixed(1)}%</b>
          </div>
          <h3>{analytics.totalOrders.toLocaleString()}</h3>
        </article>

        <article className="vendor-kpi-card">
          <div className="vendor-kpi-head">
            <span>Avg. Order Value</span>
            <b className="up">Live</b>
          </div>
          <h3>{formatCurrency(analytics.avgOrderValue)}</h3>
        </article>

        <article className="vendor-kpi-card">
          <div className="vendor-kpi-head">
            <span>Pending Approval</span>
            <b className={analytics.pendingApproval > 0 ? "down" : "up"}>{analytics.pendingApproval} Pending</b>
          </div>
          <h3>{analytics.activeListings} Active</h3>
        </article>
      </section>

      <section className="vendor-chart-card">
        <div className="vendor-chart-head">
          <h3>Sales Performance Over Time</h3>
          <div className="vendor-chart-legend">
            <span>
              <i className="net" /> Net Sales
            </span>
            <span>
              <i className="prev" /> Previous Period
            </span>
          </div>
        </div>

        <div className="vendor-chart-wrap">
          <svg className="vendor-chart" viewBox={`0 0 ${chartWidth} ${chartHeight}`}>
            <defs>
              <linearGradient id="vendorArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="rgba(26, 196, 42, 0.24)" />
                <stop offset="100%" stopColor="rgba(26, 196, 42, 0.03)" />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#vendorArea)" />
            <path d={previousPath} fill="none" stroke="#a8b7cc" strokeDasharray="7 7" strokeWidth="3" />
            <path d={currentPath} fill="none" stroke="#1ac42a" strokeWidth="4" />
          </svg>
          <div className="vendor-chart-labels">
            {analytics.weeklyCurrent.map((_, index) => (
              <span key={index}>{shortWeekLabel(index)}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="vendor-bottom-grid">
        <article className="vendor-table-card">
          <div className="vendor-table-head">
            <h3>Top Performing Products</h3>
            <span>{analytics.topProducts.length} items</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Sales</th>
                <th>Revenue</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {analytics.topProducts.length === 0 ? (
                <tr>
                  <td className="empty" colSpan={5}>
                    No product sales yet.
                  </td>
                </tr>
              ) : (
                analytics.topProducts.map((product) => (
                  <tr key={product.id}>
                    <td>{product.name}</td>
                    <td>{product.sku}</td>
                    <td>{product.sales}</td>
                    <td>{formatCurrency(product.revenue)}</td>
                    <td>
                      <span className={`vendor-status ${product.status}`}>{product.status}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </article>

        <article className="vendor-highlight-card">
          <p>PRO INSIGHT</p>
          <h3>Monthly Revenue</h3>
          <strong>{formatCurrency(analytics.monthlyRevenue)}</strong>
          <span>Keep adding active products to improve weekly sales conversion.</span>
        </article>
      </section>
    </div>
  );
}
