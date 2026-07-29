import { Navigate, Route, Routes } from "react-router-dom";

import LoginPage from "./auth/LoginPage";
import RegisterPage from "./auth/RegisterPage";
import { useAuth } from "./auth/AuthContext";
import AppShell from "./components/AppShell";
import RoleGuard from "./components/RoleGuard";
import AdminDashboardPage from "./workspaces/admin/AdminDashboardPage";
import AdminModerationPage from "./workspaces/admin/AdminModerationPage";
import AdminOperationsPage from "./workspaces/admin/AdminOperationsPage";
import AdminSettlementCenterPage from "./workspaces/admin/AdminSettlementCenterPage";
import AdminUsersPage from "./workspaces/admin/AdminUsersPage";
import CustomerCartPage from "./workspaces/customer/CustomerCartPage";
import CustomerFavoritesPage from "./workspaces/customer/CustomerFavoritesPage";
import CustomerHomePage from "./workspaces/customer/CustomerHomePage";
import CustomerOrdersPage from "./workspaces/customer/CustomerOrdersPage";
import CustomerPaymentPage from "./workspaces/customer/CustomerPaymentPage";
import CustomerProductDetailPage from "./workspaces/customer/CustomerProductDetailPage";
import CustomerProductsPage from "./workspaces/customer/CustomerProductsPage";
import CustomerProfilePage from "./workspaces/customer/CustomerProfilePage";
import LogisticsDashboardPage from "./workspaces/logistics/LogisticsDashboardPage";
import LogisticsDeliveryBoysPage from "./workspaces/logistics/LogisticsDeliveryBoysPage";
import LogisticsEarningsPage from "./workspaces/logistics/LogisticsEarningsPage";
import LogisticsPayoutsPage from "./workspaces/logistics/LogisticsPayoutsPage";
import LogisticsShipmentsPage from "./workspaces/logistics/LogisticsShipmentsPage";
import DeliveryDashboardPage from "./workspaces/delivery/DeliveryDashboardPage";
import DeliveryEarnedPage from "./workspaces/delivery/DeliveryEarnedPage";
import DeliveryPayoutsPage from "./workspaces/delivery/DeliveryPayoutsPage";
import DeliveryShipmentDetailPage from "./workspaces/delivery/DeliveryShipmentDetailPage";
import DeliveryShipmentsPage from "./workspaces/delivery/DeliveryShipmentsPage";
import VendorDashboardPage from "./workspaces/vendor/VendorDashboardPage";
import VendorEarningsPage from "./workspaces/vendor/VendorEarningsPage";
import VendorOrdersPage from "./workspaces/vendor/VendorOrdersPage";
import VendorPayoutsPage from "./workspaces/vendor/VendorPayoutsPage";
import VendorProductsPage from "./workspaces/vendor/VendorProductsPage";

function Protected({ allow, children }) {
  return (
    <RoleGuard allow={allow}>
      <AppShell>{children}</AppShell>
    </RoleGuard>
  );
}

function HomeRedirect() {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const home = {
    customer: "/customer/home",
    vendor: "/vendor/dashboard",
    logistics: "/logistics/dashboard",
    delivery_boy: "/delivery/dashboard",
    admin: "/admin/dashboard",
  };
  return <Navigate to={home[user.role] || "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/customer/home"
        element={
          <Protected allow={["customer"]}>
            <CustomerHomePage />
          </Protected>
        }
      />
      <Route
        path="/customer/products"
        element={
          <Protected allow={["customer"]}>
            <CustomerProductsPage />
          </Protected>
        }
      />
      <Route
        path="/customer/products/:id"
        element={
          <Protected allow={["customer"]}>
            <CustomerProductDetailPage />
          </Protected>
        }
      />
      <Route
        path="/customer/cart"
        element={
          <Protected allow={["customer"]}>
            <CustomerCartPage />
          </Protected>
        }
      />
      <Route
        path="/customer/favorites"
        element={
          <Protected allow={["customer"]}>
            <CustomerFavoritesPage />
          </Protected>
        }
      />
      <Route
        path="/customer/payment"
        element={
          <Protected allow={["customer"]}>
            <CustomerPaymentPage />
          </Protected>
        }
      />
      <Route
        path="/customer/orders"
        element={
          <Protected allow={["customer"]}>
            <CustomerOrdersPage />
          </Protected>
        }
      />
      <Route
        path="/customer/profile"
        element={
          <Protected allow={["customer"]}>
            <CustomerProfilePage />
          </Protected>
        }
      />

      <Route
        path="/vendor/dashboard"
        element={
          <Protected allow={["vendor"]}>
            <VendorDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/vendor/products"
        element={
          <Protected allow={["vendor"]}>
            <VendorProductsPage />
          </Protected>
        }
      />
      <Route
        path="/vendor/orders"
        element={
          <Protected allow={["vendor"]}>
            <VendorOrdersPage />
          </Protected>
        }
      />
      <Route
        path="/vendor/earnings"
        element={
          <Protected allow={["vendor"]}>
            <VendorEarningsPage />
          </Protected>
        }
      />
      <Route
        path="/vendor/payouts"
        element={
          <Protected allow={["vendor"]}>
            <VendorPayoutsPage />
          </Protected>
        }
      />

      <Route
        path="/logistics/dashboard"
        element={
          <Protected allow={["logistics", "admin"]}>
            <LogisticsDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/logistics/shipments"
        element={
          <Protected allow={["logistics", "admin"]}>
            <LogisticsShipmentsPage />
          </Protected>
        }
      />
      <Route
        path="/logistics/delivery-boys"
        element={
          <Protected allow={["logistics", "admin"]}>
            <LogisticsDeliveryBoysPage />
          </Protected>
        }
      />
      <Route
        path="/logistics/earnings"
        element={
          <Protected allow={["logistics", "admin"]}>
            <LogisticsEarningsPage />
          </Protected>
        }
      />
      <Route
        path="/logistics/payouts"
        element={
          <Protected allow={["logistics", "admin"]}>
            <LogisticsPayoutsPage />
          </Protected>
        }
      />

      <Route
        path="/delivery/dashboard"
        element={
          <Protected allow={["delivery_boy"]}>
            <DeliveryDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/delivery/shipments"
        element={
          <Protected allow={["delivery_boy"]}>
            <DeliveryShipmentsPage />
          </Protected>
        }
      />
      <Route
        path="/delivery/earned"
        element={
          <Protected allow={["delivery_boy"]}>
            <DeliveryEarnedPage />
          </Protected>
        }
      />
      <Route
        path="/delivery/payouts"
        element={
          <Protected allow={["delivery_boy"]}>
            <DeliveryPayoutsPage />
          </Protected>
        }
      />
      <Route
        path="/delivery/shipments/:id"
        element={
          <Protected allow={["delivery_boy"]}>
            <DeliveryShipmentDetailPage />
          </Protected>
        }
      />

      <Route
        path="/admin/dashboard"
        element={
          <Protected allow={["admin"]}>
            <AdminDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/admin/users"
        element={
          <Protected allow={["admin"]}>
            <AdminUsersPage />
          </Protected>
        }
      />
      <Route
        path="/admin/moderation"
        element={
          <Protected allow={["admin"]}>
            <AdminModerationPage />
          </Protected>
        }
      />
      <Route
        path="/admin/operations"
        element={
          <Protected allow={["admin"]}>
            <AdminOperationsPage />
          </Protected>
        }
      />
      <Route
        path="/admin/settlements"
        element={
          <Protected allow={["admin"]}>
            <AdminSettlementCenterPage />
          </Protected>
        }
      />

      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
