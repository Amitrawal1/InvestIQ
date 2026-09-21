import { useNavigate } from "react-router-dom"
import { motion } from "motion/react"
import { ArrowRight, Cpu, LayoutDashboard, LineChart, Newspaper, TrendingUp } from "lucide-react"
import Navbar from "../components/Navbar"
import Category from "../components/Category"
import MarketTicker from "../components/MarketTicker"
import Footer from "../components/Footer"
import { fadeUp, stagger, SectionLabel, Pill, PrimaryButton } from "../components/ui"

const highlights = [
    { icon: Newspaper, label: "News Alerts", text: "Breaking financial news, filtered to what moves Indian equities." },
    { icon: LineChart, label: "Stock Signals", text: "Sentiment from announcements and earnings turned into clear signals." },
    { icon: TrendingUp, label: "Market Trends", text: "Aggregate news sentiment to spot sector rotations early." },
    { icon: Cpu, label: "AI Predictor", text: "Machine learning models that estimate a stock's next move." },
]

export default function Home() {
    const navigate = useNavigate()

    return (
        <div className="bg-[#050011] w-full text-white min-h-screen font-sans overflow-x-hidden">
            <Navbar />

            {/* HERO */}
            <section className="px-6 md:px-16 pt-16 md:pt-24 pb-16">
                <motion.div
                    initial="initial"
                    animate="animate"
                    variants={stagger(0.1, 0.12)}
                    className="flex flex-col lg:flex-row justify-between gap-12"
                >
                    <div className="lg:w-[60%]">
                        <motion.div variants={fadeUp}>
                            <SectionLabel index="01" className="mb-6">Market Hub</SectionLabel>
                        </motion.div>
                        <motion.h1
                            variants={fadeUp}
                            className="text-[3.2rem] md:text-[5rem] lg:text-[6rem] font-normal tracking-tight leading-[0.95]"
                        >
                            MARKETS,<br />DECODED.
                        </motion.h1>
                    </div>

                    <motion.div variants={fadeUp} className="lg:w-[35%] flex flex-col justify-end gap-8">
                        <div className="flex items-start gap-4 text-[11px] font-mono tracking-[0.2em] uppercase text-gray-300 leading-relaxed">
                            <ArrowRight size={14} strokeWidth={1} className="mt-0.5 shrink-0 text-gray-400" />
                            <p>
                                Live Indian market data, sector views and AI forecasts in one place.
                                Read the news. Watch the ticker. Act on the signal.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <PrimaryButton icon={LayoutDashboard} onClick={() => navigate("/dashboard")}>
                                Open Dashboard
                            </PrimaryButton>
                            <Pill icon={Cpu} onClick={() => navigate("/predictor")} className="py-3.5">
                                AI Predictor
                            </Pill>
                        </div>
                    </motion.div>
                </motion.div>
            </section>

            <MarketTicker />

            {/* FEATURE STRIP */}
            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-gray-800 border-b border-gray-800">
                {highlights.map(({ icon: Icon, label, text }, i) => (
                    <motion.div
                        key={label}
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: i * 0.08 }}
                        className="group p-8 md:p-10 bg-[#050011]"
                    >
                        <div className="flex justify-between items-start mb-10">
                            <span className="text-[10px] font-mono tracking-widest text-gray-500">0{i + 1}</span>
                            <span className="flex items-center justify-center w-10 h-10 rounded-full border border-gray-600 text-gray-400 group-hover:bg-white group-hover:text-black group-hover:border-white transition-colors duration-300">
                                <Icon size={18} />
                            </span>
                        </div>
                        <h3 className="text-xl font-medium tracking-tight mb-3">{label}</h3>
                        <p className="text-sm text-gray-400 leading-relaxed font-light">{text}</p>
                    </motion.div>
                ))}
            </section>

            <Category />

            <Footer />
        </div>
    )
}
