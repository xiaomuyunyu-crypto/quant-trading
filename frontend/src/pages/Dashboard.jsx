import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BriefcaseBusiness,
  CalendarClock,
  Database,
  FlaskConical,
  RefreshCw,
  Search,
  Star,
  TrendingUp,
} from "lucide-react";
import api from "../api/index";
import StockSearchInput, { formatStockLabel } from "../components/StockSearchInput";
import {
  Button,
  EmptyState,
  LoadingState,
  MetricCard,
  Notice,
  PageHeader,
  Panel,
  SignalBadge,
  TableShell,
} from "../components/WorkbenchUI";
import {
  compactDate,
  formatCurrency,
  formatNumber,
  formatPercent,
  toneByValue,
} from "../lib/format";

const MOCK_DASHBOARD = {
  watchlistCount: 213,
  totalStocks: 5258,
  totalKlines: 81037,
  todayPnL: 0,
  todayPnLPct: 0,
  totalEquity: 0,
  activeStrategies: 2,
  latestDataDate: "2026-05-08",
};

const MOCK_WATCHLIST = [
  { code: "000001", name: "平安银行", exchange: "SZ", industry: "银行", change_pct: 1.15 },
  { code: "600036", name: "招商银行", exchange: "SH", industry: "银行", change_pct: 0.5 },
  { code: "300750", name: "宁德时代", exchange: "SZ", industry: "新能源", change_pct: -1.2 },
  { code: "159915", name: "创业板ETF", exchange: "SZ", industry: "ETF", change_pct: 0.34 },
];

