import { BrowserRouter, Routes, Route } from "react-router-dom";

import Home from "./pages/Home";
import Sectors from "./pages/Sectors";
import SectorDetails from "./pages/SectorDetails";
import CompanyDetails from "./pages/CompanyDetails";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/sectors" element={<Sectors />} />
        <Route path="/sector/:sectorId" element={<SectorDetails />} />
        <Route path="/company/:companyId" element={<CompanyDetails />} />
      </Routes>
    </BrowserRouter>
  );
}