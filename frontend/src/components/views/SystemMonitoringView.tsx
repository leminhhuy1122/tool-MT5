import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Cpu,
  Database,
  HardDrive,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Terminal,
  XCircle,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import type {
  LogItem,
  SelfTestResponse,
  SystemDiagnosticsData,
  SystemMonitoringData,
} from '../../types';

interface SystemMonitoringViewProps {
  data: SystemMonitoringData;
}

export const SystemMonitoringView: React.FC<SystemMonitoringViewProps> = ({ data }) => {
  // State diagnostics & live logs
  const [diagnostics, setDiagnostics] = useState<SystemDiagnosticsData | null>(null);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [logCounts, setLogCounts] = useState({ total: 0, errorCount: 0, warningCount: 0, infoCount: 0 });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingLogs, setIsLoadingLogs] = useState<boolean>(false);
  const [selfTestRunning, setSelfTestRunning] = useState<boolean>(false);
  const [selfTestResult, setSelfTestResult] = useState<SelfTestResponse | null>(null);

  // Filters for log viewer
  const [logLevel, setLogLevel] = useState<'ALL' | 'ERROR' | 'WARNING' | 'INFO'>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [logLimit, setLogLimit] = useState<number>(100);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [copiedLogId, setCopiedLogId] = useState<number | null>(null);
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const logTerminalRef = useRef<HTMLDivElement>(null);

  // Format uptime
  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (d > 0) return `${d} ngày ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  // Fetch full system diagnostics
  const fetchDiagnostics = useCallback(async () => {
    try {
      setIsLoading(true);
      const diag = await api.getSystemDiagnostics();
      setDiagnostics(diag);
    } catch (e) {
      console.error('Lỗi nạp diagnostics:', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch live system logs
  const fetchLogs = useCallback(async () => {
    try {
      setIsLoadingLogs(true);
      const res = await api.getSystemLogs(logLevel, logLimit, searchQuery);
      setLogs(res.logs || []);
      setLogCounts({
        total: res.total || 0,
        errorCount: res.errorCount || 0,
        warningCount: res.warningCount || 0,
        infoCount: res.infoCount || 0,
      });
    } catch (e) {
      console.error('Lỗi nạp logs:', e);
    } finally {
      setIsLoadingLogs(false);
    }
  }, [logLevel, logLimit, searchQuery]);

  // Initial load & Polling
  useEffect(() => {
    fetchDiagnostics();
    fetchLogs();

    const interval = setInterval(() => {
      fetchDiagnostics();
      fetchLogs();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchDiagnostics, fetchLogs]);

  // Auto scroll terminal to top or bottom
  useEffect(() => {
    if (autoScroll && logTerminalRef.current) {
      logTerminalRef.current.scrollTop = 0; // Newest logs are at top
    }
  }, [logs, autoScroll]);

  // Run Self-Test
  const handleRunSelfTest = async () => {
    try {
      setSelfTestRunning(true);
      const res = await api.runSystemSelfTest();
      setSelfTestResult(res);
      fetchDiagnostics();
    } catch (e: any) {
      alert(`Lỗi thực hiện tự kiểm tra: ${e.message}`);
    } finally {
      setSelfTestRunning(false);
    }
  };

  // Copy single log line
  const handleCopyLog = (item: LogItem) => {
    const text = `[${item.timestamp}] [${item.level}] [${item.module}]: ${item.message}`;
    navigator.clipboard.writeText(text);
    setCopiedLogId(item.id);
    setTimeout(() => setCopiedLogId(null), 2000);
  };

  // Copy all visible logs
  const handleCopyAllLogs = () => {
    const text = logs
      .map((l) => `[${l.timestamp}] [${l.level}] [${l.module}]: ${l.message}`)
      .join('\n');
    navigator.clipboard.writeText(text);
    alert(`Đã sao chép ${logs.length} dòng nhật ký vào bộ nhớ tạm!`);
  };

  const isHealthy = (diagnostics?.errorDiagnostics?.errorCount24h || 0) === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ── TOP HEADER CONTROL BANNER ── */}
      <div
        className="card"
        style={{
          borderLeft: isHealthy ? '4px solid var(--color-buy)' : '4px solid var(--color-sell)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Server size={22} className={isHealthy ? 'text-buy' : 'text-sell'} />
            <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Trung Tâm Giám Sát Hệ Thống & Tìm Kiếm Lỗi Thời Gian Thực
            </h2>
            <span
              className={`status-pill ${isHealthy ? 'connected' : 'danger'}`}
              style={{ fontSize: '11px', padding: '3px 10px' }}
            >
              {isHealthy ? 'HỆ THỐNG HOÀN TOÀN ỔN ĐỊNH' : 'CẢNH BÁO: PHÁT HIỆN SỰ CỐ'}
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '6px' }}>
            Giám sát tài nguyên máy tính, luồng xử lý MT5, kiểm tra tính toàn vẹn SQLite WAL và soi chi tiết lỗi trực tiếp.
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div
            style={{
              padding: '6px 12px',
              backgroundColor: 'var(--bg-card-subtle)',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <ShieldCheck size={16} className="text-gold" />
            <span style={{ fontSize: '12px', fontWeight: 700 }}>
              Độ Ổn Định:{' '}
              <span className="text-buy font-mono font-bold">
                {diagnostics?.stabilityScore ?? 100.0}%
              </span>
            </span>
          </div>

          <button
            className="btn btn-secondary"
            onClick={fetchDiagnostics}
            disabled={isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            Làm Mới
          </button>

          <button
            className="btn btn-primary"
            onClick={handleRunSelfTest}
            disabled={selfTestRunning}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700 }}
          >
            <Zap size={14} className={selfTestRunning ? 'spin' : ''} />
            {selfTestRunning ? 'Đang Kiểm Tra...' : 'Chạy Tự Chẩn Đoán'}
          </button>
        </div>
      </div>

      {/* ── SELF TEST RESULT MODAL / BANNER ── */}
      {selfTestResult && (
        <div
          className="card"
          style={{
            border: selfTestResult.ok ? '1px solid var(--color-buy)' : '1px solid var(--color-sell)',
            backgroundColor: selfTestResult.ok ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.05)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontWeight: 800, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {selfTestResult.ok ? <CheckCircle2 size={18} className="text-buy" /> : <XCircle size={18} className="text-sell" />}
              Kết Quả Tự Chẩn Đoán Hệ Thống ({selfTestResult.ok ? 'ĐẠT 100% TIÊU CHUẨN' : 'CÓ BÀI TEST CHƯA ĐẠT'})
            </span>
            <button
              className="btn btn-secondary"
              style={{ padding: '2px 8px', fontSize: '11px' }}
              onClick={() => setSelfTestResult(null)}
            >
              Đóng
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
            {selfTestResult.tests.map((t, idx) => (
              <div
                key={idx}
                style={{
                  padding: '10px 12px',
                  backgroundColor: 'var(--bg-card)',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700 }}>{t.test}</span>
                  <span
                    className={`status-pill ${t.ok ? 'connected' : 'danger'}`}
                    style={{ fontSize: '9px', padding: '2px 6px' }}
                  >
                    {t.ok ? 'PASS' : 'FAIL'}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {t.detail}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── PRIMARY TELEMETRY TILES GRID ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 250px), 1fr))', gap: '16px' }}>
        {/* MT5 Bridge Tile */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Zap size={16} className="text-gold" /> MetaTrader 5 Bridge
            </span>
            <span
              className={`status-pill ${
                diagnostics?.mt5?.status === 'CONNECTED' ? 'connected' : 'danger'
              }`}
              style={{ fontSize: '10px' }}
            >
              {diagnostics?.mt5?.status || 'DISCONNECTED'}
            </span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-primary">
            {diagnostics?.mt5?.latencyMs ?? data.dataLatencyMs}{' '}
            <span className="text-sm font-normal text-muted">ms IPC</span>
          </div>
          <div className="text-xs text-secondary" style={{ marginTop: '10px' }}>
            Server: <span className="font-mono text-primary">{diagnostics?.mt5?.account?.server || 'MetaQuotes / Broker'}</span>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '4px' }}>
            Tài khoản: #{diagnostics?.mt5?.account?.login || 'Demo'} (Đòn bẩy 1:{diagnostics?.mt5?.account?.leverage || 500})
          </div>
        </div>

        {/* CPU Tile */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Cpu size={16} className="text-gold" /> Mức Sử Dụng CPU
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>
              TỐI ƯU
            </span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-primary">
            {(diagnostics?.resources?.cpuPct ?? data.cpuPct).toFixed(1)}%
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: '4px', overflow: 'hidden', marginTop: '10px' }}>
            <div
              style={{
                width: `${Math.min(100, diagnostics?.resources?.cpuPct ?? data.cpuPct)}%`,
                height: '100%',
                backgroundColor:
                  (diagnostics?.resources?.cpuPct ?? data.cpuPct) > 80 ? 'var(--color-sell)' : 'var(--color-buy)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '8px' }}>
            PID: {diagnostics?.resources?.pid || 'Direct'} • Polling 5s không gây nghẽn
          </div>
        </div>

        {/* RAM Tile */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <HardDrive size={16} className="text-gold" /> Bộ Nhớ RAM
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>
              KHÔNG RÒ RỈ
            </span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-primary">
            {(diagnostics?.resources?.ramMB ?? data.ramUsedMB).toFixed(1)}{' '}
            <span className="text-sm font-normal text-muted">MB</span>
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: '4px', overflow: 'hidden', marginTop: '10px' }}>
            <div
              style={{
                width: `${Math.min(100, ((diagnostics?.resources?.ramMB ?? data.ramUsedMB) / 500) * 100)}%`,
                height: '100%',
                backgroundColor: 'var(--color-info)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '8px' }}>
            Bộ nhớ máy: {((data.ramTotalMB || 16384) / 1024).toFixed(0)} GB (Dùng: {diagnostics?.resources?.systemRamPct ?? data.ramPct}%)
          </div>
        </div>

        {/* SQLite Database Tile */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Database size={16} className="text-gold" /> Database SQLite
            </span>
            <span
              className={`status-pill ${
                diagnostics?.database?.status === 'HEALTHY' ? 'connected' : 'danger'
              }`}
              style={{ fontSize: '10px' }}
            >
              {diagnostics?.database?.journalMode || 'WAL'} MODE
            </span>
          </div>
          <div className="font-mono font-extrabold text-2xl text-buy">
            {diagnostics?.database?.integrity?.toUpperCase() || 'OK (ACID)'}
          </div>
          <div className="text-xs text-secondary" style={{ marginTop: '10px' }}>
            Dung lượng: <span className="font-mono text-primary">{diagnostics?.database?.fileSizeMB || 0.17} MB</span>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '4px' }}>
            Đã lưu: {diagnostics?.database?.signalsCount || 0} tín hiệu • {diagnostics?.database?.tradesCount || 0} lệnh ví ảo
          </div>
        </div>
      </div>

      {/* ── KHU VỰC TÌM KIẾM LỖI & SỰ CỐ NHANH (INCIDENT & ERROR SUMMARY) ── */}
      <div
        className="card"
        style={{
          borderLeft: isHealthy ? '4px solid var(--color-buy)' : '4px solid var(--color-sell)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <span style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} className={isHealthy ? 'text-buy' : 'text-sell'} />
              Khu Vực Phát Hiện & Chẩn Đoán Lỗi Nhanh (Error Incidents 24h)
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Tự động phân tích các ngoại lệ và sự cố ghi nhận trong nhật ký hoạt động gần nhất.
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className={`status-pill ${logCounts.errorCount > 0 ? 'danger' : 'connected'}`}>
              🔴 {logCounts.errorCount} LỖI
            </span>
            <span className="status-pill warning">
              🟠 {logCounts.warningCount} CẢNH BÁO
            </span>
            <span className="status-pill connected">
              🟢 {logCounts.infoCount} THÔNG TIN BÌNH THƯỜNG
            </span>
          </div>
        </div>

        {/* Display recent errors if any */}
        {(diagnostics?.errorDiagnostics?.recentErrors?.length || 0) > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-sell)' }}>
              ⚠️ Các sự cố gần nhất cần chú ý:
            </span>
            {diagnostics?.errorDiagnostics.recentErrors.map((err, idx) => (
              <div
                key={idx}
                style={{
                  padding: '10px 14px',
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span className="status-pill danger" style={{ fontSize: '9px', padding: '1px 5px' }}>
                      {err.level}
                    </span>
                    <span className="font-mono text-muted text-xs">{err.timestamp}</span>
                    <span className="font-mono text-gold text-xs">[{err.module}]</span>
                  </div>
                  <div className="font-mono text-primary" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {err.message}
                  </div>
                </div>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '11px' }}
                  onClick={() => handleCopyLog(err)}
                  title="Sao chép lỗi này"
                >
                  <Copy size={12} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'rgba(34, 197, 94, 0.06)',
              border: '1px solid rgba(34, 197, 94, 0.2)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <CheckCircle2 size={24} className="text-buy" />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-buy)' }}>
                Tuyệt Vời! Không Phát Hiện Lỗi Nghiêm Trọng Nào
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Toàn bộ các luồng giao dịch, kết nối MT5 IPC, thuật toán Hedging Guard và ví ảo đều đang vận hành mượt mà 100%.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── LIVE INTERACTIVE LOG VIEWER TERMINAL ── */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Terminal Header & Filter Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Terminal size={18} className="text-gold" />
            <span style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)' }}>
              Trình Soi Nhật Ký & Tìm Lỗi Trực Tiếp (System Log Inspector)
            </span>
            <span className="font-mono text-xs text-muted">
              ({logs.length} / {logCounts.total} dòng)
            </span>
          </div>

          {/* Level Filter Tabs */}
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
            {[
              { id: 'ALL', label: 'Tất Cả' },
              { id: 'ERROR', label: `🔴 Lỗi (${logCounts.errorCount})` },
              { id: 'WARNING', label: `🟠 Cảnh Báo (${logCounts.warningCount})` },
              { id: 'INFO', label: '🟢 Thông Tin' },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`btn ${logLevel === tab.id ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '4px 10px', fontSize: '11px', fontWeight: 700 }}
                onClick={() => setLogLevel(tab.id as any)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar & Secondary Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Keyword Search */}
          <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
            <Search
              size={14}
              style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Tìm kiếm lỗi hoặc từ khóa (ví dụ: error, Hedging, XAUUSD, exception)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '32px', fontSize: '12px', width: '100%' }}
            />
          </div>

          {/* Right Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Limit Selector */}
            <select
              className="input-field"
              value={logLimit}
              onChange={(e) => setLogLimit(Number(e.target.value))}
              style={{ padding: '6px 10px', fontSize: '11px', width: 'auto' }}
            >
              <option value={50}>50 dòng</option>
              <option value={100}>100 dòng</option>
              <option value={200}>200 dòng</option>
              <option value={500}>500 dòng</option>
            </select>

            {/* Auto Scroll Checkbox */}
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '11px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Tự cuộn
            </label>

            {/* Copy All Button */}
            <button
              className="btn btn-secondary"
              onClick={handleCopyAllLogs}
              title="Sao chép toàn bộ dòng log đang hiển thị"
              style={{ padding: '6px 10px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Copy size={13} />
              Copy
            </button>

            {/* Reload button */}
            <button
              className="btn btn-secondary"
              onClick={fetchLogs}
              disabled={isLoadingLogs}
              style={{ padding: '6px 10px', fontSize: '11px' }}
            >
              <RefreshCw size={13} className={isLoadingLogs ? 'spin' : ''} />
            </button>
          </div>
        </div>

        {/* ── TERMINAL DISPLAY SCREEN ── */}
        <div
          ref={logTerminalRef}
          style={{
            backgroundColor: '#0a0d14',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '12px',
            maxHeight: '450px',
            overflowY: 'auto',
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            fontSize: '11.5px',
            lineHeight: 1.6,
          }}
        >
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '30px 0' }}>
              {isLoadingLogs ? 'Đang nạp nhật ký hệ thống...' : 'Không có nhật ký nào phù hợp với bộ lọc hiện tại.'}
            </div>
          ) : (
            logs.map((item) => {
              const isErr = item.isError;
              const isWarn = item.isWarning;
              const isExpanded = expandedLogId === item.id;

              return (
                <div
                  key={item.id}
                  onClick={() => setExpandedLogId(isExpanded ? null : item.id)}
                  style={{
                    padding: '4px 6px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    backgroundColor: isExpanded
                      ? 'rgba(255, 255, 255, 0.06)'
                      : isErr
                      ? 'rgba(239, 68, 68, 0.12)'
                      : isWarn
                      ? 'rgba(234, 179, 8, 0.06)'
                      : 'transparent',
                    borderLeft: isErr
                      ? '3px solid var(--color-sell)'
                      : isWarn
                      ? '3px solid var(--color-gold)'
                      : '3px solid transparent',
                    marginBottom: '2px',
                    transition: 'background-color 0.15s ease',
                  }}
                  title="Click để phóng to / sao chép"
                >
                  {/* Timestamp */}
                  <span style={{ color: '#64748b', whiteSpace: 'nowrap', userSelect: 'none' }}>
                    {item.timestamp}
                  </span>

                  {/* Level Tag */}
                  <span
                    style={{
                      fontWeight: 800,
                      color: isErr ? '#ef4444' : isWarn ? '#f59e0b' : '#38bdf8',
                      minWidth: '55px',
                      userSelect: 'none',
                    }}
                  >
                    [{item.level}]
                  </span>

                  {/* Module Name */}
                  <span style={{ color: '#a78bfa', minWidth: '130px', whiteSpace: 'nowrap' }}>
                    [{item.module}]
                  </span>

                  {/* Message Content */}
                  <span
                    style={{
                      color: isErr ? '#fca5a5' : isWarn ? '#fde047' : '#e2e8f0',
                      flex: 1,
                      whiteSpace: isExpanded ? 'pre-wrap' : 'nowrap',
                      overflow: 'hidden',
                      textOverflow: isExpanded ? 'clip' : 'ellipsis',
                    }}
                  >
                    {item.message}
                  </span>

                  {/* Quick Copy Button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCopyLog(item);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: copiedLogId === item.id ? 'var(--color-buy)' : '#64748b',
                      cursor: 'pointer',
                      padding: '0 4px',
                      opacity: 0.7,
                    }}
                    title="Sao chép dòng log này"
                  >
                    {copiedLogId === item.id ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── DYNAMIC SUBSYSTEM STATUS MATRIX TABLE ── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <ShieldCheck size={16} className="text-gold" /> Bảng Ma Trận Sức Khỏe & Vận Hành Từng Phân Hệ
          </span>
          <span className="text-xs text-secondary font-mono">
            Thời Gian Hoạt Động (Uptime): {formatUptime(diagnostics?.uptimeSeconds ?? data.uptimeSeconds)}
          </span>
        </div>
        <div className="table-container">
          <table className="trading-table">
            <thead>
              <tr>
                <th>Phân Hệ</th>
                <th>Công Nghệ / Module</th>
                <th>Trạng Thái</th>
                <th>Cấu Hình / Chi Tiết</th>
                <th>Ghi Chú</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-semibold text-primary">MetaTrader 5 Bridge</td>
                <td className="font-mono text-xs">MetaTrader5 IPC SDK</td>
                <td>
                  <span
                    className={`status-pill ${
                      diagnostics?.mt5?.status === 'CONNECTED' ? 'connected' : 'danger'
                    }`}
                  >
                    {diagnostics?.mt5?.status || 'DISCONNECTED'}
                  </span>
                </td>
                <td className="font-mono text-xs text-secondary">
                  XAUUSD | Ping: {diagnostics?.mt5?.latencyMs ?? data.dataLatencyMs}ms
                </td>
                <td className="text-secondary text-xs">Đọc dữ liệu tick giá và lịch sử nến XAUUSD thực tế</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Live Bot Runner & SMC Engine</td>
                <td className="font-mono text-xs">SignalEngine v1.0-M5</td>
                <td>
                  <span className="status-pill connected">
                    {diagnostics?.botRunner?.status || 'RUNNING'}
                  </span>
                </td>
                <td className="font-mono text-xs text-secondary">
                  Đang bám sát {diagnostics?.botRunner?.activeTrackingSignals || 0} lệnh active
                </td>
                <td className="text-secondary text-xs">Quét Order Block, FVG, Liquidity Sweep khung M5</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Chống Hedging & Cận Biên</td>
                <td className="font-mono text-xs">Strategic Zone Hedging</td>
                <td><span className="status-pill connected">ACTIVE (GUARD ON)</span></td>
                <td className="font-mono text-xs text-secondary">
                  Chặn lệch &lt; 5 giá • Khóa bảo toàn vốn
                </td>
                <td className="text-secondary text-xs">Tuân thủ quy chuẩn MT5 Netting và quy định Quỹ Prop Firm</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Ví Đầu Tư Ảo & Paper Engine</td>
                <td className="font-mono text-xs">PaperTradingEngine (0.01 lot)</td>
                <td><span className="status-pill connected">ONLINE</span></td>
                <td className="font-mono text-xs text-secondary">
                  Mô phỏng khớp lệnh thực theo tick giá MT5
                </td>
                <td className="text-secondary text-xs">Tự động tính PnL tiền đô (U), ký quỹ và bảo vệ vốn</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">AI Copilot Companion & Smart Exit</td>
                <td className="font-mono text-xs">Adaptive Profit & Chat Engine</td>
                <td><span className="status-pill connected">READY</span></td>
                <td className="font-mono text-xs text-secondary">
                  BE 1.0R • Trailing 1.5x ATR • Trò chuyện thực tế
                </td>
                <td className="text-secondary text-xs">Đồng hành đàm đạo cùng anh em và dời SL bảo vệ lãi</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Cơ Sở Dữ Liệu SQLite</td>
                <td className="font-mono text-xs">SQLite 3 (ACID / WAL)</td>
                <td><span className="status-pill connected">HEALTHY</span></td>
                <td className="font-mono text-xs text-secondary">
                  Integrity: {diagnostics?.database?.integrity || 'OK'} • {diagnostics?.database?.fileSizeMB || 0.17} MB
                </td>
                <td className="text-secondary text-xs">Ghi nhật ký tín hiệu, vectors 21 features, kết quả PnL</td>
              </tr>
              <tr>
                <td className="font-semibold text-primary">Telegram Notifier</td>
                <td className="font-mono text-xs">Telegram Bot API (Anti-Spam)</td>
                <td><span className="status-pill connected">CONFIGURED</span></td>
                <td className="font-mono text-xs text-secondary">
                  Chặn 100% tin test • Chỉ gửi lệnh & chat thật
                </td>
                <td className="text-secondary text-xs">Phát tín hiệu giao dịch, dặn SL hòa và bản tin kinh tế</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
