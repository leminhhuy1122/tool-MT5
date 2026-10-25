import React from 'react';
import {
  Activity,
  Bot,
  Cpu,
  DollarSign,
  HardDrive,
  Radio,
  Sliders,
  Zap,
} from 'lucide-react';
import type { StatusCardData } from '../../types';

interface StatusCardsProps {
  data: StatusCardData;
}

export const StatusCards: React.FC<StatusCardsProps> = ({ data }) => {
  return (
    <div className="grid-status-cards">
      {/* 1. Bot Status */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Bot size={15} className="text-gold" /> Bot Status
          </span>
          <span className={`status-pill ${data.botStatus.toLowerCase()}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
            <span className={`live-dot ${data.botStatus === 'RUNNING' ? 'pulse' : ''}`} />
            {data.botStatus}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="font-bold text-lg text-primary">v1.0-M5</span>
          <span className="text-xs text-secondary">Active Engine</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          Multi-Timeframe Strategy
        </div>
      </div>

      {/* 2. MT5 Connection */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Activity size={15} className="text-gold" /> MT5 Connection
          </span>
          <span className={`status-pill ${data.mt5Status.toLowerCase()}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
            <span className={`live-dot ${data.mt5Status === 'CONNECTED' ? 'pulse' : ''}`} />
            {data.mt5Status}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="font-bold text-lg text-primary">Terminal</span>
          <span className="text-xs text-secondary">IPC Live</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          MetaTrader 5 Bridge
        </div>
      </div>

      {/* 3. Current Symbol & Price */}
      <div className="card" style={{ borderLeft: '3px solid var(--color-accent-gold)' }}>
        <div className="card-header">
          <span className="card-title">
            <Zap size={15} className="text-gold" /> {data.symbol} Price
          </span>
          <span className="text-xs font-mono text-secondary">LIVE FEED</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="font-mono font-extrabold text-2xl text-gold">
            ${data.currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="text-xs text-secondary" style={{ marginTop: '6px', display: 'flex', gap: '10px' }}>
          <span>Bid: <strong className="font-mono text-primary">${data.currentPrice.toFixed(2)}</strong></span>
          <span>Ask: <strong className="font-mono text-primary">${(data.currentPrice + data.spread).toFixed(2)}</strong></span>
        </div>
      </div>

      {/* 4. Spread */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Sliders size={15} className="text-gold" /> Spread
          </span>
          <span className="text-xs font-mono text-secondary">POINT SPREAD</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span className="font-mono font-bold text-2xl text-primary">
            {data.spread.toFixed(2)}
          </span>
          <span className="text-xs text-muted">giá vàng (~{(data.spread * 10).toFixed(0)} pips)</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          {data.spread <= 0.5 ? '✓ Spread hẹp tối ưu' : 'Spread bình thường'}
        </div>
      </div>

      {/* 5. Active Signals */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Radio size={15} className="text-gold" /> Active Signals
          </span>
          <span className="text-xs text-secondary">THEO DÕI</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="font-mono font-extrabold text-2xl text-primary">
            {data.activeSignals}
          </span>
          <span className="text-xs text-secondary">lệnh đang chạy</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          Chờ chạm Entry / TP / SL
        </div>
      </div>

      {/* 6. Total Signals Today */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <DollarSign size={15} className="text-gold" /> Signals Today
          </span>
          <span className="text-xs text-secondary">SQLITE DB</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="font-mono font-extrabold text-2xl text-primary">
            {data.totalSignalsToday}
          </span>
          <span className="text-xs text-secondary">tín hiệu ghi nhận</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          Lưu vết toàn bộ tín hiệu
        </div>
      </div>

      {/* 7. RAM Usage */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <HardDrive size={15} className="text-gold" /> RAM Usage
          </span>
          <span className="text-xs font-mono text-secondary">{data.ramUsagePct}% sys</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span className="font-mono font-bold text-2xl text-primary">
            {data.ramUsageMB.toFixed(1)}
          </span>
          <span className="text-xs text-secondary">MB Process</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          Tối ưu hóa bộ nhớ RAM
        </div>
      </div>

      {/* 8. CPU Usage */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Cpu size={15} className="text-gold" /> CPU Load
          </span>
          <span className="text-xs font-mono text-secondary">psutil live</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span className="font-mono font-bold text-2xl text-primary">
            {data.cpuUsagePct.toFixed(1)}%
          </span>
          <span className="text-xs text-secondary">Core Load</span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: '6px' }}>
          Hiệu suất xử lý ổn định
        </div>
      </div>
    </div>
  );
};
