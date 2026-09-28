import React from "react";
import useMarketTicker, { formatPrice, formatChangePct } from "../hooks/useMarketTicker";


const TickerSet = ({ setKey, stocks, tick }) => (
  <div className="flex shrink-0">
    {stocks.map((stock) => (
      <div
        key={`${setKey}-${stock.name}`}
        className="flex items-center gap-3 px-8 whitespace-nowrap text-[11px] font-mono tracking-widest uppercase border-r border-gray-800"
      >
        <span className="text-white">{stock.name}</span>
        <span
          key={stock.moved ? `${tick}` : "still"}
          className={`text-gray-400 ${stock.moved ? `price-flash-${stock.moved}` : ""}`}
        >
          {stock.price == null ? "—" : `₹${formatPrice(stock.price)}`}
        </span>
        <span className={stock.changePct == null ? "text-gray-500" : stock.changePct < 0 ? "text-red-400" : "text-green-500"}>
          {formatChangePct(stock.changePct)}
        </span>
      </div>
    ))}
  </div>
);

const MarketTicker = () => {
  const { quotes, tick } = useMarketTicker();

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

      <div className="w-full overflow-hidden border-y border-gray-800 bg-surface py-4">
        <div className="market-ticker-track flex w-max">
          <TickerSet setKey="a" stocks={quotes} tick={tick} />
          <TickerSet setKey="b" stocks={quotes} tick={tick} />
        </div>
      </div>
    </>
  );
};

export default MarketTicker;
