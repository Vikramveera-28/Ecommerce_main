import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  FINANCE_RANGE_OPTIONS,
  FinanceLedgerTable,
  FinanceSummaryCards,
  formatFinanceCurrency,
  formatFinanceDate,
} from "./FinanceShared";

export default function ActorEarningsPage({
  title,
  description,
  emptyMessage,
  compensationDescription,
}) {
  const { accessToken } = useAuth();
  const [range, setRange] = useState("all");
  const [summary, setSummary] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [summaryPayload, ledgerRows, payoutRows] = await Promise.all([
          apiClient.getFinanceSummary(accessToken, { range }),
          apiClient.getFinanceLedger(accessToken, { range }),
          apiClient.getFinancePayouts(accessToken),
        ]);
        if (cancelled) return;
        setSummary(summaryPayload);
        setLedger(ledgerRows || []);
        setPayouts(payoutRows || []);
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

    load();
    return () => {
      cancelled = true;
    };
  }, [accessToken, range]);

  const lastPayout = payouts[0] || summary?.last_payout || null;
  const cards = [
    {
      label: "Available Balance",
      value: formatFinanceCurrency(summary?.balances?.eligible || 0),
      highlight: true,
    },
    {
      label: "Queued In Payout",
      value: formatFinanceCurrency(summary?.balances?.in_payout || 0),
    },
    {
      label: "Settled",
      value: formatFinanceCurrency(summary?.balances?.settled || 0),
    },
    {
      label: `${range === "all" ? "Lifetime" : "Range"} Net`,
      value: formatFinanceCurrency(summary?.period?.net || 0),
    },
  ];

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading earnings...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head split">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <label className="delivery-range-filter">
          <span>Range</span>
          <select onChange={(event) => setRange(event.target.value)} value={range}>
            {FINANCE_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      {error && <p className="delivery-error">{error}</p>}
      <FinanceSummaryCards cards={cards} />

      {(summary?.compensation || compensationDescription || lastPayout) && (
        <div className="finance-insight-grid">
          {(summary?.compensation || compensationDescription) && (
            <article className="delivery-card">
              <div className="delivery-card-head">
                <h3>Compensation Rule</h3>
                <span>Server ledger is authoritative</span>
              </div>
              <p className="delivery-note">
                {compensationDescription ? compensationDescription(summary?.compensation || {}) : null}
              </p>
            </article>
          )}

          <article className="delivery-card">
            <div className="delivery-card-head">
              <h3>Latest Payout</h3>
              <span>{payouts.length} total payouts</span>
            </div>
            {lastPayout ? (
              <div className="finance-cell-stack">
                <strong>{formatFinanceCurrency(lastPayout.net_amount)}</strong>
                <span>
                  {lastPayout.status?.replaceAll("_", " ") || "pending"} on{" "}
                  {formatFinanceDate(lastPayout.paid_at || lastPayout.created_at)}
                </span>
              </div>
            ) : (
              <p className="delivery-note">No payouts have been created yet.</p>
            )}
          </article>
        </div>
      )}

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Ledger Entries</h3>
          <span>{ledger.length} rows</span>
        </div>
        <FinanceLedgerTable emptyMessage={emptyMessage} entries={ledger} />
      </article>
    </section>
  );
}
