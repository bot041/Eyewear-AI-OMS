"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, ShoppingCart, Package, AlertTriangle, LogOut, Eye } from "lucide-react";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/orders", label: "Orders", icon: ShoppingCart },
  { href: "/risk", label: "Risk Center", icon: AlertTriangle },
  { href: "/inventory", label: "Inventory", icon: Package },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-3 border-b border-slate-200 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600 text-white">
          <Eye size={22} />
        </div>
        <div>
          <h2 className="font-bold text-slate-900">Eluno OMS</h2>
          <p className="text-xs text-slate-500">AI Powered</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {nav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4">
        <div className="mb-3 text-sm">
          <p className="font-medium text-slate-900">{user?.name}</p>
          <p className="text-xs text-slate-500 capitalize">{user?.role.replace("_", " ")}</p>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          <LogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
}
