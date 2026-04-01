import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Download,
  Loader,
  RefreshCw,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  deactivatePackage,
  deployPackage,
  getDeploymentJobs,
  getDeployments,
  getDevices,
  getPackages,
  uploadPackage,
} from '../api/client'
import type {
  DeploymentSummary,
  DeployRequest,
  UpdateJobStatus,
  UpdateJobStatusValue,
  UpdatePackage,
} from '../types'


const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = API_BASE.replace('http', 'ws') + '/ws'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtBytes(n: number | null) {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleString()
}

function shortHash(h: string) {
  return h.slice(0, 12) + '…'
}

// ── status badge ──────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<UpdateJobStatusValue, string> = {
  pending: 'bg-warning/15 text-warning',
  downloading: 'bg-secondary/15 text-secondary',
  installing: 'bg-secondary/15 text-secondary',
  success: 'bg-success/15 text-success',
  failed: 'bg-error/15 text-error',
  rolledback: 'bg-warning/15 text-warning',
  aborted: 'bg-border text-text-secondary/50',
}

function JobStatusBadge({ status }: { status: UpdateJobStatusValue }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[status]}`}>
      {status}
    </span>
  )
}

// ── deployment progress bar ───────────────────────────────────────────────────

function DeploymentBar({ d }: { d: DeploymentSummary }) {
  const pct = (n: number) => (d.total > 0 ? Math.round((n / d.total) * 100) : 0)
  return (
    <div className="w-full h-2 bg-background rounded-full overflow-hidden flex gap-px">
      {d.success > 0 && (
        <div
          className="h-full bg-success rounded-l-full"
          style={{ width: `${pct(d.success)}%` }}
          title={`Success: ${d.success}`}
        />
      )}
      {d.failed + d.rolledback > 0 && (
        <div
          className="h-full bg-error"
          style={{ width: `${pct(d.failed + d.rolledback)}%` }}
          title={`Failed/Rolledback: ${d.failed + d.rolledback}`}
        />
      )}
      {d.downloading + d.installing > 0 && (
        <div
          className="h-full bg-secondary animate-pulse"
          style={{ width: `${pct(d.downloading + d.installing)}%` }}
          title={`In progress: ${d.downloading + d.installing}`}
        />
      )}
      {d.aborted > 0 && (
        <div
          className="h-full bg-border"
          style={{ width: `${pct(d.aborted)}%` }}
          title={`Aborted: ${d.aborted}`}
        />
      )}
    </div>
  )
}

// ── packages tab ──────────────────────────────────────────────────────────────

function PackagesTab() {
  const [packages, setPackages] = useState<UpdatePackage[]>([])
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () =>
    getPackages()
      .then(setPackages)
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const handleUpload = async () => {
    if (!version.trim() || !file) return
    setUploadError('')
    setUploading(true)
    try {
      await uploadPackage(version.trim(), file)
      setVersion('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      await load()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setUploadError(msg ?? 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDeactivate = async (ver: string) => {
    await deactivatePackage(ver)
    await load()
  }

  return (
    <div className="space-y-6">
      {/* Upload card */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-base font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Upload size={16} /> Upload Package
        </h2>
        <div className="flex gap-3 flex-wrap items-end">
          <div>
            <label className="text-xs text-text-secondary mb-1 block">Version</label>
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g. 1.2.3"
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-secondary/40 focus:outline-none focus:border-secondary w-36"
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary mb-1 block">ZIP file</label>
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm text-text-secondary file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-secondary/20 file:text-secondary hover:file:bg-secondary/30 cursor-pointer"
            />
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading || !version.trim() || !file}
            className="flex items-center gap-2 bg-secondary hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed text-background font-medium text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {uploading ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {uploadError && <p className="text-error text-xs mt-2">{uploadError}</p>}
      </div>

      {/* Packages table */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">Packages</h2>
          <button
            onClick={load}
            className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {loading ? (
          <p className="text-text-secondary/60 text-sm py-6 text-center">Loading…</p>
        ) : packages.length === 0 ? (
          <p className="text-text-secondary/60 text-sm py-6 text-center">No packages uploaded yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary text-left border-b border-border">
                <th className="pb-2 font-medium">Version</th>
                <th className="pb-2 font-medium">Size</th>
                <th className="pb-2 font-medium">SHA-256</th>
                <th className="pb-2 font-medium">Uploaded</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {packages.map((pkg, i) => (
                <tr key={pkg.id} className="border-b border-border/60 hover:bg-background/40">
                  <td className="py-2 font-mono font-semibold text-text-primary flex items-center gap-2">
                    {pkg.version}
                    {i === 0 && pkg.is_active && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-secondary/20 text-secondary font-medium">
                        latest
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-text-secondary font-mono">{fmtBytes(pkg.size_bytes)}</td>
                  <td className="py-2 text-text-secondary/60 font-mono text-xs" title={pkg.checksum_sha256}>
                    {shortHash(pkg.checksum_sha256)}
                  </td>
                  <td className="py-2 text-text-secondary/70">{fmtDate(pkg.created_at)}</td>
                  <td className="py-2">
                    {pkg.is_active ? (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-success/15 text-success font-medium">active</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-border text-text-secondary/50 font-medium">inactive</span>
                    )}
                  </td>
                  <td className="py-2">
                    <div className="flex items-center gap-3">
                      <a
                        href={`${API_BASE}/updates/${pkg.version}/download`}
                        download
                        className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
                      >
                        <Download size={13} /> Download
                      </a>
                      {pkg.is_active && (
                        <button
                          onClick={() => handleDeactivate(pkg.version)}
                          className="flex items-center gap-1 text-xs text-error/70 hover:text-error transition-colors"
                        >
                          <Trash2 size={13} /> Deactivate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── deploy tab ────────────────────────────────────────────────────────────────

function DeployTab({ onDeployed }: { onDeployed: (deployId: string) => void }) {
  const [packages, setPackages] = useState<UpdatePackage[]>([])
  const [deviceIds, setDeviceIds] = useState<string[]>([])
  const [selectedVersion, setSelectedVersion] = useState('')
  const [targetAll, setTargetAll] = useState(true)
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set())
  const [batchSize, setBatchSize] = useState(10)
  const [batchDelay, setBatchDelay] = useState(60)
  const [threshold, setThreshold] = useState(90)
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ deploy_id: string; message: string } | null>(null)

  useEffect(() => {
    getPackages().then((pkgs) => {
      const active = pkgs.filter((p) => p.is_active)
      setPackages(active)
      if (active.length > 0) setSelectedVersion(active[0].version)
    })
    getDevices().then((devs) => setDeviceIds(devs.map((d) => d.device_id)))
  }, [])

  const toggleDevice = (id: string) =>
    setSelectedDevices((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const handleDeploy = async () => {
    if (!selectedVersion) return
    setError('')
    setResult(null)
    setDeploying(true)
    try {
      const body: DeployRequest = {
        target: targetAll ? 'all' : Array.from(selectedDevices),
        batch_size: batchSize,
        batch_delay_seconds: batchDelay,
        success_threshold: threshold / 100,
      }
      const res = await deployPackage(selectedVersion, body)
      setResult({ deploy_id: res.deploy_id, message: res.message })
      onDeployed(res.deploy_id)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Deploy failed')
    } finally {
      setDeploying(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="bg-surface border border-border rounded-xl p-5 space-y-5">
        <h2 className="text-base font-semibold text-text-primary">Deploy Update</h2>

        {/* Package */}
        <div>
          <label className="text-xs text-text-secondary mb-1 block">Package version</label>
          {packages.length === 0 ? (
            <p className="text-sm text-error">No active packages available. Upload one first.</p>
          ) : (
            <select
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-secondary"
            >
              {packages.map((p) => (
                <option key={p.id} value={p.version}>
                  {p.version} ({fmtBytes(p.size_bytes)})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Target */}
        <div>
          <label className="text-xs text-text-secondary mb-2 block">Target devices</label>
          <div className="flex gap-4 mb-3">
            <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
              <input
                type="radio"
                checked={targetAll}
                onChange={() => setTargetAll(true)}
                className="accent-secondary"
              />
              All devices ({deviceIds.length})
            </label>
            <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
              <input
                type="radio"
                checked={!targetAll}
                onChange={() => setTargetAll(false)}
                className="accent-secondary"
              />
              Specific devices
            </label>
          </div>
          {!targetAll && (
            <div className="border border-border rounded-lg overflow-auto max-h-40 bg-background">
              {deviceIds.length === 0 ? (
                <p className="text-xs text-text-secondary/60 p-3">No devices registered</p>
              ) : (
                deviceIds.map((id) => (
                  <label
                    key={id}
                    className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface cursor-pointer text-sm text-text-primary border-b border-border/40 last:border-0"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDevices.has(id)}
                      onChange={() => toggleDevice(id)}
                      className="accent-secondary"
                    />
                    {id}
                  </label>
                ))
              )}
            </div>
          )}
        </div>

        {/* Batch settings */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-text-secondary mb-1 block">Batch size</label>
            <input
              type="number"
              min={1}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-secondary"
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary mb-1 block">
              Delay between batches (s)
            </label>
            <input
              type="number"
              min={0}
              value={batchDelay}
              onChange={(e) => setBatchDelay(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-secondary"
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary mb-1 block">
              Success threshold (%)
            </label>
            <input
              type="number"
              min={0}
              max={100}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-secondary"
            />
            <p className="text-xs text-text-secondary/50 mt-1">
              Next batch triggers only if ≥{threshold}% of current batch succeeds
            </p>
          </div>
        </div>

        {error && (
          <p className="flex items-center gap-1 text-error text-sm">
            <AlertTriangle size={14} /> {error}
          </p>
        )}

        <button
          onClick={handleDeploy}
          disabled={deploying || !selectedVersion || (!targetAll && selectedDevices.size === 0)}
          className="flex items-center gap-2 bg-secondary hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed text-background font-medium text-sm px-5 py-2 rounded-lg transition-colors"
        >
          {deploying ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
          {deploying ? 'Deploying…' : 'Deploy'}
        </button>

        {result && (
          <div className="bg-success/10 border border-success/30 rounded-lg p-3 text-sm text-success">
            <p className="font-medium">{result.message}</p>
            <p className="text-xs mt-1 font-mono opacity-70">Deploy ID: {result.deploy_id}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── deployments tab ───────────────────────────────────────────────────────────

function DeploymentsTab({
  highlightId,
  wsUpdateCount,
}: {
  highlightId: string | null
  wsUpdateCount: number
}) {
  const [deployments, setDeployments] = useState<DeploymentSummary[]>([])
  const [expanded, setExpanded] = useState<string | null>(highlightId)
  const [jobs, setJobs] = useState<Record<string, UpdateJobStatus[]>>({})
  const [loading, setLoading] = useState(true)
  const expandedRef = useRef(expanded)
  expandedRef.current = expanded

  const loadSummaries = () =>
    getDeployments()
      .then(setDeployments)
      .finally(() => setLoading(false))

  const refreshExpandedJobs = (deployId: string) =>
    getDeploymentJobs(deployId).then((j) =>
      setJobs((prev) => ({ ...prev, [deployId]: j })),
    )

  // Initial load
  useEffect(() => { loadSummaries() }, [])

  // Auto-expand newly triggered deployment
  useEffect(() => {
    if (highlightId) setExpanded(highlightId)
  }, [highlightId])

  // Re-fetch on every WS update_status event
  useEffect(() => {
    if (wsUpdateCount === 0) return
    loadSummaries()
    if (expandedRef.current) refreshExpandedJobs(expandedRef.current)
  }, [wsUpdateCount])

  // Polling while any deployment is still active (3 s)
  useEffect(() => {
    const hasActive = deployments.some(
      (d) => d.pending + d.downloading + d.installing > 0,
    )
    if (!hasActive) return
    const id = setInterval(() => {
      loadSummaries()
      if (expandedRef.current) refreshExpandedJobs(expandedRef.current)
    }, 3000)
    return () => clearInterval(id)
  }, [deployments])

  const toggleExpand = async (deployId: string) => {
    if (expanded === deployId) {
      setExpanded(null)
      return
    }
    setExpanded(deployId)
    // Always fetch fresh jobs when expanding
    const j = await getDeploymentJobs(deployId)
    setJobs((prev) => ({ ...prev, [deployId]: j }))
  }

  const inProgress = (d: DeploymentSummary) =>
    d.downloading + d.installing + d.pending > 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-text-primary">Deployment History</h2>
        <button
          onClick={loadSummaries}
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-text-secondary/60 text-sm py-8 text-center">Loading…</p>
      ) : deployments.length === 0 ? (
        <p className="text-text-secondary/60 text-sm py-8 text-center">No deployments yet</p>
      ) : (
        deployments.map((d) => (
          <div
            key={d.deploy_id}
            className={`bg-surface border rounded-xl overflow-hidden transition-colors ${
              d.deploy_id === highlightId ? 'border-secondary' : 'border-border'
            }`}
          >
            {/* Summary row */}
            <button
              onClick={() => toggleExpand(d.deploy_id)}
              className="w-full flex items-center gap-4 p-4 hover:bg-background/40 transition-colors text-left"
            >
              {expanded === d.deploy_id ? (
                <ChevronDown size={16} className="text-text-secondary shrink-0" />
              ) : (
                <ChevronRight size={16} className="text-text-secondary shrink-0" />
              )}

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3 mb-1 flex-wrap">
                  <span className="font-mono font-semibold text-text-primary">v{d.version}</span>
                  <span className="font-mono text-xs text-text-secondary/50 truncate">
                    {d.deploy_id}
                  </span>
                  {inProgress(d) && (
                    <span className="flex items-center gap-1 text-xs text-secondary">
                      <Loader size={11} className="animate-spin" /> in progress
                    </span>
                  )}
                </div>
                <DeploymentBar d={d} />
              </div>

              {/* Pill counters */}
              <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
                {d.success > 0 && (
                  <Pill color="success" icon={<CheckCircle size={11} />} label={`${d.success} ok`} />
                )}
                {d.failed + d.rolledback > 0 && (
                  <Pill
                    color="error"
                    icon={<XCircle size={11} />}
                    label={`${d.failed + d.rolledback} err`}
                  />
                )}
                {d.downloading + d.installing > 0 && (
                  <Pill
                    color="secondary"
                    icon={<Loader size={11} className="animate-spin" />}
                    label={`${d.downloading + d.installing} active`}
                  />
                )}
                {d.pending > 0 && (
                  <Pill color="warning" icon={null} label={`${d.pending} pending`} />
                )}
                {d.aborted > 0 && (
                  <Pill color="muted" icon={null} label={`${d.aborted} aborted`} />
                )}
              </div>
            </button>

            {/* Expanded job table */}
            {expanded === d.deploy_id && (
              <div className="border-t border-border px-4 pb-4 pt-3">
                {!jobs[d.deploy_id] ? (
                  <p className="text-text-secondary/60 text-sm py-4 text-center">Loading…</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-text-secondary text-left border-b border-border">
                        <th className="pb-2 font-medium">Device</th>
                        <th className="pb-2 font-medium">Batch</th>
                        <th className="pb-2 font-medium">Status</th>
                        <th className="pb-2 font-medium">Error</th>
                        <th className="pb-2 font-medium">Started</th>
                        <th className="pb-2 font-medium">Finished</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs[d.deploy_id].map((j) => (
                        <tr key={j.id} className="border-b border-border/50 hover:bg-background/40">
                          <td className="py-1.5 font-mono text-text-primary">{j.device_id}</td>
                          <td className="py-1.5 text-text-secondary text-center">{j.batch_index}</td>
                          <td className="py-1.5">
                            <JobStatusBadge status={j.status} />
                          </td>
                          <td
                            className="py-1.5 text-xs text-error/80 max-w-[200px] truncate"
                            title={j.error_msg ?? undefined}
                          >
                            {j.error_msg ?? '—'}
                          </td>
                          <td className="py-1.5 text-text-secondary/70 text-xs">
                            {j.started_at ? new Date(j.started_at).toLocaleTimeString() : '—'}
                          </td>
                          <td className="py-1.5 text-text-secondary/70 text-xs">
                            {j.finished_at ? new Date(j.finished_at).toLocaleTimeString() : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function Pill({
  color,
  icon,
  label,
}: {
  color: 'success' | 'error' | 'secondary' | 'warning' | 'muted'
  icon: React.ReactNode
  label: string
}) {
  const cls = {
    success: 'bg-success/15 text-success',
    error: 'bg-error/15 text-error',
    secondary: 'bg-secondary/15 text-secondary',
    warning: 'bg-warning/15 text-warning',
    muted: 'bg-border text-text-secondary/50',
  }[color]
  return (
    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {icon}
      {label}
    </span>
  )
}

// ── page root ─────────────────────────────────────────────────────────────────

type Tab = 'packages' | 'deploy' | 'deployments'

export default function UpdatesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('packages')
  const [highlightDeployId, setHighlightDeployId] = useState<string | null>(null)
  const [wsUpdateCount, setWsUpdateCount] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'update_status') {
          setWsUpdateCount((n) => n + 1)
        }
      }
      ws.onclose = () => setTimeout(connect, 3000)
      ws.onerror = () => ws.close()
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const handleDeployed = (deployId: string) => {
    setHighlightDeployId(deployId)
    setActiveTab('deployments')
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'packages', label: 'Packages' },
    { key: 'deploy', label: 'Deploy' },
    { key: 'deployments', label: 'Deployments' },
  ]

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">OTA Updates</h1>
        <p className="text-text-secondary text-sm mt-1">
          Manage software packages and deploy updates to the fleet
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? 'border-secondary text-text-primary'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'packages' && <PackagesTab />}
      {activeTab === 'deploy' && <DeployTab onDeployed={handleDeployed} />}
      {activeTab === 'deployments' && (
        <DeploymentsTab highlightId={highlightDeployId} wsUpdateCount={wsUpdateCount} />
      )}
    </div>
  )
}
