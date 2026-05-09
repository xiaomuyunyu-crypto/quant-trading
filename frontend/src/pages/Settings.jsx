import { useEffect, useState } from "react";
import { Cloud, Database, ExternalLink, GitBranch, Server } from "lucide-react";
import api, { API_BASE_URL, API_MODE } from "../api/index";
import {
  Button,
  LoadingState,
  MetricCard,
  Notice,
  PageHeader,
  Panel,
} from "../components/WorkbenchUI";
import { formatNumber } from "../lib/format";

export default function Settings() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let canceled = false;
    async function load() {
      setLoading(true);
      setLoadError("");
      try {
        const [dashboardRes, healthRes] = await Promise.allSettled([
          api.get("/dashboard"),
          api.get("/health"),
        ]);
        if (canceled) return;
        if (dashboardRes.status === "fulfilled") setStats(dashboardRes.value);
        if (healthRes.status === "fulfilled") setHealth(healthRes.value);
        if (dashboardRes.status !== "fulfilled" && healthRes.status !== "fulfilled") {
          throw dashboardRes.reason || healthRes.reason;
        }
      } catch (e) {
        if (!canceled) setLoadError(e.message || "后端未连接");
      } finally {
        if (!canceled) setLoading(false);
      }
    }
    load();
    return () => {
      canceled = true;
    };
  }, []);

  return (
    <div className="p-5">
      <PageHeader
        title="系统与部署"
        description="本地完整使用，Vercel 提供随时随地访问的网址，Render 提供公网后端和持久化 SQLite。"
      />

      {loadError && (
        <Notice tone="warn" className="mb-4">
          当前前端没有连上后端：{loadError}。如果这是 Vercel 预览环境，请确认已设置 `VITE_API_BASE_URL`。
        </Notice>
      )}

      {loading ? (
        <LoadingState label="正在检查系统状态..." />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="总股票数" value={formatNumber(stats?.totalStocks)} icon={Database} />
            <MetricCard label="K线数据量" value={formatNumber(stats?.totalKlines)} icon={Database} />
            <MetricCard label="自选股" value={formatNumber(stats?.watchlistCount)} icon={GitBranch} />
            <MetricCard label="后端版本" value={health?.version || "-"} icon={Server} />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="API 连接" description="Vercel 线上环境必须指向公网后端，本地开发默认走 Vite 代理。">
              <div className="space-y-1 rounded border border-slate-800 bg-slate-950/50 p-4">
                <ConfigRow label="当前模式" value={API_MODE === "local-proxy" ? "本地代理" : "远程后端"} />
                <ConfigRow label="API Base URL" value={API_BASE_URL} mono />
                <ConfigRow label="健康检查" value={health?.status === "ok" ? "正常" : "未连接"} tone={health?.status === "ok" ? "success" : "danger"} />
                <ConfigRow label="数据最新日期" value={stats?.latestDataDate || "-"} />
              </div>
            </Panel>

            <Panel title="公网部署结构" description="这是当前项目最稳的随时访问方案。">
              <div className="space-y-3 text-sm text-slate-400">
                <DeployRow
                  icon={Cloud}
                  title="Vercel 前端"
                  description="部署 `frontend/`，构建命令 `npm run build`，输出目录 `dist`。"
                />
                <DeployRow
                  icon={Server}
                  title="Render 后端"
                  description="部署仓库根目录的 FastAPI 服务，`render.yaml` 会挂载持久盘到 `/var/data`。"
                />
                <DeployRow
                  icon={Database}
                  title="SQLite 持久化"
                  description="后端通过 `QUANT_DB_PATH=/var/data/quant.db` 保存数据库；后续可迁移 PostgreSQL。"
                />
              </div>
            </Panel>
          </div>

          <Panel title="部署后检查" description="第一次上线后按这个顺序验收。">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <CheckCard title="后端健康检查" text="打开 Render 域名的 /api/health，看到 ok。" />
              <CheckCard title="前端环境变量" text="Vercel 设置 VITE_API_BASE_URL 为 Render 后端域名。" />
              <CheckCard title="SPA 路由" text="直接刷新 /backtest、/paper、/stock/000001 不应 404。" />
              <CheckCard title="移动端访问" text="用手机流量打开 Vercel 域名，确认表格可横向滚动。" />
            </div>
          </Panel>

          <Panel title="外部入口">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                icon={ExternalLink}
                onClick={() => window.open(`${API_BASE_URL}/health`, "_blank")}
              >
                API 健康检查
              </Button>
              <Button
                variant="secondary"
                icon={ExternalLink}
                onClick={() => window.open(`${API_BASE_URL.replace(/\/api$/, "")}/docs`, "_blank")}
              >
                后端文档
              </Button>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

function ConfigRow({ label, value, mono, tone }) {
  const toneClass =
    tone === "success" ? "text-emerald-300" : tone === "danger" ? "text-red-300" : "text-slate-200";
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-800/60 py-2 last:border-b-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`truncate text-right text-xs ${mono ? "font-mono" : ""} ${toneClass}`}>
        {value}
      </span>
    </div>
  );
}

function DeployRow({ icon: Icon, title, description }) {
  return (
    <div className="flex gap-3 rounded border border-slate-800 bg-slate-950/50 p-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-blue-300" strokeWidth={1.8} />
      <div>
        <div className="text-sm font-medium text-slate-100">{title}</div>
        <div className="mt-1 text-xs leading-5 text-slate-500">{description}</div>
      </div>
    </div>
  );
}

function CheckCard({ title, text }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/50 p-3">
      <div className="text-sm font-medium text-slate-100">{title}</div>
      <div className="mt-2 text-xs leading-5 text-slate-500">{text}</div>
    </div>
  );
}
