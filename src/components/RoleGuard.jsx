import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function RoleGuard({ allow, children }) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!allow.includes(user.role)) {
    const roleHome = {
      customer: "/customer/home",
      vendor: "/vendor/dashboard",
      logistics: "/logistics/dashboard",
      delivery_boy: "/delivery/dashboard",
      admin: "/admin/dashboard",
    };
    return <Navigate to={roleHome[user.role] || "/login"} replace />;
  }

  return children;
}
