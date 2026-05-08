import { Routes, Route } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import Dashboard from "./pages/Dashboard";
import Watchlist from "./pages/Watchlist";
import StockDetail from "./pages/StockDetail";
import Backtest from "./pages/Backtest";
import Paper from "./pages/Paper";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/stock/:code" element={<StockDetail />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/paper" element={<Paper />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
