import { SearchX } from "lucide-react";

export default function EmptyState({
  title = "No results found",
  description = "Try changing your search or explore another option.",
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-100">
        <SearchX size={24} className="text-gray-500" />
      </div>

      <h3 className="mt-5 text-lg font-semibold text-gray-900">
        {title}
      </h3>

      <p className="mt-2 max-w-md text-sm text-gray-500">
        {description}
      </p>
    </div>
  );
}