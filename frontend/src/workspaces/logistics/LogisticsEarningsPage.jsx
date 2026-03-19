import ActorEarningsPage from "../finance/ActorEarningsPage";

export default function LogisticsEarningsPage() {
  return (
    <ActorEarningsPage
      title="Logistics Earnings"
      description="Monitor completed-shipment settlement credits and watch how much is available versus already included in payout batches."
      emptyMessage="No logistics earnings are available in the selected range."
      compensationDescription={(compensation) =>
        `Each delivered shipment assigned to your logistics profile credits ${new Intl.NumberFormat("en-IN", {
          style: "currency",
          currency: "INR",
          maximumFractionDigits: 2,
        }).format(Number(compensation?.per_completed_shipment || 0))}.`
      }
    />
  );
}
