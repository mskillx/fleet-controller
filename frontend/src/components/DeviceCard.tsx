import { Activity, Camera, Factory, GitCommit, HardDrive, Layers, Radio, Waves } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { DeviceInfo } from '../types'

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
      className="bg-surface border border-border rounded-xl p-5 cursor-pointer hover:border-secondary transition-all hover:shadow-lg hover:shadow-background/40"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-text-primary">{device.device_id}</h3>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium ${
            isRecent
              ? 'bg-secondary/20 text-secondary'
              : 'bg-background text-text-secondary/50'
          }`}
        >
          {isRecent ? 'Live' : 'Idle'}
        </span>
      </div>

      <div className="space-y-2">
        <StatusRow
          icon={<Radio size={14} />}
          label="Lights"
          value={device.lights_on == null ? '—' : device.lights_on ? 'ON' : 'OFF'}
          active={device.lights_on ?? false}
        />
        <StatusRow
          icon={<Camera size={14} />}
          label="Camera"
          value={device.is_camera_acquiring == null ? '—' : device.is_camera_acquiring ? 'Acquiring' : 'Idle'}
          active={device.is_camera_acquiring ?? false}
        />
        <MetricRow icon={<HardDrive size={14} />} label="Disk" value={device.disk_usage} unit="%" />
        <MetricRow icon={<Waves size={14} />} label="Lidar" value={device.lidar} unit=" mm" />
        <MetricRow icon={<Layers size={14} />} label="COM4" value={device.com4} unit="" />
        {device.analysis_queue != null && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary flex items-center gap-1">
              <Layers size={14} /> Queue
            </span>
            <span className="text-text-primary font-mono">{device.analysis_queue}</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3">
        {device.factory_name ? (
          <p className="text-xs text-text-secondary/50 flex items-center gap-1">
            <Factory size={12} />
            {device.factory_name}
          </p>
        ) : <span />}

        {device.current_version && (
          <span className="flex items-center gap-1 text-xs font-mono text-text-secondary/60 bg-background px-1.5 py-0.5 rounded">
            <GitCommit size={11} />
            v{device.current_version}
          </span>
        )}
      </div>

      <p className="text-xs text-text-secondary/60 mt-1 flex items-center gap-1">
        <Activity size={12} />
        Last seen {formatTime(device.last_seen)}
      </p>
    </div>
  )
}

function MetricRow({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode
  label: string
  value?: number | null
  unit: string
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-text-secondary flex items-center gap-1">
        {icon} {label}
      </span>
      <span className="text-text-primary font-mono">
        {value == null ? '—' : `${value.toFixed(1)}${unit}`}
      </span>
    </div>
  )
}

function StatusRow({
  icon,
  label,
  value,
  active,
}: {
  icon: React.ReactNode
  label: string
  value: string
  active: boolean
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-text-secondary flex items-center gap-1">
        {icon} {label}
      </span>
      <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${active ? 'text-secondary bg-secondary/10' : 'text-text-secondary/60'}`}>
        {value}
      </span>
    </div>
  )
}
