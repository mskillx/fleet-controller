import { Radio } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getDevices, getFactories } from '../api/client'
import type { DeviceInfo, Factory, WsMessage } from '../types'
import DeviceCard from './DeviceCard'

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('http', 'ws') + '/ws'

export default function Dashboard() {
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [factories, setFactories] = useState<Factory[]>([])
  const [selectedFactory, setSelectedFactory] = useState<string | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const fetchDevices = async () => {
    try {
      const data = await getDevices()
      console.log(data)
      setDevices(data)
    } catch (e) {
      console.error('Failed to fetch devices', e)
    }
  }

  const fetchFactories = async () => {
    try {
      const data = await getFactories()
      setFactories(data)
    } catch (e) {
      console.error('Failed to fetch factories', e)
    }
  }

  useEffect(() => {
    fetchDevices()
    fetchFactories()
    const interval = setInterval(fetchDevices, 5000)
    const factoryInterval = setInterval(fetchFactories, 10000)

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
              last_seen: msg.data.clock,
              current_version: msg.data.version ?? (idx >= 0 ? prev[idx].current_version : undefined),
              last_acquisition: msg.data.last_acquisition,
              last_boot: msg.data.last_boot,
              lights_on: msg.data.lights_on,
              disk_usage: msg.data.disk_usage,
              analysis_queue: msg.data.analysis_queue,
              is_camera_acquiring: msg.data.is_camera_acquiring,
              lidar: msg.data.lidar,
              com4: msg.data.com4,
              factory_name: idx >= 0 ? prev[idx].factory_name : undefined,
            }
            if (idx >= 0) {
              const next = [...prev]
              next[idx] = updated
              return next
            }
            return [...prev, updated]
          })
        } else if (msg.type === 'device_registered') {
          fetchFactories()
          fetchDevices()
        }
      }
    }

    connect()
    return () => {
      clearInterval(interval)
      clearInterval(factoryInterval)
      wsRef.current?.close()
    }
  }, [])

  const visibleDevices = selectedFactory
    ? devices.filter((d) => d.factory_name === selectedFactory)
    : devices

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Fleet Dashboard</h1>
          <p className="text-text-secondary text-sm mt-1">
            {visibleDevices.length} of {devices.length} devices
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Radio size={14} className={wsConnected ? 'text-secondary' : 'text-secondary/30'} />
          <span className={wsConnected ? 'text-secondary' : 'text-secondary/30'}>
            {wsConnected ? 'Live' : 'Polling'}
          </span>
        </div>
      </div>

      {factories.length > 0 && (
        <div className="flex gap-2 mb-6 flex-wrap">
          <button
            onClick={() => setSelectedFactory(null)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              selectedFactory === null
                ? 'bg-secondary text-background'
                : 'bg-surface border border-border text-text-secondary hover:border-secondary'
            }`}
          >
            All factories
          </button>
          {factories.map((f) => (
            <button
              key={f.id}
              onClick={() => setSelectedFactory(f.name)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                selectedFactory === f.name
                  ? 'bg-secondary text-background'
                  : 'bg-surface border border-border text-text-secondary hover:border-secondary'
              }`}
            >
              {f.name}
            </button>
          ))}
        </div>
      )}

      {visibleDevices.length === 0 ? (
        <div className="text-center text-text-secondary/60 py-20">
          <p>{devices.length === 0 ? 'Waiting for devices to connect...' : 'No devices in this factory.'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {visibleDevices.map((d) => (
            <DeviceCard key={d.device_id} device={d} />
          ))}
        </div>
      )}
    </div>
  )
}
