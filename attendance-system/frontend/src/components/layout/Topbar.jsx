export default function Topbar() {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900 flex items-center justify-between px-6">

      <div>

        <h2 className="font-semibold text-lg">
          Dashboard
        </h2>

      </div>

      <div className="flex items-center gap-4">

        <span className="text-green-400">
          ● Online
        </span>

        <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center">
          A
        </div>

      </div>

    </header>
  );
}