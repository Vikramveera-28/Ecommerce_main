export const FINANCE_RANGE_OPTIONS = [
  { value: "all", label: "All Time" },
  { value: "30d", label: "Last 30 Days" },
  { value: "7d", label: "Last 7 Days" },
];

export function formatFinanceCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function formatFinanceDate(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleString();
}

export function financeStatusTone(status) {
  if (status === "paid" || status === "settled") return "success";
  if (status === "approved" || status === "eligible") return "warning";
  if (status === "failed" || status === "void" || status === "cancelled") return "danger";
  return "neutral";
}

export function ledgerSourceLabel(entry) {
  const context = entry?.source_context || {};
  if (entry?.source_type === "shipment") {
    return context.tracking_number || `Shipment #${entry.source_id}`;
  }
  if (entry?.source_type === "order_item") {
    return context.order_id ? `Order #${context.order_id} / Item #${entry.source_id}` : `Order Item #${entry.source_id}`;
  }
  if (entry?.source_type === "adjustment") {
    return "Manual Adjustment";
  }
  return entry?.source_type || "-";
}

export function ledgerDetailLabel(entry) {
  const context = entry?.source_context || {};
  if (entry?.source_type === "shipment") {
    const itemCount = Number(context.item_count || 0);
    return itemCount > 0 ? `${itemCount} item${itemCount === 1 ? "" : "s"}` : "Shipment settlement";
  }
  if (entry?.source_type === "order_item") {
    const quantity = Number(context.quantity || 0);
    return quantity > 0 ? `${quantity} unit${quantity === 1 ? "" : "s"}` : "Order commission";
  }
  return entry?.entry_code?.replaceAll("_", " ") || "-";
}

export function FinanceSummaryCards({ cards }) {
  return (
    <div className="delivery-summary-grid earned">
      {cards.map((card) => (
        <article className={card.highlight ? "highlight" : ""} key={card.label}>
          <p>{card.label}</p>
          <h3>{card.value}</h3>
        </article>
      ))}
    </div>
  );
}

export function FinanceLedgerTable({ entries, emptyMessage = "No ledger entries found." }) {
  return (
    <div className="delivery-task-table-wrap">
      <table className="delivery-task-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Details</th>
            <th>Effective At</th>
            <th>Status</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 && (
            <tr>
              <td className="empty" colSpan={5}>
                {emptyMessage}
              </td>
            </tr>
          )}
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{ledgerSourceLabel(entry)}</td>
              <td>
                <div className="finance-cell-stack">
                  <strong>{entry.description || "-"}</strong>
                  <span>{ledgerDetailLabel(entry)}</span>
                </div>
              </td>
              <td>{formatFinanceDate(entry.effective_at)}</td>
              <td>
                <span className={`delivery-status-pill ${financeStatusTone(entry.payout_status || entry.status)}`}>
                  {(entry.payout_status || entry.status || "-").replaceAll("_", " ")}
                </span>
              </td>
              <td className={`finance-amount ${entry.direction === "debit" ? "negative" : "positive"}`}>
                {entry.direction === "debit" ? "-" : "+"}
                {formatFinanceCurrency(entry.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FinancePayoutTable({
  payouts,
  emptyMessage = "No payouts found.",
  renderActions = null,
}) {
  const hasActions = typeof renderActions === "function";

  return (
    <div className="delivery-task-table-wrap">
      <table className="delivery-task-table">
        <thead>
          <tr>
            <th>Period</th>
            <th>Status</th>
            <th>Gross</th>
            <th>Net</th>
            <th>Created</th>
            <th>Paid At</th>
            <th>Payment Ref</th>
            {hasActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {payouts.length === 0 && (
            <tr>
              <td className="empty" colSpan={hasActions ? 8 : 7}>
                {emptyMessage}
              </td>
            </tr>
          )}
          {payouts.map((payout) => (
            <tr key={payout.id}>
              <td>
                <div className="finance-cell-stack">
                  <strong>{formatFinanceDate(payout.period_start)}</strong>
                  <span>to {formatFinanceDate(payout.period_end)}</span>
                </div>
              </td>
              <td>
                <span className={`delivery-status-pill ${financeStatusTone(payout.status)}`}>
                  {(payout.status || "-").replaceAll("_", " ")}
                </span>
              </td>
              <td>{formatFinanceCurrency(payout.gross_amount)}</td>
              <td>{formatFinanceCurrency(payout.net_amount)}</td>
              <td>{formatFinanceDate(payout.created_at)}</td>
              <td>{formatFinanceDate(payout.paid_at)}</td>
              <td>{payout.payment_ref || "-"}</td>
              {hasActions && <td>{renderActions(payout)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
