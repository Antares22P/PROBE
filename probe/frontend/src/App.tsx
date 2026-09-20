import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Home } from './pages/Home'
import { Test } from './pages/Test'
import { History } from './pages/History'

function NavTab({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `text-[10.5px] font-mono px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 uppercase tracking-wider ${
          isActive
            ? 'text-white bg-[#1e212b] border border-[#2e3240] font-semibold'
            : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#161820]'
        }`
      }
    >
      <span>{icon}</span>
      <span>{label}</span>
    </NavLink>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-[#0c0d11] text-[#d1d5db] font-mono selection:bg-indigo-600/30 selection:text-indigo-200">
        {/* Compact Web App Header Bar */}
        <header className="h-9 border-b border-[#1c1e27] bg-[#101117] sticky top-0 z-50 flex items-center px-3 justify-between select-none">
          <div className="flex items-center gap-4">
            {/* Console Logo */}
            <NavLink to="/" className="flex items-center gap-1.5 group">
              <span className="px-1 py-0.2 rounded bg-indigo-600 text-white font-bold text-[10px] tracking-widest">
                PRB
              </span>
              <span className="text-[11px] font-bold text-zinc-100 tracking-wider">PROBE.CONSOLE</span>
              <span className="text-[8.5px] px-1 py-0.2 rounded bg-[#1c1e27] text-zinc-400 border border-[#2b2e3c]">
                v1.0.0
              </span>
            </NavLink>

            {/* Navigation Tabs */}
            <nav className="flex items-center gap-1">
              <NavTab to="/" label="New Session" icon="[+]" />
              <NavTab to="/history" label="Archive" icon="[=]" />
            </nav>
          </div>

          {/* System Telemetry Chips */}
          <div className="flex items-center gap-3 text-[9.5px] text-zinc-400">
            <div className="hidden sm:flex items-center gap-2 border-r border-[#1f212c] pr-3">
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>PLAYWRIGHT: ONLINE</span>
              </span>
              <span className="text-zinc-600">/</span>
              <span className="text-indigo-300">GEMINI: READY</span>
            </div>

            <span className="text-zinc-500">SYS_OK</span>
          </div>
        </header>

        {/* Workspace Views */}
        <main className="flex-1 flex flex-col min-h-0">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/test/:id" element={<Test />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
