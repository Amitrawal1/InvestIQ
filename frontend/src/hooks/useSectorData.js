import { useEffect, useState } from "react";
import { getSectors, getCompaniesBySector } from "../services/api";

// Bundled DB export (backend/scripts/exportSectorSnapshot.js), loaded only when the API is down
const loadSnapshot = () => import("../data/sectorsSnapshot.json").then((m) => m.default);

// Module-level caches so moving between Home and sector pages doesn't refetch
let sectorsPromise = null;
const companiesCache = new Map();

function fetchSectors() {
  if (!sectorsPromise) {
    sectorsPromise = getSectors()
      .then((rows) => ({ rows, source: { live: true } }))
      .catch(() =>
        loadSnapshot().then((snap) => ({
          rows: snap.sectors,
          source: { live: false, exportedAt: snap.exported_at },
        }))
      );

    sectorsPromise.catch(() => { sectorsPromise = null; });
  }
  return sectorsPromise;
}

function fetchCompanies(sector, live) {
  if (!companiesCache.has(sector.id)) {
    const fromSnapshot = () => loadSnapshot().then((snap) => snap.companiesBySector[sector.id] || []);
    const promise = live ? getCompaniesBySector(sector.name).catch(fromSnapshot) : fromSnapshot();

    companiesCache.set(sector.id, promise);
    promise.catch(() => companiesCache.delete(sector.id));
  }
  return companiesCache.get(sector.id);
}

export function useSectors() {
  const [state, setState] = useState({ sectors: [], source: null, loading: true, error: false });

  useEffect(() => {
    let cancelled = false;

    fetchSectors()
      .then(({ rows, source }) => {
        if (!cancelled) setState({ sectors: rows, source, loading: false, error: false });
      })
      .catch(() => {
        if (!cancelled) setState((prev) => ({ ...prev, loading: false, error: true }));
      });

    return () => { cancelled = true; };
  }, []);

  return state;
}

export function useSectorCompanies(sector, live) {
  const [state, setState] = useState({ companies: null, error: false });

  useEffect(() => {
    if (!sector) return;
    let cancelled = false;

    setState({ companies: null, error: false });
    fetchCompanies(sector, live)
      .then((rows) => { if (!cancelled) setState({ companies: rows, error: false }); })
      .catch(() => { if (!cancelled) setState({ companies: null, error: true }); });

    return () => { cancelled = true; };
  }, [sector, live]);

  return state;
}
