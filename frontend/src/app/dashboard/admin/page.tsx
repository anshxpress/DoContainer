"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "../../../lib/apiClient";
import {
  Users, Shield, Building2, Plus, MoreHorizontal,
  Check, X, Search, Mail, UserCheck, ChevronDown, Loader2,
  Activity, Clock, Trash2, Save
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────

type AdminUser = { id: string; name: string; email: string; role: string; team: string; status: string; initials: string; joined: string };
type AdminTeam = { id: string; name: string; members: number; folders: number; acl: string };
type AdminPermission = { action: string; desc: string; roles: Record<string, boolean> };
type AuditLog = { id: string; user_id: string | null; ip_address: string | null; action: string; resource: string; metadata: string; created_at: string };
type RetentionPolicy = { id: string; name: string; folder_id: string | null; retain_days: number; auto_delete: boolean };

const ROLE_COLORS: Record<string, string> = {
  "Organization Admin": "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  "Team Admin":         "bg-blue-500/15 text-blue-400 border-blue-500/20",
  "Team Member":        "bg-zinc-700/50 text-zinc-300 border-zinc-600/20",
  "Viewer":             "bg-zinc-800/50 text-zinc-500 border-zinc-700/20",
};

type Tab = "users" | "teams" | "permissions" | "audit" | "retention";

// ─── Users Tab ────────────────────────────────────────────────────────────────

function UsersTab({ users }: { users: AdminUser[] }) {
  const [search, setSearch] = useState("");
  const filtered = users.filter(
    (u) =>
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search users…"
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-zinc-900/80 border border-white/8 text-zinc-300 placeholder-zinc-600 text-sm focus:outline-none focus:border-emerald-500/40 transition-all"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all">
          <Mail size={14} />
          Invite User
        </button>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden border border-white/5">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5 bg-zinc-900/40 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
              <th className="p-4 pl-5">User</th>
              <th className="p-4 hidden md:table-cell">Role</th>
              <th className="p-4 hidden lg:table-cell">Team</th>
              <th className="p-4 hidden lg:table-cell">Joined</th>
              <th className="p-4">Status</th>
              <th className="p-4 pr-5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((user) => (
              <tr key={user.id} className="hover:bg-white/[0.02] transition-colors group">
                <td className="p-4 pl-5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-200 shrink-0">
                      {user.initials}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-zinc-200 truncate">{user.name}</p>
                      <p className="text-xs text-zinc-500 truncate">{user.email}</p>
                    </div>
                  </div>
                </td>
                <td className="p-4 hidden md:table-cell">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${ROLE_COLORS[user.role] ?? "bg-zinc-800 text-zinc-400"}`}>
                    {user.role}
                  </span>
                </td>
                <td className="p-4 hidden lg:table-cell">
                  <span className="text-sm text-zinc-400">{user.team}</span>
                </td>
                <td className="p-4 hidden lg:table-cell">
                  <span className="text-xs text-zinc-500">{user.joined}</span>
                </td>
                <td className="p-4">
                  <span className={`flex items-center gap-1.5 text-[10px] font-semibold ${user.status === "active" ? "text-emerald-400" : "text-zinc-500"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${user.status === "active" ? "bg-emerald-400" : "bg-zinc-600"}`} />
                    {user.status}
                  </span>
                </td>
                <td className="p-4 pr-5 text-right">
                  <button className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors opacity-0 group-hover:opacity-100">
                    <MoreHorizontal size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-zinc-500 text-sm">No users found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Teams Tab ────────────────────────────────────────────────────────────────

function TeamsTab({ teams }: { teams: AdminTeam[] }) {
  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white text-sm font-semibold transition-all">
          <Plus size={14} />
          Create Team
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map((team) => (
          <div key={team.id} className="glass-panel p-5 rounded-2xl border border-white/5 hover:border-white/10 transition-colors">
            <div className="flex justify-between items-start mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
                <Building2 size={20} className="text-emerald-400" />
              </div>
              <button className="text-zinc-500 hover:text-zinc-300">
                <MoreHorizontal size={16} />
              </button>
            </div>
            <h3 className="text-base font-semibold text-zinc-200 mb-1">{team.name}</h3>
            <p className="text-xs text-zinc-500 mb-4">{team.acl} permissions</p>
            
            <div className="flex items-center gap-4 border-t border-white/5 pt-4 mt-auto">
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-0.5">Members</p>
                <p className="text-sm font-semibold text-zinc-300">{team.members}</p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-0.5">Folders</p>
                <p className="text-sm font-semibold text-zinc-300">{team.folders}</p>
              </div>
            </div>
          </div>
        ))}
        {teams.length === 0 && (
          <div className="col-span-full p-8 text-center text-zinc-500 text-sm">No teams found</div>
        )}
      </div>
    </div>
  );
}

// ─── Permissions Tab ──────────────────────────────────────────────────────────

function PermissionsTab({ permissions }: { permissions: AdminPermission[] }) {
  // Extract unique roles from the first permission object
  const roles = permissions.length > 0 ? Object.keys(permissions[0].roles) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Shield size={16} className="text-emerald-400" />
        <p className="text-sm text-zinc-400">
          Role-Permission matrix. Contact your Super Admin to modify permissions.
        </p>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden border border-white/5">
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[600px]">
            <thead>
              <tr className="border-b border-white/5 bg-zinc-900/50">
                <th className="p-4 pl-5 text-xs font-semibold text-zinc-400 min-w-[200px]">Permission</th>
                {roles.map((role) => (
                  <th key={role} className="p-4 text-[10px] font-semibold text-zinc-500 text-center uppercase tracking-wider whitespace-nowrap">
                    {role}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {permissions.map((perm) => (
                <tr key={perm.action} className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-4 pl-5">
                    <p className="text-xs font-semibold text-zinc-200">{perm.desc}</p>
                    <p className="text-[10px] font-mono text-zinc-600 mt-0.5">{perm.action}</p>
                  </td>
                  {roles.map((role) => (
                    <td key={role} className="p-4 text-center">
                      {perm.roles[role] ? (
                        <div className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/15">
                          <Check size={12} className="text-emerald-400" />
                        </div>
                      ) : (
                        <div className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-zinc-800">
                          <X size={12} className="text-zinc-600" />
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {permissions.length === 0 && (
                <tr>
                  <td colSpan={roles.length + 1} className="p-8 text-center text-zinc-500 text-sm">No permissions configured</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-zinc-600 italic">
        * Permissions are enforced server-side via the RBAC middleware. This matrix is read-only.
      </p>
    </div>
  );
}


// ─── Audit Logs Tab ──────────────────────────────────────────────────────────
function AuditTab({ logs }: { logs: AuditLog[] }) {
  const [search, setSearch] = useState("");
  const filtered = logs.filter((l) => l.action.toLowerCase().includes(search.toLowerCase()) || l.resource.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search audit logs..."
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-zinc-900/80 border border-white/8 text-zinc-300 placeholder-zinc-600 text-sm focus:outline-none focus:border-emerald-500/40 transition-all"
          />
        </div>
      </div>
      <div className="glass-panel rounded-2xl overflow-hidden border border-white/5">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5 bg-zinc-900/40 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
              <th className="p-4 pl-5">Timestamp</th>
              <th className="p-4">Action</th>
              <th className="p-4">User ID / IP</th>
              <th className="p-4">Resource</th>
              <th className="p-4">Metadata</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((log) => (
              <tr key={log.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="p-4 pl-5 text-xs text-zinc-400">{new Date(log.created_at).toLocaleString()}</td>
                <td className="p-4 text-xs font-semibold text-zinc-200">{log.action}</td>
                <td className="p-4 text-xs text-zinc-500">{log.user_id ? log.user_id.slice(0,8) : log.ip_address}</td>
                <td className="p-4 text-xs text-zinc-400 truncate max-w-[200px]" title={log.resource}>{log.resource}</td>
                <td className="p-4 text-[10px] font-mono text-zinc-500 truncate max-w-[200px]" title={log.metadata}>{log.metadata}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-zinc-500 text-sm">No audit logs found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Retention Policies Tab ──────────────────────────────────────────────────────────
function RetentionTab({ policies, onRefresh }: { policies: RetentionPolicy[], onRefresh: () => void }) {
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [days, setDays] = useState(30);
  const [autoDel, setAutoDel] = useState(false);

  const handleCreate = async () => {
    try {
      await apiClient.post("/api/v1/retention/policies", { name, retain_days: days, auto_delete: autoDel });
      setIsCreating(false);
      onRefresh();
    } catch (err) {}
  };

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-center">
        <p className="text-sm text-zinc-400">Manage data retention lifecycle policies.</p>
        <button onClick={() => setIsCreating(true)} className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all">
          <Plus size={14} /> Create Policy
        </button>
      </div>

      {isCreating && (
        <div className="glass-panel p-5 rounded-2xl border border-white/5 space-y-4 mb-4">
          <h3 className="text-sm font-semibold text-zinc-200">New Retention Policy</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Policy Name" className="bg-zinc-900/80 border border-white/8 text-sm px-3 py-2 rounded-lg text-white" />
            <input type="number" value={days} onChange={e => setDays(Number(e.target.value))} placeholder="Days to retain" className="bg-zinc-900/80 border border-white/8 text-sm px-3 py-2 rounded-lg text-white" />
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <input type="checkbox" checked={autoDel} onChange={e => setAutoDel(e.target.checked)} className="rounded border-zinc-700 bg-zinc-800" />
              Auto-delete (Hard Delete)
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setIsCreating(false)} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-white">Cancel</button>
            <button onClick={handleCreate} className="px-3 py-1.5 text-xs bg-emerald-600 rounded text-white">Save Policy</button>
          </div>
        </div>
      )}

      <div className="glass-panel rounded-2xl overflow-hidden border border-white/5">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5 bg-zinc-900/40 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
              <th className="p-4 pl-5">Policy Name</th>
              <th className="p-4">Retention Window</th>
              <th className="p-4">Action Type</th>
              <th className="p-4">Target Folder</th>
              <th className="p-4 text-right pr-5">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {policies.map(p => (
              <tr key={p.id} className="hover:bg-white/[0.02]">
                <td className="p-4 pl-5 text-sm font-semibold text-zinc-200">{p.name}</td>
                <td className="p-4 text-sm text-zinc-400">{p.retain_days} days</td>
                <td className="p-4 text-xs">
                  <span className={`px-2 py-1 rounded-md ${p.auto_delete ? 'bg-red-500/15 text-red-400' : 'bg-yellow-500/15 text-yellow-400'}`}>
                    {p.auto_delete ? 'Hard Delete' : 'Soft Expire'}
                  </span>
                </td>
                <td className="p-4 text-sm text-zinc-500">{p.folder_id ? p.folder_id.slice(0,8) : "Org-wide"}</td>
                <td className="p-4 text-right pr-5">
                  <button onClick={async () => {
                    try {
                      await apiClient.delete(`/api/v1/retention/policies/${p.id}`);
                      onRefresh();
                    } catch (e) {}
                  }} className="p-1.5 rounded-lg text-red-400 hover:bg-white/5"><Trash2 size={16} /></button>
                </td>
              </tr>
            ))}
            {policies.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-zinc-500 text-sm">No retention policies.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main Admin Page


const TABS = [
  { id: "users",       label: "Users",       icon: Users },
  { id: "teams",       label: "Teams",       icon: Building2 },
  { id: "permissions", label: "Permissions", icon: Shield },
  { id: "audit",       label: "Audit Logs",  icon: Activity },
  { id: "retention",   label: "Retention",   icon: Clock },
];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("users");
  const [loading, setLoading] = useState(true);
  
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [teams, setTeams] = useState<AdminTeam[]>([]);
  const [permissions, setPermissions] = useState<AdminPermission[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [retentionPolicies, setRetentionPolicies] = useState<RetentionPolicy[]>([]);

  useEffect(() => {
    const fetchAdminData = async () => {
      const token = localStorage.getItem("docscope_token");
      if (!token) {
        window.location.href = "/login";
        return;
      }
      
      try {
        const [usersData, teamsData, permsData, auditData, retData] = await Promise.all([
          apiClient.get("/api/v1/admin/users"),
          apiClient.get("/api/v1/admin/teams"),
          apiClient.get("/api/v1/admin/roles"),
          apiClient.get("/api/v1/admin/audit"),
          apiClient.get("/api/v1/retention/policies")
        ]);
        
        setUsers(Array.isArray(usersData) ? usersData : []);
        setTeams(Array.isArray(teamsData) ? teamsData : []);
        setPermissions(Array.isArray(permsData) ? permsData : []);
        setAuditLogs(Array.isArray(auditData) ? auditData : []);
        setRetentionPolicies(Array.isArray(retData) ? retData : []);
      } catch (err) {
        console.error("Failed to fetch admin data", err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchAdminData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <Loader2 className="animate-spin text-emerald-500" size={32} />
      </div>
    );
  }

  const activeUsersCount = users.filter((u) => u.status === "active").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Admin Dashboard
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Manage users, teams, and access control
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl glass-panel border border-white/5 text-xs text-zinc-400">
          <UserCheck size={14} className="text-emerald-400" />
          <span><strong className="text-zinc-200">{activeUsersCount}</strong> active members</span>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-1 border-b border-white/5 pb-0">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          let count = 0;
          if (tab.id === "users") count = users.length;
          if (tab.id === "teams") count = teams.length;
          
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold transition-all duration-200 border-b-2 -mb-px ${
                isActive
                  ? "text-emerald-400 border-emerald-400"
                  : "text-zinc-500 border-transparent hover:text-zinc-300 hover:border-white/20"
              }`}
            >
              <Icon size={15} />
              {tab.label}
              {tab.id !== "permissions" && (
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                  isActive ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-500"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === "users"       && <UsersTab users={users} />}
        {activeTab === "teams"       && <TeamsTab teams={teams} />}
        {activeTab === "permissions" && <PermissionsTab permissions={permissions} />}
        {activeTab === "audit"       && <AuditTab logs={auditLogs} />}
        {activeTab === "retention"   && <RetentionTab policies={retentionPolicies} onRefresh={() => window.location.reload()} />}
      </div>
    </div>
  );
}
