import React from 'react';
import { HandoffStats, AgentRunRecord } from '../types';
import { StatCard } from '../components/StatCard';
import { HandoffTable } from '../components/HandoffTable';
import { PhoneCall, CheckCircle, AlertOctagon, Flame } from 'lucide-react';

interface HandoffQueueProps {
  stats: HandoffStats;
  conversations: AgentRunRecord[];
  onSelectConversation: (id: string) => void;
  onResolve: (id: string, e: React.MouseEvent) => void;
}

export const HandoffQueue: React.FC<HandoffQueueProps> = ({
  stats,
  conversations,
  onSelectConversation,
  onResolve,
}) => (
  <div className="main-viewport">
    <div className="top-bar">
      <div className="page-title">
        <h2>Handoff Queue</h2>
        <p>Sunrise Clinic, Dehradun — conversations the agent escalated</p>
      </div>
      <div className="top-bar-actions">
        <div className="status-pill">
          <span className="status-dot" />
          <span>{stats.open_escalated} OPEN</span>
        </div>
      </div>
    </div>

    <div className="content-body">
      <div className="stat-cards-grid">
        <StatCard title="CONVERSATIONS" value={stats.total_conversations} subtext="today" icon={<PhoneCall size={18} color="#38bdf8" />} />
        <StatCard title="COMPLETED BY AGENT" value={stats.completed_by_agent} subtext={`${stats.completion_rate}%`} icon={<CheckCircle size={18} color="#10b981" />} />
        <StatCard title="ESCALATED" value={stats.escalated_count} subtext={`${stats.open_escalated} still open`} icon={<AlertOctagon size={18} color="#f59e0b" />} />
        <StatCard title="URGENT" value={stats.urgent_count} subtext="clinical, unresolved" isUrgent icon={<Flame size={18} color="#ef4444" />} />
      </div>

      <HandoffTable
        conversations={conversations}
        onSelectConversation={onSelectConversation}
        onResolve={onResolve}
      />
    </div>
  </div>
);
