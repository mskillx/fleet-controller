import { ArrowLeft, CheckCircle, Clock, Eye, RefreshCw, Send, X, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getCommands, getHistory, sendCommand } from '../api/client'
import type { CommandLog, DeviceStat } from '../types'
import SensorChart from './SensorChart'

const PRESET_COMMANDS = ['ping', 'reboot', 'reset_sensors', 'report_full', 'update_software']

function StatusBadge({ status }: { status: CommandLog['status'] }) {
  if (status === 'executed')
    return (
      <span className="flex items-center gap-1 text-green-400 text-xs">
        <CheckCircle size={12} /> executed
      </span>
    )
  if (status === 'failed')
    return (
      <span className="flex items-center gap-1 text-red-400 text-xs">
        <XCircle size={12} /> failed
      </span>
    )
  return (
    <span className="flex items-center gap-1 text-yellow-400 text-xs">
      <Clock size={12} /> sent
    </span>
  )
}

export default function DeviceDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [activeTab, setActiveTab] = useState<'device' | 'command'>('device')
  const [history, setHistory] = useState<DeviceStat[]>([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [commands, setCommands] = useState<CommandLog[]>([])
  const [cmdInput, setCmdInput] = useState(PRESET_COMMANDS[0])
  const [payloadInput, setPayloadInput] = useState('')
  const [sending, setSending] = useState(false)
  const [cmdError, setCmdError] = useState('')
  const [selectedResponse, setSelectedResponse] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const fetchData = async (isInitial = false) => {
    if (!id) return
    try {
      const [hist, cmds] = await Promise.all([getHistory(id, 100), getCommands(id)])
      console.log(hist)
      setHistory(hist)
      setCommands(cmds)
    } finally {
      if (isInitial) setInitialLoading(false)
    }
  }

  // Poll stats + subscribe to WS command_response updates
  useEffect(() => {
    fetchData(true)
    const interval = setInterval(fetchData, 5000)

    const WS_URL =
      (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws') + '/ws'
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (id && msg.type === 'command_response' && msg.data.device_id === id) {
        getCommands(id).then(setCommands)
      }
    }
    ws.onerror = () => ws.close()

    return () => {
      clearInterval(interval)
      ws.close()
    }
  }, [id])

  const handleSend = async () => {
    if (!id || !cmdInput.trim()) return
    setCmdError('')

    let payload: Record<string, unknown> | undefined
    if (payloadInput.trim()) {
      try {
        payload = JSON.parse(payloadInput)
      } catch {
        setCmdError('Payload must be valid JSON')
        return
      }
    }

    setSending(true)
    try {
      const log = await sendCommand(id, cmdInput.trim(), payload)
      setCommands((prev) => [log, ...prev])
      setPayloadInput('')
    } catch {
      setCmdError('Failed to send command')
    } finally {
      setSending(false)
    }
  }

  const latest = history[0]

  const tabs = [
    { key: 'device', label: 'Device & Sensors' },
    { key: 'command', label: 'Send Command' },
  ] as const

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-secondary hover:text-bg-light transition-colors"
      >
        <ArrowLeft size={16} /> Back to Dashboard
      </button>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-bg-light">{id}</h1>
        <button
          onClick={() => fetchData()}
          className="flex items-center gap-2 text-sm text-bg-light bg-primary-dark hover:bg-primary border border-secondary/30 px-3 py-2 rounded-lg transition-colors"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-secondary/30">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? 'border-secondary text-bg-light'
                : 'border-transparent text-secondary hover:text-bg-light'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'device' && (
        <>
          {/* Latest sensor readings */}
          {latest && (
            <>
              <div className="grid grid-cols-3 gap-4">
                {(['sensor1', 'sensor2', 'sensor3'] as const).map((key, i) => (
                  <div key={key} className="bg-primary border border-secondary/30 rounded-xl p-4">
                    <p className="text-secondary text-sm mb-1">Sensor {i + 1}</p>
                    <p className="text-3xl font-bold text-bg-light font-mono">{latest[key].toFixed(2)}</p>
                    <p className="text-xs text-secondary/60 mt-2">
                      {new Date(latest.timestamp).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
              <div className="bg-primary border border-secondary/30 rounded-xl p-4 flex items-center gap-3">
                <span className="text-secondary text-sm">Software version</span>
                <span className="font-mono font-semibold text-bg-light">
                  {latest.version ?? '—'}
                </span>
              </div>
            </>
          )}

          {/* Sensor chart */}
          <div className="bg-primary border border-secondary/30 rounded-xl p-5">
            <h2 className="text-lg font-semibold text-bg-light mb-4">
              Sensor History{' '}
              <span className="text-sm text-secondary/60 font-normal">
                (last {history.length} readings)
              </span>
            </h2>
            <div className="relative">
              <SensorChart data={history} />
              {(initialLoading || history.length === 0) && (
                <div className="absolute inset-0 flex items-center justify-center bg-primary/80">
                  <p className="text-secondary/60">
                    {initialLoading ? 'Loading...' : 'No data available'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {activeTab === 'command' && (
        <>
          {/* Send command */}
          <div className="bg-primary border border-secondary/30 rounded-xl p-5">
            <h2 className="text-lg font-semibold text-bg-light mb-4">Send Command</h2>
            <div className="flex gap-3 mb-3">
              <div className="flex-1">
                <label className="text-xs text-secondary mb-1 block">Command</label>
                <input
                  list="cmd-presets"
                  value={cmdInput}
                  onChange={(e) => setCmdInput(e.target.value)}
                  placeholder="e.g. ping"
                  className="w-full bg-primary-dark border border-secondary/40 rounded-lg px-3 py-2 text-sm text-bg-light placeholder-secondary/40 focus:outline-none focus:border-secondary"
                />
                <datalist id="cmd-presets">
                  {PRESET_COMMANDS.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </div>
              <div className="flex-1">
                <label className="text-xs text-secondary mb-1 block">Payload (JSON, optional)</label>
                <input
                  value={payloadInput}
                  onChange={(e) => setPayloadInput(e.target.value)}
                  placeholder='{"key": "value"}'
                  className="w-full bg-primary-dark border border-secondary/40 rounded-lg px-3 py-2 text-sm text-bg-light placeholder-secondary/40 focus:outline-none focus:border-secondary"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleSend}
                  disabled={sending || !cmdInput.trim()}
                  className="flex items-center gap-2 bg-secondary hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed text-primary-dark font-medium text-sm px-4 py-2 rounded-lg transition-colors"
                >
                  <Send size={14} /> {sending ? 'Sending…' : 'Send'}
                </button>
              </div>
            </div>
            {cmdError && <p className="text-red-400 text-xs">{cmdError}</p>}
          </div>

          {/* Command history */}
          <div className="bg-primary border border-secondary/30 rounded-xl p-5">
            <h2 className="text-lg font-semibold text-bg-light mb-4">Command History</h2>
            {commands.length === 0 ? (
              <p className="text-secondary/60 text-sm text-center py-6">No commands sent yet</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-secondary text-left border-b border-secondary/30">
                    <th className="pb-2 font-medium">Command</th>
                    <th className="pb-2 font-medium">Payload</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Sent</th>
                    <th className="pb-2 font-medium">Responded</th>
                    <th className="pb-2 font-medium">Response</th>
                  </tr>
                </thead>
                <tbody>
                  {commands.slice(0, 10).map((c) => (
                    <tr key={c.id} className="border-b border-secondary/20 hover:bg-primary-dark/40">
                      <td className="py-2 font-mono text-bg-light">{c.command}</td>
                      <td className="py-2 text-secondary font-mono text-xs truncate max-w-[120px]">
                        {c.payload ?? '—'}
                      </td>
                      <td className="py-2">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-2 text-secondary/70">
                        {c.sent_at ? new Date(c.sent_at).toLocaleTimeString() : '—'}
                      </td>
                      <td className="py-2 text-secondary/70">
                        {c.responded_at ? new Date(c.responded_at).toLocaleTimeString() : '—'}
                      </td>
                      <td className="py-2">
                        {c.response ? (
                          <button
                            onClick={() => setSelectedResponse(c.response)}
                            className="flex items-center gap-1 text-xs text-secondary hover:text-bg-light transition-colors"
                          >
                            <Eye size={13} /> View
                          </button>
                        ) : (
                          <span className="text-secondary/40 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* Response modal */}
      {selectedResponse && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedResponse(null)}
        >
          <div
            className="bg-primary border border-secondary/30 rounded-xl p-5 w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-bg-light">Device Response</h3>
              <button
                onClick={() => setSelectedResponse(null)}
                className="text-secondary hover:text-bg-light transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <pre className="bg-primary-dark rounded-lg p-3 text-xs text-bg-light font-mono overflow-auto max-h-64">
              {JSON.stringify(JSON.parse(selectedResponse), null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
