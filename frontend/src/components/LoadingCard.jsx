export default function LoadingCard() {
  return (
    <div className="animate-pulse rounded-2xl border border-gray-200 bg-white p-6">
      <div className="h-12 w-12 rounded-xl bg-gray-200" />

      <div className="mt-5 h-5 w-2/3 rounded bg-gray-200" />

      <div className="mt-3 h-4 w-full rounded bg-gray-200" />

      <div className="mt-2 h-4 w-4/5 rounded bg-gray-200" />

      <div className="mt-6 h-4 w-1/3 rounded bg-gray-200" />
    </div>
  );
}