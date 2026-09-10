import Navbar from "../components/Navbar"
import Logo from "../components/Logo"
import Category from "../components/Category"
import MarketTicker from "../components/MarketTicker"

export default function Home() {
    return(
        <>
        <div className="bg-[#050011] w-full text-white min-h-screen flex  font-sans">
            <div className=" flex flex-col items-center  w-full px-4 py-2 border-b border-[#333]">
                <Logo/>
                <Navbar/>
                <Category/>

                <MarketTicker/>
            </div>
        </div>
        </>
    )
}