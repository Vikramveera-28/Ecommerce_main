import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const NEXT_STATUS_OPTIONS = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["packed", "cancelled"],
  packed: ["shipped"],
};

export default function VendorOrdersPage() {
  const { accessToken } = useAuth();
  const [orders, setOrders] = useState([]);
  const [error, setError] = useState("");

  const load = async () => {
    const rows = await apiClient.listVendorOrders(accessToken);
    setOrders(rows || []);
  };

  useEffect(() => {
    load().catch((err) => alert(err.message));
  }, []);

  const update = async (orderId, status) => {
    setError("");
    try {
      await apiClient.updateVendorOrderStatus(accessToken, orderId, { status });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="panel stack">
      <div className="panel-header">
        <h2>Vendor Orders</h2>
        <span className="chip">{orders.length} lines</span>
      </div>
      {error && <p className="error">{error}</p>}
      {orders.length === 0 && <p className="muted">No order lines yet.</p>}
      <div className="list">
        {orders.map((row) => (
          <article key={`${row.order_id}-${row.order_item_id}`} className="list-row">
            <div>
              <strong>Order #{row.order_id}</strong>
              <p className="muted">Product {row.product_id} x {row.quantity}</p>
            </div>
            <div className="row">
              <span className="chip">{row.order_status}</span>
              {(NEXT_STATUS_OPTIONS[row.order_status] || []).length > 0 ? (
                <select onChange={(e) => update(row.order_id, e.target.value)} defaultValue="">
                  <option value="" disabled>Update</option>
                  {(NEXT_STATUS_OPTIONS[row.order_status] || []).map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              ) : (
                <span className="muted">Read only</span>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
