import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import CustomerEmptyState from "./components/CustomerEmptyState";

const FALLBACK_IMAGE = "https://dummyimage.com/600x420/e6eaee/1a2336&text=Elite+Order";

const STATUS_META = {
  pending: { label: "Processing", group: "processing", tone: "processing" },
  confirmed: { label: "Processing", group: "processing", tone: "processing" },
  packed: { label: "Processing", group: "processing", tone: "processing" },
  shipped: { label: "Shipped", group: "shipped", tone: "shipped" },
  delivered: { label: "Delivered", group: "delivered", tone: "delivered" },
  cancelled: { label: "Cancelled", group: "cancelled", tone: "cancelled" },
  returned: { label: "Cancelled", group: "cancelled", tone: "cancelled" },
};

const PROCESSING_STEPS = [
  { id: "pending", title: "Order placed", note: "Your order has been created." },
  { id: "confirmed", title: "Order confirmed", note: "Payment mode verified and order accepted." },
  { id: "packed", title: "Packed", note: "Items are packed and ready for dispatch." },
  { id: "shipped", title: "Shipped", note: "Package handed over to logistics." },
  { id: "delivered", title: "Delivered", note: "Order delivered successfully." },
];

const DELIVERY_STEPS = [
  { id: "pickup_requested", title: "Pickup requested" },
  { id: "picked", title: "Picked" },
  { id: "in_transit", title: "In transit" },
  { id: "out_for_delivery", title: "Out for delivery" },
  { id: "delivered", title: "Delivered" },
];

const TABS = [
  { id: "all", label: "All Orders" },
  { id: "processing", label: "Processing" },
  { id: "shipped", label: "Shipped" },
  { id: "delivered", label: "Delivered" },
  { id: "cancelled", label: "Cancelled" },
];
const ORDER_MODAL_TYPES = new Set(["details", "invoice", "processing", "delivery"]);

function getStatusMeta(status) {
  return STATUS_META[status] || { label: "Processing", group: "processing", tone: "processing" };
}

function formatDate(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Recent";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(parsed);
}

