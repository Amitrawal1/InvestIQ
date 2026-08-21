import Button from "./Button";

export default function ErrorState({ onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h3 className="text-lg font-semibold text-gray-900">
        Something went wrong
      </h3>

      <p className="mt-2 text-sm text-gray-500">
        We couldn't load this data.
      </p>

      {onRetry && (
        <div className="mt-5">
          <Button onClick={onRetry}>
            Try Again
          </Button>
        </div>
      )}
    </div>
  );
}