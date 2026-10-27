import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Wallet,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import type { MenuId, PaperWalletOverviewSummary, SignalItem } from '../../types';

interface PaperWalletHeroCardProps {
  paperWallet?: PaperWalletOverviewSummary;
  currentPrice?: number;
  signals?: SignalItem[];
  onNavigateToWallet?: (menu: MenuId) => void;
  onRefresh?: () => void;
}

export const PaperWalletHeroCard: React.FC<PaperWalletHeroCardProps> = ({
  paperWallet,
  signals,
  onNavigateToWallet,
  onRefresh,
}) => {
  const [closingId, setClosingId] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<{ text: string; ok: boolean } | null>(null);

  if (!paperWallet) {
    return null;
  }

  const {
    balance = 50.0,
    equity = 50.0,
    floatingPnl = 0.0,
    netProfitUsd = 0.0,
    openCount = 0,
    isAutoTrading = true,
    usedMargin = 0.0,
    winRate = 0.0,
    totalTrades = 0,
    openPositions = [],
  } = paperWallet;

  const isProfit = floatingPnl >= 0;
  const hasOpenOrder = openCount > 0 && openPositions && openPositions.length > 0;
  const activePos = hasOpenOrder ? openPositions[0] : null;
  const pendingSignal = signals?.find((s) => s.status === 'ACTIVE');
  const floatingPct = balance > 0 ? (floatingPnl / balance) * 100 : 0;

  const handleManualClose = async (positionId: string) => {
    setClosingId(positionId);
    setToastMsg(null);
    try {
      const res = await api.closePaperPosition(positionId);
      if (res.ok) {
        setToastMsg({ text: res.message || 'Đã đóng lệnh thành công!', ok: true });
        if (onRefresh) onRefresh();
      } else {
        setToastMsg({ text: res.message || 'Không thể đóng lệnh', ok: false });
      }
    } catch (e: any) {
      setToastMsg({ text: e.message || 'Lỗi khi đóng lệnh', ok: false });
    } finally {
      setClosingId(null);
      setTimeout(() => setToastMsg(null), 5000);
    }
  };

  return (
    <div
      id="paper-wallet-hero-compact"
      className="card"
      style={{
        marginBottom: '12px',
        background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.98) 0%, rgba(15, 23, 42, 0.95) 100%)',
        border: `1px solid ${hasOpenOrder ? (isProfit ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)') : 'rgba(245, 158, 11, 0.25)'}`,
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.25)',
        padding: '10px 16px',
        borderRadius: '10px',
      }}
    >
      {/* Toast Feedback */}
      {toastMsg && (
        <div
          style={{
            marginBottom: '8px',
            padding: '6px 12px',
            borderRadius: '6px',
            backgroundColor: toastMsg.ok ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${toastMsg.ok ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
            color: toastMsg.ok ? '#10B981' : '#F87171',
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {toastMsg.ok ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
            <span>{toastMsg.text}</span>
          </div>
          <button
            onClick={() => setToastMsg(null)}
            style={{ background: 'transparent', border: 'none', color: '#94A3B8', cursor: 'pointer', fontSize: '11px' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Single Row Cockpit */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {/* Left Wing: Title & PnL Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              backgroundColor: 'rgba(245, 158, 11, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#F59E0B',
            }}
          >
            <Wallet size={15} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 800, color: '#F8FAFC' }}>
              Ví Đầu Tư Ảo (0.01 Lot)
            </span>
            <span
              style={{
                fontSize: '9px',
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: '999px',
                backgroundColor: isAutoTrading ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                color: isAutoTrading ? '#10B981' : '#EF4444',
                border: `1px solid ${isAutoTrading ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              }}
            >
              {isAutoTrading ? 'AUTO ON' : 'PAUSED'}
            </span>
          </div>

          <span style={{ color: 'rgba(255, 255, 255, 0.15)' }}>|</span>

          {/* Floating PnL Display */}
          {hasOpenOrder && activePos ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  backgroundColor: activePos.direction === 'SELL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                  color: activePos.direction === 'SELL' ? '#EF4444' : '#10B981',
                }}
              >
                {activePos.direction} {activePos.volume}L
              </span>

              <span
                style={{
                  fontSize: '15px',
                  fontWeight: 900,
                  fontFamily: 'monospace',
                  color: isProfit ? '#10B981' : '#EF4444',
                }}
              >
                {isProfit ? `+${floatingPnl.toFixed(2)} U` : `${floatingPnl.toFixed(2)} U`} ({isProfit ? '+' : ''}{floatingPct.toFixed(1)}%)
              </span>

              <button
                onClick={() => handleManualClose(activePos.position_id)}
                disabled={closingId === activePos.position_id}
                className="btn btn-primary"
                style={{
                  padding: '3px 8px',
                  fontSize: '10px',
                  fontWeight: 800,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  backgroundColor: isProfit ? '#059669' : '#DC2626',
                }}
              >
                {closingId === activePos.position_id ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
                Chốt Lệnh
              </button>
            </div>
          ) : pendingSignal ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  padding: '2px 7px',
                  borderRadius: '4px',
                  backgroundColor: pendingSignal.direction === 'SELL' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: `1px dashed ${pendingSignal.direction === 'SELL' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                  color: pendingSignal.direction === 'SELL' ? '#FCA5A5' : '#86EFAC',
                }}
              >
                CHỜ ENTRY: {pendingSignal.direction} 0.01L
              </span>
              <span style={{ fontSize: '11px', color: '#CBD5E1', fontFamily: 'monospace' }}>
                @ ${(pendingSignal.plannedEntry || pendingSignal.entryZone?.[0] || 0).toFixed(2)} (Sẵn sàng khớp khi chạm)
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
              <span style={{ fontFamily: 'monospace', fontWeight: 800, color: '#94A3B8' }}>0.00 U</span>
              <span style={{ color: '#64748B', fontSize: '10px' }}>(Đang chờ lệnh M5)</span>
            </div>
          )}
        </div>

        {/* Right Wing: 4 Compact Financial Metrics & Link */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '11px' }}>
          <div>
            <span style={{ color: '#64748B' }}>Vốn: </span>
            <strong style={{ color: '#F1F5F9', fontFamily: 'monospace' }}>${balance.toFixed(2)}</strong>
          </div>

          <div>
            <span style={{ color: '#64748B' }}>Tài sản: </span>
            <strong style={{ color: hasOpenOrder ? (isProfit ? '#10B981' : '#EF4444') : '#F1F5F9', fontFamily: 'monospace' }}>
              ${equity.toFixed(2)}
            </strong>
          </div>

          <div>
            <span style={{ color: '#64748B' }}>Ký quỹ: </span>
            <strong style={{ color: '#38BDF8', fontFamily: 'monospace' }}>${usedMargin.toFixed(2)}</strong>
          </div>

          <div>
            <span style={{ color: '#64748B' }}>Lãi chốt: </span>
            <strong style={{ color: netProfitUsd >= 0 ? '#10B981' : '#EF4444', fontFamily: 'monospace' }}>
              {netProfitUsd >= 0 ? `+${netProfitUsd.toFixed(2)}` : netProfitUsd.toFixed(2)} U
              {totalTrades > 0 && <span style={{ color: '#64748B', fontSize: '10px', marginLeft: '3px' }}>({winRate.toFixed(0)}%)</span>}
            </strong>
          </div>

          {onNavigateToWallet && (
            <button
              onClick={() => onNavigateToWallet('paper-wallet')}
              className="btn-icon"
              style={{
                width: '24px',
                height: '24px',
                color: '#F59E0B',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Quản lý chi tiết Ví Đầu Tư Ảo"
            >
              <ExternalLink size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
