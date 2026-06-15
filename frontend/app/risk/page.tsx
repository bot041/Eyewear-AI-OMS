"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { formatOrderNumber } from "@/lib/utils";
import { Sidebar } from "@/components/sidebar";

export default function RiskPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch("/api/dashboard/risk-orders", {}, token).then(setOrders);
  }, [token]);

  const explain = async (order: any) => {
    const res = await apiFetch("/api/ai/explain-risk", {
      method: "POST",
      body: JSON.stringify({ order_id: order.id }),
    }, token);
    setSelected({ ...order, explanation: res.explanation });
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-slate-50 p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">AI Risk Center</h1>
          <p className="text-slate-500">SLA breach predictions, expected delays, and AI-generated explanations.</p>
        </header>

        <div className="grid gap-4">
          {orders.map((o) => (
            <div
              key={o.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-bold text-slate-900">{formatOrderNumber(o.order_number)}</h3>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        o.risk_score >= 80
                          ? "bg-red-100 text-red-700"
                          : o.risk_score >= 60
                          ? "bg-amber-100 text-amber-700"
                          : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      Risk {o.risk_score}%
                    </span>
                  </div>
                  <p className="text-sm text-slate-600">{o.customer_name} • {o.current_status}</p>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  <div>
                    <p className="text-xs text-slate-500">Predicted Completion</p>
                    <p className="font-semibold text-slate-900">{Math.round(Number(o.predicted_completion_hours))}h</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Expected Delay</p>
                    <p className="font-semibold text-red-600">+{Math.round(Number(o.expected_delay_hours))}h</p>
                  </div>
                  <button
                    onClick={() => explain(o)}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    Explain
                  </button>
                </div>
              </div>
            </div>
          ))}
          {orders.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
              No high-risk orders right now.
            </div>
          )}
        </div>

        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
              <h3 className="mb-1 text-lg font-bold text-slate-900">AI Explanation: {formatOrderNumber(selected.order_number)}</h3>
              <p className="mb-4 text-sm text-slate-500">
                Risk Score: <span className="font-semibold text-red-600">{selected.risk_score}%</span> • Expected Delay: +{Math.round(Number(selected.expected_delay_hours))}h
              </p>
              <div className="whitespace-pre-line rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
                {selected.explanation}
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
