import React from 'react';
import {
  Clock,
  Cpu,
  Database,
  HardDrive,
  MessageSquare,
  Radio,
  Server,
  Zap,
} from 'lucide-react';
import type { SystemMonitoringData } from '../../types';

interface SystemMonitoringWidgetProps {
  data: SystemMonitoringData;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}

export const SystemMonitoringWidget: React.FC<SystemMonitoringWidgetProps> = ({ data }) => {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <Server size={16} className="text-gold" /> Giám Sát Hệ Thống & Tài Nguyên
        </span>
        <span className="text-xs text-secondary font-mono">psutil Realtime</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '12px',
          marginBottom: '16px',
        }}
      >
        {/* CPU */}
        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Cpu size={14} className="text-gold" /> CPU Load
          </div>
          <div className="font-mono font-bold text-xl text-primary" style={{ marginTop: '6px' }}>
            {data.cpuPct.toFixed(1)}%
          </div>
          <div
            style={{
              height: '4px',
              backgroundColor: 'var(--border-subtle)',
              borderRadius: '2px',
              marginTop: '8px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${Math.min(100, data.cpuPct)}%`,
                height: '100%',
                backgroundColor: data.cpuPct > 80 ? 'var(--color-sell)' : 'var(--color-buy)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>

        {/* RAM */}
        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <HardDrive size={14} className="text-gold" /> RAM Process
          </div>
          <div className="font-mono font-bold text-xl text-primary" style={{ marginTop: '6px' }}>
            {data.ramUsedMB.toFixed(1)} <span className="text-xs text-muted font-normal">MB</span>
          </div>
          <div className="text-xs text-secondary" style={{ marginTop: '4px' }}>
            Hệ thống: {data.ramPct.toFixed(1)}%
          </div>
        </div>

        {/* Uptime */}
        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={14} className="text-gold" /> Process Uptime
          </div>
          <div className="font-mono font-bold text-lg text-primary" style={{ marginTop: '6px' }}>
            {formatUptime(data.uptimeSeconds)}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '4px' }}>Thời gian hoạt động</div>
        </div>

        {/* Latency */}
        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Radio size={14} className="text-gold" /> MT5 IPC Latency
          </div>
          <div className="font-mono font-bold text-xl text-buy" style={{ marginTop: '6px' }}>
            {data.dataLatencyMs} <span className="text-xs text-muted font-normal">ms</span>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '4px' }}>Độ trễ truy vấn</div>
        </div>
      </div>

      {/* Services Status Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          backgroundColor: 'var(--bg-card-subtle)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-subtle)',
          fontSize: '12px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Database size={13} className="text-gold" /> SQLite:
          <strong className="text-buy font-mono"> {data.databaseStatus}</strong>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <MessageSquare size={13} className="text-gold" /> Telegram:
          <strong className="text-buy font-mono"> {data.telegramStatus}</strong>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Zap size={13} className="text-gold" /> Cập nhật:
          <span className="text-secondary"> {data.lastMarketUpdate}</span>
        </span>
      </div>
    </div>
  );
};
