"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  UploadCloud, 
  Search, 
  MessageSquare, 
  ShieldAlert, 
  BarChart3, 
  History, 
  Settings, 
  LogOut, 
  User, 
  ChevronRight,
  Menu,
  X,
  FileSearch2,
  Activity,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<any>;
}

const navItems: NavItem[] = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Documents", href: "/dashboard/documents", icon: FileSearch2 },
  { name: "Upload", href: "/dashboard/upload", icon: UploadCloud },
  { name: "Processing", href: "/dashboard/processing", icon: Activity },
  { name: "Search", href: "/dashboard/search", icon: Search },
  { name: "Chat", href: "/dashboard/chat", icon: MessageSquare },
  { name: "Admin", href: "/dashboard/admin", icon: ShieldAlert },
  { name: "Analytics", href: "/dashboard", icon: BarChart3 },
  { name: "Audit Logs", href: "/dashboard", icon: History },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true); // Default dark mode optimized
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
      const token = typeof window !== "undefined" ? localStorage.getItem("docscope_token") : null;
      if (!token) {
          setProfileLoading(false);
          return;
      }
      try {
        const resp = await fetch("/api/v1/auth/me", {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (resp.ok) {
          const profile = await resp.json();
          setUserProfile(profile);
        } else if (resp.status === 401) {
          console.warn("Session expired. Redirecting to login...");
          localStorage.removeItem("docscope_token");
          window.location.href = "/login";
          return;
        }
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
  
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
    // In a real app we'd toggle dark class on document element
    if (typeof document !== "undefined") {
      document.documentElement.classList.toggle("light-mode");
    }
  };

  return (
    <>
      {/* Mobile Toggle Button */}
      <button 
        onClick={toggleSidebar}
        className="fixed top-4 left-4 z-50 md:hidden p-2 rounded-lg glass-panel text-zinc-400 hover:text-emerald-400"
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
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
              <FileSearch2 size={24} className="text-emerald-400 text-glow" />
            </div>
            {isOpen && (
              <span className="font-bold text-lg tracking-wider text-glow bg-gradient-to-r from-emerald-400 to-emerald-200 bg-clip-text text-transparent">
                DOCSCOPE
              </span>
            )}
          </Link>
          
          <button 
            onClick={toggleSidebar}
            className="hidden md:block p-1 rounded-md text-zinc-400 hover:text-emerald-400 hover:bg-white/5 transition-colors"
          >
            <ChevronRight size={16} className={`transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`} />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-200 group relative
                  ${isActive 
                    ? "bg-emerald-500/10 text-emerald-400 border-l-2 border-emerald-500 font-semibold" 
                    : "text-zinc-400 hover:text-emerald-400 hover:bg-white/5"
                  }
                `}
              >
                <Icon size={20} className={`${isActive ? "text-emerald-400" : "text-zinc-400 group-hover:text-emerald-400"} transition-colors`} />
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

        {/* Footer Settings & User Profile */}
        <div className="p-4 border-t border-white/5 space-y-3">
          {/* Theme Toggle & Collapse Support */}
          <div className="flex items-center justify-between px-2">
            {isOpen && <span className="text-xs text-zinc-500">Aesthetic theme</span>}
            <button 
              onClick={toggleTheme}
              className="p-2 rounded-lg text-zinc-400 hover:text-emerald-400 hover:bg-white/5 transition-colors"
              title="Toggle aesthetic theme"
            >
              {isDarkMode ? (
                <span className="text-sm flex items-center gap-2">🌙 {isOpen && "Dark Optimized"}</span>
              ) : (
                <span className="text-sm flex items-center gap-2">☀️ {isOpen && "Light Accent"}</span>
              )}
            </button>
          </div>

          {/* User Profile Popover Trigger */}
          <div className="relative">
            <button 
              onClick={toggleProfile}
              className="w-full flex items-center gap-3 p-2.5 rounded-xl hover:bg-white/5 transition-colors justify-between text-left"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold border border-emerald-500/30 shrink-0">
                  {profileLoading ? "..." : (userProfile 
                    ? `${userProfile.first_name?.[0] ?? ""}${userProfile.last_name?.[0] ?? ""}`.trim() || userProfile.email[0].toUpperCase() 
                    : "JD")}
                </div>
                {isOpen && (
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-zinc-200 truncate">
                      {profileLoading ? "Loading..." : (userProfile 
                        ? `${userProfile.first_name ?? ""} ${userProfile.last_name ?? ""}`.trim() || userProfile.email.split("@")[0] 
                        : "John Doe")}
                    </p>
                    <p className="text-[10px] text-zinc-500 truncate">{profileLoading ? "..." : (userProfile ? userProfile.role : "Org Admin")}</p>
                  </div>
                )}
              </div>
              {isOpen && <ChevronRight size={14} className="text-zinc-500" />}
            </button>

            {/* Profile Popover Menu */}
            {profileOpen && (
              <div className="absolute bottom-14 left-0 right-0 mx-2 bg-zinc-900 border border-white/10 rounded-2xl p-2.5 shadow-2xl z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <div className="px-2.5 py-1.5 border-b border-white/5 mb-1.5">
                  <p className="text-xs font-bold text-zinc-300">{profileLoading ? "Loading..." : (userProfile ? userProfile.organization_name : "Docscope Inc")}</p>
                  <p className="text-[10px] text-zinc-500 truncate">{profileLoading ? "..." : (userProfile ? userProfile.email : "john.doe@docscope.io")}</p>
                </div>
                <button className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-zinc-400 hover:text-emerald-400 hover:bg-white/5 rounded-lg transition-colors">
                  <User size={14} />
                  <span>My Profile</span>
                </button>
                <button className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-zinc-400 hover:text-emerald-400 hover:bg-white/5 rounded-lg transition-colors">
                  <Settings size={14} />
                  <span>Workspace Settings</span>
                </button>
                <div className="h-px bg-white/5 my-1.5" />
                <button 
                  onClick={() => {
                    localStorage.removeItem("docscope_token");
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
