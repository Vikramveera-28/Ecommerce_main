import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

const roleOptions = [
  { id: "customer", label: "Customer", icon: "CU" },
  { id: "vendor", label: "Vendor", icon: "VE" },
  { id: "logistics", label: "Logistics", icon: "LO" },
  { id: "delivery_boy", label: "Delivery Boy", icon: "DB" },
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "", role: "customer" });
  const [showPassword, setShowPassword] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    if (!acceptTerms) {
      setError("Please accept the terms to continue.");
      setLoading(false);
      return;
    }

    try {
      await register(form);
      navigate("/login");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page elite-login-page elite-register-page">
      <div className="elite-login-shell elite-register-shell">
        <aside className="elite-login-visual elite-register-visual">
          <div className="elite-login-visual-content">
            <h1>Elite Sports</h1>
            <p>Build Your Pro Profile</p>
            <span />
          </div>
        </aside>

        <form className="elite-login-form elite-register-form" onSubmit={onSubmit}>
          <div className="elite-login-head">
            <h2>Create Account</h2>
            <p>Set up your role and profile to access the Elite Sports platform.</p>
          </div>

          <div className="elite-role-picker">
            <p>Account Type</p>
            <div className="elite-role-grid elite-role-grid-3">
              {roleOptions.map((role) => (
                <button
                  className={`elite-role-btn${form.role === role.id ? " active" : ""}`}
                  key={role.id}
                  onClick={() => setForm((old) => ({ ...old, role: role.id }))}
                  type="button"
                >
                  <span>{role.icon}</span>
                  <strong>{role.label}</strong>
                </button>
              ))}
            </div>
          </div>

          <label className="elite-input-label">
            <span>Full Name</span>
            <div className="elite-input-wrap">
              <i>NM</i>
              <input
                onChange={(event) => setForm((old) => ({ ...old, name: event.target.value }))}
                placeholder="Your full name"
                required
                value={form.name}
              />
            </div>
          </label>

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
            <span>Phone</span>
            <div className="elite-input-wrap">
              <i>PH</i>
              <input
                onChange={(event) => setForm((old) => ({ ...old, phone: event.target.value }))}
                placeholder="Optional"
                value={form.phone}
              />
            </div>
          </label>

          <label className="elite-input-label">
            <span>Password</span>
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
            <input checked={acceptTerms} onChange={(event) => setAcceptTerms(event.target.checked)} type="checkbox" />
            I agree to the platform terms and policies
          </label>

          {error && <p className="elite-login-error">{error}</p>}

          <button className="elite-login-submit elite-register-submit" disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </button>

          <p className="elite-login-register">
            Already have an account? <Link to="/login">Log In</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