function formatDateTime(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function formatPaymentMethod(method) {
  if (!method) return "N/A";
  return method.toUpperCase();
}

function formatAddress(address) {
  if (!address) return "Address unavailable";
  return [
    address.full_name,
    address.phone,
    address.address_line_1,
    address.address_line_2,
    `${address.city}, ${address.state} ${address.postal_code}`,
    address.country,
  ]
    .filter(Boolean)
    .join(" | ");
}

function getProcessingStepIndex(orderStatus) {
  const index = PROCESSING_STEPS.findIndex((step) => step.id === orderStatus);
  return index === -1 ? 0 : index;
}

function getDeliveryStepIndex(order) {
  const shipmentStatus = order?.shipment?.shipment_status;
  const index = DELIVERY_STEPS.findIndex((step) => step.id === shipmentStatus);
  if (index !== -1) return index;
  if (order?.order_status === "delivered") return DELIVERY_STEPS.length - 1;
  if (order?.order_status === "shipped") return 2;
  return 0;
}

function OrderModal({ modal, onClose }) {
  if (!modal) return null;

  const { type, order } = modal;
  const status = getStatusMeta(order.order_status);
  const itemText = (order.items || [])
    .map((item) => item.product_name || `Product ${item.product_id}`)
    .join(", ");
  const itemSubtotal = (order.items || []).reduce((sum, item) => sum + Number(item.subtotal || 0), 0);
  const payments =
    order.payments && order.payments.length > 0
      ? order.payments
      : [
          {
            id: "summary",
            payment_method: "cod",
            payment_status: order.payment_status,
            transaction_id: null,
            amount: order.total_amount,
            created_at: order.created_at,
          },
        ];

  const modalTitle =
    type === "invoice"
      ? `Invoices - Order #ES-${String(order.id).padStart(5, "0")}`
      : type === "processing"
        ? `Processing Details - Order #ES-${String(order.id).padStart(5, "0")}`
        : type === "delivery"
          ? `Delivery Details - Order #ES-${String(order.id).padStart(5, "0")}`
          : `Order Details - Order #ES-${String(order.id).padStart(5, "0")}`;

  const shipmentStatus = order.shipment?.shipment_status;
  const showOtp = shipmentStatus === "out_for_delivery";
  const otpText = showOtp
    ? order.shipment?.otp_code || "Not available"
    : shipmentStatus === "delivered"
      ? "OTP verified"
      : "Available when out for delivery";

  const renderDetails = () => (
    <>
      <div className="elite-order-modal-summary">
        <div>
          <span>Status</span>
          <strong>{status.label}</strong>
        </div>
        <div>
          <span>Created</span>
          <strong>{formatDateTime(order.created_at)}</strong>
        </div>
        <div>
          <span>Total</span>
          <strong>{formatCurrency(order.total_amount)}</strong>
        </div>
        <div>
          <span>Payment</span>
          <strong>{String(order.payment_status || "N/A").replaceAll("_", " ")}</strong>
        </div>
      </div>

      <div className="elite-order-modal-section">
        <h4>Products</h4>
        <ul className="elite-order-modal-list">
          {(order.items || []).map((item) => (
            <li key={item.id || `${item.product_id}-${item.quantity}`}>
              <div>
                <strong>{item.product_name || `Product ${item.product_id}`}</strong>
                <span>
                  Qty {item.quantity} x {formatCurrency(item.price)}
                </span>
              </div>
              <strong>{formatCurrency(item.subtotal)}</strong>
            </li>
          ))}
        </ul>
      </div>

      <div className="elite-order-modal-section">
        <h4>Shipping Address</h4>
        <p>{formatAddress(order.shipping_address)}</p>
      </div>

      <div className="elite-order-modal-section">
        <h4>Shipment</h4>
        {order.shipment ? (
          <div className="elite-order-modal-grid">
            <div>
              <span>Tracking</span>
              <strong>{order.shipment.tracking_number || "N/A"}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{String(order.shipment.shipment_status || "N/A").replaceAll("_", " ")}</strong>
            </div>
            <div>
              <span>OTP</span>
              <strong>{otpText}</strong>
            </div>
          </div>
        ) : (
          <p>Shipment details are not available yet.</p>
        )}
      </div>
    </>
  );

  const renderInvoice = () => (
    <>
      <div className="elite-order-modal-section">
        <h4>Payment Invoices</h4>
        <ul className="elite-order-modal-list">
          {payments.map((payment) => (
            <li key={payment.id}>
              <div>
                <strong>
                  {formatPaymentMethod(payment.payment_method)} - {String(payment.payment_status || "N/A").replaceAll("_", " ")}
                </strong>
                <span>{formatDateTime(payment.created_at)}</span>
                <span>Txn: {payment.transaction_id || "Not generated"}</span>
              </div>
              <strong>{formatCurrency(payment.amount)}</strong>
            </li>
          ))}
        </ul>
      </div>

      <div className="elite-order-modal-section">
        <h4>Invoice Items</h4>
        <ul className="elite-order-modal-list">
          {(order.items || []).map((item) => (
            <li key={item.id || `${item.product_id}-${item.quantity}`}>
              <div>
                <strong>{item.product_name || `Product ${item.product_id}`}</strong>
                <span>
                  {item.quantity} x {formatCurrency(item.price)}
                </span>
              </div>
              <strong>{formatCurrency(item.subtotal)}</strong>
            </li>
          ))}
          <li>
            <div>
              <strong>Subtotal</strong>
            </div>
            <strong>{formatCurrency(itemSubtotal)}</strong>
          </li>
          <li>
            <div>
              <strong>Total</strong>
            </div>
            <strong>{formatCurrency(order.total_amount)}</strong>
          </li>
        </ul>
      </div>
    </>
  );

  const renderProcessing = () => {
    const currentIndex = getProcessingStepIndex(order.order_status);

    return (
      <>
        <div className="elite-order-modal-section">
          <h4>Items In Processing</h4>
          <p>{itemText || "No items found"}</p>
        </div>

        <div className="elite-order-modal-section">
          <h4>Processing Timeline</h4>
          <ul className="elite-order-modal-timeline">
            {PROCESSING_STEPS.map((step, index) => {
              const state = index < currentIndex ? "done" : index === currentIndex ? "active" : "pending";
              return (
                <li className={state} key={step.id}>
                  <strong>{step.title}</strong>
                  <span>{step.note}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="elite-order-modal-section">
          <h4>Current Note</h4>
          <p>
            {order.order_status === "cancelled"
              ? "This order has been cancelled."
              : order.order_status === "delivered"
                ? "Order completed and delivered."
                : "Order is being prepared for next shipping stage."}
          </p>
        </div>
      </>
    );
  };

  const renderDelivery = () => {
    const currentIndex = getDeliveryStepIndex(order);

    return (
      <>
        <div className="elite-order-modal-grid">
          <div>
            <span>Tracking Number</span>
            <strong>{order.shipment?.tracking_number || "Not assigned"}</strong>
          </div>
          <div>
            <span>Shipment Status</span>
            <strong>{String(order.shipment?.shipment_status || "pending").replaceAll("_", " ")}</strong>
          </div>
          <div>
            <span>Updated</span>
            <strong>{formatDateTime(order.shipment?.updated_at || order.created_at)}</strong>
          </div>
        </div>

        <div className="elite-order-modal-section">
          <h4>Delivery Timeline</h4>
          <ul className="elite-order-modal-timeline">
            {DELIVERY_STEPS.map((step, index) => {
              const state = index < currentIndex ? "done" : index === currentIndex ? "active" : "pending";
              return (
                <li className={state} key={step.id}>
                  <strong>{step.title}</strong>
                  <span>{index <= currentIndex ? "Completed" : "Pending"}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="elite-order-modal-section">
          <h4>Delivery OTP</h4>
          <p>
            {showOtp
              ? `Share this OTP with delivery partner: ${order.shipment?.otp_code || "Not available"}`
              : shipmentStatus === "delivered"
                ? "Delivery OTP verified successfully."
                : "OTP will be visible once the shipment is out for delivery."}
          </p>
        </div>

        <div className="elite-order-modal-section">
          <h4>Delivery Address</h4>
          <p>{formatAddress(order.shipping_address)}</p>
        </div>
      </>
    );
  };

  return (
    <div className="elite-order-modal-backdrop" onClick={onClose} role="presentation">
      <section
        aria-labelledby="elite-order-modal-title"
        aria-modal="true"
        className="elite-order-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="elite-order-modal-header">
          <h3 id="elite-order-modal-title">{modalTitle}</h3>
          <button onClick={onClose} type="button">
            Close
          </button>
        </header>

        <div className="elite-order-modal-body">
          {type === "invoice" && renderInvoice()}
          {type === "processing" && renderProcessing()}
          {type === "delivery" && renderDelivery()}
          {type === "details" && renderDetails()}
        </div>
      </section>
    </div>
  );
}

export default function CustomerOrdersPage() {
  const { accessToken } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const [actionBusy, setActionBusy] = useState({});
  const [activeModal, setActiveModal] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await apiClient.listOrders(accessToken);
      const firstProductIds = [...new Set((rows || []).map((row) => row.items?.[0]?.product_id).filter(Boolean))];
      const imageMap = {};

      await Promise.all(
        firstProductIds.map(async (productId) => {
          try {
            const product = await apiClient.getProduct(productId);
            imageMap[productId] = product.thumbnail || FALLBACK_IMAGE;
          } catch {
            imageMap[productId] = FALLBACK_IMAGE;
          }
        })
      );

      const decorated = (rows || []).map((row) => ({
        ...row,
        previewImage: imageMap[row.items?.[0]?.product_id] || FALLBACK_IMAGE,
      }));

      setOrders(decorated);
    } catch (err) {
      setError(err.message);
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const paymentNotice = location.state?.paymentNotice;
    if (!paymentNotice) return;

    setNotice(paymentNotice);
    setActiveModal(null);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (!activeModal) return undefined;
    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setActiveModal(null);
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [activeModal]);

  useEffect(() => {
    if (!activeModal?.order?.id) return;
    const orderExists = orders.some((row) => row.id === activeModal.order.id);
    if (!orderExists) {
      setActiveModal(null);
    }
  }, [activeModal, orders]);

  const filteredOrders = useMemo(() => {
    const q = query.trim().toLowerCase();
    return orders.filter((order) => {
      const status = getStatusMeta(order.order_status);
      if (activeTab !== "all" && status.group !== activeTab) {
        return false;
      }
      if (!q) return true;

      const names = (order.items || []).map((item) => item.product_name || `Product ${item.product_id}`).join(" ").toLowerCase();
      const orderCode = `es-${String(order.id).padStart(5, "0")}`;
      return orderCode.includes(q) || status.label.toLowerCase().includes(q) || names.includes(q);
    });
  }, [orders, activeTab, query]);

  const handleCancel = async (orderId) => {
    setActionBusy((old) => ({ ...old, [orderId]: true }));
    setError("");
    setNotice("");
    try {
      await apiClient.cancelOrder(accessToken, orderId);
      setNotice(`Order #ES-${String(orderId).padStart(5, "0")} cancelled.`);
      setActiveModal(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionBusy((old) => ({ ...old, [orderId]: false }));
    }
  };

  const openModal = (type, order) => {
    if (!order?.id || !ORDER_MODAL_TYPES.has(type)) {
      return;
    }
    setNotice("");
    setActiveModal({ type, order });
  };

  const visibleModal = useMemo(() => {
    if (!activeModal?.order?.id) return null;
    if (!ORDER_MODAL_TYPES.has(activeModal.type)) return null;
    return activeModal;
  }, [activeModal]);

  const showEmptyState = !loading && !error && filteredOrders.length === 0;
  const noOrdersExist = orders.length === 0;

  return (
    <>
      <div className="elite-account-content elite-order-main">
        <div className="elite-order-main-top">
          <label>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search orders, items, or status..."
              value={query}
            />
          </label>
        </div>

        <section className="elite-order-hero">
          <h2>Order History</h2>
          <p>Manage and track your premium sports equipment purchases.</p>
        </section>

        <section className="elite-order-tabs">
          {TABS.map((tab) => (
            <button
              className={activeTab === tab.id ? "active" : ""}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </section>

        {loading && <p className="elite-muted">Loading orders...</p>}
        {error && <p className="elite-error">{error}</p>}
        {notice && <p className="elite-notice">{notice}</p>}

        {showEmptyState ? (
          <CustomerEmptyState
            actionLabel={noOrdersExist ? "Continue Shopping" : "Clear Filters"}
            actionTo={noOrdersExist ? "/customer/products" : undefined}
            description={
              noOrdersExist
                ? "Looks like you have not placed any orders yet. Start shopping and your order history will appear here."
                : "No orders match the current filter. Clear filters to view all your orders."
            }
            icon="orders"
            onAction={
              noOrdersExist
                ? undefined
                : () => {
                    setQuery("");
                    setActiveTab("all");
                  }
            }
            title={noOrdersExist ? "No orders yet" : "No orders found"}
          />
        ) : (
          <section className="elite-order-list">
            {filteredOrders.map((order) => {
              const status = getStatusMeta(order.order_status);
              const itemCount = (order.items || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0);
              const itemText = (order.items || [])
                .map((item) => item.product_name || `Product ${item.product_id}`)
                .join(", ");
              const canCancel = ["pending", "confirmed"].includes(order.order_status);
              const busy = Boolean(actionBusy[order.id]);

              const primaryAction =
                status.group === "delivered" || status.group === "cancelled"
                  ? { label: "View Details", modalType: "details" }
                  : status.group === "shipped"
                    ? { label: "View Delivery", modalType: "delivery" }
                    : { label: "View Processing", modalType: "processing" };

              return (
                <article className="elite-order-card" key={order.id}>
                  <img alt={`Order ${order.id}`} src={order.previewImage || FALLBACK_IMAGE} />

                  <div className="elite-order-card-content">
                    <div className="elite-order-card-head">
                      <div>
                        <div className="elite-order-card-meta">
                          <span className={`elite-order-status ${status.tone}`}>{status.label}</span>
                          <span>{formatDate(order.created_at)}</span>
                        </div>
                        <h3>Order #ES-{String(order.id).padStart(5, "0")}</h3>
                        <p>{itemText || "Order items unavailable"}</p>
                      </div>

                      <div className="elite-order-amount">
                        <strong>{formatCurrency(order.total_amount)}</strong>
                        <span>{itemCount} items</span>
                      </div>
                    </div>

                    <div className="elite-order-card-footer">
                      <p>
                        {status.group === "delivered"
                          ? "Delivered successfully"
                          : status.group === "cancelled"
                            ? "Order status updated"
                            : status.group === "shipped"
                              ? "Expected delivery in 2-4 days"
                              : "Preparing for dispatch"}
                      </p>

                      <div className="elite-order-card-actions">
                        <button
                          className="elite-order-primary-action"
                          onClick={() => openModal(primaryAction.modalType, order)}
                          type="button"
                        >
                          {primaryAction.label}
                        </button>

                        {canCancel ? (
                          <button className="elite-order-secondary-action" disabled={busy} onClick={() => handleCancel(order.id)} type="button">
                            {busy ? "Cancelling..." : "Cancel"}
                          </button>
                        ) : (
                          <button className="elite-order-secondary-action" onClick={() => openModal("invoice", order)} type="button">
                            Invoices
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>

      <OrderModal modal={visibleModal} onClose={() => setActiveModal(null)} />
    </>
  );
}
