import { Search, Menu } from "lucide-react";
import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-2xl font-bold tracking-tight">
          InvestIQ
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <Link
            to="/"
            className="text-sm font-medium text-gray-600 hover:text-black"
          >
            Home
          </Link>

          <Link
            to="/sectors"
            className="text-sm font-medium text-gray-600 hover:text-black"
          >
            Sectors
          </Link>

          <Link
            to="/sectors"
            className="text-sm font-medium text-gray-600 hover:text-black"
          >
            Companies
          </Link>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            to="/sectors"
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            <Search size={17} />
            Search
          </Link>

          <Link
            to="/sectors"
            className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
          >
            Explore
          </Link>
        </div>

        <button className="md:hidden">
          <Menu size={24} />
        </button>
      </div>
    </nav>
  );
}