import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Home } from './pages/Home'
import { Test } from './pages/Test'
import { History } from './pages/History'

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `text-sm font-mono px-3 py-1.5 rounded transition-colors ${
          isActive
            ? 'text-indigo-400 bg-indigo-500/10'
            : 'text-slate-400 hover:text-slate-200'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col" style={{ background: '#0a0a0f' }}>
        {/* Top nav */}
        <header
          className="border-b flex items-center px-6 py-3 gap-6"
          style={{ borderColor: '#1e1e2e', background: '#0d0d15' }}
        >
          <NavLink to="/" className="flex items-center gap-2 group">
            <span
              className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded"
              style={{ background: '#6366f1', color: '#fff' }}
            >
              PRB
            </span>
            <span className="text-sm font-mono font-semibold text-slate-200">PROBE</span>
          </NavLink>

          <nav className="flex items-center gap-1 ml-4">
            <NavItem to="/" label="Home" />
            <NavItem to="/history" label="History" />
          </nav>

          <div className="ml-auto">
            <span className="text-xs font-mono text-slate-600">v1.0.0</span>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1">
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
