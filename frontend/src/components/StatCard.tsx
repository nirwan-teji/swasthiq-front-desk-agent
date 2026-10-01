import React from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtext: string;
  isUrgent?: boolean;
  icon?: React.ReactNode;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtext,
  isUrgent = false,
  icon,
}) => {
  return (
    <div className="stat-card">
      <div className="stat-header">
        <span className="stat-title">{title}</span>
        {icon && <div className="stat-icon">{icon}</div>}
      </div>
      <div className="stat-value">{value}</div>
      <div className={`stat-subtext ${isUrgent ? 'highlight-red' : ''}`}>
        {subtext}
      </div>
    </div>
  );
};
