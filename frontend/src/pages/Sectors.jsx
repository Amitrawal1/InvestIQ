import { useState } from "react";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import SearchBar from "../components/SearchBar";
import SectorCard from "../components/SectorCard";
import EmptyState from "../components/EmptyState";
import SectionHeader from "../components/SectionHeader";

const sectors = [
  {
    id: "artificial-intelligence",
    name: "Artificial Intelligence",
    description: "Companies working on AI and intelligent technologies.",
    companies: 28,
    category: "Technology",
    icon: "🤖",
  },
  {
    id: "solar",
    name: "Solar & Renewable Energy",
    description: "Companies building India's clean-energy future.",
    companies: 42,
    category: "Energy",
    icon: "☀️",
  },
  {
    id: "electric-vehicles",
    name: "Electric Vehicles",
    description: "Businesses shaping India's electric mobility ecosystem.",
    companies: 35,
    category: "Technology",
    icon: "⚡",
  },
  {
    id: "defence",
    name: "Defence",
    description: "Indian companies supporting defence and aerospace.",
    companies: 31,
    category: "Manufacturing",
    icon: "🛡️",
  },
  {
    id: "healthcare",
    name: "Healthcare",
    description: "Companies improving India's healthcare ecosystem.",
    companies: 54,
    category: "Healthcare",
    icon: "🏥",
  },
  {
    id: "pharmaceuticals",
    name: "Pharmaceuticals",
    description: "Indian pharmaceutical and healthcare businesses.",
    companies: 67,
    category: "Healthcare",
    icon: "💊",
  },
  {
    id: "semiconductors",
    name: "Semiconductors",
    description: "Companies involved in India's semiconductor ecosystem.",
    companies: 19,
    category: "Technology",
    icon: "💻",
  },
  {
    id: "infrastructure",
    name: "Infrastructure",
    description: "Companies building India's physical infrastructure.",
    companies: 73,
    category: "Manufacturing",
    icon: "🏗️",
  },
];

const categories = [
  "All",
  "Technology",
  "Energy",
  "Healthcare",
  "Manufacturing",
];

export default function Sectors() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");

  const filteredSectors = sectors.filter((sector) => {
    const matchesSearch = sector.name
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesCategory =
      category === "All" || sector.category === category;

    return matchesSearch && matchesCategory;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main>
        <section className="bg-white">
          <div className="mx-auto max-w-7xl px-6 py-16">
            <SectionHeader
              eyebrow="Discover"
              title="Explore Sectors"
              description="Find companies by industry and explore where India's economy is evolving."
            />

            <div className="mt-8 max-w-xl">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search sectors..."
              />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex flex-wrap gap-3">
            {categories.map((item) => (
              <button
                key={item}
                onClick={() => setCategory(item)}
                className={`rounded-full px-5 py-2 text-sm font-medium transition ${
                  category === item
                    ? "bg-black text-white"
                    : "border border-gray-200 bg-white text-gray-600 hover:border-gray-400"
                }`}
              >
                {item}
              </button>
            ))}
          </div>

          {filteredSectors.length > 0 ? (
            <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {filteredSectors.map((sector) => (
                <SectorCard key={sector.id} {...sector} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No sectors found"
              description="Try changing your search or category."
            />
          )}
        </section>
      </main>

      <Footer />
    </div>
  );
}