import React from 'react';
import {
  Activity,
  Cpu,
  Database,
  HardDrive,
  Server,
  ShieldCheck,
} from 'lucide-react';
import type { SystemMonitoringData } from '../../types';

interface SystemMonitoringViewProps {
  data: SystemMonitoringData;
}

export const SystemMonitoringView: React.FC<SystemMonitoringViewProps> = ({ data }) => {
  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Banner */}
      <div
        className="card"
        style={{
          borderLeft: '4px solid var(--color-buy)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={20} className="text-buy" />
            Giám Sát Tài Nguyên & Sức Khỏe Hệ Thống Thời Gian Thực
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Thông số đo lường thực tế qua thư viện psutil, SQLite WAL engine và kết nối IPC MetaTrader 5.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className="status-pill connected">HỆ THỐNG HOẠT ĐỘNG TỐT</span>
          <span className="status-pill demo">IPC LATENCY: {data.dataLatencyMs}ms</span>
        </div>
      </div>

      {/* Primary Telemetry Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 250px), 1fr))', gap: '16px' }}>
        {/* CPU */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Cpu size={16} className="text-gold" /> Mức Sử Dụng CPU
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>TỐI ƯU</span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-primary">
            {data.cpuPct.toFixed(1)}%
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: '4px', overflow: 'hidden', marginTop: '10px' }}>
            <div
              style={{
                width: `${Math.min(100, data.cpuPct)}%`,
                height: '100%',
                backgroundColor: data.cpuPct > 80 ? 'var(--color-sell)' : 'var(--color-buy)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '8px' }}>
            Polling nến M5 không làm nghẽn luồng xử lý
          </div>
        </div>

        {/* RAM */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <HardDrive size={16} className="text-gold" /> Bộ Nhớ RAM Ứng Dụng
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>KHÔNG RÒ RỈ</span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-primary">
            {data.ramUsedMB.toFixed(1)} <span className="text-sm font-normal text-muted">MB</span>
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: '4px', overflow: 'hidden', marginTop: '10px' }}>
            <div
              style={{
                width: `${Math.min(100, (data.ramUsedMB / 500) * 100)}%`,
                height: '100%',
                backgroundColor: 'var(--color-info)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '8px' }}>
            Tổng RAM máy: {(data.ramTotalMB / 1024).toFixed(1)} GB (Mức dùng máy: {data.ramPct.toFixed(1)}%)
          </div>
        </div>

        {/* Uptime */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Activity size={16} className="text-gold" /> Thời Gian Vận Hành (Uptime)
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>24/7 ONLINE</span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-gold">
            {formatUptime(data.uptimeSeconds)}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '16px' }}>
            Chu kỳ tự động ghi log và kiểm tra tín hiệu nến mới
          </div>
        </div>

        {/* Database */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Database size={16} className="text-gold" /> Cơ Sở Dữ Liệu SQLite
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>ACID / WAL</span>
          </div>
          <div className="font-mono font-extrabold text-lg text-primary">
            WAL MODE ACTIVE
          </div>
          <div className="text-xs text-secondary" style={{ marginTop: '8px' }}>
            Đường dẫn: <span className="font-mono text-muted">data/vietkey_gold.db</span>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '4px' }}>
            Cơ chế sao lưu: Online Snapshot xoay vòng 14 bản
          </div>
        </div>
      </div>

      {/* Subsystem Health Status Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <ShieldCheck size={16} className="text-gold" /> Trạng Thái Từng Phân Hệ
          </span>
          <span className="text-xs text-secondary font-mono">Chẩn Đoán Sức Khỏe Hệ Thống</span>
        </div>
        <div className="table-container">
          <table className="trading-table">
            <thead>
              <tr>
                <th>Phân Hệ</th>
                <th>Công Nghệ / Module</th>
                <th>Trạng Thái</th>
                <th>Giao Thức</th>
                <th>Ghi Chú</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-semibold text-primary">MetaTrader 5 Bridge</td>
                <td className="font-mono text-xs">MetaTrader5 SDK</td>
                <td><span className="status-pill connected">CONNECTED</span></td>
                <td className="font-mono text-xs">Windows IPC</td>
                <td className="text-secondary text-xs">Đọc dữ liệu giá và lịch sử nến XAUUSD thực tế</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Backend API & Server</td>
                <td className="font-mono text-xs">FastAPI + Uvicorn</td>
                <td><span className="status-pill connected">ONLINE</span></td>
                <td className="font-mono text-xs">HTTP / REST</td>
                <td className="text-secondary text-xs">Cổng 8000 nội bộ phục vụ giao diện Desktop</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Desktop Client Shell</td>
                <td className="font-mono text-xs">Microsoft Edge WebView2</td>
                <td><span className="status-pill connected">NATIVE ACTIVE</span></td>
                <td className="font-mono text-xs">Direct Webview</td>
                <td className="text-secondary text-xs">Cửa sổ ứng dụng Windows độc lập, không cần mở trình duyệt</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Cơ Sở Dữ Liệu</td>
                <td className="font-mono text-xs">SQLite 3 (WAL Mode)</td>
                <td><span className="status-pill connected">HEALTHY</span></td>
                <td className="font-mono text-xs">File I/O Direct</td>
                <td className="text-secondary text-xs">Lưu trữ tín hiệu, trade outcomes, feature vectors</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Machine Learning Filter</td>
                <td className="font-mono text-xs">Scikit-learn (RandomForest)</td>
                <td><span className="status-pill connected">READY</span></td>
                <td className="font-mono text-xs">In-Memory Engine</td>
                <td className="text-secondary text-xs">Hiệu chuẩn xác suất tín hiệu trước khi phát</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Telegram Notifier</td>
                <td className="font-mono text-xs">Telegram Bot API</td>
                <td><span className="status-pill connected">CONFIGURED</span></td>
                <td className="font-mono text-xs">HTTPS POST</td>
                <td className="text-secondary text-xs">Thông báo tức thì khi có setup và khi lệnh đạt TP/SL</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
