import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { HandoffQueue } from './pages/HandoffQueue';
import { ConversationDetail } from './pages/ConversationDetail';
import { RunSimulationModal } from './components/RunSimulationModal';
import { AgentRunRecord, HandoffStats } from './types';
import { 
  fetchStats, 
  fetchConversations, 
  fetchConversationDetail, 
  resolveHandoff, 
  INITIAL_STATS
} from './api/client';

export const App: React.FC = () => {
  const [stats, setStats] = useState<HandoffStats>(INITIAL_STATS);
  const [conversations, setConversations] = useState<AgentRunRecord[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [isSimulateOpen, setIsSimulateOpen] = useState<boolean>(false);

  // Load from backend on start
  useEffect(() => {
    async function loadData() {
      const [fetchedStats, fetchedConvs] = await Promise.all([
        fetchStats(),
        fetchConversations(),
      ]);
      setStats(fetchedStats);
      if (fetchedConvs && fetchedConvs.length > 0) {
        setConversations(fetchedConvs);
      }
    }
    loadData();
  }, []);

  const handleResolve = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const resolved = await resolveHandoff(id);
    if (!resolved) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, resolved: true } : c))
    );
    setStats((prev) => ({
      ...prev,
      open_escalated: Math.max(0, prev.open_escalated - 1),
    }));
  };

  const handleSimulationComplete = (newRecord: AgentRunRecord) => {
    setConversations((prev) => [newRecord, ...prev]);
    setSelectedConversationId(newRecord.id);
    if (newRecord.terminal_state === 'escalated') {
      setStats((prev) => ({
        ...prev,
        total_conversations: prev.total_conversations + 1,
        escalated_count: prev.escalated_count + 1,
        open_escalated: prev.open_escalated + 1,
        urgent_count: newRecord.escalation_reason === 'clinical_urgent' ? prev.urgent_count + 1 : prev.urgent_count,
      }));
    } else {
      setStats((prev) => ({
        ...prev,
        total_conversations: prev.total_conversations + 1,
        completed_by_agent: prev.completed_by_agent + 1,
        completion_rate: Math.round(((prev.completed_by_agent + 1) / (prev.total_conversations + 1)) * 100),
      }));
    }
  };

  const activeConversation = selectedConversationId
    ? conversations.find((c) => c.id === selectedConversationId) || null
    : null;

  return (
    <div className="app-container">
      {/* Shared Sidebar */}
      <Sidebar
        openCount={stats.open_escalated}
        onOpenSimulate={() => setIsSimulateOpen(true)}
      />

      {/* Main Viewport: Either Detail or Queue/History */}
      {activeConversation ? (
        <ConversationDetail
          conversation={activeConversation}
          onBack={() => setSelectedConversationId(null)}
        />
      ) : (
        <HandoffQueue
          stats={stats}
          conversations={conversations.filter((c) => c.terminal_state === 'escalated' && !c.resolved)}
          onSelectConversation={(id) => setSelectedConversationId(id)}
          onResolve={handleResolve}
        />
      )}

      {/* Interactive Simulation Modal */}
      <RunSimulationModal
        isOpen={isSimulateOpen}
        onClose={() => setIsSimulateOpen(false)}
        onSimulationComplete={handleSimulationComplete}
      />
    </div>
  );
};

export default App;
