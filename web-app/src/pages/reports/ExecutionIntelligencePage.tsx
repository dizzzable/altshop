import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileCode2,
  GitBranch,
  Radar,
  ShieldAlert,
  Users,
} from 'lucide-react'
import snapshotData from '@/data/execution-intelligence-snapshot.json'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, formatRelativeTime } from '@/lib/utils'
import type {
  ExecutionAgentLane,
  ExecutionChangeCluster,
  ExecutionChangedFile,
  ExecutionIssueRecord,
  ExecutionParentTrack,
  ExecutionSnapshot,
} from '@/types/execution-intelligence'


const snapshot = snapshotData as unknown as ExecutionSnapshot

type OpenLaneKey = 'inProgress' | 'todo' | 'blocked' | 'inReview'

const laneOrder: OpenLaneKey[] = [
  'inProgress',
  'todo',
  'blocked',
  'inReview',
]

const laneMeta: Record<OpenLaneKey, { title: string; variant: 'warning' | 'secondary' | 'destructive' | 'outline' }> = {
  inProgress: { title: 'In Progress', variant: 'warning' },
  todo: { title: 'Todo', variant: 'secondary' },
  blocked: { title: 'Blocked', variant: 'destructive' },
  inReview: { title: 'In Review', variant: 'outline' },
}