const MOCK_SIGNALS = [
  {
    id: "demo-1",
    code: "159915",
    name: "创业板ETF",
    signal_type: "BUY",
    confidence: 0.72,
    reason: "MACD绿柱缩短，RSI进入观察区",
  },
  {
    id: "demo-2",
    code: "300750",
    name: "宁德时代",
    signal_type: "SELL",
    confidence: 0.64,
    reason: "日线动能减弱，等待周线确认",
  },
];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [signals, setSignals] = useState([]);
  const [activeAccount, setActiveAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);
  const [stockInput, setStockInput] = useState("");
  const [selectedStock, setSelectedStock] = useState(null);
  const navigate = useNavigate();

  const loadDashboard = async () => {
    setLoading(true);
    setDemoMode(false);
    try {
      const [dashboardRes, watchlistRes, accountsRes, reviewRes] =
        await Promise.allSettled([
          api.get("/dashboard"),
          api.get("/watchlist"),
          api.get("/paper/accounts"),
          api.get("/paper/signals/review?status=pending"),
        ]);

      if (dashboardRes.status === "fulfilled") {
        setSummary(dashboardRes.value);
      } else {
        throw dashboardRes.reason;
      }

      setWatchlist(
        watchlistRes.status === "fulfilled" ? watchlistRes.value.items || [] : []
      );
      setSignals(
        reviewRes.status === "fulfilled" ? reviewRes.value.signals || [] : []
      );

      const accounts =
        accountsRes.status === "fulfilled" ? accountsRes.value.items || [] : [];
      const active = accounts.find((item) => item.status === "active") || accounts[0];
      if (active) {
        try {
          const detail = await api.get(`/paper/account/${active.id}`);
          setActiveAccount(detail);
        } catch {
          setActiveAccount({ account: active, positions: [], pending_signals: [] });
        }
      } else {
        setActiveAccount(null);
      }
    } catch {
      setDemoMode(true);
      setSummary(MOCK_DASHBOARD);
      setWatchlist(MOCK_WATCHLIST);
      setSignals(MOCK_SIGNALS);
      setActiveAccount(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const topWatchlist = useMemo(
    () => [...watchlist].slice(0, 8),
    [watchlist]
  );

  const pendingSignals =
    signals.length > 0
      ? signals
      : activeAccount?.pending_signals?.length
        ? activeAccount.pending_signals
        : [];

  const handleStockSelect = (stock) => {
    setSelectedStock(stock);
    setStockInput(formatStockLabel(stock));
    navigate(`/stock/${stock.code}`);
  };

  if (loading) {
    return <LoadingState label="正在整理今日决策中心..." />;
  }

  return (
    <div className="p-5">
      <PageHeader
        title="今日决策中心"
        description="先看数据是否新鲜，再处理信号，最后进入回测或实盘模拟。这个首页只保留每天真正会用的入口。"
        meta={
          <span className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-500">
            最新数据 {compactDate(summary?.latestDataDate)}
          </span>
        }
      >
        <div className="w-full min-w-[320px] lg:w-[460px]">
          <StockSearchInput
            value={stockInput}
            selectedStock={selectedStock}
            onChange={(value) => {
              setStockInput(value);
              setSelectedStock(null);
            }}
            onSelect={handleStockSelect}
            onSubmitCode={(code) => navigate(`/stock/${code}`)}
            placeholder="搜索标的，例如 万化 / 600309"
            helperText="选择候选项后进入标的分析"
          />
        </div>
      </PageHeader>

      {demoMode && (
        <Notice tone="warn" className="mb-4">
          后端未连接，当前展示演示数据。Vercel 预览环境可用这种状态做只读演示，本地启动 FastAPI 后会自动切换为真实数据。
        </Notice>
      )}

      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="自选股"
          value={formatNumber(summary?.watchlistCount)}
          unit="只"
          icon={Star}
        />
        <MetricCard
          label="K线数据"
          value={formatNumber(summary?.totalKlines)}
          unit="条"
          icon={Database}
        />
        <MetricCard
          label="模拟总权益"
          value={formatCurrency(summary?.totalEquity)}
          tone={toneByValue(summary?.todayPnL)}
          icon={BriefcaseBusiness}
        />
        <MetricCard
          label="今日盈亏"
          value={formatCurrency(summary?.todayPnL)}
          subValue={formatPercent(summary?.todayPnLPct, 2, true)}
          tone={toneByValue(summary?.todayPnL)}
          icon={TrendingUp}
        />
        <MetricCard
          label="活跃账户"
          value={formatNumber(summary?.activeStrategies)}
          unit="个"
          icon={CalendarClock}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel
          title="待处理交易信号"
          description="优先处理账户持仓或手动观察标的，不默认扫全市场。"
          actions={
            <>
              <Button icon={RefreshCw} onClick={() => navigate("/paper")}>
                分析观察股
              </Button>
              <Button variant="secondary" icon={FlaskConical} onClick={() => navigate("/backtest")}>
                进入回测
              </Button>
            </>
          }
        >
          {pendingSignals.length === 0 ? (
            <EmptyState
              title="暂无待确认信号"
              description="进入实盘模拟后可对当前持仓、自选股或手动标的生成信号。"
            />
          ) : (
            <div className="space-y-2">
              {pendingSignals.slice(0, 6).map((item) => (
                <button
                  key={`${item.id}-${item.code}`}
                  onClick={() => navigate(`/stock/${item.code}`)}
                  className="flex w-full items-center gap-3 rounded border border-slate-800 bg-slate-950/50 px-3 py-2.5 text-left transition-colors hover:border-slate-700 hover:bg-slate-900"
                >
                  <SignalBadge type={item.signal_type} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-slate-100">
                      {item.name || "未命名"}{" "}
                      <span className="font-mono text-xs text-slate-500">{item.code}</span>
                    </div>
                    <div className="mt-0.5 truncate text-xs text-slate-500">
                      {item.reason || "暂无理由"}
                    </div>
                  </div>
                  <div className="font-mono text-xs text-slate-500">
                    {Math.round((item.confidence || 0) * 100)}%
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-600" strokeWidth={1.8} />
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel
          title="当前模拟账户"
          description="用于记录你手动确认后的买卖、现金和持仓。"
          actions={
            <Button variant="secondary" icon={BriefcaseBusiness} onClick={() => navigate("/paper")}>
              查看账户
            </Button>
          }
        >
          {activeAccount ? (
            <div>
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold text-slate-100">
                    {activeAccount.account?.name}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {activeAccount.account?.status === "active" ? "运行中" : "已停止"} ·{" "}
                    {activeAccount.account?.strategy_key || "默认策略"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-lg text-slate-100">
                    {formatCurrency(activeAccount.total_equity)}
                  </div>
                  <div
                    className={`mt-1 font-mono text-xs ${
                      toneByValue(activeAccount.total_return_pct) === "up"
                        ? "text-up"
                        : toneByValue(activeAccount.total_return_pct) === "down"
                          ? "text-down"
                          : "text-slate-500"
                    }`}
                  >
                    {formatPercent(activeAccount.total_return_pct, 2, true)}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard
                  label="现金"
                  value={formatCurrency(activeAccount.account?.cash)}
                />
                <MetricCard
                  label="持仓"
                  value={formatNumber(activeAccount.positions?.length || 0)}
                  unit="只"
                />
              </div>
            </div>
          ) : (
            <EmptyState
              title="还没有活跃账户"
              description="创建一个模拟账户后，系统会把确认信号、持仓和交易记录串起来。"
              action={<Button onClick={() => navigate("/paper")}>创建账户</Button>}
            />
          )}
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel
          title="核心自选池"
          description="先从自选股里做观察和回测，避免一开始扫全市场。"
          actions={
            <Button variant="secondary" icon={Search} onClick={() => navigate("/watchlist")}>
              管理自选
            </Button>
          }
        >
          <TableShell minWidth="560px">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="px-2 py-2 font-normal">代码</th>
                <th className="px-2 py-2 font-normal">名称</th>
                <th className="px-2 py-2 font-normal">行业</th>
                <th className="px-2 py-2 text-right font-normal">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              {topWatchlist.map((stock) => (
                <tr
                  key={stock.code}
                  className="border-b border-slate-800/50 hover:bg-slate-900"
                >
                  <td className="px-2 py-2 font-mono text-slate-400">{stock.code}</td>
                  <td className="px-2 py-2">
                    <button
                      onClick={() => navigate(`/stock/${stock.code}`)}
                      className="text-slate-100 hover:text-blue-300"
                    >
                      {stock.name}
                    </button>
                  </td>
                  <td className="px-2 py-2 text-slate-500">{stock.industry || "-"}</td>
                  <td
                    className={`px-2 py-2 text-right font-mono ${
                      (stock.change_pct || 0) >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {formatPercent(stock.change_pct || 0, 2, true)}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Panel>

        <Panel
          title="策略研究入口"
          description="当前后端已有单股回测、策略对比和参数优化；下一步重点是把结果保存为可复盘的记忆。"
          actions={
            <Button icon={BarChart3} onClick={() => navigate("/backtest")}>
              打开回测
            </Button>
          }
        >
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded border border-slate-800 bg-slate-950/50 p-4">
              <div className="text-sm font-medium text-slate-200">单股回测</div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                按收盘价、满仓进出、忽略手续费，快速验证标的与策略。
              </p>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/50 p-4">
              <div className="text-sm font-medium text-slate-200">策略对比</div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                同一标的一次跑全部预设策略，按收益率和回撤排序。
              </p>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/50 p-4">
              <div className="text-sm font-medium text-slate-200">参数优化</div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                对均线或 MACD 参数做网格搜索，找出当前区间表现。
              </p>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
