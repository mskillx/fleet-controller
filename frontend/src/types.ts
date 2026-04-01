export interface DeviceInfo {
  device_id: string
  last_seen: string
  current_version?: string | null
  last_acquisition?: string | null
  last_boot?: string | null
  lights_on?: boolean | null
  disk_usage?: number | null
  analysis_queue?: number | null
  is_camera_acquiring?: boolean | null
  lidar?: number | null
  com4?: number | null
  factory_name?: string | null
}

export interface Factory {
  id: number
  name: string
  created_at?: string
}

export interface DeviceStat {
  id: number
  device_id: string
  timestamp: string
  last_acquisition?: string | null
  last_boot?: string | null
  lights_on?: boolean | null
  disk_usage?: number | null
  analysis_queue?: number | null
  is_camera_acquiring?: boolean | null
  lidar?: number | null
  com4?: number | null
  created_at?: string
}

export interface WsPayload {
  device_id: string
  clock: string
  version?: string | null
  last_acquisition?: string | null
  last_boot?: string | null
  lights_on?: boolean | null
  disk_usage?: number | null
  analysis_queue?: number | null
  is_camera_acquiring?: boolean | null
  lidar?: number | null
  com4?: number | null
}

export interface WsMessage {
  type: string
  data: WsPayload
}

export interface CommandLog {
  id: number
  command_id: string
  device_id: string
  command: string
  payload: string | null
  status: 'sent' | 'executed' | 'failed'
  response: string | null
  sent_at: string | null
  responded_at: string | null
}

// ── OTA update types ──────────────────────────────────────────────────────────

export interface UpdatePackage {
  id: number
  version: string
  filename: string
  checksum_sha256: string
  size_bytes: number | null
  is_active: boolean
  created_at: string | null
}

export type UpdateJobStatusValue =
  | 'pending'
  | 'downloading'
  | 'installing'
  | 'success'
  | 'failed'
  | 'rolledback'
  | 'aborted'

export interface UpdateJobStatus {
  id: number
  deploy_id: string
  device_id: string
  version: string
  batch_index: number
  status: UpdateJobStatusValue
  error_msg: string | null
  command_id: string | null
  started_at: string | null
  finished_at: string | null
}

export interface DeploymentSummary {
  deploy_id: string
  version: string
  total: number
  pending: number
  downloading: number
  installing: number
  success: number
  failed: number
  rolledback: number
  aborted: number
}

export interface DeployRequest {
  target: 'all' | string[]
  batch_size: number
  batch_delay_seconds: number
  success_threshold: number
}

export interface DeployResponse {
  deploy_id: string
  version: string
  total_devices: number
  batches: number
  message: string
}
