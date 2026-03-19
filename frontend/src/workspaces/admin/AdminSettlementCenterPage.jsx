import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  FINANCE_RANGE_OPTIONS,
  FinancePayoutTable,
  FinanceSummaryCards,
  financeStatusTone,
  formatFinanceCurrency,
  formatFinanceDate,
} from "../finance/FinanceShared";

const ADMIN_RANGE_OPTIONS = FINANCE_RANGE_OPTIONS.filter((option) => option.value !== "7d").concat({
  value: "90d",
  label: "Last 90 Days",
});

const ROLE_TABS = [
  { value: "vendor", label: "Vendors" },
  { value: "delivery_boy", label: "Delivery Boys" },
  { value: "logistics", label: "Logistics" },
  { value: "platform", label: "Platform" },
];

function dateValue(daysAgo = 0) {
  const current = new Date();
  current.setDate(current.getDate() - daysAgo);
  return current.toISOString().slice(0, 10);
}

export default function AdminSettlementCenterPage() {
  const { accessToken } = useAuth();
  const [range, setRange] = useState("30d");
  const [role, setRole] = useState("vendor");
  const [overview, setOverview] = useState(null);
  const [actors, setActors] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [adjustments, setAdjustments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedActorId, setSelectedActorId] = useState("");
  const [payoutStart, setPayoutStart] = useState(dateValue(30));
  const [payoutEnd, setPayoutEnd] = useState(dateValue(0));
  const [payoutNotes, setPayoutNotes] = useState("");
  const [adjustmentDirection, setAdjustmentDirection] = useState("credit");
  const [adjustmentAmount, setAdjustmentAmount] = useState("");
  const [adjustmentDescription, setAdjustmentDescription] = useState("");
  const [paymentRefs, setPaymentRefs] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const requests = [
        apiClient.adminFinanceOverview(accessToken, { range }),
        apiClient.adminFinancePayouts(accessToken, role === "platform" ? {} : { role }),
        apiClient.adminFinanceAdjustments(accessToken, role === "platform" ? { role } : { role }),
      ];
      if (role !== "platform") {
        requests.push(apiClient.adminFinanceActors(accessToken, { role }));
      }

      const [overviewPayload, payoutRows, adjustmentRows, actorRows] = await Promise.all(requests);
      setOverview(overviewPayload);
      setPayouts(payoutRows || []);
      setAdjustments(adjustmentRows || []);
      setActors(role === "platform" ? [] : actorRows || []);
    } catch (err) {
      setError(err.message);
      setOverview(null);
      setPayouts([]);
      setAdjustments([]);
      setActors([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [accessToken, range, role]);

  useEffect(() => {
    if (role === "platform") {
      setSelectedActorId("");
      return;
    }
    if (!actors.length) {
      setSelectedActorId("");
      return;
    }
    const exists = actors.some((actor) => String(actor.actor_id) === String(selectedActorId));
    if (!exists) {
      setSelectedActorId(String(actors[0].actor_id));
    }
  }, [actors, role, selectedActorId]);

  const currentOverview = (overview?.overview || []).find((row) => row.actor_type === role);
  const cards = [
    {
      label: "Period Net",
      value: formatFinanceCurrency(currentOverview?.period_net || 0),
      highlight: true,
    },
    {
      label: "Available Balance",
      value: formatFinanceCurrency(currentOverview?.eligible_balance || 0),
    },
    {
      label: "Queued In Payout",
      value: formatFinanceCurrency(currentOverview?.in_payout_amount || 0),
    },
    {
      label: "Actor Count",
      value: String(currentOverview?.actor_count || (role === "platform" ? 1 : 0)),
    },
  ];

  const onCreatePayout = async (event) => {
    event.preventDefault();
    if (role === "platform") return;

    setSubmitting(true);
    setError("");
    try {
      await apiClient.createAdminPayout(accessToken, {
        actor_type: role,
        actor_id: selectedActorId,
        period_start: payoutStart,
        period_end: payoutEnd,
        notes: payoutNotes,
      });
      setPayoutNotes("");
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onCreateAdjustment = async (event) => {
    event.preventDefault();

    setSubmitting(true);
    setError("");
    try {
      await apiClient.createAdminAdjustment(accessToken, {
        actor_type: role,
        actor_id: role === "platform" ? null : selectedActorId,
        direction: adjustmentDirection,
        amount: adjustmentAmount,
        description: adjustmentDescription,
      });
      setAdjustmentAmount("");
      setAdjustmentDescription("");
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onApprovePayout = async (payoutId) => {
    setSubmitting(true);
    setError("");
    try {
      await apiClient.approveAdminPayout(accessToken, payoutId);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onMarkPaid = async (payout) => {
    setSubmitting(true);
    setError("");
    try {
      await apiClient.markAdminPayoutPaid(accessToken, payout.id, {
        payment_ref: paymentRefs[payout.id] || payout.payment_ref || `manual-${payout.id}`,
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading settlement center...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head split">
        <div>
          <h2>Settlement Center</h2>
          <p>Monitor balances, create payout batches, and capture finance adjustments for every settlement role.</p>
        </div>
        <label className="delivery-range-filter">
          <span>Range</span>
          <select onChange={(event) => setRange(event.target.value)} value={range}>
            {ADMIN_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      <div className="finance-tab-row">
        {ROLE_TABS.map((tab) => (
          <button
            className={`finance-tab-btn${role === tab.value ? " active" : ""}`}
            key={tab.value}
            onClick={() => setRole(tab.value)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <p className="delivery-error">{error}</p>}
      <FinanceSummaryCards cards={cards} />

      <div className="finance-insight-grid">
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Settlement Workflow</h3>
            <span>{role.replaceAll("_", " ")}</span>
          </div>
          <p className="delivery-note">
            Pending payouts reserve eligible ledger rows. Marking a payout as paid flips those rows to settled and
            preserves the payment reference.
          </p>
        </article>
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Recent Payout Count</h3>
            <span>{payouts.length} rows</span>
          </div>
          <p className="delivery-note">
            Approved: {currentOverview?.payout_counts?.approved || 0} | Pending:{" "}
            {currentOverview?.payout_counts?.pending || 0} | Paid: {currentOverview?.payout_counts?.paid || 0}
          </p>
        </article>
      </div>

      {role !== "platform" ? (
        <>
          <article className="delivery-card">
            <div className="delivery-card-head">
              <h3>Actors and Live Balances</h3>
              <span>{actors.length} actors</span>
            </div>
            <div className="delivery-task-table-wrap">
              <table className="delivery-task-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Available</th>
                    <th>In Payout</th>
                    <th>Settled</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {actors.length === 0 && (
                    <tr>
                      <td className="empty" colSpan={6}>
                        No actors found for this role.
                      </td>
                    </tr>
                  )}
                  {actors.map((actor) => (
                    <tr key={actor.actor_id}>
                      <td>
                        <div className="finance-cell-stack">
                          <strong>{actor.name}</strong>
                          <span>{actor.secondary_label || "-"}</span>
                        </div>
                      </td>
                      <td>{actor.email || "-"}</td>
                      <td>{formatFinanceCurrency(actor.balances?.eligible || 0)}</td>
                      <td>{formatFinanceCurrency(actor.balances?.in_payout || 0)}</td>
                      <td>{formatFinanceCurrency(actor.balances?.settled || 0)}</td>
                      <td>
                        <button
                          className="finance-action-btn"
                          onClick={() => setSelectedActorId(String(actor.actor_id))}
                          type="button"
                        >
                          {String(selectedActorId) === String(actor.actor_id) ? "Selected" : "Settle"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="delivery-card">
            <div className="delivery-card-head">
              <h3>Create Payout Batch</h3>
              <span>Weekly or monthly settlement</span>
            </div>
            <form className="finance-form-grid" onSubmit={onCreatePayout}>
              <label>
                <span>Actor</span>
                <select onChange={(event) => setSelectedActorId(event.target.value)} value={selectedActorId}>
                  {actors.map((actor) => (
                    <option key={actor.actor_id} value={actor.actor_id}>
                      {actor.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Period Start</span>
                <input onChange={(event) => setPayoutStart(event.target.value)} type="date" value={payoutStart} />
              </label>
              <label>
                <span>Period End</span>
                <input onChange={(event) => setPayoutEnd(event.target.value)} type="date" value={payoutEnd} />
              </label>
              <label className="finance-form-span">
                <span>Notes</span>
                <input
                  onChange={(event) => setPayoutNotes(event.target.value)}
                  placeholder="Weekly settlement batch"
                  value={payoutNotes}
                />
              </label>
              <button className="finance-primary-btn" disabled={submitting || !selectedActorId} type="submit">
                Create Payout
              </button>
            </form>
          </article>
        </>
      ) : (
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Platform Ledger</h3>
            <span>Unified view</span>
          </div>
          <p className="delivery-note">
            Platform revenue entries come from order-item commissions. Use adjustments here for manual corrections or
            internal finance accounting.
          </p>
        </article>
      )}

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Recent Payouts</h3>
          <span>{payouts.length} rows</span>
        </div>
        <FinancePayoutTable
          payouts={payouts}
          renderActions={(payout) => (
            <div className="finance-actions">
              {payout.status === "pending" && (
                <button
                  className="finance-action-btn"
                  disabled={submitting}
                  onClick={() => onApprovePayout(payout.id)}
                  type="button"
                >
                  Approve
                </button>
              )}
              {payout.status !== "paid" && payout.status !== "cancelled" && (
                <div className="finance-inline-field">
                  <input
                    onChange={(event) =>
                      setPaymentRefs((current) => ({
                        ...current,
                        [payout.id]: event.target.value,
                      }))
                    }
                    placeholder="Payment ref"
                    value={paymentRefs[payout.id] ?? payout.payment_ref ?? ""}
                  />
                  <button
                    className="finance-action-btn primary"
                    disabled={submitting}
                    onClick={() => onMarkPaid(payout)}
                    type="button"
                  >
                    Mark Paid
                  </button>
                </div>
              )}
            </div>
          )}
        />
      </article>

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Manual Adjustments</h3>
          <span>{adjustments.length} rows</span>
        </div>
        <form className="finance-form-grid" onSubmit={onCreateAdjustment}>
          <label>
            <span>Direction</span>
            <select onChange={(event) => setAdjustmentDirection(event.target.value)} value={adjustmentDirection}>
              <option value="credit">Credit</option>
              <option value="debit">Debit</option>
            </select>
          </label>
          <label>
            <span>Amount</span>
            <input
              min="0"
              onChange={(event) => setAdjustmentAmount(event.target.value)}
              placeholder="0.00"
              step="0.01"
              type="number"
              value={adjustmentAmount}
            />
          </label>
          <label className="finance-form-span">
            <span>Description</span>
            <input
              onChange={(event) => setAdjustmentDescription(event.target.value)}
              placeholder="Manual settlement correction"
              value={adjustmentDescription}
            />
          </label>
          <button className="finance-primary-btn" disabled={submitting || !adjustmentAmount} type="submit">
            Add Adjustment
          </button>
        </form>

        <div className="delivery-task-table-wrap">
          <table className="delivery-task-table">
            <thead>
              <tr>
                <th>Actor</th>
                <th>Description</th>
                <th>Direction</th>
                <th>Status</th>
                <th>Amount</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {adjustments.length === 0 && (
                <tr>
                  <td className="empty" colSpan={6}>
                    No adjustments for this filter.
                  </td>
                </tr>
              )}
              {adjustments.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.actor?.name || "Platform"}</td>
                  <td>{entry.description || "-"}</td>
                  <td>{entry.direction}</td>
                  <td>
                    <span className={`delivery-status-pill ${financeStatusTone(entry.status)}`}>
                      {(entry.status || "-").replaceAll("_", " ")}
                    </span>
                  </td>
                  <td className={`finance-amount ${entry.direction === "debit" ? "negative" : "positive"}`}>
                    {entry.direction === "debit" ? "-" : "+"}
                    {formatFinanceCurrency(entry.amount)}
                  </td>
                  <td>{formatFinanceDate(entry.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
