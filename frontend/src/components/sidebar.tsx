"use client";

import {
  Calendar,
  FileText,
  Key,
  LayoutDashboard,
  LogOut,
  Newspaper,
  Settings,
  Share2,
  Sparkles,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { clearToken } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/niches", label: "Niche", icon: Sparkles },
  { href: "/keys", label: "API Keys", icon: Key },
  { href: "/socials", label: "Social Accounts", icon: Share2 },
  { href: "/topics", label: "Topics", icon: Newspaper },
  { href: "/posts", label: "Posts", icon: FileText },
  { href: "/schedule", label: "Schedule", icon: Calendar },
  { href: "/usage", label: "Cost & Usage", icon: Wallet },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-slate-200 bg-slate-50">
      <div className="flex h-16 items-center border-b border-slate-200 px-6">
        <Link href="/" className="flex flex-col text-slate-900">
          <span className="text-sm font-semibold leading-tight">Summit Automates</span>
          <span className="text-[10px] uppercase tracking-wider text-slate-500">Admin</span>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-slate-200 p-3">
        <button
          onClick={() => {
            clearToken();
            router.replace("/login");
          }}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
