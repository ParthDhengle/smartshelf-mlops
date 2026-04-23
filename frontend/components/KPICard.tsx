import React from "react";

interface KPICardProps {
  label: string;
  value: string | number;
  icon: string;
  color: string;
  change?: string;
  index?: number;
}

export default function KPICard({ label, value, icon, color, change, index = 0 }: KPICardProps) {
  const isPositive = change?.startsWith("+");
  return (
    <div
      className={`kpi-card animate-in stagger-${index + 1}`}
      style={{ "--kpi-color": color } as React.CSSProperties}
    >
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {change && (
        <div className={`kpi-change ${isPositive ? "positive" : "negative"}`}>
          {isPositive ? "▲" : "▼"} {change}
        </div>
      )}
    </div>
  );
}
