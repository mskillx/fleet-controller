import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { DeviceStat } from '../types'

interface Props {
  data: DeviceStat[]
}

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString()
}

const CHART_COLORS: Record<string, { grid: string; axis: string; tooltip: string; surface: string; text: string; lines: [string, string, string] }> = {
  blue: {
    grid: '#1F2937',
    axis: '#9CA3AF',
    tooltip: '#111827',
    surface: '#1F2937',
    text: '#E5E7EB',
    lines: ['#3B82F6', '#10B981', '#8B5CF6'],
  },
  orange: {
    grid: '#3D1F1F',
    axis: '#A07060',
    tooltip: '#1C0F0F',
    surface: '#3D1F1F',
    text: '#F5E6D8',
    lines: ['#F97316', '#EF4444', '#A855F7'],
  },
}

const colors = CHART_COLORS[import.meta.env.VITE_THEME ?? 'blue'] ?? CHART_COLORS.blue

export default function SensorChart({ data }: Props) {
  const chartData = [...data]
    .reverse()
    .map((d) => ({
      time: fmt(d.timestamp),
      'Sensor 1': d.sensor1,
      'Sensor 2': d.sensor2,
      'Sensor 3': d.sensor3,
    }))

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
        <XAxis dataKey="time" tick={{ fill: colors.axis, fontSize: 11 }} />
        <YAxis tick={{ fill: colors.axis, fontSize: 11 }} />
        <Tooltip
          contentStyle={{ backgroundColor: colors.tooltip, border: `1px solid ${colors.surface}` }}
          labelStyle={{ color: colors.text }}
          itemStyle={{ color: colors.text }}
        />
        <Legend wrapperStyle={{ color: colors.axis }} />
        <Line type="monotone" dataKey="Sensor 1" stroke={colors.lines[0]} dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="Sensor 2" stroke={colors.lines[1]} dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="Sensor 3" stroke={colors.lines[2]} dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}
