import { useNavigate } from 'react-router-dom'
import type { DeviceInfo } from '../types'
import { Activity, Cpu, Thermometer, Zap } from 'lucide-react'

interface Props {
  device: DeviceInfo
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString()
}

export default function DeviceCard({ device }: Props) {
  const navigate = useNavigate()
  const isRecent = Date.now() - new Date(device.last_seen).getTime() < 10_000

  return (
    <div
      onClick={() => navigate(`/devices/${device.device_id}`)}
      className="bg-primary border border-secondary/30 rounded-xl p-5 cursor-pointer hover:border-secondary transition-all hover:shadow-lg hover:shadow-primary-dark/40"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-bg-light">{device.device_id}</h3>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium ${
            isRecent
              ? 'bg-secondary/20 text-secondary'
              : 'bg-primary-dark text-secondary/50'
          }`}
        >
          {isRecent ? 'Live' : 'Idle'}
        </span>
      </div>

      <div className="space-y-2">
        <SensorRow icon={<Cpu size={14} />} label="Sensor 1" value={device.sensor1} unit="%" />
        <SensorRow icon={<Thermometer size={14} />} label="Sensor 2" value={device.sensor2} unit="°C" />
        <SensorRow icon={<Zap size={14} />} label="Sensor 3" value={device.sensor3} unit="V" />
      </div>

      <p className="text-xs text-secondary/60 mt-4 flex items-center gap-1">
        <Activity size={12} />
        Last seen {formatTime(device.last_seen)}
      </p>
    </div>
  )
}

function SensorRow({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode
  label: string
  value: number
  unit: string
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-secondary flex items-center gap-1">
        {icon} {label}
      </span>
      <span className="text-bg-light font-mono">
        {value.toFixed(1)} {unit}
      </span>
    </div>
  )
}
