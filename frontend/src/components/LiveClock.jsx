import { useEffect, useState } from "react"

// Market time is always IST, whatever the viewer's timezone
const dateFmt = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit", month: "short", year: "numeric",
})
const timeFmt = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
})

export default function LiveClock({ className = "" }) {
    const [now, setNow] = useState(() => new Date())

    useEffect(() => {
        const id = setInterval(() => setNow(new Date()), 1000)
        return () => clearInterval(id)
    }, [])

    return (
        <div className={`flex flex-col gap-2 font-mono text-white ${className}`}>
            <span className="text-4xl md:text-5xl tracking-tight tabular-nums">{timeFmt.format(now)}</span>
            <span className="text-[11px] tracking-[0.2em] uppercase">{dateFmt.format(now).replace(/,/g, "")}</span>
        </div>
    )
}
