import { AgentRunRecord, HandoffStats } from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

// Dashboard data is always calculated by the backend from actual runs.
export const INITIAL_STATS: HandoffStats = {
  total_conversations: 0,
  completed_by_agent: 0,
  completion_rate: 0,
  escalated_count: 0,
  open_escalated: 0,
  urgent_count: 0,
};

function normalizeRecord(record: any): AgentRunRecord {
  return {
    ...record,
    id: record.id ?? record.conversation_id,
    caller_preview: record.caller_preview ?? record.raw_turns?.[0] ?? '',
    turns_count: record.turns_count ?? record.metrics?.turns ?? 0,
    created_at: record.created_at ?? new Date().toISOString(),
    resolved: record.resolved ?? record._resolved ?? false,
    raw_turns: record.raw_turns ?? [],
    tool_calls: record.tool_calls ?? [],
  } as AgentRunRecord;
}

export async function fetchStats(): Promise<HandoffStats> {
  try {
    const res = await fetch(apiUrl('/api/conversations/stats'));
    if (res.ok) return await res.json();
  } catch {
    // Keep the zero state while the backend is starting.
  }
  return INITIAL_STATS;
}

export async function fetchConversations(): Promise<AgentRunRecord[]> {
  try {
    const res = await fetch(apiUrl('/api/conversations'));
    if (res.ok) {
      const data = await res.json();
      const conversations = Array.isArray(data) ? data : data.conversations;
      return Array.isArray(conversations)
        ? conversations.map(normalizeRecord).filter((record) =>
            Boolean(record.id && record.raw_turns.some((turn) => turn.trim()))
          )
        : [];
    }
  } catch {
    // Do not show fabricated fallback conversations.
  }
  return [];
}

export async function fetchConversationDetail(id: string): Promise<AgentRunRecord | null> {
  try {
    const res = await fetch(apiUrl(`/api/conversations/${encodeURIComponent(id)}`));
    if (res.ok) return normalizeRecord(await res.json());
  } catch {
    // The caller receives a not-found state in the UI.
  }
  return null;
}

export async function resolveHandoff(id: string): Promise<boolean> {
  try {
    const res = await fetch(apiUrl(`/api/conversations/${encodeURIComponent(id)}/resolve`), {
      method: 'POST',
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function runAgentSimulation(payload: {
  conversation_id: string;
  today: string;
  turns: string[];
}): Promise<any> {
  const res = await fetch(apiUrl('/agent/run'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Simulation failed: ${res.status} - ${errText}`);
  }
  return await res.json();
}
