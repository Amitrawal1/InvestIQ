import React from "react";
import { Database } from "lucide-react";
import { PillTag } from "./ui";

// Shows whether sector data came from the live API or the bundled snapshot
export default function SourcePill({ source }) {
  if (!source) return null;

  return (
    <PillTag
      icon={Database}
      title={source.live ? "Loaded from the InvestIQ API" : "Backend offline: showing the bundled database snapshot"}
    >
      {source.live
        ? "Live DB"
        : `Snapshot ${new Date(source.exportedAt).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}`}
      <span className={`w-1.5 h-1.5 rounded-full ${source.live ? "bg-green-500 animate-pulse" : "bg-yellow-500"}`} />
    </PillTag>
  );
}
