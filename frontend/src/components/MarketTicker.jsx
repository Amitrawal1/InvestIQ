import React from "react";
import useMarketTicker, { formatPrice, formatChangePct } from "../hooks/useMarketTicker";


const TickerSet = ({ setKey, stocks }) => (
  <div className="flex shrink-0">
    {stocks.map((stock) => (
      <div
        key={`${setKey}-${stock.name}`}
        className="flex items-center gap-3 px-8 whitespace-nowrap text-[11px] font-mono tracking-widest uppercase border-r border-gray-800"
      >
        <span className="text-white">{stock.name}</span>
        <span className="text-gray-400">{stock.price == null ? "—" : `₹${formatPrice(stock.price)}`}</span>
        <span className={stock.changePct == null ? "text-gray-500" : stock.changePct < 0 ? "text-red-400" : "text-green-500"}>
          {formatChangePct(stock.changePct)}
        </span>
      </div>
    ))}
  </div>
);

const MarketTicker = () => {
  const { quotes } = useMarketTicker();

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
          <TickerSet setKey="a" stocks={quotes} />
          <TickerSet setKey="b" stocks={quotes} />
        </div>
      </div>
    </>
  );
};

export default MarketTicker;
