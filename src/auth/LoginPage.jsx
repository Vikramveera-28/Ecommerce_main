import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

const accountTypes = [
  { id: "customer", label: "Customer", icon: "CU" },
  { id: "vendor", label: "Vendor", icon: "VE" },
  { id: "admin", label: "Admin", icon: "AD" },
  { id: "logistics", label: "Client", icon: "CL" },
];

export default function LoginPage() {
  const { login, isAuthenticated, user } = useAuth();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [selectedType, setSelectedType] = useState("customer");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    const home = {
      customer: "/customer/home",
      vendor: "/vendor/dashboard",
      logistics: "/logistics/shipments",
      admin: "/admin/dashboard",
    };
    return <Navigate to={location.state?.from || home[user.role] || "/"} replace />;
  }

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(form);
      if (!rememberMe) {
        // Current auth flow persists by default; this toggle is present for UI parity.
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page elite-login-page">
      <div className="elite-login-shell">
        <aside className="elite-login-visual">
          <div className="elite-login-visual-content">
            <h1>Elite Sports</h1>
            <p>Performance Excellence</p>
            <span />
          </div>
        </aside>

        <form className="elite-login-form" onSubmit={onSubmit}>
          <div className="elite-login-head">
            <h2>Welcome Back</h2>
            <p>Please select your role and log in to your dashboard.</p>
          </div>

          <div className="elite-role-picker">
            <p>Account Type</p>
            <div className="elite-role-grid">
              {accountTypes.map((type) => (
                <button
                  className={`elite-role-btn${selectedType === type.id ? " active" : ""}`}
                  key={type.id}
                  onClick={() => setSelectedType(type.id)}
                  type="button"
                >
                  <span>{type.icon}</span>
                  <strong>{type.label}</strong>
                </button>
              ))}
            </div>
          </div>

          <label className="elite-input-label">
            <span>Email Address</span>
            <div className="elite-input-wrap">
              <i>@</i>
              <input
                onChange={(event) => setForm((old) => ({ ...old, email: event.target.value }))}
                placeholder="name@example.com"
                required
                type="email"
                value={form.email}
              />
            </div>
          </label>

          <label className="elite-input-label">
            <span className="elite-label-row">
              <span>Password</span>
              <a href="#!">Forgot Password?</a>
            </span>
            <div className="elite-input-wrap">
              <i>**</i>
              <input
                onChange={(event) => setForm((old) => ({ ...old, password: event.target.value }))}
                required
                type={showPassword ? "text" : "password"}
                value={form.password}
              />
              <button className="elite-password-toggle" onClick={() => setShowPassword((old) => !old)} type="button">
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          <label className="elite-remember-row">
            <input checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} type="checkbox" />
            Keep me logged in
          </label>

          {error && <p className="elite-login-error">{error}</p>}

          <button className="elite-login-submit" disabled={loading}>
            {loading ? "Signing in..." : "Log In To Account"}
          </button>

          <p className="elite-login-register">
            New to Elite Sports? <Link to="/register">Create an Account</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
