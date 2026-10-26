import React from 'react';
import {
  Clock,
  Cpu,
  Database,
  HardDrive,
  MessageSquare,
  Radio,
} from 'lucide-react';
import type { SystemMonitoringData } from '../../types';

interface SystemHealthFooterProps {
  data: SystemMonitoringData;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}

export const SystemHealthFooter: React.FC<SystemHealthFooterProps> = ({ data }) => {
  return (
    <div
      style={{
        marginTop: '24px',
        padding: '12px 18px',
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        fontSize: '11px',
        color: 'var(--text-secondary)',
      }}
    >
      {/* Trạng thái vận hành tổng thể */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: '#10B981',
            fontWeight: 700,
            padding: '2px 8px',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
          }}
        >
          <span className="live-dot pulse" style={{ width: '6px', height: '6px' }} />
          HỆ THỐNG HOẠT ĐỘNG ỔN ĐỊNH
        </span>
        <span className="text-muted">•</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <Clock size={12} /> Uptime: <strong className="font-mono text-primary">{formatUptime(data.uptimeSeconds)}</strong>
        </span>
      </div>

      {/* Cụm thông số kỹ thuật phụ đưa xuống dưới cùng */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Tải trọng CPU Core hiện tại">
          <Cpu size={12} className="text-gold" />
          <span>CPU:</span>
          <strong className="font-mono text-primary">{data.cpuPct.toFixed(1)}%</strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Bộ nhớ RAM tiến trình Python & MT5">
          <HardDrive size={12} className="text-gold" />
          <span>RAM Process:</span>
          <strong className="font-mono text-primary">{data.ramUsedMB.toFixed(1)} MB</strong>
          <span className="text-muted">({data.ramPct.toFixed(0)}% sys)</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Độ trễ truy vấn dữ liệu từ MT5 Terminal">
          <Radio size={12} className="text-buy" />
          <span>MT5 Ping:</span>
          <strong className="font-mono text-buy">{data.dataLatencyMs}ms</strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Chế độ ghi cơ sở dữ liệu SQLite">
          <Database size={12} className="text-gold" />
          <span>DB:</span>
          <strong className="font-mono text-primary">{data.databaseStatus}</strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Kênh phát tín hiệu Telegram">
          <MessageSquare size={12} className="text-buy" />
          <span>Telegram:</span>
          <strong className="font-mono text-buy">{data.telegramStatus}</strong>
        </div>
      </div>
    </div>
  );
};
