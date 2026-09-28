import { Link } from "react-router-dom";

export default function Logo({ className = "" }) {
  return (
    <Link to="/home" aria-label="InvestIQ home" className={`inline-flex items-center touch:min-h-11 font-sans font-black text-lg tracking-tight text-white ${className}`}>
      INVEST IQ
    </Link>
  );
}
