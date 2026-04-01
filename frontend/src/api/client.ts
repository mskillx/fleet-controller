import axios from 'axios'
import type {
  CommandLog,
  DeploymentSummary,
  DeployRequest,
  DeployResponse,
  DeviceInfo,
  DeviceStat,
  Factory,
  UpdateJobStatus,
  UpdatePackage,
} from '../types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: API_BASE })

export const getDevices = (): Promise<DeviceInfo[]> =>
  api.get('/devices/').then((r) => r.data)

export const getFactories = (): Promise<Factory[]> =>
  api.get('/factories/').then((r) => r.data)

export const getDeviceStats = (id: string): Promise<DeviceStat> =>
  api.get(`/devices/${id}/stats`).then((r) => r.data)

export const getAllStats = (): Promise<DeviceInfo[]> =>
  api.get('/stats/').then((r) => r.data)

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

// ── OTA updates ───────────────────────────────────────────────────────────────

export const getPackages = (): Promise<UpdatePackage[]> =>
  api.get('/updates/').then((r) => r.data)

export const getLatestPackage = (): Promise<UpdatePackage> =>
  api.get('/updates/latest').then((r) => r.data)

export const uploadPackage = (version: string, file: File): Promise<UpdatePackage> => {
  const form = new FormData()
  form.append('file', file)
  return api
    .post(`/updates/?version=${encodeURIComponent(version)}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}

export const deactivatePackage = (version: string): Promise<void> =>
  api.delete(`/updates/${version}`).then(() => undefined)

export const deployPackage = (version: string, body: DeployRequest): Promise<DeployResponse> =>
  api.post(`/updates/${version}/deploy`, body).then((r) => r.data)

export const getDeployments = (): Promise<DeploymentSummary[]> =>
  api.get('/updates/deployments').then((r) => r.data)

export const getDeploymentJobs = (deployId: string): Promise<UpdateJobStatus[]> =>
  api.get(`/updates/deployments/${deployId}`).then((r) => r.data)

export const getDeviceUpdateJobs = (deviceId: string): Promise<UpdateJobStatus[]> =>
  api.get(`/updates/jobs/${deviceId}`).then((r) => r.data)
