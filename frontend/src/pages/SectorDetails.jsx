import { Link, useParams } from "react-router-dom";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import CompanyCard from "../components/CompanyCard";

const sectorData = {
  solar: {
    name: "Solar & Renewable Energy",
    description:
      "India's renewable energy sector is expanding rapidly, driven by increasing capacity, government initiatives and growing demand for clean energy.",
    companies: 42,
    growth: "18.4%",
    trend: "Positive",
    risk: "Medium",
    companiesList: [
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
        id: "green-power",
        name: "Green Power India",
        symbol: "GREEN",
        sector: "Solar & Renewable Energy",
        marketCap: "₹1,920 Cr",
        revenueGrowth: "+16.8%",
        profitGrowth: "+28.1%",
      },
    ],
  },

  "artificial-intelligence": {
    name: "Artificial Intelligence",
    description:
      "Companies developing software, infrastructure and services around artificial intelligence and intelligent computing.",
    companies: 28,
    growth: "21.7%",
    trend: "Strong",
    risk: "Medium",
    companiesList: [
      {
        id: "nova-tech",
        name: "Nova Technologies",
        symbol: "NOVA",
        sector: "Artificial Intelligence",
        marketCap: "₹4,820 Cr",
        revenueGrowth: "+21.4%",
        profitGrowth: "+17.8%",
      },
    ],
  },
};

export default function SectorDetails() {
  const { sectorId } = useParams();

  const sector = sectorData[sectorId];

  if (!sector) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />

        <main className="mx-auto max-w-7xl px-6 py-20">
          <h1 className="text-3xl font-bold">
            Sector not found
          </h1>

          <Link
            to="/sectors"
            className="mt-5 inline-block text-sm font-medium underline"
          >
            Back to sectors
          </Link>
        </main>

        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main>
        <section className="bg-white">
          <div className="mx-auto max-w-7xl px-6 py-12">
            <div className="text-sm text-gray-400">
              <Link to="/">Home</Link>
              <span className="mx-2">/</span>
              <Link to="/sectors">Sectors</Link>
              <span className="mx-2">/</span>
              <span>{sector.name}</span>
            </div>

            <div className="mt-10 max-w-3xl">
              <h1 className="text-4xl font-bold">
                {sector.name}
              </h1>

              <p className="mt-5 text-lg leading-8 text-gray-500">
                {sector.description}
              </p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <div className="grid gap-4 md:grid-cols-4">
            <Metric title="Companies" value={sector.companies} />

            <Metric
              title="Avg. Revenue Growth"
              value={sector.growth}
            />

            <Metric
              title="Industry Trend"
              value={sector.trend}
            />

            <Metric
              title="Risk Level"
              value={sector.risk}
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <h2 className="text-2xl font-bold">
            Companies in {sector.name}
          </h2>

          <div className="mt-6 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {sector.companiesList.map((company) => (
              <CompanyCard
                key={company.id}
                {...company}
              />
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <h2 className="text-2xl font-bold">
            Research Insights
          </h2>

          <div className="mt-6 grid gap-5 md:grid-cols-3">
            <Insight
              title="What's happening?"
              text="Renewable capacity and clean-energy investments continue to expand."
            />

            <Insight
              title="Growth Drivers"
              text="Government incentives, falling technology costs and increasing energy demand."
            />

            <Insight
              title="Key Risks"
              text="Execution risk, capital requirements, regulatory changes and competition."
            />
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}

function Metric({ title, value }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6">
      <p className="text-sm text-gray-400">{title}</p>

      <p className="mt-2 text-2xl font-bold">
        {value}
      </p>
    </div>
  );
}

function Insight({ title, text }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6">
      <h3 className="font-semibold">{title}</h3>

      <p className="mt-3 text-sm leading-6 text-gray-500">
        {text}
      </p>
    </div>
  );
}