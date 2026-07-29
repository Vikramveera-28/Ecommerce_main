import ActorEarningsPage from "../finance/ActorEarningsPage";

export default function VendorEarningsPage() {
  return (
    <ActorEarningsPage
      title="Vendor Earnings"
      description="View delivered-order earnings from the finance ledger and monitor what is available, queued, or settled."
      emptyMessage="No vendor earnings are available in the selected range."
    />
  );
}
