import React from "react";

const stocks = [
  { name: "NIFTY 50", value: "22,957.10", change: "+0.82%" },
  { name: "SENSEX", value: "75,410.35", change: "+0.78%" },
  { name: "BANK NIFTY", value: "49,120.40", change: "+1.12%" },
  { name: "RELIANCE", value: "1,425.50", change: "+1.45%" },
  { name: "TCS", value: "3,892.20", change: "+0.64%" },
  { name: "INFY", value: "1,812.30", change: "+1.03%" },
  { name: "HDFC BANK", value: "1,964.80", change: "+0.92%" },
  { name: "ICICI BANK", value: "1,342.60", change: "+1.28%" },
  { name: "ITC", value: "462.35", change: "+0.51%" },
];

const TickerSet = ({ setKey }) => (
  <div className="flex shrink-0">
    {stocks.map((stock) => (
      <div
        key={`${setKey}-${stock.name}`}
        className="flex items-center gap-3 px-8 whitespace-nowrap text-[11px] font-mono tracking-widest uppercase border-r border-gray-800"
      >
        <span className="text-white">{stock.name}</span>
        <span className="text-gray-400">₹{stock.value}</span>
        <span className={stock.change.startsWith("-") ? "text-red-400" : "text-green-500"}>
          {stock.change}
        </span>
      </div>
    ))}
  </div>
);

const MarketTicker = () => {
  return (
    <>
      <style>{`
        @keyframes marketTicker {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        .market-ticker-track { animation: marketTicker 40s linear infinite; }
        .market-ticker-track:hover { animation-play-state: paused; }
      `}</style>

      <div className="w-full overflow-hidden border-y border-gray-800 bg-[#0a0a0a] py-4">
        <div className="market-ticker-track flex w-max">
          <TickerSet setKey="a" />
          <TickerSet setKey="b" />
        </div>
      </div>
    </>
  );
};

export default MarketTicker;
