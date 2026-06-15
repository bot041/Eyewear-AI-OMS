"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { formatOrderNumber, formatSLARemaining } from "@/lib/utils";
import { Sidebar } from "@/components/sidebar";

const STATUSES = [
  "Order Placed",
  "Inventory Check",
  "Lens Manufacturing",
  "Coating",
  "Frame Assembly",
  "Quality Check",
  "QC Failed",
  "Rework",
  "Packaging",
  "Dispatch",
  "Delivered",
];

const LENS_TYPES = ["Single Vision", "Bifocal", "Progressive", "Computer Vision"];
const LOCATIONS = ["Bangalore", "Mumbai", "Delhi"];

export default function OrdersPage() {
  const { user, token } = useAuth();
  const [orders, setOrders] = useState<any[]>([]);
  const [filters, setFilters] = useState({ status: "", lens_type: "", store_location: "" });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [newStatus, setNewStatus] = useState("");
  const [reason, setReason] = useState("");

  const fetchOrders = async () => {
    if (!token) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.lens_type) params.append("lens_type", filters.lens_type);
    if (filters.store_location) params.append("store_location", filters.store_location);
    try {
      const data = await apiFetch(`/api/orders?${params.toString()}`, {}, token);
      setOrders(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [token, filters]);

  const updateStatus = async () => {
    if (!selected || !newStatus || !token) return;
    await apiFetch(`/api/orders/${selected.id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus, reason: reason || undefined }),
    }, token);
    setSelected(null);
    setNewStatus("");
    setReason("");
    fetchOrders();
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-slate-50 p-6">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Orders</h1>
            <p className="text-slate-500">Track and manage eyewear orders across the lifecycle.</p>
          </div>
        </header>

        <div className="mb-4 flex flex-wrap gap-3">
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={filters.lens_type}
            onChange={(e) => setFilters({ ...filters, lens_type: e.target.value })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Lens Type</option>
            {LENS_TYPES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={filters.store_location}
            onChange={(e) => setFilters({ ...filters, store_location: e.target.value })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Location</option>
            {LOCATIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-4 py-3">Order #</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Power</th>
                  <th className="px-4 py-3">Lens</th>
                  <th className="px-4 py-3">Coating</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">SLA Remaining</th>
                  <th className="px-4 py-3">Delay Reason</th>
                  <th className="px-4 py-3">Risk</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-indigo-600">{formatOrderNumber(o.order_number)}</td>
                    <td className="px-4 py-3">{o.customer_name}</td>
                    <td className="px-4 py-3">{o.power > 0 ? `+${o.power}` : o.power}</td>
                    <td className="px-4 py-3">{o.lens_type} ({o.lens_index})</td>
                    <td className="px-4 py-3">{o.coating}</td>
                    <td className="px-4 py-3">{o.store_location}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        {o.current_status}
                      </span>
                    </td>
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
                    <td className="px-4 py-3 max-w-xs truncate text-slate-600">
                      {o.delay_logs && o.delay_logs.length > 0
                        ? o.delay_logs[o.delay_logs.length - 1].reason
                        : "-"}
                    </td>
                    <td className="px-4 py-3">
                      {o.current_status === "Delivered" ? (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500">
                          -
                        </span>
                      ) : (
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
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => { setSelected(o); setNewStatus(o.current_status); }}
                        className="text-xs font-semibold text-indigo-600 hover:underline"
                      >
                        Update
                      </button>
                    </td>
                  </tr>
                ))}
                {orders.length === 0 && !loading && (
                  <tr><td colSpan={11} className="px-4 py-6 text-center text-slate-500">No orders found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
              <h3 className="mb-1 text-lg font-bold text-slate-900">Update Status</h3>
              <p className="mb-4 text-sm text-slate-500">{formatOrderNumber(selected.order_number)} - {selected.customer_name}</p>
              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">New Status</label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Delay Reason (optional)</label>
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Coating machine maintenance"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={updateStatus}
                    className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setSelected(null)}
                    className="flex-1 rounded-lg border border-slate-300 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
