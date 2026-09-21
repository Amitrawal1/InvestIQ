import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowRight, Cpu, AreaChart, Newspaper } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { fadeUp, stagger, SectionLabel, PrimaryButton } from '../components/ui';

const features = [
  {
    icon: Cpu,
    title: 'AI Projections',
    text: 'Gradient-boosted models trained on returns, moving averages, volatility and company fundamentals.',
  },
  {
    icon: AreaChart,
    title: 'Upstox Market Data',
    text: 'Daily NSE price history and financial statements ingested server-side into InvestIQ.',
  },
  {
    icon: Newspaper,
    title: 'News Intelligence',
    text: 'Financial news classified by company and sector, so you see the stories that move your stocks.',
  },
];

export default function Landing() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleEnterTerminal = () => navigate(user ? '/dashboard' : '/login');

  return (
    <div className="min-h-screen w-full bg-[#050011] text-white font-sans overflow-x-hidden">
      <Navbar />

      <main className="px-6 md:px-16 pt-16 md:pt-28 pb-16">
        <motion.div initial="initial" animate="animate" variants={stagger(0.1, 0.12)} className="max-w-[1100px]">
          <motion.div variants={fadeUp}>
            <SectionLabel index="01" className="mb-6">Quantitative forecasting</SectionLabel>
          </motion.div>
          <motion.h1
            variants={fadeUp}
            className="text-[2.8rem] sm:text-[4rem] lg:text-[5.5rem] font-normal tracking-tight leading-[1]"
          >
            THE FUTURE OF STOCK FORECASTING.
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-8 text-[14px] md:text-[16px] text-gray-300 max-w-[560px] leading-[1.6]">
            Build watchlists, follow NSE price action and run machine learning inference, all inside one focused terminal.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-10">
            <PrimaryButton icon={ArrowRight} onClick={handleEnterTerminal}>
              {user ? 'Go to terminal' : 'Enter trading terminal'}
            </PrimaryButton>
          </motion.div>
        </motion.div>
      </main>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-px bg-gray-800 border-y border-gray-800">
        {features.map(({ icon: Icon, title, text }, i) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
            className="group bg-[#0a0a0a] p-8 md:p-10"
          >
            <div className="flex justify-between items-start mb-10">
              <span className="text-[10px] font-mono tracking-widest text-gray-500">0{i + 1}</span>
              <span className="flex items-center justify-center w-12 h-12 rounded-full border border-gray-600 text-gray-400 group-hover:bg-white group-hover:text-black group-hover:border-white transition-colors duration-300">
                <Icon size={20} />
              </span>
            </div>
            <h3 className="text-2xl font-medium tracking-tight mb-3">{title}</h3>
            <p className="text-sm text-gray-400 leading-relaxed font-light">{text}</p>
          </motion.div>
        ))}
      </section>

      <Footer />
    </div>
  );
}
