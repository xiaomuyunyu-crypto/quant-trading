import { Outlet, NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  FlaskConical,
  LayoutDashboard,
  Settings,
  Star,
} from "lucide-react";
import { API_BASE_URL, API_MODE } from "../api/index";

const NAV = [
  { to: "/", label: "决策中心", icon: LayoutDashboard },
  { to: "/watchlist", label: "自选股", icon: Star },
  { to: "/backtest", label: "策略回测", icon: FlaskConical },
  { to: "/paper", label: "实盘模拟", icon: BriefcaseBusiness },
  { to: "/settings", label: "系统设置", icon: Settings },
];

const pageTitle = {
  "/": "今日决策中心",
  "/watchlist": "自选池管理",
  "/backtest": "策略回测工作台",
  "/paper": "实盘模拟跟踪",
  "/settings": "系统与部署",
};

export default function MainLayout() {
  const location = useLocation();
  const title =
    pageTitle[location.pathname] ||
    (location.pathname.startsWith("/stock/") ? "标的分析" : "量化工作台");

  return (
    <div className="flex h-screen overflow-hidden bg-white text-slate-950">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200 bg-blue-50 text-blue-600">
              <Activity className="h-5 w-5" strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-950">量化交易系统</div>
              <div className="mt-0.5 text-xs text-slate-500">双模式工作台</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex h-10 items-center gap-3 rounded px-3 text-sm transition-colors ${
                    isActive
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-100"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                  }`
                }
              >
                <Icon className="h-4 w-4" strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-slate-200 px-4 py-3">
          <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">API 模式</span>
              <span
                className={
                  API_MODE === "local-proxy" ? "text-emerald-300" : "text-sky-300"
                }
              >
              {API_MODE === "local-proxy" ? "本地代理" : "远程后端"}
              </span>
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-slate-600">
              {API_BASE_URL}
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-600">
            <BarChart3 className="h-3.5 w-3.5" strokeWidth={1.8} />
            <span>v0.1.0 · MVP</span>
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5">
          <div>
            <div className="text-sm font-medium text-slate-950">{title}</div>
            <div className="text-xs text-slate-600">
              本地完整交易辅助，Vercel 用于预览和演示
            </div>
          </div>
          <div className="hidden items-center gap-2 text-xs text-slate-500 md:flex">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>手动确认 · 收盘价记录 · 趋势优先</span>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
