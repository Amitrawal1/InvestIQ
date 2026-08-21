import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function SectorCard({
  id,
  name,
  description,
  companies,
  icon,
}) {
  return (
    <Link
      to={`/sector/${id}`}
      className="group rounded-2xl border border-gray-200 bg-white p-6 transition hover:-translate-y-1 hover:border-gray-300 hover:shadow-lg"
    >
      <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100 text-xl">
        {icon}
      </div>

      <h3 className="text-lg font-semibold text-gray-900">
        {name}
      </h3>

      <p className="mt-2 min-h-12 text-sm leading-6 text-gray-500">
        {description}
      </p>

      <div className="mt-5 flex items-center justify-between">
        <span className="text-sm text-gray-500">
          {companies} Companies
        </span>

        <ArrowRight
          size={18}
          className="transition group-hover:translate-x-1"
        />
      </div>
    </Link>
  );
}