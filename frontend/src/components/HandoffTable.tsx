import React from 'react';
import { AgentRunRecord, EscalationReason } from '../types';
import { ChevronRight, CheckCircle2, AlertTriangle, ShieldAlert, UserX, Stethoscope, HelpCircle } from 'lucide-react';

interface HandoffTableProps {
  conversations: AgentRunRecord[];
  onSelectConversation: (id: string) => void;
  onResolve: (id: string, e: React.MouseEvent) => void;
}

export const HandoffTable: React.FC<HandoffTableProps> = ({
  conversations,
  onSelectConversation,
  onResolve,
}) => {
  const renderReasonBadge = (reason?: EscalationReason | null) => {
    switch (reason) {
      case 'clinical_urgent':
        return (
          <span className="badge badge-clinical">
            <AlertTriangle size={12} />
            CLINICAL
          </span>
        );
      case 'not_authorised':
        return (
          <span className="badge badge-authorisation">
            <ShieldAlert size={12} />
            NOT AUTHORISED
          </span>
        );
      case 'ambiguous_patient':
        return (
          <span className="badge badge-ambiguous">
            <UserX size={12} />
            AMBIGUOUS PATIENT
          </span>
        );
      case 'medical_advice':
        return (
          <span className="badge badge-medical">
            <Stethoscope size={12} />
            MEDICAL ADVICE
          </span>
        );
      case 'out_of_scope':
        return (
          <span className="badge badge-scope">
            <HelpCircle size={12} />
            OUT OF SCOPE
          </span>
        );
      default:
        return (
          <span className="badge badge-booked">
            <CheckCircle2 size={12} />
            NORMAL
          </span>
        );
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '—';
    }
  };

  return (
    <div className="table-card">
      <div className="table-header-bar">
        <h3>Open Handoffs</h3>
      </div>

      <table className="handoff-table">
        <thead>
          <tr>
            <th>Conversation</th>
            <th>Caller Said</th>
            <th>Reason</th>
            <th>Time</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {conversations.length === 0 ? (
            <tr>
              <td colSpan={5} style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                No conversations matching this filter.
              </td>
            </tr>
          ) : (
            conversations.map((item) => (
              <tr key={item.id} onClick={() => onSelectConversation(item.id)}>
                <td>
                  <div className="conv-id-cell">
                    <span>{item.id}</span>
                    <ChevronRight size={14} color="#64748b" />
                  </div>
                </td>
                <td>
                  <div className="caller-quote">
                    "{item.caller_preview || item.raw_turns?.[0] || '—'}"
                  </div>
                </td>
                <td>{renderReasonBadge(item.escalation_reason)}</td>
                <td style={{ color: '#94a3b8', fontSize: '0.82rem' }}>
                  {formatTime(item.created_at)}
                </td>
                <td>
                  {item.resolved ? (
                    <span style={{ color: '#10b981', fontSize: '0.8rem', fontWeight: 600 }}>
                      Resolved
                    </span>
                  ) : (
                    <button
                      className="btn-action btn-resolve"
                      onClick={(e) => onResolve(item.id, e)}
                    >
                      Resolve
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};
