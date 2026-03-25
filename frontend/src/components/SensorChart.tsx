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
        <CartesianGrid strokeDasharray="3 3" stroke="#061E29" />
        <XAxis dataKey="time" tick={{ fill: '#5F9598', fontSize: 11 }} />
        <YAxis tick={{ fill: '#5F9598', fontSize: 11 }} />
        <Tooltip
          contentStyle={{ backgroundColor: '#061E29', border: '1px solid rgba(95,149,152,0.4)' }}
          labelStyle={{ color: '#F3F4F4' }}
          itemStyle={{ color: '#F3F4F4' }}
        />
        <Legend wrapperStyle={{ color: '#5F9598' }} />
        <Line type="monotone" dataKey="Sensor 1" stroke="#5F9598" dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="Sensor 2" stroke="#93c5cf" dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="Sensor 3" stroke="#F3F4F4" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}
