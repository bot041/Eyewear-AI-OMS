"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { formatOrderNumber, formatSLARemaining } from "@/lib/utils";
import { Sidebar } from "@/components/sidebar";
import { KPICard } from "@/components/kpi-card";
import {
  ShoppingCart,
  AlertTriangle,
  Clock,
  Package,
  TrendingUp,
  Truck,
  Mail,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";

const COLORS = [
  "#4f46e5", "#06b6d4", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#64748b", "#84cc16"
];

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [mounted, setMounted] = useState(false);
  const [sendMailLoading, setSendMailLoading] = useState(false);
  const [sendMailMessage, setSendMailMessage] = useState("");

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch("/api/dashboard", {}, token)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [token]);

  const sendTestMail = async () => {
    if (!token) return;
    setSendMailLoading(true);
    setSendMailMessage("");
    try {
      const res = await apiFetch("/api/alerts/send-test", { method: "POST" }, token);
      setSendMailMessage(`Email ${res.status} for order ${res.order_id} (risk ${res.risk_score}%). ${res.message}`);
      // Refresh dashboard to update alerts table and KPI
      const updated = await apiFetch("/api/dashboard", {}, token);
      setData(updated);
    } catch (err: any) {
      setSendMailMessage(`Failed: ${err.message}`);
    } finally {
      setSendMailLoading(false);
    }
  };

  if (loading) return null;
  if (!user) return null;

  const statusData = data
    ? Object.entries(data.status_distribution).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-slate-50 p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Executive Dashboard</h1>
          <p className="text-slate-500">Real-time AI insights across orders, SLA risk, and inventory.</p>
        </header>

        {error && <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        {data && (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <KPICard title="Total Orders" value={data.kpis.total_orders} icon={ShoppingCart} color="bg-blue-600" />
              <KPICard title="Orders at Risk" value={data.kpis.orders_at_risk} icon={AlertTriangle} color="bg-red-600" />
              <KPICard title="SLA Breaches" value={data.kpis.sla_breaches} icon={Clock} color="bg-amber-600" />
              <KPICard title="Inventory Health" value={`${data.kpis.inventory_health_score}%`} icon={Package} color="bg-emerald-600" />
              <KPICard title="Forecast Accuracy" value={`${data.kpis.forecast_accuracy}%`} icon={TrendingUp} color="bg-violet-600" />
              <KPICard title="Procurement" value={data.kpis.procurement_requests} icon={Truck} color="bg-indigo-600" />
              <KPICard title="Email Alerts Sent Today" value={data.kpis.email_alerts_sent_today} icon={Mail} color="bg-rose-600" />
            </div>

            <div className="mb-6 flex flex-wrap items-center gap-4">
              <button
                onClick={sendTestMail}
                disabled={sendMailLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Mail className="h-4 w-4" />
                {sendMailLoading ? "Sending..." : "Send Mail to samasur018@gmail.com"}
              </button>
              {sendMailMessage && (
                <span className={`text-sm ${sendMailMessage.includes("Failed") ? "text-red-600" : "text-emerald-700"}`}>
                  {sendMailMessage}
                </span>
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-5">
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
                <h3 className="mb-4 text-lg font-semibold text-slate-900">AI Risk Center</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                      <tr>
                        <th className="px-4 py-2">Order</th>
                        <th className="px-4 py-2">Customer</th>
                        <th className="px-4 py-2">Risk</th>
                        <th className="px-4 py-2">Delay</th>
                        <th className="px-4 py-2">SLA Remaining</th>
                        <th className="px-4 py-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.risk_orders.map((o: any) => (
                        <tr key={o.id}>
                          <td className="px-4 py-3 font-medium text-indigo-600">{formatOrderNumber(o.order_number)}</td>
                          <td className="px-4 py-3 text-slate-700">{o.customer_name}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                o.risk_score >= 80
                                  ? "bg-red-100 text-red-700"
                                  : o.risk_score >= 60
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-emerald-100 text-emerald-700"
                              }`}
                            >
                              {o.risk_score}%
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-600">+{Math.round(Number(o.expected_delay_hours))}h</td>
                          <td className="px-4 py-3">
                            {(() => {
                              const sla = formatSLARemaining(Number(o.sla_time_remaining_hours ?? 0), o.current_status);
                              return (
                                <span
                                  title={`SLA target: ${o.sla_hours}h`}
                                  className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${
                                    sla.isOverdue
                                      ? "bg-red-100 text-red-700"
                                      : sla.isCritical
                                      ? "bg-amber-100 text-amber-700"
                                      : "bg-emerald-100 text-emerald-700"
                                  }`}
                                >
                                  {sla.text}
                                </span>
                              );
                            })()}
                          </td>
                          <td className="px-4 py-3 text-slate-600">{o.current_status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
                <h3 className="mb-4 text-lg font-semibold text-slate-900">Order Status Distribution</h3>
                <div className="flex flex-col items-center">
                  <div className="h-64 w-full min-w-0">
                    {mounted && (
                      <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={200}>
                        <PieChart>
                          <Pie
                            data={statusData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={55}
                            outerRadius={90}
                            paddingAngle={2}
                            labelLine={false}
                          >
                            {statusData.map((_: any, i: number) => (
                              <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                            ))}
                          </Pie>
                          <RechartsTooltip formatter={(value: any, name: any) => [`${value}`, `${name}`]} />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                  <div className="mt-4 flex flex-wrap justify-center gap-2">
                    {statusData.map((entry: any, i: number) => (
                      <div
                        key={entry.name}
                        className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs"
                      >
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: COLORS[i % COLORS.length] }}
                        />
                        <span className="font-medium text-slate-700">{entry.name}</span>
                        <span className="text-slate-500">({entry.value})</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-slate-900">Recent Alerts</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-4 py-2">Order ID</th>
                      <th className="px-4 py-2">Channel</th>
                      <th className="px-4 py-2">Recipient</th>
                      <th className="px-4 py-2">Risk Score</th>
                      <th className="px-4 py-2">Status</th>
                      <th className="px-4 py-2">Sent At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.recent_alerts && data.recent_alerts.length > 0 ? (
                      data.recent_alerts.map((alert: any) => (
                        <tr key={alert.id}>
                          <td className="px-4 py-3 font-medium text-indigo-600">{alert.order_id}</td>
                          <td className="px-4 py-3 text-slate-700">{alert.channel}</td>
                          <td className="px-4 py-3 text-slate-700">{alert.recipient}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                alert.risk_score >= 80
                                  ? "bg-red-100 text-red-700"
                                  : alert.risk_score >= 60
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-emerald-100 text-emerald-700"
                              }`}
                            >
                              {alert.risk_score}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                alert.status === "sent" || alert.status === "sent (mock)"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : alert.status === "failed"
                                  ? "bg-red-100 text-red-700"
                                  : "bg-amber-100 text-amber-700"
                              }`}
                            >
                              {alert.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-600">
                            {alert.sent_at ? new Date(alert.sent_at).toLocaleString() : "-"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="px-4 py-6 text-center text-slate-500">No alerts yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-slate-900">Inventory Intelligence</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="px-4 py-2">Power</th>
                      <th className="px-4 py-2">Lens Type</th>
                      <th className="px-4 py-2">Coating</th>
                      <th className="px-4 py-2">Stock</th>
                      <th className="px-4 py-2">Forecast</th>
                      <th className="px-4 py-2">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.inventory_summary.map((item: any) => (
                      <tr key={item.id}>
                        <td className="px-4 py-3">{item.power > 0 ? `+${item.power}` : item.power}</td>
                        <td className="px-4 py-3">{item.lens_type}</td>
                        <td className="px-4 py-3">{item.coating}</td>
                        <td className="px-4 py-3">{item.quantity}</td>
                        <td className="px-4 py-3">{item.forecast_demand}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                              item.recommendation === "Restock"
                                ? "bg-red-100 text-red-700"
                                : item.recommendation === "Overstocked"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-emerald-100 text-emerald-700"
                            }`}
                          >
                            {item.recommendation}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold text-slate-900">Order Source Analytics</h3>
              <div className="h-64 w-full">
                {mounted && (
                  <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={200}>
                    <BarChart
                      data={data.order_source_distribution ? Object.entries(data.order_source_distribution).map(([name, value]) => ({ name, value })) : []}
                      margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                      <RechartsTooltip formatter={(value: any, name: any) => [`${value}`, `${name}`]} />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {data.order_source_distribution && Object.entries(data.order_source_distribution).map((_: any, i: number) => (
                          <Cell key={`cell-source-${i}`} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
