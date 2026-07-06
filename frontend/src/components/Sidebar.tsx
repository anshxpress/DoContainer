"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { apiClient } from "../lib/apiClient";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  UploadCloud, 
  Search, 
  MessageSquare, 
  Settings, 
  LogOut, 
  User, 
  ChevronRight,
  Menu,
  X,
  FileSearch2,
  Star,
  Clock,
  // ─── Enterprise Feature Icons (Disabled in Personal Edition) ───────────────
  // ShieldAlert,   // Admin
  // BarChart3,     // Analytics
  // Activity,      // Processing / Monitoring
  // CheckCircle,   // Approvals
  // Bell,          // Notifications
  // Users,         // Teams
  // Building2,     // Organizations
  // ─────────────────────────────────────────────────────────────────────────
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<any>;
}

// ─── Personal Edition Navigation ──────────────────────────────────────────────
// Only core personal features are listed here.
// Enterprise items are preserved below in comments and can be restored by
// uncommenting them and adding them back to navItems[].
const navItems: NavItem[] = [
  { name: "Dashboard",  href: "/dashboard",           icon: LayoutDashboard },
  { name: "Documents",  href: "/dashboard/documents", icon: FileSearch2 },
  { name: "Upload",     href: "/dashboard/upload",    icon: UploadCloud },
  { name: "Search",     href: "/dashboard/search",    icon: Search },
  { name: "AI Chat",    href: "/dashboard/chat",      icon: MessageSquare },
  { name: "Favorites",  href: "/dashboard/favorites", icon: Star },
  { name: "Recent",     href: "/dashboard/recent",    icon: Clock },
  { name: "Settings",   href: "/dashboard/settings",  icon: Settings },
];

