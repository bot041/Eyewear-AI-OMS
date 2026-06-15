"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";
import { KPICard } from "@/components/kpi-card";
import { Package, AlertCircle, CheckCircle, Plus } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from "recharts";

const LENS_TYPES = ["Single Vision", "Bifocal", "Progressive", "Computer Vision"];
const COATINGS = ["Standard", "Anti-Glare", "Blue Cut", "Photochromic"];
const INDICES = [1.5, 1.56, 1.61, 1.67, 1.74];

interface InventoryItem {
  id: number;
  power: number;
  lens_type: string;
  lens_index: number;
  coating: string;
  quantity: number;
  forecast_demand: number;
  recommendation: string;
}

interface ConsumptionPoint {
  date: string;
  quantity: number;
}

export default function InventoryPage() {
  const { token, user } = useAuth();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [consumption, setConsumption] = useState<ConsumptionPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [procureItem, setProcureItem] = useState<InventoryItem | null>(null);
  const [procureQty, setProcureQty] = useState<number>(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState("");
  const [mounted, setMounted] = useState(false);
  const [newSku, setNewSku] = useState({
    power: "",
    lens_type: LENS_TYPES[0],
    lens_index: INDICES[0].toString(),
    coating: COATINGS[0],
    quantity: "0",
    forecast_demand: "0",
  });

  const canManage = user?.role === "admin" || user?.role === "operations_manager";

  const fetchItems = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [data, cons] = await Promise.all([
        apiFetch("/api/inventory/", {}, token),
        apiFetch("/api/inventory/consumption?days=30", {}, token),
      ]);
      setItems(data);
      setConsumption(cons);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    fetchItems();
  }, [token]);

  const updateStock = async (id: number, quantity: number) => {
    await apiFetch(`/api/inventory/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }, token);
    fetchItems();
  };

  const createSku = async () => {
    setCreateError("");
    const payload = {
      power: Number(newSku.power),
      lens_type: newSku.lens_type,
      lens_index: Number(newSku.lens_index),
      coating: newSku.coating,
      quantity: Number(newSku.quantity),
      forecast_demand: Number(newSku.forecast_demand),
    };
    try {
      await apiFetch("/api/inventory/", {
        method: "POST",
        body: JSON.stringify(payload),
      }, token);
      setNewSku({
        power: "",
        lens_type: LENS_TYPES[0],
        lens_index: INDICES[0].toString(),
        coating: COATINGS[0],
        quantity: "0",
        forecast_demand: "0",
      });
      setCreateOpen(false);
      fetchItems();
    } catch (err: any) {
      setCreateError(err.message || "Failed to create SKU");
    }
  };

  const restockCount = items.filter((i) => i.recommendation === "Restock").length;
  const overstockCount = items.filter((i) => i.recommendation === "Overstocked").length;
  const healthyCount = items.filter((i) => i.recommendation === "Healthy").length;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-slate-50 p-6">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Inventory Intelligence</h1>
            <p className="text-slate-500">Lens stock levels, demand forecast, and AI restock recommendations.</p>
          </div>
          {canManage && (
            <button
              onClick={() => setCreateOpen(true)}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              <Plus size={16} />
              Create SKU
            </button>
          )}
        </header>

        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <KPICard title="Healthy SKUs" value={healthyCount} icon={CheckCircle} color="bg-emerald-600" />
          <KPICard title="Restock Needed" value={restockCount} icon={AlertCircle} color="bg-red-600" />
          <KPICard title="Overstocked" value={overstockCount} icon={Package} color="bg-amber-600" />
        </div>

        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Inventory Consumption (Last 30 Days)</h3>
          <div className="h-64 w-full">
            {mounted && consumption.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={200}>
                <LineChart data={consumption} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  />
                  <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                  <RechartsTooltip
                    formatter={(value: any) => [`${value} units`, "Consumed"]}
                    labelFormatter={(label: any) => new Date(label).toLocaleDateString()}
                  />
                  <Line
                    type="monotone"
                    dataKey="quantity"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#4f46e5" }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                No consumption data available for the selected period.
              </div>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase">
                <tr>
                  <th className="px-4 py-3">Power</th>
                  <th className="px-4 py-3">Lens Type</th>
                  <th className="px-4 py-3">Index</th>
                  <th className="px-4 py-3">Coating</th>
                  <th className="px-4 py-3">Stock</th>
                  <th className="px-4 py-3">Forecast Demand</th>
                  <th className="px-4 py-3">Recommendation</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">{item.power > 0 ? `+${item.power}` : item.power}</td>
                    <td className="px-4 py-3">{item.lens_type}</td>
                    <td className="px-4 py-3">{item.lens_index}</td>
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
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {canManage && (
                          <>
                            {item.recommendation === "Restock" && (
                              <button
                                onClick={() => { setProcureItem(item); setProcureQty(Math.max(1, Math.round(item.forecast_demand * 2))); }}
                                className="rounded bg-indigo-600 px-2 py-1 text-xs font-semibold text-white hover:bg-indigo-700"
                              >
                                Procure
                              </button>
                            )}
                          </>
                        )}
                        {!canManage && <span className="text-xs text-slate-500">View only</span>}
                      </div>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && !loading && (
                  <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-500">No inventory found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {procureItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
              <h3 className="mb-1 text-lg font-bold text-slate-900">Procure Stock</h3>
              <p className="mb-4 text-sm text-slate-500">
                {procureItem.lens_type} ({procureItem.coating}) — Power {procureItem.power > 0 ? `+${procureItem.power}` : procureItem.power}
              </p>
              <div className="mb-6">
                <label className="mb-1 block text-sm font-medium text-slate-700">Quantity to add</label>
                <input
                  type="number"
                  min={1}
                  value={procureQty}
                  onChange={(e) => setProcureQty(Math.max(1, parseInt(e.target.value || "0", 10)))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={async () => {
                    if (procureQty > 0) {
                      await updateStock(procureItem.id, procureItem.quantity + procureQty);
                    }
                    setProcureItem(null);
                  }}
                  className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Procure
                </button>
                <button
                  onClick={() => setProcureItem(null)}
                  className="flex-1 rounded-lg border border-slate-300 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {createOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
              <h3 className="mb-1 text-lg font-bold text-slate-900">Create Inventory SKU</h3>
              <p className="mb-4 text-sm text-slate-500">Add a new lens configuration to inventory tracking.</p>
              {createError && (
                <div className="mb-4 rounded-lg bg-red-50 p-2 text-xs text-red-700">{createError}</div>
              )}
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Power</label>
                  <input
                    type="number"
                    step="0.25"
                    value={newSku.power}
                    onChange={(e) => setNewSku({ ...newSku, power: e.target.value })}
                    placeholder="-1.50"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Lens Index</label>
                  <select
                    value={newSku.lens_index}
                    onChange={(e) => setNewSku({ ...newSku, lens_index: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    {INDICES.map((i) => (
                      <option key={i} value={i}>{i}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Lens Type</label>
                  <select
                    value={newSku.lens_type}
                    onChange={(e) => setNewSku({ ...newSku, lens_type: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    {LENS_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Coating</label>
                  <select
                    value={newSku.coating}
                    onChange={(e) => setNewSku({ ...newSku, coating: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    {COATINGS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Initial Stock</label>
                  <input
                    type="number"
                    min={0}
                    value={newSku.quantity}
                    onChange={(e) => setNewSku({ ...newSku, quantity: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">Forecast Demand</label>
                  <input
                    type="number"
                    min={0}
                    value={newSku.forecast_demand}
                    onChange={(e) => setNewSku({ ...newSku, forecast_demand: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={createSku}
                  className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Create SKU
                </button>
                <button
                  onClick={() => { setCreateOpen(false); setCreateError(""); }}
                  className="flex-1 rounded-lg border border-slate-300 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
