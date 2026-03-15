import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const ROLE_FILTER = ["", "customer", "vendor", "logistics", "delivery_boy", "admin"];
const STATUS_FILTER = ["", "active", "blocked", "pending"];

export default function AdminUsersPage() {
  const { accessToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const roleFilter = searchParams.get("role") || "";
  const statusFilter = searchParams.get("status") || "";
  const queryFilter = searchParams.get("q") || "";
  const [queryInput, setQueryInput] = useState(queryFilter);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setQueryInput(queryFilter);
  }, [queryFilter]);

  const load = async () => {
    const rows = await apiClient.listUsers(accessToken, {
      ...(roleFilter ? { role: roleFilter } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
    });
    setUsers(rows || []);
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
  }, [accessToken, roleFilter, statusFilter]);

  const filteredUsers = useMemo(() => {
    const needle = queryFilter.trim().toLowerCase();
    if (!needle) {
      return users;
    }
    return users.filter((user) =>
      [user.name, user.email, user.phone, user.role, user.status]
        .map((value) => String(value || "").toLowerCase())
        .join(" ")
        .includes(needle)
    );
  }, [queryFilter, users]);

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

  const setStatus = async (userId, status) => {
    setError("");
    try {
      await apiClient.setUserStatus(accessToken, userId, { status });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading users...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>User Management</h2>
        <p>Filter user base by role/status and control account access from a single table.</p>
      </header>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Users</h3>
          <span>{filteredUsers.length} records</span>
        </div>

        <div className="delivery-filter-row">
          <label>
            <span>Role</span>
            <select value={roleFilter} onChange={(event) => setParam("role", event.target.value)}>
              {ROLE_FILTER.map((role) => (
                <option key={role || "all"} value={role}>
                  {role || "All Roles"}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Status</span>
            <select value={statusFilter} onChange={(event) => setParam("status", event.target.value)}>
              {STATUS_FILTER.map((status) => (
                <option key={status || "all"} value={status}>
                  {status || "All Status"}
                </option>
              ))}
            </select>
          </label>
          <form onSubmit={onQuerySubmit}>
            <label>
              <span>Search</span>
              <input
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder="Name, email, role..."
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
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 && (
                <tr>
                  <td className="empty" colSpan={5}>
                    No users found for this filter.
                  </td>
                </tr>
              )}
              {filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>{user.role}</td>
                  <td>
                    <span className={`delivery-status-pill ${user.status === "active" ? "success" : "danger"}`}>
                      {user.status}
                    </span>
                  </td>
                  <td>
                    <div className="delivery-row-actions">
                      <button className="delivery-mini-btn strong" onClick={() => setStatus(user.id, "active")} type="button">
                        Activate
                      </button>
                      <button className="delivery-mini-btn muted" onClick={() => setStatus(user.id, "blocked")} type="button">
                        Block
                      </button>
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
