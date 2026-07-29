import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const roleLinks = {
  customer: [
    { to: "/customer/home", label: "Home" },
    { to: "/customer/products", label: "Products" },
    { to: "/customer/favorites", label: "Favorites" },
    { to: "/customer/cart", label: "Cart" },
    { to: "/customer/orders", label: "Orders" },
    { to: "/customer/profile", label: "Profile" },
  ],
  vendor: [
    { to: "/vendor/dashboard", label: "Dashboard" },
    { to: "/vendor/products", label: "Products" },
    { to: "/vendor/orders", label: "Orders" },
    { to: "/vendor/earnings", label: "Earnings" },
    { to: "/vendor/payouts", label: "Payouts" },
  ],
  logistics: [
    { to: "/logistics/dashboard", label: "Dashboard" },
    { to: "/logistics/shipments", label: "Shipments" },
    { to: "/logistics/delivery-boys", label: "Delivery Boys" },
    { to: "/logistics/earnings", label: "Earnings" },
    { to: "/logistics/payouts", label: "Payouts" },
  ],
  delivery_boy: [
    { to: "/delivery/dashboard", label: "Dashboard" },
    { to: "/delivery/shipments", label: "My Deliveries" },
    { to: "/delivery/earned", label: "Earnings" },
    { to: "/delivery/payouts", label: "Payouts" },
  ],
  admin: [
    { to: "/admin/dashboard", label: "Dashboard" },
    { to: "/admin/users", label: "Users" },
    { to: "/admin/moderation", label: "Moderation" },
    { to: "/admin/operations", label: "Operations" },
    { to: "/admin/settlements", label: "Settlements" },
  ],
};

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const links = roleLinks[user?.role] || [];
  const isCustomer = user?.role === "customer";
  const isVendor = user?.role === "vendor";
  const isLogistics = user?.role === "logistics";
  const isDelivery = user?.role === "delivery_boy";
  const isAdmin = user?.role === "admin";
  const roleHome = links[0]?.to || "/";
  const roleLabel = user?.role ? `${user.role.toUpperCase()} WORKSPACE` : "WORKSPACE";
  const [commandSearch, setCommandSearch] = useState("");
  const [vendorSearch, setVendorSearch] = useState("");
  const [logisticsSearch, setLogisticsSearch] = useState("");
  const [deliverySearch, setDeliverySearch] = useState("");
  const [adminSearch, setAdminSearch] = useState("");

  useEffect(() => {
    if (!isCustomer) return;
    if (location.pathname === "/customer/products") {
      const q = new URLSearchParams(location.search).get("q") || "";
      setCommandSearch(q);
      return;
    }
    setCommandSearch("");
  }, [isCustomer, location.pathname, location.search]);

  useEffect(() => {
    if (!isAdmin) return;
    if (location.pathname === "/admin/users" || location.pathname === "/admin/operations") {
      const q = new URLSearchParams(location.search).get("q") || "";
      setAdminSearch(q);
      return;
    }
    setAdminSearch("");
  }, [isAdmin, location.pathname, location.search]);

  useEffect(() => {
    if (!isVendor) return;
    if (location.pathname === "/vendor/products") {
      const q = new URLSearchParams(location.search).get("q") || "";
      setVendorSearch(q);
      return;
    }
    setVendorSearch("");
  }, [isVendor, location.pathname, location.search]);

  useEffect(() => {
    if (!isLogistics) return;
    if (location.pathname === "/logistics/shipments") {
      const q = new URLSearchParams(location.search).get("q") || "";
      setLogisticsSearch(q);
      return;
    }
    setLogisticsSearch("");
  }, [isLogistics, location.pathname, location.search]);

  useEffect(() => {
    if (!isDelivery) return;
    if (location.pathname === "/delivery/shipments") {
      const q = new URLSearchParams(location.search).get("q") || "";
      setDeliverySearch(q);
      return;
    }
    setDeliverySearch("");
  }, [isDelivery, location.pathname, location.search]);

  const onSearchSubmit = (event) => {
    event.preventDefault();
    const q = commandSearch.trim();
    navigate(`/customer/products${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  };

  const onDeliverySearchSubmit = (event) => {
    event.preventDefault();
    const q = deliverySearch.trim();
    navigate(`/delivery/shipments${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  };

  const onVendorSearchSubmit = (event) => {
    event.preventDefault();
    const q = vendorSearch.trim();
    navigate(`/vendor/products${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  };

  const onLogisticsSearchSubmit = (event) => {
    event.preventDefault();
    const q = logisticsSearch.trim();
    navigate(`/logistics/shipments${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  };

  const onAdminSearchSubmit = (event) => {
    event.preventDefault();
    const q = adminSearch.trim();
    navigate(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  };

  if (isCustomer || isVendor || isLogistics || isDelivery || isAdmin) {
    const roleConfig = {
      customer: {
        brandMark: "CU",
        subtitle: "Premium Customer",
        searchValue: commandSearch,
        onSearchChange: setCommandSearch,
        onSearchSubmit,
        searchPlaceholder: "Search products, categories...",
        iconByRoute: {
          "/customer/home": "HM",
          "/customer/products": "PRD",
          "/customer/favorites": "FAV",
          "/customer/cart": "CRT",
          "/customer/orders": "ORD",
          "/customer/profile": "PRO",
        },
      },
      vendor: {
        brandMark: "VN",
        subtitle: "Vendor Workspace",
        searchValue: vendorSearch,
        onSearchChange: setVendorSearch,
        onSearchSubmit: onVendorSearchSubmit,
        searchPlaceholder: "Search products, sku...",
        iconByRoute: {
          "/vendor/dashboard": "DB",
          "/vendor/products": "PRD",
          "/vendor/orders": "ORD",
          "/vendor/earnings": "ERN",
          "/vendor/payouts": "PAY",
        },
      },
      logistics: {
        brandMark: "LG",
        subtitle: "Dispatch Control",
        searchValue: logisticsSearch,
        onSearchChange: setLogisticsSearch,
        onSearchSubmit: onLogisticsSearchSubmit,
        searchPlaceholder: "Search shipments, order id...",
        iconByRoute: {
          "/logistics/dashboard": "DB",
          "/logistics/shipments": "SHP",
          "/logistics/delivery-boys": "BOY",
          "/logistics/earnings": "ERN",
          "/logistics/payouts": "PAY",
        },
      },
      delivery_boy: {
        brandMark: "DL",
        subtitle: "Gold Tier Courier",
        searchValue: deliverySearch,
        onSearchChange: setDeliverySearch,
        onSearchSubmit: onDeliverySearchSubmit,
        searchPlaceholder: "Search orders, customers...",
        iconByRoute: {
          "/delivery/dashboard": "DB",
          "/delivery/shipments": "DL",
          "/delivery/earned": "ERN",
          "/delivery/payouts": "PAY",
        },
      },
      admin: {
        brandMark: "AD",
        subtitle: "Control Center",
        searchValue: adminSearch,
        onSearchChange: setAdminSearch,
        onSearchSubmit: onAdminSearchSubmit,
        searchPlaceholder: "Search users, deliveries, vendors...",
        iconByRoute: {
          "/admin/dashboard": "DB",
          "/admin/users": "USR",
          "/admin/moderation": "MOD",
          "/admin/operations": "OPS",
          "/admin/settlements": "SET",
        },
      },
    };

    const currentRoleConfig = roleConfig[user?.role] || roleConfig.logistics;

    return (
      <div className="app-shell delivery-shell">
        <aside className="delivery-sidebar">
          <Link className="delivery-brand" to={roleHome}>
            <span className="delivery-brand-mark">{currentRoleConfig.brandMark}</span>
            <span>Workspace</span>
          </Link>

          <nav className="delivery-sidebar-nav">
            {links.map((link) => (
              <NavLink
                key={link.to}
                className={({ isActive }) => `delivery-menu-item${isActive ? " active" : ""}`}
                to={link.to}
              >
                <span className="delivery-menu-icon">{currentRoleConfig.iconByRoute[link.to] || "."}</span>
                <span>{link.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="delivery-sidebar-user">
            <strong>{user?.name || "Workspace User"}</strong>
            <span>{user?.email || "No email"}</span>
          </div>
        </aside>

        <div className="delivery-main">
          <header className="delivery-topbar">
            <h1>Workspace</h1>

            <form className="delivery-search-form" onSubmit={currentRoleConfig.onSearchSubmit}>
              <input
                className="delivery-search-input"
                onChange={(event) => currentRoleConfig.onSearchChange(event.target.value)}
                placeholder={currentRoleConfig.searchPlaceholder}
                value={currentRoleConfig.searchValue}
              />
            </form>

            <div className="delivery-topbar-user">
              <div>
                <strong>{user?.name || "Workspace User"}</strong>
                <span>{currentRoleConfig.subtitle}</span>
              </div>
              <button className="delivery-logout" onClick={logout} type="button">
                Logout
              </button>
            </div>
          </header>

          <main className="delivery-workspace">{children}</main>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell elite-shell">
      <header className="elite-topbar">
        <div className="elite-brand-zone">
          <Link className="elite-logo" to={roleHome}>
            <span className="elite-logo-mark">S</span>
            <span className="elite-logo-word">ELITE SPORTS</span>
          </Link>
        </div>

        <div className="elite-search-form">
          <input className="elite-search-input" readOnly value={roleLabel} />
        </div>

        <div className="elite-quick-tools">
          {links.slice(0, 2).map((link) => (
            <NavLink className="elite-icon-pill" key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
          <span className="elite-avatar-pill">{user?.role || "role"}</span>
          <button className="elite-header-logout-btn" onClick={logout} type="button">
            Logout
          </button>
        </div>
      </header>

      <main className="elite-workspace">
        <div className="elite-account-layout">
          <aside className="elite-account-sidebar">
            <div className="elite-account-sidebar-brand">
              <div className="elite-logo">
                <span className="elite-logo-mark">S</span>
                <span className="elite-logo-word">Elite Sports</span>
              </div>
              <p>{roleLabel}</p>
            </div>

            <nav className="elite-account-sidebar-nav">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  className={({ isActive }) => `elite-account-menu-item${isActive ? " active" : ""}`}
                  to={link.to}
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>

            <div className="elite-account-sidebar-user">
              <strong>{user?.name || "User"}</strong>
              <span>{user?.email || "No email"}</span>
              <button onClick={logout} type="button">
                Logout
              </button>
            </div>
          </aside>

          <div className="elite-account-content">{children}</div>
        </div>
      </main>
    </div>
  );
}
