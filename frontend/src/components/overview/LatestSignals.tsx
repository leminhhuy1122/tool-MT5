import React, { useMemo, useState } from 'react';
import {
  AlertCircle,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Radio,
  Scale,
  Search,
  Send,
  TrendingDown,
  TrendingUp,
  Trophy,
  XCircle,
  Zap,
} from 'lucide-react';
import type { SignalItem } from '../../types';
import { SignalDetailModal } from './SignalDetailModal';
import { api } from '../../services/api';

interface LatestSignalsProps {
  signals: SignalItem[];
  currentPrice?: number;
}

export const LatestSignals: React.FC<LatestSignalsProps> = ({ signals, currentPrice }) => {
  const [selectedSignal, setSelectedSignal] = useState<SignalItem | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filterMode, setFilterMode] = useState<'ALL' | 'WIN' | 'LOST' | 'ACTIVE' | 'PREDICTIVE' | 'BUY' | 'SELL'>('ALL');

  // Admin Quick Announcement state
  const [customMsg, setCustomMsg] = useState<string>('');
  const [isSendingCustom, setIsSendingCustom] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Resend signal tracking
  const [resendingId, setResendingId] = useState<string | null>(null);

  // Thống kê Win / Lost nhanh trên danh sách tín hiệu
  const winCount = useMemo(() => signals.filter((s) => s.isWin || s.status === 'TP_REACHED').length, [signals]);
  const lossCount = useMemo(() => signals.filter((s) => s.isLoss || s.status === 'SL_REACHED').length, [signals]);
  const beCount = useMemo(() => signals.filter((s) => s.isBreakeven).length, [signals]);
  const activeCount = useMemo(() => signals.filter((s) => s.status === 'ACTIVE' || s.status === 'ENTRY_REACHED').length, [signals]);
  const predictiveCount = useMemo(() => signals.filter((s) => s.isPredictive || s.setupType === 'PREDICTIVE_LIMIT').length, [signals]);
  const buyCount = useMemo(() => signals.filter((s) => s.direction === 'BUY').length, [signals]);
  const sellCount = useMemo(() => signals.filter((s) => s.direction === 'SELL').length, [signals]);

  const resolvedCount = winCount + lossCount + beCount;
  const winRate = resolvedCount > 0 ? (winCount / resolvedCount) * 100 : 0;

  const totalNetPips = useMemo(() => {
    return signals.reduce((sum, s) => {
      if (s.pnlPips !== undefined && s.pnlPips !== null) {
        return sum + s.pnlPips;
      }
      return sum;
    }, 0);
  }, [signals]);

  const filteredSignals = useMemo(() => {
    return signals.filter((s) => {
      const matchSearch =
        searchTerm === '' ||
        s.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.timeframe.toLowerCase().includes(searchTerm.toLowerCase());

      let matchFilter = true;
      if (filterMode === 'WIN') {
        matchFilter = Boolean(s.isWin || s.status === 'TP_REACHED');
      } else if (filterMode === 'LOST') {
        matchFilter = Boolean(s.isLoss || s.status === 'SL_REACHED');
      } else if (filterMode === 'ACTIVE') {
        matchFilter = s.status === 'ACTIVE' || s.status === 'ENTRY_REACHED';
      } else if (filterMode === 'PREDICTIVE') {
        matchFilter = Boolean(s.isPredictive || s.setupType === 'PREDICTIVE_LIMIT');
      } else if (filterMode === 'BUY') {
        matchFilter = s.direction === 'BUY';
      } else if (filterMode === 'SELL') {
        matchFilter = s.direction === 'SELL';
      }

      return matchSearch && matchFilter;
    });
  }, [signals, searchTerm, filterMode]);

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
          borderLeft: '3px solid var(--color-accent-gold)',
          backgroundColor: '#0F172A',
          padding: '8px 14px',
          borderRadius: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px', flexWrap: 'wrap', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px' }}>📢</span>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Bắn Tin Nhanh Telegram (@dbgtradingfx)
            </span>
          </div>
        </div>

        <form onSubmit={handleSendCustomMessage} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Nhập thông báo gửi Telegram..."
            value={customMsg}
            onChange={(e) => setCustomMsg(e.target.value)}
            disabled={isSendingCustom}
            style={{
              flex: 1,
              minWidth: '220px',
              padding: '6px 12px',
              backgroundColor: 'var(--bg-card-subtle)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: '12px',
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
              gap: '4px',
              padding: '6px 12px',
              fontWeight: 700,
              fontSize: '11px',
            }}
          >
            <Send size={11} />
            {isSendingCustom ? 'Đang gửi...' : 'Gửi'}
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
      <div className="card" style={{ padding: '12px 16px', borderRadius: '10px' }}>
        <div className="card-header" style={{ flexWrap: 'wrap', gap: '8px', paddingBottom: '8px' }}>
          <span className="card-title" style={{ fontSize: '13px' }}>
            <Radio size={14} className="text-gold" /> Tín Hiệu & Lệnh Giao Dịch
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
                flexWrap: 'wrap',
              }}
            >
              {[
                { id: 'ALL', label: `Tất cả (${signals.length})`, color: 'var(--color-accent-gold)' },
                { id: 'WIN', label: `🏆 WIN (${winCount})`, color: '#10B981' },
                { id: 'LOST', label: `❌ LOST (${lossCount})`, color: '#EF4444' },
                { id: 'ACTIVE', label: `⚡ Đang chạy (${activeCount})`, color: '#38BDF8' },
                { id: 'PREDICTIVE', label: `🔮 Dự đoán (${predictiveCount})`, color: '#C084FC' },
                { id: 'BUY', label: `BUY (${buyCount})`, color: '#10B981' },
                { id: 'SELL', label: `SELL (${sellCount})`, color: '#EF4444' },
              ].map((btn) => {
                const isActive = filterMode === btn.id;
                return (
                  <button
                    key={btn.id}
                    onClick={() => setFilterMode(btn.id as any)}
                    style={{
                      padding: '3px 8px',
                      fontSize: '11px',
                      fontWeight: 700,
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      backgroundColor: isActive ? btn.color : 'transparent',
                      color: isActive ? '#0B0F19' : 'var(--text-secondary)',
                      transition: 'all 0.12s ease',
                    }}
                  >
                    {btn.label}
                  </button>
                );
              })}
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

        {/* Win / Lost Telemetry Summary Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '10px 16px',
            backgroundColor: 'rgba(15, 23, 42, 0.6)',
            borderBottom: '1px solid var(--border-color)',
            flexWrap: 'wrap',
            fontSize: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Tổng lệnh:</span>
            <strong style={{ color: 'var(--text-primary)' }}>{signals.length}</strong>
          </div>
          <span style={{ color: 'var(--border-color)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <TrendingUp size={14} /> Thắng (WIN):
            </span>
            <strong style={{ color: '#10B981' }}>{winCount} lệnh</strong>
            {resolvedCount > 0 && (
              <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10B981', fontSize: '10px', padding: '1px 6px', borderRadius: '4px', fontWeight: 800 }}>
                {winRate.toFixed(1)}% WR
              </span>
            )}
          </div>
          <span style={{ color: 'var(--border-color)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: '#EF4444', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <TrendingDown size={14} /> Thua (LOST):
            </span>
            <strong style={{ color: '#EF4444' }}>{lossCount} lệnh</strong>
          </div>
          {beCount > 0 && (
            <>
              <span style={{ color: 'var(--border-color)' }}>|</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#F59E0B' }}>⚖️ Hòa vốn:</span>
                <strong style={{ color: '#F59E0B' }}>{beCount}</strong>
              </div>
            </>
          )}
          {activeCount > 0 && (
            <>
              <span style={{ color: 'var(--border-color)' }}>|</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#38BDF8' }}>⚡ Đang chạy:</span>
                <strong style={{ color: '#38BDF8' }}>{activeCount}</strong>
              </div>
            </>
          )}
          {resolvedCount > 0 && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Tổng Net Pips:</span>
              <strong style={{ color: totalNetPips >= 0 ? '#10B981' : '#EF4444', fontFamily: 'monospace' }}>
                {totalNetPips >= 0 ? `+${totalNetPips.toFixed(1)}` : totalNetPips.toFixed(1)} Pips
              </strong>
            </div>
          )}
        </div>

        {filteredSignals.length === 0 ? (
          <div
            style={{
              padding: '32px 24px',
              textAlign: 'center',
              backgroundColor: 'rgba(15, 23, 42, 0.75)',
              borderRadius: '12px',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '12px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Top scanning pulse accent */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '2px',
                background: 'linear-gradient(90deg, #38BDF8, #F59E0B, #10B981)',
              }}
            />

            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38BDF8',
                position: 'relative',
              }}
            >
              <BrainCircuit size={24} />
              <span
                style={{
                  position: 'absolute',
                  top: '-2px',
                  right: '-2px',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  backgroundColor: '#10B981',
                  boxShadow: '0 0 8px #10B981',
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  padding: '3px 10px',
                  borderRadius: '999px',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  color: '#10B981',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                }}
              >
                <span className="live-dot pulse" style={{ width: '6px', height: '6px' }} />
                HỆ THỐNG ĐANG CHẠY 100% • KHÔNG BỊ TREO
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '999px',
                  backgroundColor: 'rgba(245, 158, 11, 0.12)',
                  color: '#F59E0B',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                QUÉT GIÁ MT5 MỖI 5 GIÂY
              </span>
            </div>

            <h4 style={{ fontSize: '15px', fontWeight: 800, color: '#F8FAFC', margin: 0 }}>
              {signals.length === 0
                ? 'AI Đang Quét Nến M5 & Chờ Setup Đạt Chuẩn Smart Money (SMC)'
                : 'Không tìm thấy tín hiệu phù hợp với bộ lọc hiện tại'}
            </h4>

            <p style={{ fontSize: '12px', color: '#94A3B8', maxWidth: '640px', lineHeight: 1.6, margin: 0 }}>
              {signals.length === 0 ? (
                <>
                  Hệ thống đang hoạt động bình thường và liên tục phân tích từng tick giá XAUUSD.
                  Khi thị trường đi ngang (Ranging) hoặc các khung thời gian H4/H1/M5 đang mâu thuẫn,
                  thuật toán kích hoạt chế độ <strong>Bảo Vệ Vốn</strong> (kiên quyết không vào lệnh bừa bãi).
                  Ngay khi nến M5 đóng cửa xác nhận điểm vào lệnh đẹp, lệnh sẽ tự động xuất hiện tại đây và khớp ngay vào <strong>Ví Đầu Tư Ảo (0.01 lot)</strong>!
                </>
              ) : (
                'Hãy thử chọn bộ lọc khác (Tất cả, Thắng, Thua, Đang chạy) hoặc nhập từ khóa tìm kiếm mới.'
              )}
            </p>
          </div>
        ) : (
          <div className="table-container">
            {/* Thanh hướng dẫn tương tác */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 14px',
                backgroundColor: 'rgba(15, 23, 42, 0.45)',
                borderBottom: '1px solid var(--border-color)',
                fontSize: '11px',
                color: '#94A3B8',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: 'var(--color-accent-gold)' }}>💡</span>
                <span>Nhấn vào <strong>bất kỳ vị trí nào trên dòng</strong> để xem chi tiết phân tích SMC & Order Block.</span>
              </div>
              <span style={{ fontSize: '10px', color: '#64748B' }}>Tự động đồng bộ tick MT5</span>
            </div>

            <table className="trading-table">
              <thead>
                <tr>
                  <th style={{ width: '190px' }}>Tín Hiệu</th>
                  <th>Kế Hoạch Giá (Entry • SL • TP)</th>
                  <th style={{ width: '90px', textAlign: 'center' }}>Điểm AI</th>
                  <th style={{ width: '210px' }}>Kết Quả / Trạng Thái</th>
                  <th style={{ width: '100px', textAlign: 'right' }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredSignals.map((s) => {
                  const isBuy = s.direction === 'BUY';
                  const isSell = s.direction === 'SELL';
                  const dirClass = isBuy ? 'buy' : isSell ? 'sell' : 'wait';
                  const isThisResending = resendingId === s.id;

                  return (
                    <tr
                      key={s.id}
                      onClick={() => setSelectedSignal(s)}
                      className="clickable-signal-row"
                      title={`Nhấn vào đây để xem phân tích chi tiết lệnh #${s.id}`}
                    >
                      {/* Cột 1: Tín Hiệu (Lệnh / Mã / Khung) */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span
                            className={`badge-direction ${dirClass}`}
                            style={{
                              padding: '3px 7px',
                              fontSize: '11px',
                              fontWeight: 800,
                              borderRadius: '4px',
                            }}
                          >
                            {isBuy ? <TrendingUp size={12} /> : isSell ? <TrendingDown size={12} /> : null}
                            {s.direction}
                          </span>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                              <span className="font-mono font-bold text-sm text-primary">#{s.id}</span>
                              {(s.isPredictive || s.setupType === 'PREDICTIVE_LIMIT') && (
                                <span
                                  style={{
                                    padding: '1px 5px',
                                    borderRadius: '3px',
                                    backgroundColor: 'rgba(168, 85, 247, 0.2)',
                                    color: '#C084FC',
                                    fontSize: '9px',
                                    fontWeight: 800,
                                    border: '1px solid rgba(168, 85, 247, 0.35)',
                                  }}
                                >
                                  DỰ ĐOÁN
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                              {s.timeframe} • SMC Setup
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Cột 2: Kế Hoạch Giá (Entry • SL • TP) - Gom gọn thông minh */}
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontSize: '10px', color: '#94A3B8', fontWeight: 600 }}>Entry:</span>
                            <span className="font-mono font-bold" style={{ color: '#F8FAFC', fontSize: '12px' }}>
                              {s.entryZone[0] ? `$${s.entryZone[0].toFixed(2)} - $${s.entryZone[1].toFixed(2)}` : 'Chờ nến xác nhận'}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', fontFamily: 'monospace' }}>
                            <span style={{ color: '#F87171' }}>
                              <span style={{ fontSize: '9px', color: '#94A3B8', marginRight: '3px' }}>SL</span>
                              ${s.stopLoss ? s.stopLoss.toFixed(2) : '-'}
                            </span>
                            <span style={{ color: 'rgba(255, 255, 255, 0.2)' }}>|</span>
                            <span style={{ color: '#34D399' }}>
                              <span style={{ fontSize: '9px', color: '#94A3B8', marginRight: '3px' }}>TP1</span>
                              ${s.takeProfit1 ? s.takeProfit1.toFixed(2) : '-'}
                            </span>
                            {s.takeProfit2 && (
                              <>
                                <span style={{ color: 'rgba(255, 255, 255, 0.2)' }}>|</span>
                                <span style={{ color: '#10B981' }}>
                                  <span style={{ fontSize: '9px', color: '#94A3B8', marginRight: '3px' }}>TP2</span>
                                  ${s.takeProfit2.toFixed(2)}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Cột 3: Điểm AI (Score) */}
                      <td style={{ textAlign: 'center' }}>
                        <div
                          style={{
                            display: 'inline-block',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontFamily: 'monospace',
                            fontWeight: 800,
                            fontSize: '12px',
                            backgroundColor:
                              s.score >= 80 ? 'rgba(16, 185, 129, 0.15)' : s.score >= 70 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            color: s.score >= 80 ? '#10B981' : s.score >= 70 ? '#F59E0B' : '#EF4444',
                            border: `1px solid ${
                              s.score >= 80 ? 'rgba(16, 185, 129, 0.35)' : s.score >= 70 ? 'rgba(245, 158, 11, 0.35)' : 'rgba(239, 68, 68, 0.35)'
                            }`,
                          }}
                        >
                          {s.score}
                          <span style={{ fontSize: '10px', opacity: 0.7 }}>/100</span>
                        </div>
                      </td>

                      {/* Cột 4: Kết Quả / Trạng Thái */}
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          {(s.isWin || s.status === 'TP_REACHED') ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '3px 8px',
                                  fontSize: '11px',
                                  fontWeight: 800,
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(16, 185, 129, 0.2)',
                                  color: '#10B981',
                                  border: '1px solid rgba(16, 185, 129, 0.4)',
                                  boxShadow: '0 0 8px rgba(16, 185, 129, 0.15)',
                                  width: 'fit-content',
                                }}
                              >
                                <Trophy size={12} /> WIN {s.pnlPips !== null && s.pnlPips !== undefined ? `(+${s.pnlPips.toFixed(1)}p)` : '(+100p)'}
                              </span>
                              {s.exitPrice ? (
                                <span style={{ fontSize: '10px', color: '#10B981', fontFamily: 'monospace' }}>
                                  Chốt @ ${s.exitPrice.toFixed(2)}
                                </span>
                              ) : null}
                            </div>
                          ) : (s.isLoss || s.status === 'SL_REACHED') ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '3px 8px',
                                  fontSize: '11px',
                                  fontWeight: 800,
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                  color: '#EF4444',
                                  border: '1px solid rgba(239, 68, 68, 0.4)',
                                  width: 'fit-content',
                                }}
                              >
                                <XCircle size={12} /> LOST {s.pnlPips !== null && s.pnlPips !== undefined ? `(${s.pnlPips.toFixed(1)}p)` : '(-100p)'}
                              </span>
                              {s.exitPrice ? (
                                <span style={{ fontSize: '10px', color: '#EF4444', fontFamily: 'monospace' }}>
                                  Cắt @ ${s.exitPrice.toFixed(2)}
                                </span>
                              ) : null}
                            </div>
                          ) : s.isBreakeven ? (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                fontSize: '11px',
                                fontWeight: 800,
                                borderRadius: '4px',
                                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                                color: '#F59E0B',
                                border: '1px solid rgba(245, 158, 11, 0.4)',
                                width: 'fit-content',
                              }}
                            >
                              <Scale size={12} /> HÒA VỐN (0.0p)
                            </span>
                          ) : s.status === 'ENTRY_REACHED' ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '3px 8px',
                                  fontSize: '11px',
                                  fontWeight: 800,
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(56, 189, 248, 0.2)',
                                  color: '#38BDF8',
                                  border: '1px solid rgba(56, 189, 248, 0.4)',
                                  width: 'fit-content',
                                }}
                              >
                                <Zap size={12} /> ĐANG KHỚP
                              </span>
                              {currentPrice && currentPrice > 0 && (() => {
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
                                  >
                                    {isProf ? `+${pnlPips.toFixed(1)}p` : `${pnlPips.toFixed(1)}p`} ({isProf ? `+${pnlPoints.toFixed(2)}` : pnlPoints.toFixed(2)})
                                  </span>
                                );
                              })()}
                            </div>
                          ) : s.status === 'ACTIVE' ? (
                            (s.isPredictive || s.setupType === 'PREDICTIVE_LIMIT') ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                                <span
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '3px',
                                    padding: '3px 8px',
                                    fontSize: '11px',
                                    fontWeight: 800,
                                    borderRadius: '4px',
                                    backgroundColor: 'rgba(168, 85, 247, 0.2)',
                                    color: '#C084FC',
                                    border: '1px solid rgba(168, 85, 247, 0.45)',
                                    width: 'fit-content',
                                  }}
                                >
                                  🔮 DỰ ĐOÁN TỪ XA
                                </span>
                                {currentPrice && currentPrice > 0 && (() => {
                                  const dist = Math.abs(currentPrice - (s.plannedEntry || s.entryZone[0]));
                                  return (
                                    <span style={{ fontSize: '10px', color: '#C084FC', fontFamily: 'monospace', fontWeight: 600 }}>
                                      Cách {dist.toFixed(1)} giá
                                    </span>
                                  );
                                })()}
                              </div>
                            ) : (
                              <span
                                style={{
                                  padding: '3px 8px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(245, 158, 11, 0.15)',
                                  color: '#F59E0B',
                                  border: '1px solid rgba(245, 158, 11, 0.3)',
                                  width: 'fit-content',
                                }}
                              >
                                ⏳ CHỜ ENTRY
                              </span>
                            )
                          ) : (
                            <span
                              style={{
                                padding: '2px 8px',
                                fontSize: '10px',
                                fontWeight: 600,
                                borderRadius: '4px',
                                backgroundColor: 'rgba(148, 163, 184, 0.1)',
                                color: '#94A3B8',
                                border: '1px solid rgba(148, 163, 184, 0.2)',
                                width: 'fit-content',
                              }}
                            >
                              {s.status === 'EXPIRED' ? 'HẾT HẠN' : s.status === 'INVALIDATED' ? 'HỦY SETUP' : s.status}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Cột 5: Thao Tác (Gửi Tele & Mũi tên xem chi tiết) */}
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end' }}>
                          <button
                            className="btn btn-primary"
                            style={{
                              padding: '4px 8px',
                              fontSize: '11px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontWeight: 700,
                              borderRadius: '4px',
                            }}
                            onClick={(e) => {
                              e.stopPropagation(); // Ngăn mở modal khi bấm gửi Telegram
                              handleResendSignal(s.id);
                            }}
                            disabled={isThisResending}
                            title="Bấm gửi lại tín hiệu này lên Kênh Telegram"
                          >
                            <Send size={11} />
                            {isThisResending ? 'Gửi...' : 'Tele'}
                          </button>

                          <div
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#64748B',
                              padding: '2px',
                            }}
                            title="Nhấn để xem phân tích chi tiết"
                          >
                            <ChevronRight size={16} />
                          </div>
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
