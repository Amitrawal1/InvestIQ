import React from "react";
import { TrendingUp } from "lucide-react";

const stocks = [
  {
    name: "NIFTY 50",
    value: "22,957.10",
    change: "+0.82%",
    icon: "📈",
  },
  {
    name: "SENSEX",
    value: "75,410.35",
    change: "+0.78%",
    icon: "📊",
  },
  {
    name: "BANK NIFTY",
    value: "49,120.40",
    change: "+1.12%",
    icon: "🏦",
  },
  {
    name: "RELIANCE",
    value: "1,425.50",
    change: "+1.45%",
    icon: "🔵",
  },
  {
    name: "TCS",
    value: "3,892.20",
    change: "+0.64%",
    icon: "🔷",
  },
  {
    name: "INFY",
    value: "1,812.30",
    change: "+1.03%",
    icon: "🟣",
  },
  {
    name: "HDFC BANK",
    value: "1,964.80",
    change: "+0.92%",
    icon: "🟢",
  },
  {
    name: "ICICI BANK",
    value: "1,342.60",
    change: "+1.28%",
    icon: "🟠",
  },
  {
    name: "ITC",
    value: "462.35",
    change: "+0.51%",
    icon: "🟡",
  },
];

const MarketTicker = () => {
  return (
    <>
      <style>{`
        @keyframes marketTicker {
          from {
            transform: translateX(0);
          }

          to {
            transform: translateX(-50%);
          }
        }

        .market-ticker-track {
          animation: marketTicker 30s linear infinite;
        }

        .market-ticker-track:hover {
          animation-play-state: paused;
        }
      `}</style>

      <div className="w-full overflow-hidden bg-[#0d1423] py-3">

        <div className="market-ticker-track flex w-max">

          {/* FIRST SET */}
          <div className="flex shrink-0">

            {stocks.map((stock, index) => (
              <div
                key={`first-${index}`}
                className="flex items-center gap-2 px-6 whitespace-nowrap"
              >

                {/* Icon */}
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#182235] text-sm">
                  {stock.icon}
                </div>

                {/* Stock Name */}
                <span className="text-sm font-semibold text-white">
                  {stock.name}
                </span>

                {/* Price */}
                <span className="text-sm text-gray-400">
                  ₹{stock.value}
                </span>

                {/* Change */}
                <span className="flex items-center gap-1 text-sm font-medium text-emerald-400">
                  {stock.change}
                  <TrendingUp size={14} />
                </span>

              </div>
            ))}

          </div>


          {/* SECOND SET */}
          <div className="flex shrink-0">

            {stocks.map((stock, index) => (
              <div
                key={`second-${index}`}
                className="flex items-center gap-2 px-6 whitespace-nowrap"
              >

                {/* Icon */}
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#182235] text-sm">
                  {stock.icon}
                </div>

                {/* Stock Name */}
                <span className="text-sm font-semibold text-white">
                  {stock.name}
                </span>

                {/* Price */}
                <span className="text-sm text-gray-400">
                  ₹{stock.value}
                </span>

                {/* Change */}
                <span className="flex items-center gap-1 text-sm font-medium text-emerald-400">
                  {stock.change}
                  <TrendingUp size={14} />
                </span>

              </div>
            ))}

          </div>

        </div>
      </div>
    </>
  );
};

export default MarketTicker;