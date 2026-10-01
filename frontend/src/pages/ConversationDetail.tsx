import React from 'react';
import { AgentRunRecord } from '../types';
import { TranscriptView } from '../components/TranscriptView';
import { OutcomePanel } from '../components/OutcomePanel';
import { ArrowLeft, AlertTriangle, ShieldCheck, CheckCircle2, ShieldAlert } from 'lucide-react';

interface ConversationDetailProps {
  conversation: AgentRunRecord;
  onBack: () => void;
}

export const ConversationDetail: React.FC<ConversationDetailProps> = ({
  conversation,
  onBack,
}) => {
  const getHeaderBadge = () => {
    if (conversation.terminal_state === 'escalated') {
      const reasonLabel = conversation.escalation_reason?.replace('_', ' ').toUpperCase() || 'URGENT';
      return (
        <span className="badge badge-clinical" style={{ fontSize: '0.8rem', padding: '0.35rem 0.85rem' }}>
          <AlertTriangle size={14} />
          ESCALATED — {reasonLabel}
        </span>
      );
    }
    if (conversation.terminal_state === 'booked') {
      return (
        <span className="badge badge-booked" style={{ fontSize: '0.8rem', padding: '0.35rem 0.85rem' }}>
          <CheckCircle2 size={14} />
          BOOKED — CONFIRMED
        </span>
      );
    }
    return (
      <span className="badge badge-scope" style={{ fontSize: '0.8rem', padding: '0.35rem 0.85rem' }}>
        {conversation.terminal_state.toUpperCase()}
      </span>
    );
  };

  return (
    <div className="main-viewport">
      {/* Detail Header Bar matching PDF Page 4 */}
      <div className="detail-header">
        <div className="detail-nav-left">
          <button className="btn-back" onClick={onBack}>
            <ArrowLeft size={16} />
            <span>Queue</span>
          </button>
          <div className="detail-title">
            <h2>Conversation {conversation.id}</h2>
            <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: '0.15rem' }}>
              Sunrise Clinic, Dehradun &bull; Reference Date: {conversation.today}
            </div>
          </div>
        </div>

        <div>
          {getHeaderBadge()}
        </div>
      </div>

      {/* Split Screen Layout matching PDF Page 4 */}
      <div className="detail-split-layout">
        <TranscriptView conversation={conversation} />
        <OutcomePanel conversation={conversation} />
      </div>
    </div>
  );
};
