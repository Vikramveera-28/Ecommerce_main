import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const STATUS_OPTIONS = ["picked", "in_transit", "out_for_delivery", "failed"];

export default function DeliveryShipmentDetailPage() {
  const { id } = useParams();
  const { accessToken } = useAuth();
  const [shipment, setShipment] = useState(null);
  const [error, setError] = useState("");
  const [otp, setOtp] = useState("");
  const [proofUrl, setProofUrl] = useState("");

  const load = async () => {
    const data = await apiClient.getMyDelivery(accessToken, id);
    setShipment(data);
  };

  useEffect(() => {
    load().catch((err) => alert(err.message));
  }, [id]);

  const updateStatus = async (status) => {
    setError("");
    const payload = { status };
    if (status === "failed") {
      const reason = window.prompt("Failure reason (optional)");
      if (reason !== null) payload.failure_reason = reason;
    }
    try {
      await apiClient.updateDeliveryStatus(accessToken, id, payload);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const confirmDelivery = async (e) => {
    e.preventDefault();
    setError("");
    if (!otp.trim()) {
      setError("Enter OTP");
      return;
    }
    try {
      const body = { otp: otp.trim() };
      if (proofUrl.trim()) body.proof_of_delivery_url = proofUrl.trim();
      await apiClient.confirmDelivery(accessToken, id, body);
      setOtp("");
      setProofUrl("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!shipment) {
    return <p>Loading...</p>;
  }

  const isDelivered = shipment.shipment_status === "delivered";
  const canConfirm = shipment.shipment_status === "out_for_delivery";

  return (
    <section className="panel stack">
      <div className="panel-header row">
        <Link to="/delivery/shipments" className="muted">&lt;- My Deliveries</Link>
      </div>
      <div className="panel-header">
        <h2>{shipment.tracking_number || `Shipment ${shipment.id}`}</h2>
        <span className="chip">{shipment.shipment_status}</span>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="stack" style={{ gap: "1rem" }}>
        <div>
          <h3>Order &amp; Customer</h3>
          <p><strong>Order #</strong> {shipment.order_id}</p>
          <p><strong>Customer</strong> {shipment.customer_name || "-"}</p>
          <p><strong>Phone</strong>{" "}
            {shipment.customer_phone ? (
              <a href={`tel:${shipment.customer_phone}`}>{shipment.customer_phone}</a>
            ) : (
              "-"
            )}
          </p>
          {shipment.customer_address && (
            <p>
              <strong>Address</strong> {shipment.customer_address}
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(shipment.customer_address)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="button small"
                style={{ marginLeft: "0.5rem" }}
              >
                Navigate
              </a>
            </p>
          )}
        </div>

        <div>
          <h3>Update status</h3>
          {isDelivered ? (
            <p className="muted">Shipment is finalized. No further status updates are allowed.</p>
          ) : (
            <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
              {STATUS_OPTIONS.map((status) => (
                <button
                  key={status}
                  className="button small"
                  onClick={() => updateStatus(status)}
                  type="button"
                >
                  Mark {status.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>

        {canConfirm && (
          <div className="panel">
            <h3>Confirm delivery (OTP)</h3>
            <form onSubmit={confirmDelivery} className="stack" style={{ gap: "0.75rem", maxWidth: "20rem" }}>
              <label>
                <span>OTP from customer</span>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  placeholder="e.g. 123456"
                  maxLength={6}
                />
              </label>
              <label>
                <span>Proof of delivery URL (optional)</span>
                <input
                  type="url"
                  value={proofUrl}
                  onChange={(e) => setProofUrl(e.target.value)}
                  placeholder="https://..."
                />
              </label>
              <button type="submit" className="button">
                Confirm delivery
              </button>
            </form>
          </div>
        )}

        {shipment.shipment_status === "delivered" && shipment.delivery_time && (
          <p className="muted">Delivered at {new Date(shipment.delivery_time).toLocaleString()}</p>
        )}
        {shipment.failure_reason && (
          <p className="muted">Failure reason: {shipment.failure_reason}</p>
        )}
      </div>
    </section>
  );
}
