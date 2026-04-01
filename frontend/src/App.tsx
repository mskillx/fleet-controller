import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import DeviceDetail from './components/DeviceDetail'
import UpdatesPage from './components/UpdatesPage'

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="bg-surface border-b border-border px-6 py-4 flex items-center gap-8">
        <a href="/" className="text-xl font-bold text-text-primary tracking-wide shrink-0">
          Fleet Controller
        </a>
        <div className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-secondary/15 text-secondary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-background'
              }`
            }
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/updates"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-secondary/15 text-secondary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-background'
              }`
            }
          >
            OTA Updates
          </NavLink>
        </div>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices/:id" element={<DeviceDetail />} />
          <Route path="/updates" element={<UpdatesPage />} />
        </Routes>
      </main>
    </div>
  )
}
