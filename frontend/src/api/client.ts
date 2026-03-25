import axios from 'axios'
import type { CommandLog, DeviceInfo, DeviceStat } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: API_BASE })

export const getDevices = (): Promise<DeviceInfo[]> =>
  api.get('/devices').then((r) => r.data)

export const getDeviceStats = (id: string): Promise<DeviceStat> =>
  api.get(`/devices/${id}/stats`).then((r) => r.data)

export const getAllStats = (): Promise<DeviceInfo[]> =>
  api.get('/stats').then((r) => r.data)

export const getHistory = (deviceId?: string, limit = 50): Promise<DeviceStat[]> =>
  api
    .get('/stats/history', { params: { device_id: deviceId, limit } })
    .then((r) => r.data)

export const getCommands = (deviceId: string, limit = 20): Promise<CommandLog[]> =>
  api.get(`/devices/${deviceId}/commands`, { params: { limit } }).then((r) => r.data)

export const sendCommand = (
  deviceId: string,
  command: string,
  payload?: Record<string, unknown>,
): Promise<CommandLog> =>
  api.post(`/devices/${deviceId}/commands`, { command, payload }).then((r) => r.data)
