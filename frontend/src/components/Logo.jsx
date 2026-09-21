import { Link } from "react-router-dom";

export default function Logo({ className = "" }) {
  return (
    <Link to="/" className={`font-sans font-black text-lg tracking-tight text-white ${className}`}>
      INVEST IQ
    </Link>
  );
}
