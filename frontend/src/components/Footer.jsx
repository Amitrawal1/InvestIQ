import { Link } from "react-router-dom";


export default function Footer() {
  return (
    <footer className="mt-20 border-t border-gray-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-bold">InvestIQ</h2>

          <p className="mt-2 text-sm text-gray-500">
            Research smarter. Discover better.
          </p>
        </div>

        <div className="flex gap-6 text-sm text-gray-500">
          <Link to="/sectors">Sectors</Link>
          <Link to="/sectors">Companies</Link>
        </div>

        <p className="text-sm text-gray-400">
          © 2026 InvestIQ
        </p>
      </div>
    </footer>
  );
}