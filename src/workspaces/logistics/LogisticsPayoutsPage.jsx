import ActorPayoutsPage from "../finance/ActorPayoutsPage";

export default function LogisticsPayoutsPage() {
  return (
    <ActorPayoutsPage
      title="Logistics Payouts"
      description="Review settlement batches created for your completed logistics work."
      emptyMessage="No logistics payouts have been created yet."
    />
  );
}
