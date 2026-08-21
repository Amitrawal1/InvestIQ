import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function CompanyCard({
  id,
  name,
  symbol,
  sector,
  marketCap,
  revenueGrowth,
  profitGrowth,
}) {
  return (
    <Link
      to={`/company/${id}`}
      className="group rounded-2xl border border-gray-200 bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">
            {name}
          </h3>

          <p className="mt-1 text-xs text-gray-400">
            NSE: {symbol}
          </p>
        </div>

        <ArrowUpRight
          size={18}
          className="text-gray-400 transition group-hover:text-black"
        />
      </div>

      {sector && (
        <p className="mt-4 text-sm text-gray-500">
          {sector}
        </p>
      )}

      <div className="mt-6 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-gray-400">Market Cap</p>
          <p className="mt-1 text-sm font-semibold">
            {marketCap}
          </p>
        </div>

        <div>
          <p className="text-xs text-gray-400">Revenue</p>
          <p className="mt-1 text-sm font-semibold">
            {revenueGrowth}
          </p>
        </div>

        <div>
          <p className="text-xs text-gray-400">Profit</p>
          <p className="mt-1 text-sm font-semibold">
            {profitGrowth}
          </p>
        </div>
      </div>

      <div className="mt-5 text-sm font-medium text-gray-700">
        View Research →
      </div>
    </Link>
  );
}