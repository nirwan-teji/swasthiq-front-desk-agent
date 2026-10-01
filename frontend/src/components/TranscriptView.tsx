import React from 'react';
import { AgentRunRecord } from '../types';
import { Terminal, ShieldAlert, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';

interface TranscriptViewProps {
  conversation: AgentRunRecord;
}

export const TranscriptView: React.FC<TranscriptViewProps> = ({ conversation }) => {
  const turns = conversation.raw_turns || [];
  const tools = conversation.tool_calls || [];

  return (
    <div className="transcript-card">
      <div className="section-label">
        <Terminal size={14} />
        <span>Transcript & Tool Execution Stream</span>
      </div>

      <div className="turns-stream">
        {turns.map((callerText, index) => {
          // The API returns an ordered tool list, not a turn number. Render
          // the execution stream after the caller's final turn so a safety
          // tool is not misleadingly shown after Turn 1.
          const associatedTools = index === turns.length - 1 ? tools : [];

          return (
            <React.Fragment key={index}>
              {/* Caller Turn Bubble */}
              <div className="turn-caller">
                <span className="speaker-tag">CALLER (Turn {index + 1})</span>
                <div className="bubble-caller">
                  {callerText}
                </div>
              </div>

              {/* Inline Tool Call Box (if executed) */}
              {associatedTools.map((tool, toolIndex) => (
                <div className="tool-call-box" key={`${tool.name}-${toolIndex}`}>
                  <div className="tool-signature">
                    <span>{tool.name}</span>
                    <span>({JSON.stringify(tool.arguments).replace(/"/g, '')})</span>
                  </div>
                  {tool.result && <div className="tool-output">-&gt; {typeof tool.result === 'object' ? JSON.stringify(tool.result) : String(tool.result)}</div>}
                </div>
              ))}
            </React.Fragment>
          );
        })}

        {/* Final Agent Response Bubble */}
        {conversation.reply && (
          <div className="turn-agent">
            <span className="speaker-tag-agent">AGENT</span>
            <div className="bubble-agent">
              {conversation.reply}
            </div>
          </div>
        )}

        {/* Terminal Action Notification Box */}
        {conversation.terminal_state === 'escalated' && (
          <div className="terminal-action-box terminal-escalated">
            <ShieldAlert size={18} />
            <span>
              Escalation triggered ({conversation.escalation_reason || 'clinical'}). No appointment created.
            </span>
          </div>
        )}

        {conversation.terminal_state === 'booked' && (
          <div className="terminal-action-box terminal-booked">
            <CheckCircle size={18} />
            <span>
              Booking confirmed: appointment {conversation.appointment_id || '—'} created for patient {conversation.patient_id || '—'}.
            </span>
          </div>
        )}

        {conversation.terminal_state === 'abandoned' && (
          <div className="terminal-action-box terminal-abandoned">
            <AlertCircle size={18} />
            <span>Booking flow abandoned by caller. No appointment was created.</span>
          </div>
        )}
      </div>
    </div>
  );
};
