export interface DeviceInfo {
  device_id: string
  last_seen: string
  sensor1: number
  sensor2: number
  sensor3: number
  version: string
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
  sensor1: number
  sensor2: number
  sensor3: number
  version?: string | null
  created_at?: string
}

export interface WsPayload {
  device_id: string
  timestamp: string
  sensor1: number
  sensor2: number
  sensor3: number
  version: string
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
