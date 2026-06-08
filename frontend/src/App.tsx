import React from "react";
import { Activity, BatteryCharging, Bell, BookOpen, Bot, Brain, CalendarClock, Camera, Code2, Download, Focus, Gauge, Globe, LayoutDashboard, Menu, Settings, Shield, Sparkles, Workflow, X } from "lucide-react";
import { Dashboard } from "./pages/Dashboard";
import { Chat } from "./pages/Chat";
import { CodingAnalytics } from "./pages/CodingAnalytics";
import { Automations } from "./pages/Automations";
import { Memory } from "./pages/Memory";
import { SettingsPage } from "./pages/Settings";
import { WebsiteVault } from "./pages/WebsiteVault";
import { Alerts } from "./pages/Alerts";
import { BatteryHealth } from "./pages/BatteryHealth";
import { ResourceMonitor } from "./pages/ResourceMonitor";
import { Evolution } from "./pages/Evolution";
import { DailyBriefingPage } from "./pages/DailyBriefing";
import { FocusModePage } from "./pages/FocusMode";
import { StudyAssistant } from "./pages/StudyAssistant";
import { ProjectGuardian } from "./pages/ProjectGuardian";
import { DownloadManager } from "./pages/DownloadManager";
import { ScreenshotAssistant } from "./pages/ScreenshotAssistant";

const pages = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, component: Dashboard },
  { id: "chat", label: "Chat", icon: Bot, component: Chat },
  { id: "automation", label: "Automation", icon: Workflow, component: Automations },
  { id: "alerts", label: "Alerts", icon: Bell, component: Alerts },
  { id: "briefing", label: "Briefing", icon: CalendarClock, component: DailyBriefingPage },
  { id: "focus", label: "Focus Mode", icon: Focus, component: FocusModePage },
  { id: "study", label: "Study", icon: BookOpen, component: StudyAssistant },
  { id: "guardian", label: "Guardian", icon: Shield, component: ProjectGuardian },
  { id: "downloads", label: "Downloads", icon: Download, component: DownloadManager },
  { id: "screenshots", label: "Screenshots", icon: Camera, component: ScreenshotAssistant },
  { id: "battery", label: "Battery Health", icon: BatteryCharging, component: BatteryHealth },
  { id: "resources", label: "Resources", icon: Gauge, component: ResourceMonitor },
  { id: "evolution", label: "Evolution", icon: Sparkles, component: Evolution },
  { id: "websites", label: "Website Vault", icon: Globe, component: WebsiteVault },
  { id: "memory", label: "Memory", icon: Brain, component: Memory },
  { id: "coding", label: "Analytics", icon: Code2, component: CodingAnalytics },
  { id: "settings", label: "Settings", icon: Settings, component: SettingsPage }
] as const;

export function App() {
  const [active, setActive] = React.useState<(typeof pages)[number]["id"]>("dashboard");
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const Page = pages.find((page) => page.id === active)?.component ?? Dashboard;

  return (
    <div className="min-h-screen overflow-x-hidden bg-obsidian text-ink">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_20%_0%,rgba(242,184,75,0.20),transparent_28%),radial-gradient(circle_at_85%_18%,rgba(247,213,138,0.10),transparent_32%),linear-gradient(135deg,#080b12,#111827_52%,#090d16)]" />
      {sidebarOpen && <button className="fixed inset-0 z-30 bg-black/50 lg:hidden" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 max-w-[86vw] flex-col border-r border-amber-200/10 bg-black/45 backdrop-blur-2xl transition-transform duration-200 lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-20 items-center justify-between border-b border-amber-200/10 px-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-accent text-lg font-bold text-obsidian shadow-[0_0_32px_rgba(242,184,75,0.28)]">N</div>
            <div className="min-w-0">
              <div className="truncate text-lg font-semibold text-amber-100">Nexa</div>
              <div className="truncate text-xs text-amber-200/60">Personal AI Operating Agent</div>
            </div>
          </div>
          <button className="grid h-9 w-9 place-items-center rounded-lg text-slate-300 hover:bg-white/10 lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {pages.map((page) => {
            const Icon = page.icon;
            const selected = active === page.id;
            return (
              <button
                key={page.id}
                className={`flex h-11 w-full items-center gap-3 rounded-lg px-3 text-sm transition ${selected ? "bg-amber-300/15 text-accent shadow-[inset_0_0_0_1px_rgba(242,184,75,0.18)]" : "text-slate-300 hover:bg-white/10 hover:text-amber-100"}`}
                onClick={() => {
                  setActive(page.id);
                  setSidebarOpen(false);
                }}
              >
                <Icon size={18} className="shrink-0" />
                <span className="truncate">{page.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <div className="min-h-screen lg:pl-72">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-amber-200/10 bg-black/35 px-4 backdrop-blur-2xl sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button className="grid h-10 w-10 place-items-center rounded-lg text-slate-200 hover:bg-white/10 lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
              <Menu size={20} />
            </button>
            <div className="flex min-w-0 items-center gap-2 text-sm text-amber-100/80">
              <Activity size={16} className="shrink-0" />
              <span className="truncate">Nexa Dashboard</span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-xs text-amber-100/70 sm:text-sm">
            <span className="hidden items-center gap-2 sm:flex"><CalendarClock size={16} /> Scheduler online</span>
            <Bell size={16} />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-4 py-5 sm:px-6 lg:px-8">
          <Page />
        </main>
      </div>
    </div>
  );
}
