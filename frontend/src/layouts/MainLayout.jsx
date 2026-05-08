import { Outlet, NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "仪表盘", icon: "📊" },
  { to: "/watchlist", label: "自选股", icon: "⭐" },
  { to: "/backtest", label: "策略回测", icon: "🧪" },
  { to: "/paper", label: "实盘模拟", icon: "💰" },
  { to: "/settings", label: "设置", icon: "⚙️" },
];

export default function MainLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* 左侧导航 */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="h-14 flex items-center px-5 border-b border-gray-800">
          <span className="text-lg font-bold tracking-wide text-white select-none">
            量化交易系统
          </span>
        </div>
        <nav className="flex-1 py-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 mx-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-gray-800 text-xs text-gray-600">
          v0.1.0 · MVP
        </div>
      </aside>

      {/* 右侧内容区 */}
      <main className="flex-1 overflow-hidden bg-gray-950 flex flex-col">
        <div className="flex-1 overflow-auto min-h-0">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
