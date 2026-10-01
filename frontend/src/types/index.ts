export type TerminalState =
  | 'booked'
  | 'rescheduled'
  | 'cancelled'
  | 'escalated'
  | 'refused'
  | 'abandoned';

export type EscalationReason =
  | 'clinical_urgent'
  | 'medical_advice'
  | 'not_authorised'
  | 'ambiguous_patient'
  | 'out_of_scope';

export interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  result?: any;
}

export interface Metrics {
  turns: number;
  tokens: number;
  latency_ms: number;
}

export interface ConversationTurn {
  speaker: 'caller' | 'agent' | 'tool';
  text?: string;
  toolCall?: ToolCall;
  timestamp?: string;
}

export interface AgentRunRecord {
  id: string; // conversation_id, e.g., cv_0011, cv_4471
  caller_preview: string;
  turns_count: number;
  today: string;
  terminal_state: TerminalState;
  escalation_reason?: EscalationReason | null;
  patient_id?: string | null;
  appointment_id?: string | null;
  reply: string;
  tool_calls: ToolCall[];
  metrics: Metrics;
  created_at: string;
  resolved: boolean;
  raw_turns: string[];
}

export interface HandoffStats {
  total_conversations: number;
  completed_by_agent: number;
  completion_rate: number;
  escalated_count: number;
  open_escalated: number;
  urgent_count: number;
}
