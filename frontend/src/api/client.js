const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

function normalizeToken(token) {
  if (typeof token !== "string") {
    return null;
  }
  const trimmed = token.trim();
  if (!trimmed || trimmed === "undefined" || trimmed === "null") {
    return null;
  }
  return trimmed;
}

function isJwtLikeToken(token) {
  const normalized = normalizeToken(token);
  if (!normalized) {
    return false;
  }
  return normalized.split(".").length === 3;
}

function clearAuthStateAndRedirect() {
  try {
    localStorage.removeItem("market_auth_state");
  } catch {
    // ignore storage errors
  }
  window.location.assign("/login");
}

function isJwtResponseError(response, payload) {
  if (response.status !== 422) {
    return false;
  }
  const message = String(payload?.msg || payload?.error || payload?.message || "").toLowerCase();
  return (
    message.includes("authorization") ||
    message.includes("token") ||
    message.includes("segments") ||
    message.includes("signature") ||
    message.includes("header")
  );
}

async function request(path, { method = "GET", body, token, headers = {} } = {}) {
  const hasBody = body !== undefined && body !== null;
  const authToken = isJwtLikeToken(token) ? normalizeToken(token) : null;
  const requestHeaders = {
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...headers,
  };

  const hasExplicitContentType =
    Object.prototype.hasOwnProperty.call(requestHeaders, "Content-Type") ||
    Object.prototype.hasOwnProperty.call(requestHeaders, "content-type");

  if (hasBody && !hasExplicitContentType) {
    requestHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: requestHeaders,
    body: hasBody ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (response.status === 401) {
    clearAuthStateAndRedirect();
    const message = payload?.error || payload?.message || "Unauthorized. Redirecting to login.";
    throw new Error(message);
  }

  if (isJwtResponseError(response, payload)) {
    clearAuthStateAndRedirect();
    const message = payload?.msg || payload?.error || payload?.message || "Session is invalid. Redirecting to login.";
    throw new Error(message);
  }

  if (!response.ok) {
    const message = payload?.error || payload?.message || payload?.msg || `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

export const apiClient = {
  register: (data) => request("/auth/register", { method: "POST", body: data }),
  login: (data) => request("/auth/login", { method: "POST", body: data }),
  refresh: (refreshToken) => request("/auth/refresh", { method: "POST", token: refreshToken }),
  logout: (token) => request("/auth/logout", { method: "POST", token }),

  listProducts: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/products${query ? `?${query}` : ""}`);
  },
  getProduct: (id) => request(`/products/${id}`),
  listCategories: () => request("/categories"),

  listCart: (token) => request("/cart/items", { token }),
  addToCart: (token, body) => request("/cart/items", { method: "POST", token, body }),
  updateCartItem: (token, id, body) => request(`/cart/items/${id}`, { method: "PATCH", token, body }),
  deleteCartItem: (token, id) => request(`/cart/items/${id}`, { method: "DELETE", token }),

  listWishlist: (token) => request("/wishlist/items", { token }),
  addToWishlist: (token, body) => request("/wishlist/items", { method: "POST", token, body }),
  deleteWishlistItem: (token, id) => request(`/wishlist/items/${id}`, { method: "DELETE", token }),

  listAddresses: (token) => request("/addresses", { token }),
  createAddress: (token, body) => request("/addresses", { method: "POST", token, body }),
  getPaymentCard: (token) => request("/payment-card", { token }),
  savePaymentCard: (token, body) => request("/payment-card", { method: "PUT", token, body }),

  createOrder: (token, body) => request("/orders", { method: "POST", token, body }),
  listOrders: (token) => request("/orders", { token }),
  getOrder: (token, id) => request(`/orders/${id}`, { token }),
  cancelOrder: (token, id) => request(`/orders/${id}/cancel`, { method: "POST", token }),

  createVendorProduct: (token, body) => request("/vendor/products", { method: "POST", token, body }),
  listVendorProducts: (token) => request("/vendor/products", { token }),
  updateVendorProduct: (token, id, body) => request(`/vendor/products/${id}`, { method: "PATCH", token, body }),
  listVendorOrders: (token) => request("/vendor/orders", { token }),
  updateVendorOrderStatus: (token, id, body) => request(`/vendor/orders/${id}/status`, { method: "PATCH", token, body }),

  listShipments: (token, params) => {
    const query = new URLSearchParams(params || {}).toString();
    return request(`/logistics/shipments${query ? `?${query}` : ""}`, { token });
  },
  getLogisticsDashboard: (token) => request("/logistics/dashboard", { token }),
  assignDeliveryBoy: (token, shipmentId, body) =>
    request(`/logistics/shipments/${shipmentId}/assign`, { method: "PATCH", token, body }),
  listDeliveryBoys: (token) => request("/logistics/delivery-boys", { token }),
  updateDeliveryBoyStatus: (token, profileId, body) =>
    request(`/logistics/delivery-boys/${profileId}`, { method: "PATCH", token, body }),

  updateShipmentStatus: (token, id, body) => request(`/logistics/shipments/${id}/status`, { method: "PATCH", token, body }),

  listMyDeliveries: (token, params) => {
    const query = new URLSearchParams(params || {}).toString();
    return request(`/delivery/shipments${query ? `?${query}` : ""}`, { token });
  },
  getMyDelivery: (token, id) => request(`/delivery/shipments/${id}`, { token }),
  getDeliveryDashboard: (token) => request("/delivery/dashboard", { token }),
  updateDeliveryStatus: (token, shipmentId, body) =>
    request(`/delivery/shipments/${shipmentId}/status`, { method: "PATCH", token, body }),
  confirmDelivery: (token, shipmentId, body) =>
    request(`/delivery/shipments/${shipmentId}/confirm`, { method: "POST", token, body }),

  getFinanceSummary: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/me/summary${query ? `?${query}` : ""}`, { token });
  },
  getFinanceLedger: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/me/ledger${query ? `?${query}` : ""}`, { token });
  },
  getFinancePayouts: (token) => request("/finance/me/payouts", { token }),

  adminFinanceOverview: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/admin/overview${query ? `?${query}` : ""}`, { token });
  },
  adminFinanceActors: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/admin/actors${query ? `?${query}` : ""}`, { token });
  },
  adminFinancePayouts: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/admin/payouts${query ? `?${query}` : ""}`, { token });
  },
  createAdminPayout: (token, body) => request("/finance/admin/payouts", { method: "POST", token, body }),
  approveAdminPayout: (token, payoutId) =>
    request(`/finance/admin/payouts/${payoutId}/approve`, { method: "PATCH", token }),
  markAdminPayoutPaid: (token, payoutId, body) =>
    request(`/finance/admin/payouts/${payoutId}/mark-paid`, { method: "PATCH", token, body }),
  adminFinanceAdjustments: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/finance/admin/adjustments${query ? `?${query}` : ""}`, { token });
  },
  createAdminAdjustment: (token, body) => request("/finance/admin/adjustments", { method: "POST", token, body }),

  listUsers: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/admin/users${query ? `?${query}` : ""}`, { token });
  },
  setUserStatus: (token, id, body) => request(`/admin/users/${id}/status`, { method: "PATCH", token, body }),
  approveVendor: (token, id) => request(`/admin/vendors/${id}/approve`, { method: "PATCH", token }),
  approveProduct: (token, id, body = { approved: true }) =>
    request(`/admin/products/${id}/approve`, { method: "PATCH", token, body }),
  salesReport: (token) => request("/admin/reports/sales", { token }),
  adminOperationsReport: (token, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/admin/reports/operations${query ? `?${query}` : ""}`, { token });
  },
  listVendors: () => request("/vendors"),
};
