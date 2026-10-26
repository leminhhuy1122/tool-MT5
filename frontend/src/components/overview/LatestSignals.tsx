import React, { useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Radio,
  Search,
  Send,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { SignalDirection, SignalItem } from '../../types';
import { SignalDetailModal } from './SignalDetailModal';
import { api } from '../../services/api';

interface LatestSignalsProps {
  signals: SignalItem[];
  currentPrice?: number;
}

export const LatestSignals: React.FC<LatestSignalsProps> = ({ signals, currentPrice }) => {
  const [selectedSignal, setSelectedSignal] = useState<SignalItem | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [directionFilter, setDirectionFilter] = useState<'ALL' | SignalDirection | 'ACTIVE'>('ALL');

  // Admin Quick Announcement state
  const [customMsg, setCustomMsg] = useState<string>('');
  const [isSendingCustom, setIsSendingCustom] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Resend signal tracking
  const [resendingId, setResendingId] = useState<string | null>(null);

  const filteredSignals = useMemo(() => {
    return signals.filter((s) => {
      const matchSearch =
        searchTerm === '' ||
        s.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.timeframe.toLowerCase().includes(searchTerm.toLowerCase());

      const matchFilter =
        directionFilter === 'ALL'
          ? true
          : directionFilter === 'ACTIVE'
          ? s.status === 'ACTIVE'
          : s.direction === directionFilter;

      return matchSearch && matchFilter;
    });
  }, [signals, searchTerm, directionFilter]);

  const handleSendCustomMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customMsg.trim();
    if (!trimmed) return;

    setIsSendingCustom(true);
    setActionFeedback(null);
    try {
      const res = await api.adminBroadcastCustom(trimmed);
      setActionFeedback({ type: 'success', message: res.message || 'Đã phát thông báo lên Kênh Telegram!' });
      setCustomMsg('');
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Gửi thông báo thất bại!' });
    } finally {
      setIsSendingCustom(false);
    }
  };

  const handleResendSignal = async (signalId: string) => {
    setResendingId(signalId);
    setActionFeedback(null);
    try {
      const res = await api.adminResendSignal(signalId);
      setActionFeedback({ type: 'success', message: res.message || `Đã gửi lại tín hiệu #${signalId} lên Telegram!` });
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || `Lỗi gửi lại tín hiệu #${signalId}` });
    } finally {
      setResendingId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Admin Quick Broadcast Bar */}
      <div
        className="card"
        style={{
          borderLeft: '4px solid var(--color-accent-gold)',
          backgroundColor: '#0F172A',
          padding: '16px 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>📢</span>
            <div>
              <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary)' }}>
                Admin Điều Khiển Phát Tin Nhanh Lên Telegram
              </h3>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Gửi thông báo khẩn cấp, nhắc nhở hoặc lệnh cập nhật tới Kênh VIP <strong>@dbgtradingfx</strong>.
              </p>
            </div>
          </div>
          <span className="status-pill connected" style={{ fontSize: '10px' }}>
            KÊNH: @dbgtradingfx
          </span>
        </div>

        <form onSubmit={handleSendCustomMessage} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Nhập thông báo Admin (Ví dụ: Chú ý Vàng sắp có biến động mạnh đầu phiên Mỹ, anh em quản trị rủi ro...)"
            value={customMsg}
            onChange={(e) => setCustomMsg(e.target.value)}
            disabled={isSendingCustom}
            style={{
              flex: 1,
              minWidth: '280px',
              padding: '10px 14px',
              backgroundColor: 'var(--bg-card-subtle)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: '13px',
              outline: 'none',
            }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isSendingCustom || !customMsg.trim()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 18px',
              fontWeight: 700,
              fontSize: '12px',
            }}
          >
            <Send size={14} />
            {isSendingCustom ? 'Đang gửi...' : 'Gửi Thông Báo Kênh'}
          </button>
        </form>

        {/* Action Feedback Banner */}
        {actionFeedback && (
          <div
            style={{
              marginTop: '12px',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor:
                actionFeedback.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              border: `1px solid ${actionFeedback.type === 'success' ? 'var(--color-buy)' : 'var(--color-sell)'}`,
              color: actionFeedback.type === 'success' ? 'var(--color-buy)' : '#F87171',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {actionFeedback.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
              {actionFeedback.message}
            </span>
            <button
              onClick={() => setActionFeedback(null)}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '11px' }}
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Signals Table Card */}
      <div className="card">
        <div className="card-header" style={{ flexWrap: 'wrap', gap: '10px' }}>
          <span className="card-title">
            <Radio size={16} className="text-gold" /> Tín Hiệu Giao Dịch & Điều Khiển Bắn Lại Lệnh
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Quick Filter buttons */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: 'var(--bg-card-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '2px',
                gap: '2px',
              }}
            >
              {(['ALL', 'BUY', 'SELL', 'ACTIVE'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setDirectionFilter(filter)}
                  style={{
                    padding: '3px 8px',
                    fontSize: '11px',
                    fontWeight: 700,
                    borderRadius: '4px',
                    border: 'none',
                    cursor: 'pointer',
                    backgroundColor:
                      directionFilter === filter ? 'var(--color-accent-gold)' : 'transparent',
                    color: directionFilter === filter ? '#0B0F19' : 'var(--text-secondary)',
                    transition: 'all 0.12s ease',
                  }}
                >
                  {filter === 'ALL' ? `Tất cả (${signals.length})` : filter}
                </button>
              ))}
            </div>

            {/* Search box */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: 'var(--bg-card-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 8px',
              }}
            >
              <Search size={13} className="text-muted" />
              <input
                type="text"
                placeholder="Tìm mã tín hiệu..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--text-primary)',
                  fontSize: '11px',
                  width: '120px',
                  fontFamily: 'var(--font-mono)',
                }}
              />
            </div>
          </div>
        </div>

        {filteredSignals.length === 0 ? (
          <div
            style={{
              padding: '36px 20px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              backgroundColor: 'var(--bg-card-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px dashed var(--border-color)',
            }}
          >
            {signals.length === 0
              ? 'Chưa có tín hiệu nào trong cơ sở dữ liệu SQLite.'
              : 'Không tìm thấy tín hiệu phù hợp với bộ lọc hiện tại.'}
          </div>
        ) : (
          <div className="table-container">
            <table className="trading-table">
              <thead>
                <tr>
                  <th>Lệnh</th>
                  <th>Mã Tín Hiệu</th>
                  <th>Khung</th>
                  <th>Vùng Entry</th>
                  <th>SL</th>
                  <th>TP1 (+10 giá)</th>
                  <th>TP2</th>
                  <th>Score</th>
                  <th>Trạng Thái</th>
                  <th style={{ textAlign: 'center' }}>Thao Tác Admin</th>
                </tr>
              </thead>
              <tbody>
                {filteredSignals.map((s) => {
                  const isBuy = s.direction === 'BUY';
                  const isSell = s.direction === 'SELL';
                  const dirClass = isBuy ? 'buy' : isSell ? 'sell' : 'wait';
                  const isThisResending = resendingId === s.id;

                  return (
                    <tr key={s.id}>
                      <td>
                        <span className={`badge-direction ${dirClass}`}>
                          {isBuy ? <TrendingUp size={12} /> : isSell ? <TrendingDown size={12} /> : null}
                          {s.direction}
                        </span>
                      </td>
                      <td className="font-mono font-medium">{s.id}</td>
                      <td>
                        <span className="font-mono text-xs text-secondary">{s.timeframe}</span>
                      </td>
                      <td className="font-mono font-semibold">
                        {s.entryZone[0] ? `${s.entryZone[0].toFixed(2)} - ${s.entryZone[1].toFixed(2)}` : 'Chờ nến'}
                      </td>
                      <td className="font-mono text-sell">
                        {s.stopLoss ? `$${s.stopLoss.toFixed(2)}` : '-'}
                      </td>
                      <td className="font-mono text-buy">
                        {s.takeProfit1 ? `$${s.takeProfit1.toFixed(2)}` : '-'}
                      </td>
                      <td className="font-mono text-buy">
                        {s.takeProfit2 ? `$${s.takeProfit2.toFixed(2)}` : '-'}
                      </td>
                      <td>
                        <span className="font-mono font-bold text-gold">{s.score}</span>
                        <span className="text-xs text-muted">/100</span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          <span
                            className={`status-pill ${
                              s.status === 'ENTRY_REACHED' || s.status === 'TP_REACHED'
                                ? 'connected'
                                : s.status === 'ACTIVE'
                                ? 'warning'
                                : 'standby'
                            }`}
                            style={{
                              padding: '2px 8px',
                              fontSize: '10px',
                              fontWeight: 800,
                              backgroundColor:
                                s.status === 'ENTRY_REACHED'
                                  ? 'rgba(16, 185, 129, 0.2)'
                                  : s.status === 'ACTIVE'
                                  ? 'rgba(245, 158, 11, 0.2)'
                                  : undefined,
                              color:
                                s.status === 'ENTRY_REACHED'
                                  ? '#10B981'
                                  : s.status === 'ACTIVE'
                                  ? '#F59E0B'
                                  : undefined,
                              border:
                                s.status === 'ENTRY_REACHED'
                                  ? '1px solid rgba(16, 185, 129, 0.4)'
                                  : s.status === 'ACTIVE'
                                  ? '1px solid rgba(245, 158, 11, 0.4)'
                                  : undefined,
                            }}
                          >
                            {s.status === 'ENTRY_REACHED' ? 'KHỚP ENTRY' : s.status === 'ACTIVE' ? 'CHỜ ENTRY' : s.status}
                          </span>

                          {/* Hiển thị số Pips lời/lỗ thả nổi nếu lệnh đang khớp ENTRY_REACHED */}
                          {s.status === 'ENTRY_REACHED' && currentPrice && currentPrice > 0 && (
                            (() => {
                              const entryPrice = s.plannedEntry || (s.entryZone[0] + s.entryZone[1]) / 2;
                              const pnlPoints = s.direction === 'SELL' ? entryPrice - currentPrice : currentPrice - entryPrice;
                              const pnlPips = pnlPoints * 10;
                              const isProf = pnlPoints >= 0;
                              return (
                                <span
                                  style={{
                                    fontSize: '10px',
                                    fontWeight: 800,
                                    fontFamily: 'monospace',
                                    color: isProf ? '#10B981' : '#EF4444',
                                  }}
                                  title={`Giá khớp: ${entryPrice.toFixed(2)} | Giá hiện tại: ${currentPrice.toFixed(2)}`}
                                >
                                  {isProf ? `+${pnlPips.toFixed(1)}p` : `${pnlPips.toFixed(1)}p`} ({isProf ? `+${pnlPoints.toFixed(2)}` : pnlPoints.toFixed(2)})
                                </span>
                              );
                            })()
                          )}
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            onClick={() => setSelectedSignal(s)}
                            title="Xem chi tiết setup và lý do phân tích"
                          >
                            <ExternalLink size={12} />
                            Xem
                          </button>
                          <button
                            className="btn btn-primary"
                            style={{
                              padding: '4px 10px',
                              fontSize: '11px',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontWeight: 700,
                            }}
                            onClick={() => handleResendSignal(s.id)}
                            disabled={isThisResending}
                            title="Admin bấm gửi lại lệnh này lên Kênh Telegram"
                          >
                            <Send size={11} />
                            {isThisResending ? 'Đang gửi...' : 'Gửi lại Telegram'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Modal chi tiết tín hiệu */}
        <SignalDetailModal
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
          onResendTelegram={(id) => handleResendSignal(id)}
        />
      </div>
    </div>
  );
};