// ─── Enterprise Feature Navigation (Disabled in Personal Edition) ─────────────
// Restore these by adding them back into navItems[] above.
//
// { name: "Approvals",    href: "/dashboard/approvals",  icon: CheckCircle },
// { name: "Processing",   href: "/dashboard/processing", icon: Activity },
// { name: "Admin",        href: "/dashboard/admin",      icon: ShieldAlert },
// { name: "Analytics",    href: "/dashboard",            icon: BarChart3 },
// { name: "Teams",        href: "/dashboard/teams",      icon: Users },
// { name: "Organizations",href: "/dashboard/org",        icon: Building2 },
// { name: "Notifications",href: "/dashboard/notifications", icon: Bell },
// ─────────────────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);
  const [userProfile, setUserProfile] = useState<{
    first_name: string | null;
    last_name: string | null;
    email: string;
    organization_name: string;
    role: string;
  } | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const profile = await apiClient.get("/api/v1/auth/me");
        setUserProfile(profile);
      } catch (err) {
        console.warn("Failed to fetch user profile, using placeholders.", err);
      } finally {
        setProfileLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const toggleSidebar = () => setIsOpen(!isOpen);
  const toggleProfile = () => setProfileOpen(!profileOpen);

  return (
    <>
      {/* Mobile Toggle Button */}
      <button 
        onClick={toggleSidebar}
        className="fixed top-4 left-4 z-50 md:hidden p-2 rounded-lg glass-panel text-zinc-400 hover:text-[#82C8E5]"
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Sidebar Container */}
      <aside 
        className={`fixed inset-y-0 left-0 z-40 flex flex-col glass-panel transition-all duration-300 ease-in-out border-r border-white/5
          ${isOpen ? "w-64" : "w-20"} 
          ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-white/5 justify-between">
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="p-2 rounded-lg bg-[#0047AB]/10 text-[#82C8E5] group-hover:bg-[#0047AB]/20 transition-colors">
              <FileSearch2 size={24} className="text-[#82C8E5] text-glow" />
            </div>
            {isOpen && (
              <div className="min-w-0">
                <span className="block font-bold text-base tracking-wide text-glow bg-gradient-to-r from-[#82C8E5] to-[#dff0fc] bg-clip-text text-transparent">
                  DoContainer
                </span>
                <span className="block text-[10px] text-zinc-500 font-medium tracking-widest uppercase">
                  Personal
                </span>
              </div>
            )}
          </Link>
          
          <button 
            onClick={toggleSidebar}
            className="hidden md:block p-1 rounded-md text-zinc-400 hover:text-[#82C8E5] hover:bg-white/5 transition-colors"
          >
            <ChevronRight size={16} className={`transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`} />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-200 group relative
                  ${isActive 
                    ? "bg-[#0047AB]/10 text-[#82C8E5] border-l-2 border-[#0047AB] font-semibold" 
                    : "text-zinc-400 hover:text-[#82C8E5] hover:bg-white/5"
                  }
                `}
              >
                <Icon size={20} className={`${isActive ? "text-[#82C8E5]" : "text-zinc-400 group-hover:text-[#82C8E5]"} transition-colors`} />
                {isOpen && <span className="text-sm">{item.name}</span>}
                
                {/* Tooltip for collapsed sidebar */}
                {!isOpen && (
                  <div className="absolute left-16 scale-0 group-hover:scale-100 transition-all duration-200 origin-left bg-zinc-900 border border-white/10 px-3 py-1.5 rounded-lg text-xs text-zinc-200 z-50 whitespace-nowrap shadow-lg">
                    {item.name}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer: User Profile */}
        <div className="p-4 border-t border-white/5 space-y-3">
          <div className="relative">
            <button 
              onClick={toggleProfile}
              className="w-full flex items-center gap-3 p-2.5 rounded-xl hover:bg-white/5 transition-colors justify-between text-left"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-[#0047AB]/20 flex items-center justify-center text-[#82C8E5] font-bold border border-[#82C8E5]/20 shrink-0">
                  {profileLoading ? "…" : (userProfile 
                    ? `${userProfile.first_name?.[0] ?? ""}${userProfile.last_name?.[0] ?? ""}`.trim() || userProfile.email[0].toUpperCase() 
                    : "U")}
                </div>
                {isOpen && (
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-zinc-200 truncate">
                      {profileLoading ? "Loading…" : (userProfile 
                        ? `${userProfile.first_name ?? ""} ${userProfile.last_name ?? ""}`.trim() || userProfile.email.split("@")[0] 
                        : "User")}
                    </p>
                    <p className="text-[10px] text-zinc-500 truncate">
                      {profileLoading ? "…" : (userProfile ? userProfile.organization_name : "Personal Workspace")}
                    </p>
                  </div>
                )}
              </div>
              {isOpen && <ChevronRight size={14} className="text-zinc-500" />}
            </button>

            {/* Profile Popover Menu */}
            {profileOpen && (
              <div className="absolute bottom-14 left-0 right-0 mx-2 bg-zinc-900 border border-white/10 rounded-2xl p-2.5 shadow-2xl z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <div className="px-2.5 py-1.5 border-b border-white/5 mb-1.5">
                  <p className="text-xs font-bold text-zinc-300">
                    {profileLoading ? "Loading…" : (userProfile ? userProfile.organization_name : "Personal Workspace")}
                  </p>
                  <p className="text-[10px] text-zinc-500 truncate">
                    {profileLoading ? "…" : (userProfile ? userProfile.email : "")}
                  </p>
                </div>
                <button className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-zinc-400 hover:text-[#82C8E5] hover:bg-white/5 rounded-lg transition-colors">
                  <User size={14} />
                  <span>My Profile</span>
                </button>
                <button className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-zinc-400 hover:text-[#82C8E5] hover:bg-white/5 rounded-lg transition-colors">
                  <Settings size={14} />
                  <span>Settings</span>
                </button>
                <div className="h-px bg-white/5 my-1.5" />
                <button 
                  onClick={() => {
                    localStorage.removeItem("DoContainer_token");
                    window.location.href = "/login";
                  }}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                >
                  <LogOut size={14} />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
