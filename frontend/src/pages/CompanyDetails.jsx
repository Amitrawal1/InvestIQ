import { Link, useParams } from "react-router-dom";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";

const companyData = {
  "alpha-energy": {
    name: "Alpha Energy",
    symbol: "ALPHA",
    sector: "Solar & Renewable Energy",
    marketCap: "₹2,450 Cr",
    revenueGrowth: "+18.2%",
    profitGrowth: "+24.5%",
    roe: "19.8%",
    description:
      "Alpha Energy operates in India's renewable energy ecosystem with a focus on solar power generation and related clean-energy infrastructure.",
    growth: "Strong",
    profitability: "Healthy",
    financialHealth: "Moderate",
    risk: "Medium",
  },

  "nova-tech": {
    name: "Nova Technologies",
    symbol: "NOVA",
    sector: "Artificial Intelligence",
    marketCap: "₹4,820 Cr",
    revenueGrowth: "+21.4%",
    profitGrowth: "+17.8%",
    roe: "16.9%",
    description:
      "Nova Technologies develops software and technology solutions focused on artificial intelligence and intelligent computing.",
    growth: "Strong",
    profitability: "Healthy",
    financialHealth: "Strong",
    risk: "Medium",
  },

  "green-power": {
    name: "Green Power India",
    symbol: "GREEN",
    sector: "Solar & Renewable Energy",
    marketCap: "₹1,920 Cr",
    revenueGrowth: "+16.8%",
    profitGrowth: "+28.1%",
    roe: "21.3%",
    description:
      "Green Power India operates renewable power assets and provides clean-energy generation solutions.",
    growth: "Strong",
    profitability: "Strong",
    financialHealth: "Healthy",
    risk: "Medium",
  },
};

export default function CompanyDetails() {
  const { companyId } = useParams();

  const company = companyData[companyId];

  if (!company) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />

        <main className="mx-auto max-w-7xl px-6 py-20">
          <h1 className="text-3xl font-bold">
            Company not found
          </h1>

          <Link
            to="/sectors"
            className="mt-5 inline-block text-sm font-medium underline"
          >
            Explore companies
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
        <section className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-12">
            <div className="text-sm text-gray-400">
              <Link to="/">Home</Link>
              <span className="mx-2">/</span>

              <Link to="/sectors">Sectors</Link>

              <span className="mx-2">/</span>

              <span>{company.name}</span>
            </div>

            <div className="mt-10">
              <p className="text-sm font-medium text-gray-500">
                NSE: {company.symbol}
              </p>

              <h1 className="mt-2 text-4xl font-bold">
                {company.name}
              </h1>

              <p className="mt-3 text-gray-500">
                {company.sector}
              </p>

              <p className="mt-6 max-w-3xl text-lg leading-8 text-gray-500">
                {company.description}
              </p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <div className="grid gap-4 md:grid-cols-4">
            <Metric
              title="Market Cap"
              value={company.marketCap}
            />

            <Metric
              title="Revenue Growth"
              value={company.revenueGrowth}
            />

            <Metric
              title="Profit Growth"
              value={company.profitGrowth}
            />

            <Metric
              title="ROE"
              value={company.roe}
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <h2 className="text-2xl font-bold">
            Company Overview
          </h2>

          <div className="mt-5 max-w-4xl rounded-2xl border border-gray-200 bg-white p-6">
            <p className="leading-7 text-gray-600">
              {company.description}
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <h2 className="text-2xl font-bold">
            Research Signals
          </h2>

          <div className="mt-6 grid gap-4 md:grid-cols-4">
            <Signal
              title="Growth"
              value={company.growth}
            />

            <Signal
              title="Profitability"
              value={company.profitability}
            />

            <Signal
              title="Financial Health"
              value={company.financialHealth}
            />

            <Signal
              title="Risk"
              value={company.risk}
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <h2 className="text-2xl font-bold">
            What's Happening
          </h2>

          <div className="mt-6 grid gap-5 md:grid-cols-3">
            <Insight
              title="Positive Developments"
              text="Business growth and increasing demand are supporting the company's expansion."
            />

            <Insight
              title="Growth Drivers"
              text="Industry expansion, technology adoption and increasing investment can support future growth."
            />

            <Insight
              title="Key Concerns"
              text="Competition, execution, capital requirements and changing market conditions remain important risks."
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
      <p className="text-sm text-gray-400">
        {title}
      </p>

      <p className="mt-2 text-2xl font-bold">
        {value}
      </p>
    </div>
  );
}

function Signal({ title, value }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6">
      <p className="text-sm text-gray-400">
        {title}
      </p>

      <p className="mt-2 text-xl font-semibold">
        {value}
      </p>
    </div>
  );
}

function Insight({ title, text }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6">
      <h3 className="font-semibold">
        {title}
      </h3>

      <p className="mt-3 text-sm leading-6 text-gray-500">
        {text}
      </p>
    </div>
  );
}