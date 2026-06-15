import { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  color?: string;
}

export function KPICard({ title, value, icon: Icon, trend, color = "bg-indigo-600" }: KPICardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <h3 className="mt-1 text-2xl font-bold text-slate-900">{value}</h3>
          {trend && <p className="mt-1 text-xs text-slate-500">{trend}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg text-white ${color}`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}
