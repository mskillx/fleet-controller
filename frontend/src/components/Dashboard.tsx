import { useEffect, useState, useRef } from 'react'
import { getDevices } from '../api/client'
import DeviceCard from './DeviceCard'
import type { DeviceInfo, WsMessage } from '../types'
import { Radio } from 'lucide-react'

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('http', 'ws') + '/ws'

export default function Dashboard() {
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const fetchDevices = async () => {
    try {
      const data = await getDevices()
      setDevices(data)
    } catch (e) {
      console.error('Failed to fetch devices', e)
    }
  }

  useEffect(() => {
    fetchDevices()
    const interval = setInterval(fetchDevices, 5000)

    // WebSocket for real-time updates
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setWsConnected(true)
      ws.onclose = () => {
        setWsConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        const msg: WsMessage = JSON.parse(e.data)
        if (msg.type === 'stats_update') {
          setDevices((prev) => {
            const idx = prev.findIndex((d) => d.device_id === msg.data.device_id)
            const updated: DeviceInfo = {
              device_id: msg.data.device_id,
              last_seen: msg.data.timestamp,
              sensor1: msg.data.sensor1,
              sensor2: msg.data.sensor2,
              sensor3: msg.data.sensor3,
            }
            if (idx >= 0) {
              const next = [...prev]
              next[idx] = updated
              return next
            }
            return [...prev, updated]
          })
        }
      }
    }

    connect()
    return () => {
      clearInterval(interval)
      wsRef.current?.close()
    }
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-bg-light">Fleet Dashboard</h1>
          <p className="text-secondary text-sm mt-1">{devices.length} devices registered</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Radio size={14} className={wsConnected ? 'text-secondary' : 'text-secondary/30'} />
          <span className={wsConnected ? 'text-secondary' : 'text-secondary/30'}>
            {wsConnected ? 'Live' : 'Polling'}
          </span>
        </div>
      </div>

      {devices.length === 0 ? (
        <div className="text-center text-secondary/60 py-20">
          <p>Waiting for devices to connect...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {devices.map((d) => (
            <DeviceCard key={d.device_id} device={d} />
          ))}
        </div>
      )}
    </div>
  )
}
