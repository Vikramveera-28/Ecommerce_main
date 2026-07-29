import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { FinancePayoutTable, FinanceSummaryCards, formatFinanceCurrency } from "./FinanceShared";

export default function ActorPayoutsPage({ title, description, emptyMessage }) {
  const { accessToken } = useAuth();
  const [summary, setSummary] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [summaryPayload, payoutRows] = await Promise.all([
          apiClient.getFinanceSummary(accessToken, { range: "all" }),
          apiClient.getFinancePayouts(accessToken),
        ]);
        if (cancelled) return;
        setSummary(summaryPayload);
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
  }, [accessToken]);

  const paidTotal = payouts
    .filter((payout) => payout.status === "paid")
    .reduce((sum, payout) => sum + Number(payout.net_amount || 0), 0);
  const openCount = payouts.filter((payout) => payout.status === "pending" || payout.status === "approved").length;
  const cards = [
    {
      label: "Available Balance",
      value: formatFinanceCurrency(summary?.balances?.eligible || 0),
      highlight: true,
    },
    {
      label: "Paid Out",
      value: formatFinanceCurrency(paidTotal),
    },
    {
      label: "Open Payouts",
      value: openCount.toString(),
    },
    {
      label: "Total Payout Rows",
      value: payouts.length.toString(),
    },
  ];

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading payouts...</p>
      </section>
    );
  }

  return (
    <section className="delivery-page">
      <header className="delivery-page-head">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>

      {error && <p className="delivery-error">{error}</p>}
      <FinanceSummaryCards cards={cards} />

      <article className="delivery-card">
        <div className="delivery-card-head">
          <h3>Payout History</h3>
          <span>{payouts.length} rows</span>
        </div>
        <FinancePayoutTable emptyMessage={emptyMessage} payouts={payouts} />
      </article>
    </section>
  );
}
