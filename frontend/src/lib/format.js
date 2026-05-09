export function formatCurrency(value, digits = 2) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `¥${num.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function formatNumber(value, digits = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPercent(value, digits = 2, alreadyPercent = false) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  const pct = alreadyPercent ? num : num * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

export function toneByValue(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return "neutral";
  return num > 0 ? "up" : "down";
}

export function compactDate(value) {
  if (!value) return "-";
  return String(value).slice(0, 10);
}

export function stockName(stock) {
  if (!stock) return "-";
  return stock.name || stock.code || "-";
}
