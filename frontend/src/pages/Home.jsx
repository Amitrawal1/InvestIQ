import { useState } from "react";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import SearchBar from "../components/SearchBar";
import SectorCard from "../components/SectorCard";
import CompanyCard from "../components/CompanyCard";
import SectionHeader from "../components/SectionHeader";

const sectors = [
  {
    id: "solar",
    name: "Solar & Renewable Energy",
    description: "Companies building India's clean-energy future.",
    companies: 42,
    icon: "☀️",
  },
  {
    id: "artificial-intelligence",
    name: "Artificial Intelligence",
    description: "Companies working on AI and intelligent technologies.",
    companies: 28,
    icon: "🤖",
  },
  {
    id: "electric-vehicles",
    name: "Electric Vehicles",
    description: "Businesses shaping India's electric mobility ecosystem.",
    companies: 35,
    icon: "⚡",
  },
  {
    id: "defence",
    name: "Defence",
    description: "Indian companies supporting defence and aerospace.",
    companies: 31,
    icon: "🛡️",
  },
];

const companies = [
  {
    id: "alpha-energy",
    name: "Alpha Energy",
    symbol: "ALPHA",
    sector: "Solar & Renewable Energy",
    marketCap: "₹2,450 Cr",
    revenueGrowth: "+18.2%",
    profitGrowth: "+24.5%",
  },
  {
    id: "nova-tech",
    name: "Nova Technologies",
    symbol: "NOVA",
    sector: "Artificial Intelligence",
    marketCap: "₹4,820 Cr",
    revenueGrowth: "+21.4%",
    profitGrowth: "+17.8%",
  },
  {
    id: "green-power",
    name: "Green Power India",
    symbol: "GREEN",
    sector: "Solar & Renewable Energy",
    marketCap: "₹1,920 Cr",
    revenueGrowth: "+16.8%",
    profitGrowth: "+28.1%",
  },
];

export default function Home() {
  const [search, setSearch] = useState("");

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main>
        <section className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-24 text-center">
            <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500">
              Indian Equity Research
            </p>

            <h1 className="mx-auto max-w-4xl text-4xl font-bold tracking-tight text-gray-900 md:text-6xl">
              Discover India's Next
              <br />
              Potential Opportunity
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-gray-500 md:text-lg">
              Research Indian companies, explore sectors,
              and discover businesses worth knowing before
              the crowd.
            </p>

            <div className="mx-auto mt-8 max-w-xl">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search companies, sectors..."
              />
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white">
          <div className="mx-auto grid max-w-5xl grid-cols-2 divide-x divide-gray-200 md:grid-cols-4">
            <div className="p-6 text-center">
              <p className="text-2xl font-bold">3,000+</p>
              <p className="mt-1 text-sm text-gray-500">Companies</p>
            </div>

            <div className="p-6 text-center">
              <p className="text-2xl font-bold">50+</p>
              <p className="mt-1 text-sm text-gray-500">Sectors</p>
            </div>

            <div className="p-6 text-center">
              <p className="text-2xl font-bold">NSE</p>
              <p className="mt-1 text-sm text-gray-500">Focused</p>
            </div>

            <div className="p-6 text-center">
              <p className="text-2xl font-bold">Research</p>
              <p className="mt-1 text-sm text-gray-500">First</p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-20">
          <SectionHeader
            eyebrow="Explore"
            title="Popular Sectors"
            description="Discover industries worth researching."
          />

          <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {sectors.map((sector) => (
              <SectorCard key={sector.id} {...sector} />
            ))}
          </div>
        </section>

        <section className="bg-white">
          <div className="mx-auto max-w-7xl px-6 py-20">
            <SectionHeader
              eyebrow="Discover"
              title="Companies Worth Exploring"
              description="Explore companies across India's growing sectors."
            />

            <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {companies.map((company) => (
                <CompanyCard key={company.id} {...company} />
              ))}
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}