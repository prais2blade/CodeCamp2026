import {
  LayoutDashboard,
  Users,
  ClipboardCheck,
  Bell,
  FileBarChart,
  Settings,
} from "lucide-react";

import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800">

      <div className="p-5 border-b border-slate-800">

        <h1 className="text-xl font-bold">
          CodeCamp
        </h1>

        <p className="text-sm text-slate-400">
          Attendance System
        </p>

      </div>

      <nav className="p-4 space-y-2">

        <Link
          to="/"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <LayoutDashboard size={18} />
          Dashboard
        </Link>

        <Link
          to="/students"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <Users size={18} />
          Students
        </Link>

        <Link
          to="/attendance"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <ClipboardCheck size={18} />
          Attendance
        </Link>

        <Link
          to="/notifications"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <Bell size={18} />
          Notifications
        </Link>

        <Link
          to="/reports"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <FileBarChart size={18} />
          Reports
        </Link>

        <Link
          to="/settings"
          className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800"
        >
          <Settings size={18} />
          Settings
        </Link>

      </nav>

    </aside>
  );
}