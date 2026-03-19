import ActorPayoutsPage from "../finance/ActorPayoutsPage";

export default function DeliveryPayoutsPage() {
  return (
    <ActorPayoutsPage
      title="Delivery Payouts"
      description="Review your settlement batches, payment references, and current payout queue."
      emptyMessage="No delivery payouts have been created yet."
    />
  );
}
