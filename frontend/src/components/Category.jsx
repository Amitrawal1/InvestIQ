import React from "react";

const categories = [
  {
    title: "Financial Services",
    description: "Banks, NBFC, Insurance, FinTech",
    image:
      "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Technology",
    description: "IT Services, Software, AI, Cybersecurity",
    image:
      "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Healthcare & Pharmaceuticals",
    description: "Pharma, Hospitals, Diagnostics",
    image:
      "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Energy & Utilities",
    description: "Oil & Gas, Power, Renewable, Solar, Coal",
    image:
      "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Automobile & Mobility",
    description: "Automobiles, EV, Auto Components",
    image:
      "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Consumer & FMCG",
    description: "Food, Beverages, Retail, Consumer Durables",
    image:
      "https://images.unsplash.com/photo-1601598851547-4302969d9a2c?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Industrials & Infrastructure",
    description: "Manufacturing, Construction, Capital Goods",
    image:
      "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Metals, Mining & Chemicals",
    description: "Steel, Mining, Chemicals, Cement",
    image:
      "https://images.unsplash.com/photo-1513828583688-c52646db42da?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Real Estate & Construction",
    description: "Real Estate, Housing, Building Materials",
    image:
      "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Services & Others",
    description: "Telecom, Logistics, Aviation, Hotels, Media",
    image:
      "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=900&q=80",
  },
];

const Catogary = () => {
  return (
    <>
      <style>{`
        .category-card {
          flex: 1 1 0%;
          min-width: 0;
          transition:
            flex-grow 500ms cubic-bezier(0.22, 1, 0.36, 1),
            transform 500ms cubic-bezier(0.22, 1, 0.36, 1);
        }

        .category-card:hover {
          flex-grow: 2;
        }
      `}</style>

      <section className="w-full px-6 py-8">

        {/* Heading */}
        <div className="mb-5">
          <h2 className="text-2xl font-bold text-white">
            Explore Categories
          </h2>

          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Explore stocks across different sectors
          </p>
        </div>


        {/* Category Cards */}
        <div className="flex h-[400px] w-full gap-3 overflow-hidden">

          {categories.map((category, index) => (
            <div key={index} className="category-card group relative cursor-pointer overflow-hidden rounded-2xl bg-[#0d1423]">
              {/* Background Image */}
              <img
                src={category.image}
                alt={category.title}
                className=" absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"/>
              {/* Overlay */}
              <div
                className="
                  absolute
                  inset-0
                  bg-gradient-to-t
                  from-black/95
                  via-black/40
                  to-transparent
                "
              />


              {/* Content */}
              <div
                className="
                  absolute
                  top-1
                  left-0
                  w-full
                  p-5
                "
              >

                <h3 className="
                  text-lg
                  font-bold
                  text-white
                  whitespace-nowrap
                ">
                  {category.title}
                </h3>

                <p className=" mt-1 max-w-[220px] text-xs leading-relaxed text-gray-300 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  {category.description}
                </p>

              </div>

            </div>
          ))}

        </div>

      </section>
    </>
  );
};

export default Catogary;