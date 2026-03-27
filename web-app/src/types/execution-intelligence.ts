export interface ExecutionIssueLink {
  identifier: string
  title: string
  status: string
  link: string
}

export interface ExecutionIssueRecord {
  id: string
  identifier: string
  title: string
  status: string
  priority: string
  link: string
  parentIdentifier?: string | null
  parentLink?: string | null
  assigneeName?: string | null
  assigneeUrl?: string | null
  updatedAt?: string | null
  createdAt?: string | null
  startedAt?: string | null
  completedAt?: string | null
  descriptionExcerpt?: string | null
  evidencePaths: string[]
  commands: string[]
  latestComment: {
    id?: string | null
    excerpt?: string | null
    paths: string[]
    createdAt?: string | null
    hasStructuredEvidence: boolean
  }
  activeRunId?: string | null
}

export interface ExecutionParentTrack {
  identifier: string
  title: string
  link: string
  status: string
  counts: Record<string, number>
  latestUpdatedAt?: string | null
  children: ExecutionIssueRecord[]
}

export interface ExecutionAgentLane {
  id: string
  name: string
  title?: string | null
  status?: string | null
  role?: string | null
  capabilities?: string | null
  link: string
  openIssues: ExecutionIssueRecord[]
  recentDoneIssues: ExecutionIssueRecord[]
  completedLast24h: number
  evidencePaths: string[]
}

export interface ExecutionChangeCluster {
  id: string
  title: string
  note: string
  noteType: 'authored' | 'inferred'
  issues: ExecutionIssueLink[]
  files: string[]
}

export interface ExecutionChangedFileRange {
  kind: 'new' | 'edited' | 'deleted'
  start: number
  end: number
  display: string
}

export interface ExecutionChangedFile {
  path: string
  status: string
  area: string
  insertions: number
  deletions: number
  ranges: ExecutionChangedFileRange[]
  signalScore: number
  lowSignal: boolean
}

export interface ExecutionRecentCommit {
  hash: string
  shortHash: string
  authoredAt: string
  author: string
  subject: string
}

export interface ExecutionCapabilityGap {
  kind: string
  title: string
  owner: string
  status: string
  link: string
  evidence: string
}

export interface ExecutionFollowUpTask {
  title: string
  owner: string
  evidence: string
}

export interface ExecutionSnapshot {
  generatedAt: string
  context: {
    companyPrefix: string
    issue: {
      identifier: string
      title: string
      link: string
    }
    project: {
      id: string
      name: string
      status: string
    }
    goal: {
      id: string
      title: string
      status: string
    }
    git: {
      branch: string
      head: string
      headShort: string
    }
  }
  summary: {
    projectIssuesTotal: number
    projectStatusCounts: {
      done: number
      inProgress: number
      todo: number
      blocked: number
      inReview: number
    }
    companyDashboard: {
      agents: {
        active: number
        running: number
        paused: number
        error: number
      }
      tasks: {
        open: number
        inProgress: number
        blocked: number
        done: number
      }
    }
    recentCompleted24h: number
    openIssueIdentifiers: string[]
    changedFiles: number
    insertions: number
    deletions: number
    agentsTotal: number
    agentsRunning: number
  }
  statusLanes: {
    inProgress: ExecutionIssueRecord[]
    todo: ExecutionIssueRecord[]
    blocked: ExecutionIssueRecord[]
    inReview: ExecutionIssueRecord[]
    done: ExecutionIssueRecord[]
  }
  recentDoneIssues: ExecutionIssueRecord[]
  parentTracks: ExecutionParentTrack[]
  agentLanes: ExecutionAgentLane[]
  changeClusters: ExecutionChangeCluster[]
  changedFiles: ExecutionChangedFile[]
  recentCommits: ExecutionRecentCommit[]
  capabilityGaps: ExecutionCapabilityGap[]
  reportingGaps: string[]
  followUpTasks: ExecutionFollowUpTask[]
  inspectedIssueIdentifiers: string[]
  inspectedRepoPaths: string[]
}
