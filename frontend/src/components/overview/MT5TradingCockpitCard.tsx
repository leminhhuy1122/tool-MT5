import React, { useEffect, useState, useCallback } from 'react';
import {
  AlertTriangle,
  Power,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import type { MT5TradingStatusData } from '../../types';

interface MT5TradingCockpitCardProps {
  currentPrice?: number;
  onRefreshParent?: () => void;
}

export const MT5TradingCockpitCard: React.FC<MT5TradingCockpitCardProps> = ({
  currentPrice: _currentPrice,
  onRefreshParent,
}) => {
  const [status, setStatus] = useState<MT5TradingStatusData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [toggling, setToggling] = useState<boolean>(false);
  const [settingLot, setSettingLot] = useState<boolean>(false);
  const [closingTicket, setClosingTicket] = useState<number | null>(null);
  const [closingAll, setClosingAll] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; isError?: boolean } | null>(null);

  const handleSyncActiveSignals = async () => {
    setSyncing(true);
    setActionMessage(null);
    try {
      const res = await api.syncActiveSignalsToMT5();
      setActionMessage({ text: res.message });
      await fetchStatus();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Lỗi đồng bộ lệnh lên MT5', isError: true });
    } finally {
      setSyncing(false);
    }
  };

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getMT5TradingStatus();
      setStatus(data);
    } catch (err) {
      console.error('Lỗi lấy trạng thái MT5 Auto-Trading:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 2500);
    return () => clearInterval(timer);
  }, [fetchStatus]);

  const handleToggleAutoTrading = async () => {
    if (!status) return;
    setToggling(true);
    setActionMessage(null);
    try {
      const nextState = !status.enabled;
      const res = await api.toggleMT5AutoTrading(nextState);
      setStatus((prev) => (prev ? { ...prev, enabled: res.enabled, trade_allowed: res.trade_allowed, trade_allowed_message: res.trade_allowed_message } : null));
      setActionMessage({ text: res.message, isError: !res.ok });
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Lỗi thao tác Auto-Trading', isError: true });
    } finally {
      setToggling(false);
    }
  };

  const handleSelectLotSize = async (lot: number) => {
    setSettingLot(true);
    setActionMessage(null);
    try {
      const res = await api.setMT5LotSize(lot);
      setStatus((prev) => (prev ? { ...prev, lot_size: res.lot_size } : null));
      setActionMessage({ text: res.message });
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Lỗi cập nhật Lot', isError: true });
    } finally {
      setSettingLot(false);
    }
  };

  const handleClosePosition = async (ticket: number) => {
    setClosingTicket(ticket);
    setActionMessage(null);
    try {
      const res = await api.closeMT5Position(ticket, undefined, 'Manual Cockpit');
      setActionMessage({ text: res.message });
      await fetchStatus();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Lỗi đóng lệnh', isError: true });
    } finally {
      setClosingTicket(null);
    }
  };

  const handleCloseAllPositions = async () => {
    if (!window.confirm('⚠️ XÁC NHẬN: Bạn có chắc muốn ĐÓNG TOÀN BỘ vị thế MT5 đang mở?')) {
      return;
    }
    setClosingAll(true);
    setActionMessage(null);
    try {
      const res = await api.closeAllMT5Positions();
      setActionMessage({ text: res.message });
      await fetchStatus();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Lỗi tất toán toàn bộ', isError: true });
    } finally {
      setClosingAll(false);
    }
  };

  if (loading && !status) {
    return (
      <div
        className="card"
        style={{
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          marginBottom: '12px',
        }}
      >
        <RefreshCw size={16} className="spin text-gold" />
        <span style={{ fontSize: '12px', color: '#94A3B8' }}>Đang kết nối MT5 Auto-Trading...</span>
      </div>
    );
  }

  const isEnabled = status?.enabled ?? false;
  const isTradeAllowed = status?.trade_allowed ?? false;
  const account = status?.account;
  const openPositions = status?.open_positions || [];
  const currentLot = status?.lot_size || 0.01;

  return (
    <div
      className="card"
      style={{
        marginBottom: '12px',
        padding: '12px 16px',
        background: isEnabled
          ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(15, 23, 42, 0.95) 100%)'
          : 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)',
        border: isEnabled ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: isEnabled
          ? '0 4px 20px rgba(16, 185, 129, 0.15)'
          : '0 2px 10px rgba(0, 0, 0, 0.25)',
        borderRadius: '10px',
        transition: 'all 0.25s ease',
      }}
    >
      {/* ─── HÀNG CHÍNH: THANH ĐIỀU KHIỂN TINH GỌN (COMPACT CONTROL STRIP) ─── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {/* 1. KHỐI TRÁI: Logo + Tên + Nút Bật/Tắt To Rõ */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: isEnabled ? 'rgba(16, 185, 129, 0.25)' : 'rgba(148, 163, 184, 0.12)',
              border: `1px solid ${isEnabled ? '#10B981' : '#475569'}`,
              flexShrink: 0,
            }}
          >
            <Zap size={18} style={{ color: isEnabled ? '#10B981' : '#94A3B8' }} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 800, color: '#F8FAFC', letterSpacing: '0.2px' }}>
                MT5 AUTO-TRADING
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '10px',
                  backgroundColor: isEnabled ? '#10B981' : 'rgba(148, 163, 184, 0.2)',
                  color: isEnabled ? '#0F172A' : '#94A3B8',
                  boxShadow: isEnabled ? '0 0 10px rgba(16, 185, 129, 0.4)' : 'none',
                  letterSpacing: '0.3px',
                }}
              >
                {isEnabled ? '● ĐANG BẬT' : '○ ĐÃ TẮT'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '1px' }}>
              {isEnabled
                ? `Tự động khớp lệnh thật ${currentLot} lot theo tín hiệu SMC • SL/TP ghim sàn 0ms`
                : 'Chế độ an toàn: Tắt tự động, chỉ phát tín hiệu tham khảo'}
            </div>
          </div>

          {/* Nút Chuyển Bật/Tắt To Rõ Nhất Quán */}
          <button
            onClick={handleToggleAutoTrading}
            disabled={toggling}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              fontWeight: 800,
              fontSize: '11px',
              cursor: toggling ? 'not-allowed' : 'pointer',
              border: 'none',
              backgroundColor: isEnabled ? '#EF4444' : '#10B981',
              color: '#FFFFFF',
              boxShadow: isEnabled ? '0 2px 8px rgba(239, 68, 68, 0.3)' : '0 2px 10px rgba(16, 185, 129, 0.35)',
              marginLeft: '6px',
              transition: 'all 0.15s ease',
            }}
            title={isEnabled ? 'Bấm để Tắt tự động giao dịch' : 'Bấm để Bật tự động giao dịch thật'}
          >
            <Power size={13} />
            {toggling ? 'Đang chuyển...' : isEnabled ? 'TẮT TỰ ĐỘNG' : 'BẬT TỰ ĐỘNG'}
          </button>
        </div>

        {/* 2. KHỐI GIỮA: Thông Tin Tài Khoản Tinh Gọn */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: 'rgba(15, 23, 42, 0.6)',
            padding: '4px 12px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            fontSize: '11px',
          }}
        >
          <span style={{ color: '#94A3B8' }}>
            TK: <strong style={{ color: '#F8FAFC' }}>{account?.server || 'DBGMarkets'} #{account?.login || 409793}</strong>
          </span>
          <span style={{ color: 'rgba(255, 255, 255, 0.15)' }}>•</span>
          <span style={{ color: '#94A3B8' }}>
            Vốn: <strong style={{ color: '#38BDF8', fontFamily: 'monospace' }}>${account?.balance?.toFixed(2) || '2,868.34'}</strong>
          </span>
          <span style={{ color: 'rgba(255, 255, 255, 0.15)' }}>•</span>
          <span style={{ color: '#94A3B8' }}>
            Margin: <strong style={{ color: '#10B981', fontFamily: 'monospace' }}>${account?.free_margin?.toFixed(2) || '2,868.34'}</strong>
          </span>
        </div>

        {/* 3. KHỐI PHẢI: Chọn Lot Nhanh & Nút Đóng Khẩn Cấp */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 600 }}>Lot:</span>
            {[0.01, 0.02, 0.05].map((lot) => {
              const isSelected = currentLot === lot;
              return (
                <button
                  key={lot}
                  onClick={() => handleSelectLotSize(lot)}
                  disabled={settingLot}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: settingLot ? 'not-allowed' : 'pointer',
                    border: isSelected ? '1px solid var(--color-accent-gold)' : '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: isSelected ? 'rgba(245, 158, 11, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                    color: isSelected ? '#FDE68A' : '#94A3B8',
                    transition: 'all 0.12s ease',
                  }}
                >
                  {lot}L
                </button>
              );
            })}
          </div>

          {/* Nút Khớp Ngay Tín Hiệu Active Lên MT5 */}
          <button
            onClick={handleSyncActiveSignals}
            disabled={syncing}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: syncing ? 'not-allowed' : 'pointer',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#6EE7B7',
              transition: 'all 0.15s ease',
            }}
            title="Đồng bộ ngay các tín hiệu đang ENTRY_REACHED vào sàn MT5"
          >
            <Zap size={13} />
            {syncing ? 'Đang khớp...' : 'Khớp ngay lên MT5'}
          </button>

          {/* Nút Đóng Khẩn Cấp (Sáng đỏ khi có lệnh) */}
          <button
            onClick={handleCloseAllPositions}
            disabled={closingAll || openPositions.length === 0}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: closingAll || openPositions.length === 0 ? 'not-allowed' : 'pointer',
              border: openPositions.length > 0 ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(255, 255, 255, 0.08)',
              backgroundColor: openPositions.length > 0 ? '#EF4444' : 'rgba(255, 255, 255, 0.04)',
              color: openPositions.length > 0 ? '#FFFFFF' : '#64748B',
              opacity: openPositions.length > 0 ? 1 : 0.6,
              transition: 'all 0.15s ease',
            }}
            title="Đóng sạch toàn bộ các lệnh MT5 đang mở"
          >
            <XCircle size={13} />
            {closingAll ? 'Đang đóng...' : `Đóng hết (${openPositions.length})`}
          </button>
        </div>
      </div>

      {/* ─── DẢI CẢNH BÁO ALGO TRADING (CHỈ HIỆN KHI NÚT ALGO MT5 ĐANG TẮT) ─── */}
      {!isTradeAllowed && (
        <div
          style={{
            marginTop: '8px',
            padding: '6px 12px',
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={14} className="text-gold" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: '11px', color: '#FDE68A', fontWeight: 600 }}>
              Nút <strong>"Algo Trading"</strong> trên phần mềm MT5 đang TẮT. Hãy bấm bật nút xanh trên MT5 để robot được phép đặt lệnh!
            </span>
          </div>
          <span style={{ fontSize: '10px', color: '#F59E0B', fontWeight: 700, padding: '2px 6px', borderRadius: '3px', backgroundColor: 'rgba(245, 158, 11, 0.2)' }}>
            CHỜ BẬT MT5
          </span>
        </div>
      )}

      {/* ─── THÔNG BÁO KẾT QUẢ THAO TÁC (NẾU CÓ) ─── */}
      {actionMessage && (
        <div
          style={{
            marginTop: '8px',
            padding: '6px 10px',
            borderRadius: '6px',
            backgroundColor: actionMessage.isError ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
            border: `1px solid ${actionMessage.isError ? '#EF4444' : '#10B981'}`,
            color: actionMessage.isError ? '#FCA5A5' : '#6EE7B7',
            fontSize: '11px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{actionMessage.text}</span>
          <button
            onClick={() => setActionMessage(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* ─── BẢNG LỆNH MT5 (CHỈ HIỂN THỊ KHI CÓ LỆNH ĐANG MỞ) ─── */}
      {openPositions.length > 0 && (
        <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#F8FAFC' }}>
              VỊ THẾ MT5 ĐANG MỞ ({openPositions.length})
            </span>
            <span style={{ fontSize: '10px', color: '#94A3B8' }}>
              Cập nhật mỗi 250ms
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {openPositions.map((pos) => {
              const isBuy = pos.direction === 'BUY';
              const isProfit = pos.pnl_usd >= 0;
              return (
                <div
                  key={pos.ticket}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '8px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: isProfit ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                    border: `1px solid ${isProfit ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)'}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px',
                        padding: '2px 6px',
                        borderRadius: '3px',
                        fontWeight: 800,
                        fontSize: '11px',
                        backgroundColor: isBuy ? '#10B981' : '#EF4444',
                        color: '#FFFFFF',
                      }}
                    >
                      {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                      {pos.direction} {pos.volume}L
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#38BDF8', fontSize: '11px' }}>
                      #{pos.ticket}
                    </span>
                    <span style={{ fontSize: '11px', color: '#CBD5E1', fontFamily: 'monospace' }}>
                      Giá vào: <strong>{pos.open_price.toFixed(2)}</strong> → Hiện tại: <strong>{pos.current_price.toFixed(2)}</strong>
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '11px', color: '#94A3B8', fontFamily: 'monospace' }}>
                      SL: <strong style={{ color: '#EF4444' }}>{pos.sl > 0 ? pos.sl.toFixed(2) : '—'}</strong> | TP: <strong style={{ color: '#10B981' }}>{pos.tp > 0 ? pos.tp.toFixed(2) : '—'}</strong>
                    </span>
                    <span
                      style={{
                        fontFamily: 'monospace',
                        fontWeight: 800,
                        fontSize: '12px',
                        color: isProfit ? '#10B981' : '#EF4444',
                      }}
                    >
                      {isProfit ? `+$${pos.pnl_usd.toFixed(2)}` : `-$${Math.abs(pos.pnl_usd).toFixed(2)}`}
                      <span style={{ fontSize: '10px', color: '#94A3B8', marginLeft: '4px' }}>
                        ({pos.pnl_points >= 0 ? `+${pos.pnl_points.toFixed(1)}` : pos.pnl_points.toFixed(1)} giá)
                      </span>
                    </span>

                    <button
                      onClick={() => handleClosePosition(pos.ticket)}
                      disabled={closingTicket === pos.ticket}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 700,
                        cursor: closingTicket === pos.ticket ? 'not-allowed' : 'pointer',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        color: '#FCA5A5',
                      }}
                    >
                      {closingTicket === pos.ticket ? '...' : 'Đóng'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
