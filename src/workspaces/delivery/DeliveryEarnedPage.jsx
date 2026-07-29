import ActorEarningsPage from "../finance/ActorEarningsPage";

export default function DeliveryEarnedPage() {
  return (
    <ActorEarningsPage
      title="Delivery Earnings"
      description="Track delivery income from the server ledger, including queued settlements and completed payouts."
      emptyMessage="No delivery earnings found in the selected range."
      compensationDescription={(compensation) =>
        `Each delivered shipment credits ${new Intl.NumberFormat("en-IN", {
          style: "currency",
          currency: "INR",
          maximumFractionDigits: 2,
        }).format(Number(compensation?.per_delivery || 0))} plus ${new Intl.NumberFormat("en-IN", {
          style: "currency",
          currency: "INR",
          maximumFractionDigits: 2,
        }).format(Number(compensation?.per_item || 0))} per delivered item.`
      }
    />
  );
}
