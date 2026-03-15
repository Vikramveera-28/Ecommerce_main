import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

export default function LogisticsDeliveryBoysPage() {
  const { accessToken } = useAuth();
  const [list, setList] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    const rows = await apiClient.listDeliveryBoys(accessToken);
    setList(rows || []);
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

  const filteredList = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return list;
    }
    return list.filter((deliveryBoy) => {
      const haystack = [deliveryBoy.name, deliveryBoy.email, deliveryBoy.phone, deliveryBoy.vehicle_type]
        .map((value) => String(value || "").toLowerCase())
        .join(" ");
      return haystack.includes(needle);
    });
  }, [list, query]);

  const summary = useMemo(() => {
    const total = list.length;
    const active = list.filter((deliveryBoy) => deliveryBoy.is_active).length;
    const inactive = total - active;
    return { total, active, inactive };
  }, [list]);

  const toggleActive = async (profileId, currentActive) => {
    setError("");
    try {
      await apiClient.updateDeliveryBoyStatus(accessToken, profileId, { is_active: !currentActive });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading delivery boys...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>Delivery Boys</h2>
        <p>Manage active rider pool for dispatch assignment and route execution.</p>
      </header>

      <div className="delivery-summary-grid">
        <article>
          <p>Total Drivers</p>
          <h3>{summary.total}</h3>
        </article>
        <article>
          <p>Active</p>
          <h3>{summary.active}</h3>
        </article>
        <article>
          <p>Inactive</p>
          <h3>{summary.inactive}</h3>
        </article>
        <article>
          <p>Visible Rows</p>
          <h3>{filteredList.length}</h3>
        </article>
      </div>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Rider Registry</h3>
          <span>{filteredList.length} records</span>
        </div>

        <div className="delivery-filter-row">
          <label style={{ gridColumn: "1 / -1" }}>
            <span>Search</span>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Name, email, phone, vehicle..."
              value={query}
            />
          </label>
        </div>

        {error && <p className="delivery-error">{error}</p>}

        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Vehicle</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredList.length === 0 && (
                <tr>
                  <td className="empty" colSpan={6}>
                    No delivery boys found for this search.
                  </td>
                </tr>
              )}
              {filteredList.map((deliveryBoy) => (
                <tr key={deliveryBoy.id}>
                  <td>{deliveryBoy.name}</td>
                  <td>{deliveryBoy.email}</td>
                  <td>{deliveryBoy.phone || "-"}</td>
                  <td>{deliveryBoy.vehicle_type || "-"}</td>
                  <td>
                    <span className={`delivery-status-pill ${deliveryBoy.is_active ? "success" : "danger"}`}>
                      {deliveryBoy.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="delivery-mini-btn strong"
                      onClick={() => toggleActive(deliveryBoy.id, deliveryBoy.is_active)}
                      type="button"
                    >
                      {deliveryBoy.is_active ? "Deactivate" : "Activate"}
                    </button>
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
