import { useEffect } from "react";

const BASE = "InvestIQ";

// Sets the browser tab title ("Privacy Policy · InvestIQ") and restores the previous one on leave
export default function usePageTitle(title) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} · ${BASE}` : `${BASE} · AI stock research for Indian markets`;
    return () => { document.title = previous; };
  }, [title]);
}
