export default function SectionHeader({
  eyebrow,
  title,
  description,
}) {
  return (
    <div>
      {eyebrow && (
        <p className="text-sm font-medium text-gray-500">
          {eyebrow}
        </p>
      )}

      <h2 className="mt-1 text-3xl font-bold text-gray-900">
        {title}
      </h2>

      {description && (
        <p className="mt-3 max-w-2xl text-gray-500">
          {description}
        </p>
      )}
    </div>
  );
}