function formatAbsoluteDate(value?: string | null) {
  if (!value) {
    return 'n/a'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatDelta(value: number) {
  if (value === 0) {
    return '0'
  }

  return value > 0 ? `+${value}` : String(value)
}

function formatRelativeLabel(value?: string | null) {
  if (!value) {
    return 'n/a'
  }

  return formatRelativeTime(value)
}

function issueVariant(status: string): 'default' | 'secondary' | 'warning' | 'destructive' | 'outline' {
  switch (status) {
    case 'done':
      return 'default'
    case 'in_progress':
      return 'warning'
    case 'blocked':
      return 'destructive'
    case 'in_review':
      return 'outline'
    default:
      return 'secondary'
  }
}

function IssueCard({ issue }: { issue: ExecutionIssueRecord }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={issueVariant(issue.status)}>{issue.status.replace('_', ' ')}</Badge>
        <Badge variant="secondary">{issue.priority}</Badge>
        <a href={issue.link} className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-200 hover:text-cyan-100">
          {issue.identifier}
        </a>
      </div>

      <h3 className="mt-3 text-base font-semibold text-slate-100">{issue.title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-300">
        {issue.latestComment.excerpt || issue.descriptionExcerpt || 'No issue note was captured yet.'}
      </p>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-400">
          <span>{issue.assigneeName || 'Unassigned'}</span>
          <span>{formatRelativeLabel(issue.updatedAt || issue.createdAt)}</span>
          {issue.parentIdentifier && <span>Parent {issue.parentIdentifier}</span>}
        </div>

      {issue.evidencePaths.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {issue.evidencePaths.slice(0, 4).map((path) => (
            <span key={path} className="rounded-full border border-white/10 bg-black/30 px-2 py-1 font-mono text-[11px] text-slate-300">
              {path}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ParentTrackCard({ track }: { track: ExecutionParentTrack }) {
  const openCount = (track.counts.in_progress || 0) + (track.counts.todo || 0) + (track.counts.blocked || 0) + (track.counts.in_review || 0)

  return (
    <Card className="h-full">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.12em] text-slate-400">
              <a href={track.link} className="hover:text-slate-100">{track.identifier}</a>
            </div>
            <CardTitle className="mt-2 text-lg">{track.title}</CardTitle>
          </div>
          <Badge variant={openCount > 0 ? 'warning' : 'default'}>
            {openCount > 0 ? `${openCount} open` : 'closed'}
          </Badge>
        </div>
        <CardDescription>
          Last child update {formatRelativeLabel(track.latestUpdatedAt)}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {Object.entries(track.counts).map(([status, count]) => (
            <span key={status} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
              {status.replace('_', ' ')}: {count}
            </span>
          ))}
        </div>
        <div className="space-y-3">
          {track.children.slice(0, 4).map((child) => (
            <div key={child.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <a href={child.link} className="text-sm font-semibold text-slate-100 hover:text-cyan-100">
                  {child.identifier}
                </a>
                <Badge variant={issueVariant(child.status)}>{child.status.replace('_', ' ')}</Badge>
              </div>
              <p className="mt-2 text-sm text-slate-300">{child.title}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function AgentLaneCard({ lane }: { lane: ExecutionAgentLane }) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg">{lane.name}</CardTitle>
            <CardDescription>{lane.title || lane.role || 'Specialist lane'}</CardDescription>
          </div>
          <Badge variant={lane.status === 'running' ? 'warning' : 'secondary'}>
            {lane.status || 'unknown'}
          </Badge>
        </div>
        {lane.capabilities && <CardDescription>{lane.capabilities}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2 text-xs text-slate-300">
          <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1">
            open {lane.openIssues.length}
          </span>
          <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1">
            done / 24h {lane.completedLast24h}
          </span>
          <a href={lane.link} className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-cyan-100 hover:bg-cyan-500/20">
            agent page
          </a>
        </div>

        {lane.openIssues.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Open work</div>
            <div className="mt-2 space-y-2">
              {lane.openIssues.map((issue) => (
                <a
                  key={issue.id}
                  href={issue.link}
                  className="block rounded-xl border border-white/8 bg-black/20 p-3 text-sm text-slate-200 hover:border-cyan-400/30"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{issue.identifier}</span>
                    <Badge variant={issueVariant(issue.status)}>{issue.status.replace('_', ' ')}</Badge>
                  </div>
                  <div className="mt-2">{issue.title}</div>
                </a>
              ))}
            </div>
          </div>
        )}

        {lane.recentDoneIssues.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Recently shipped</div>
            <div className="mt-2 space-y-2">
              {lane.recentDoneIssues.map((issue) => (
                <a
                  key={issue.id}
                  href={issue.link}
                  className="block rounded-xl border border-white/8 bg-black/20 p-3 text-sm text-slate-200 hover:border-emerald-400/30"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{issue.identifier}</span>
                    <Badge variant="default">done</Badge>
                  </div>
                  <div className="mt-2">{issue.title}</div>
                </a>
              ))}
            </div>
          </div>
        )}

        {lane.evidencePaths.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {lane.evidencePaths.slice(0, 4).map((path) => (
              <span key={path} className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 font-mono text-[11px] text-slate-300">
                {path}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ChangeClusterCard({ cluster }: { cluster: ExecutionChangeCluster }) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-lg">{cluster.title}</CardTitle>
          <Badge variant={cluster.noteType === 'authored' ? 'default' : 'outline'}>
            {cluster.noteType}
          </Badge>
        </div>
        <CardDescription>{cluster.note}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {cluster.issues.map((issue) => (
            <a
              key={issue.identifier}
              href={issue.link}
              className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-200 hover:bg-white/[0.09]"
            >
              {issue.identifier}
            </a>
          ))}
        </div>
        <div className="space-y-2">
          {cluster.files.slice(0, 6).map((path) => (
            <div key={path} className="rounded-xl border border-white/8 bg-black/20 px-3 py-2 font-mono text-xs text-slate-300">
              {path}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function ChangedFileRow({ file }: { file: ExecutionChangedFile }) {
  return (
    <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-slate-100">{file.path}</span>
          <Badge variant={file.lowSignal ? 'secondary' : 'outline'}>{file.status}</Badge>
          <span className="text-xs text-slate-500">{file.area}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {file.ranges.slice(0, 4).map((range) => (
            <span
              key={`${file.path}-${range.kind}-${range.display}`}
              className={cn(
                'rounded-full border px-2 py-1 font-mono text-[11px]',
                range.kind === 'deleted'
                  ? 'border-red-400/20 bg-red-500/10 text-red-100'
                  : range.kind === 'new'
                    ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
                    : 'border-amber-400/20 bg-amber-500/10 text-amber-100'
              )}
            >
              {range.kind} {range.display}
            </span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-emerald-100">
          {formatDelta(file.insertions)}
        </span>
        <span className="rounded-full border border-red-400/20 bg-red-500/10 px-3 py-1 text-red-100">
          -{file.deletions}
        </span>
      </div>
    </div>
  )
}

export function ExecutionIntelligencePage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_32%),radial-gradient(circle_at_top_right,rgba(96,165,250,0.16),transparent_28%),linear-gradient(180deg,#05070b_0%,#090d14_45%,#05070b_100%)] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-black/35 shadow-[0_50px_120px_-64px_rgba(0,0,0,1)] backdrop-blur-2xl">
          <div className="border-b border-white/10 px-6 py-8 sm:px-8">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="outline">AltShop execution intelligence</Badge>
              <Badge variant="secondary">{snapshot.context.project.name}</Badge>
              <Badge variant="warning">{snapshot.context.issue.identifier}</Badge>
            </div>
            <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div>
                <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  Live execution mapped to issues, agents, diff hunks, and the remaining bottlenecks.
                </h1>
                <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">
                  Snapshot generated {formatAbsoluteDate(snapshot.generatedAt)} from Paperclip project data and the current git worktree on
                  {' '}
                  <span className="font-mono text-slate-100">{snapshot.context.git.branch}</span>
                  {' '}
                  at
                  {' '}
                  <span className="font-mono text-slate-100">{snapshot.context.git.headShort}</span>.
                </p>
                <div className="mt-6 flex flex-wrap gap-3 text-sm">
                  <a href={snapshot.context.issue.link} className="rounded-full border border-cyan-400/25 bg-cyan-500/10 px-4 py-2 text-cyan-100 hover:bg-cyan-500/20">
                    Open {snapshot.context.issue.identifier}
                  </a>
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-slate-300">
                    Goal status: {snapshot.context.goal.status}
                  </span>
                </div>
              </div>

              <div className="grid gap-3 rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5">
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Leadership readout</div>
                <div className="space-y-3 text-sm leading-6 text-slate-300">
                  <p>
                    {snapshot.summary.projectStatusCounts.done} of {snapshot.summary.projectIssuesTotal} project issues are done. Only {snapshot.summary.openIssueIdentifiers.join(', ')} remain open in this project.
                  </p>
                  <p>
                    Recent delivery is concentrated in security hardening, CI gates, auth refactoring, and web-app UX stability.
                  </p>
                  <p>
                    Reporting accuracy is still limited by missing issue-to-commit linkage and uneven completion-comment quality.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 border-b border-white/10 px-6 py-6 sm:grid-cols-2 sm:px-8 xl:grid-cols-4">
            {[
              {
                title: 'Project status',
                value: `${snapshot.summary.projectStatusCounts.done}/${snapshot.summary.projectIssuesTotal}`,
                description: 'done / total issues',
                icon: CheckCircle2,
              },
              {
                title: 'Open execution',
                value: String(
                  snapshot.summary.projectStatusCounts.inProgress +
                  snapshot.summary.projectStatusCounts.todo +
                  snapshot.summary.projectStatusCounts.blocked +
                  snapshot.summary.projectStatusCounts.inReview
                ),
                description: 'todo + in progress + review + blocked',
                icon: Clock3,
              },
              {
                title: 'Recent shipped',
                value: String(snapshot.summary.recentCompleted24h),
                description: 'issues completed in the last 24h',
                icon: Activity,
              },
              {
                title: 'Repo activity',
                value: String(snapshot.summary.changedFiles),
                description: `${formatDelta(snapshot.summary.insertions)} / -${snapshot.summary.deletions} changed lines`,
                icon: GitBranch,
              },
            ].map((item) => (
              <Card key={item.title}>
                <CardContent className="flex items-start justify-between gap-4 p-5">
                  <div>
                    <div className="text-xs uppercase tracking-[0.12em] text-slate-400">{item.title}</div>
                    <div className="mt-3 text-3xl font-semibold text-white">{item.value}</div>
                    <div className="mt-2 text-sm text-slate-300">{item.description}</div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-3 text-cyan-100">
                    <item.icon className="h-6 w-6" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="space-y-10 px-6 py-8 sm:px-8">
            <section>
              <div className="flex items-center gap-3">
                <Radar className="h-5 w-5 text-cyan-200" />
                <h2 className="text-2xl font-semibold text-white">Issue Graph</h2>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                Parent tracks show where work was clustered and which branches of the project graph still have open children.
              </p>
              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {snapshot.parentTracks.map((track) => (
                  <ParentTrackCard key={track.identifier} track={track} />
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-3">
                <Clock3 className="h-5 w-5 text-amber-200" />
                <h2 className="text-2xl font-semibold text-white">Current Status</h2>
              </div>
              <div className="mt-5 grid gap-4 xl:grid-cols-4">
                {laneOrder.map((laneKey) => {
                  const issues = snapshot.statusLanes[laneKey]
                  const meta = laneMeta[laneKey]

                  return (
                    <Card key={laneKey} className="h-full">
                      <CardHeader className="pb-4">
                        <div className="flex items-center justify-between gap-3">
                          <CardTitle className="text-lg">{meta.title}</CardTitle>
                          <Badge variant={meta.variant}>{issues.length}</Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {issues.length === 0 && (
                          <div className="rounded-xl border border-dashed border-white/12 bg-black/20 px-4 py-6 text-sm text-slate-400">
                            No issues in this lane.
                          </div>
                        )}
                        {issues.map((issue) => (
                          <IssueCard key={issue.id} issue={issue} />
                        ))}
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5 text-emerald-200" />
                <h2 className="text-2xl font-semibold text-white">Specialist Lanes</h2>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                Agent cards combine their open work, their recent deliveries, and the repo paths the current project graph ties back to them.
              </p>
              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {snapshot.agentLanes.map((lane) => (
                  <AgentLaneCard key={lane.id} lane={lane} />
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-3">
                <FileCode2 className="h-5 w-5 text-cyan-200" />
                <h2 className="text-2xl font-semibold text-white">Change Clusters</h2>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                Authored notes are taken directly from issue comments. Inferred notes are marked when the dashboard had to reconstruct the story from file movement alone.
              </p>
              <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {snapshot.changeClusters.map((cluster) => (
                  <ChangeClusterCard key={cluster.id} cluster={cluster} />
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center gap-3">
                <GitBranch className="h-5 w-5 text-violet-200" />
                <h2 className="text-2xl font-semibold text-white">Repo Evidence</h2>
              </div>
              <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
                <Card>
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">Highest-signal changed files</CardTitle>
                    <CardDescription>
                      Ranked from the live worktree diff. Lockfiles are intentionally de-emphasized.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {snapshot.changedFiles.slice(0, 12).map((file) => (
                      <ChangedFileRow key={file.path} file={file} />
                    ))}
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg">Recent commits</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {snapshot.recentCommits.slice(0, 8).map((commit) => (
                        <div key={commit.hash} className="rounded-xl border border-white/8 bg-black/20 p-3">
                          <div className="flex items-center gap-2 text-xs text-slate-400">
                            <span className="font-mono text-slate-100">{commit.shortHash}</span>
                            <span>{commit.author}</span>
                          </div>
                          <div className="mt-2 text-sm text-slate-200">{commit.subject}</div>
                          <div className="mt-2 text-xs text-slate-500">{formatAbsoluteDate(commit.authoredAt)}</div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg">Inspected evidence</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Issues</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {snapshot.inspectedIssueIdentifiers.map((identifier) => (
                            <span key={identifier} className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-200">
                              {identifier}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Repo paths</div>
                        <div className="mt-2 space-y-2">
                          {snapshot.inspectedRepoPaths.slice(0, 10).map((path) => (
                            <div key={path} className="rounded-xl border border-white/8 bg-black/20 px-3 py-2 font-mono text-xs text-slate-300">
                              {path}
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </section>

            <section>
              <div className="flex items-center gap-3">
                <ShieldAlert className="h-5 w-5 text-red-200" />
                <h2 className="text-2xl font-semibold text-white">Gaps And Follow-ups</h2>
              </div>
              <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card>
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">Capability and knowledge gaps</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {snapshot.capabilityGaps.map((gap) => (
                      <div key={gap.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="warning">{gap.kind}</Badge>
                          <Badge variant="secondary">{gap.status}</Badge>
                          <a href={gap.link} className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-200 hover:text-cyan-100">
                            source issue
                          </a>
                        </div>
                        <div className="mt-3 text-base font-semibold text-slate-100">{gap.title}</div>
                        <div className="mt-2 text-sm text-slate-300">{gap.evidence}</div>
                        <div className="mt-3 text-xs text-slate-500">Owner lane: {gap.owner}</div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-4">
                    <CardTitle className="text-lg">Reporting gaps and next tasks</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-3">
                      {snapshot.reportingGaps.map((gap) => (
                        <div key={gap} className="rounded-2xl border border-red-400/15 bg-red-500/8 p-4 text-sm leading-6 text-red-50/90">
                          <div className="flex gap-3">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-200" />
                            <span>{gap}</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-3">
                      {snapshot.followUpTasks.map((task, index) => (
                        <div key={task.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Follow-up {index + 1}</div>
                          <div className="mt-2 text-base font-semibold text-slate-100">{task.title}</div>
                          <div className="mt-2 text-sm text-slate-300">{task.evidence}</div>
                          <div className="mt-3 text-xs text-slate-500">Owner: {task.owner}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
