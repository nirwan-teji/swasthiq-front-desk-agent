import React from 'react';
import { AgentRunRecord } from '../types';
import { CheckCircle2, ShieldCheck, Cpu } from 'lucide-react';

interface OutcomePanelProps {
  conversation: AgentRunRecord;
}

export const OutcomePanel: React.FC<OutcomePanelProps> = ({ conversation }) => {
  const formatLatency = (ms?: number) => {
    if (!ms) return '—';
    return (ms / 1000).toFixed(2) + ' s';
  };

  return (
    <div className="outcome-column">
      {/* Machine-readable Key-Value Inspector */}
      <div className="inspector-card">
        <div className="inspector-title">Outcome & Machine Contract</div>

        <div className="kv-list">
          <div className="kv-row">
            <span className="kv-key">terminal_state</span>
            <span
              className={`kv-val ${
                conversation.terminal_state === 'escalated'
                  ? 'val-escalated'
                  : conversation.terminal_state === 'booked'
                  ? 'val-booked'
                  : ''
              }`}
            >
              {conversation.terminal_state}
            </span>
          </div>

          <div className="kv-row">
            <span className="kv-key">escalation_reason</span>
            <span className={`kv-val ${!conversation.escalation_reason ? 'val-null' : 'val-escalated'}`}>
              {conversation.escalation_reason || 'null'}
            </span>
          </div>

          <div className="kv-row">
            <span className="kv-key">patient_id</span>
            <span className={`kv-val ${!conversation.patient_id ? 'val-null' : ''}`}>
              {conversation.patient_id || 'null'}
            </span>
          </div>

          <div className="kv-row">
            <span className="kv-key">appointment_id</span>
            <span className={`kv-val ${!conversation.appointment_id ? 'val-null' : 'val-booked'}`}>
              {conversation.appointment_id || 'null'}
            </span>
          </div>

          <div className="kv-row">
            <span className="kv-key">tool_calls</span>
            <span className="kv-val">{conversation.tool_calls?.length || 0}</span>
          </div>

          <div className="kv-row">
            <span className="kv-key">turns</span>
            <span className="kv-val">{conversation.metrics?.turns || conversation.turns_count || 1}</span>
          </div>

          <div className="kv-row">
            <span className="kv-key">tokens</span>
            <span className="kv-val">{conversation.metrics?.tokens?.toLocaleString() || '—'}</span>
          </div>

          <div className="kv-row">
            <span className="kv-key">latency</span>
            <span className="kv-val">{formatLatency(conversation.metrics?.latency_ms)}</span>
          </div>
        </div>
      </div>

      {/* Determinism Verification Card */}
      <div className="determinism-card">
        <div className="det-header">
          <ShieldCheck size={16} />
          <span>Determinism Verification</span>
        </div>

        <div className="det-badge">
          <CheckCircle2 size={16} />
          <span>Python safety/tools repeatable; LLM path provider-dependent</span>
        </div>

        <p className="det-desc">
          Safety interception, validation, and clinic state reset are deterministic. Hosted-model tool selection and latency are measured per run and are not a guarantee.
        </p>
      </div>

      {/* Agent Model Spec */}
      <div className="inspector-card" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#94a3b8', fontSize: '0.78rem' }}>
          <Cpu size={16} color="#38bdf8" />
          <span>Primary: <strong>Groq GPT-OSS-120B</strong></span>
        </div>
      </div>
    </div>
  );
};
