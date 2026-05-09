import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Loader2,
} from "lucide-react";

const toneClass = {
  neutral: "text-slate-100",
  up: "text-up",
  down: "text-down",
  warn: "text-amber-300",
  info: "text-sky-300",
};

const noticeClass = {
  info: "border-sky-500/30 bg-sky-500/10 text-sky-100",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-100",
  error: "border-red-500/30 bg-red-500/10 text-red-100",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
};

export function PageHeader({ title, description, children, meta }) {
  return (
    <header className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-normal text-slate-50">
            {title}
          </h1>
          {meta}
        </div>
        {description && (
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
            {description}
          </p>
        )}
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </header>
  );
}

export function Panel({ title, description, actions, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-slate-800 bg-slate-900/70 ${className}`}>
      {(title || description || actions) && (
        <div className="flex flex-col gap-3 border-b border-slate-800 px-4 py-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            {title && (
              <h2 className="text-sm font-medium text-slate-200">{title}</h2>
            )}
            {description && (
              <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  unit,
  subValue,
  tone = "neutral",
  icon: Icon,
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-xs text-slate-500">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-slate-600" strokeWidth={1.8} />}
      </div>
      <div className={`font-mono text-xl font-semibold ${toneClass[tone] || toneClass.neutral}`}>
        {value}
        {unit && <span className="ml-1 text-xs font-normal text-slate-500">{unit}</span>}
      </div>
      {subValue && <div className="mt-2 text-xs text-slate-500">{subValue}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children, className = "" }) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={`flex items-start gap-2 rounded border px-3 py-2 text-xs ${noticeClass[tone] || noticeClass.info} ${className}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.8} />
      <div className="leading-5">{children}</div>
    </div>
  );
}

export function EmptyState({ title = "暂无数据", description, action }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-slate-800 bg-slate-950/40 px-4 py-8 text-center">
      <div className="text-sm font-medium text-slate-300">{title}</div>
      {description && (
        <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = "加载中..." }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.8} />
      <span>{label}</span>
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon: Icon,
  className = "",
  ...props
}) {
  const variants = {
    primary:
      "border-blue-500/60 bg-blue-600 text-white hover:bg-blue-500 disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500",
    secondary:
      "border-slate-700 bg-slate-800 text-slate-200 hover:border-slate-600 hover:bg-slate-700 disabled:text-slate-500",
    ghost:
      "border-transparent bg-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:text-slate-600",
    danger:
      "border-red-700/50 bg-red-950/40 text-red-300 hover:border-red-600 hover:bg-red-900/50 disabled:text-slate-600",
    success:
      "border-emerald-600/50 bg-emerald-600 text-white hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500",
  };
  const sizes = {
    sm: "h-8 px-2.5 text-xs",
    md: "h-9 px-3 text-sm",
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded border font-medium transition-colors ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {Icon && <Icon className="h-4 w-4" strokeWidth={1.8} />}
      <span>{children}</span>
    </button>
  );
}

export function SignalBadge({ type, children }) {
  const normalized = String(type || "").toUpperCase();
  if (normalized === "BUY") {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs font-semibold text-up">
        <ArrowUp className="h-3 w-3" strokeWidth={2} />
        {children || "BUY"}
      </span>
    );
  }
  if (normalized === "SELL") {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-down">
        <ArrowDown className="h-3 w-3" strokeWidth={2} />
        {children || "SELL"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-400">
      {children || normalized || "HOLD"}
    </span>
  );
}

export function TableShell({ children, minWidth = "720px" }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs" style={{ minWidth }}>
        {children}
      </table>
    </div>
  );
}
