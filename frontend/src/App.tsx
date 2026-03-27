import { Routes, Route } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import DeviceDetail from './components/DeviceDetail'

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="bg-surface border-b border-border px-6 py-4">
        <a href="/" className="text-xl font-bold text-text-primary tracking-wide">
          Fleet Controller
        </a>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices/:id" element={<DeviceDetail />} />
        </Routes>
      </main>
    </div>
  )
}
