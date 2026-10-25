import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react';
import type { SignalItem } from '../../types';

interface SignalDetailModalProps {
  signal: SignalItem | null;
  onClose: () => void;
  onResendTelegram?: (signalId: string) => void;
}

export const SignalDetailModal: React.FC<SignalDetailModalProps> = ({ signal, onClose, onResendTelegram }) => {
  if (!signal) return null;

  const isBuy = signal.direction === 'BUY';
  const isSell = signal.direction === 'SELL';
  const dirClass = isBuy ? 'buy' : isSell ? 'sell' : 'wait';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className={`badge-direction ${dirClass}`} style={{ fontSize: '13px', padding: '4px 10px' }}>
              {isBuy ? <TrendingUp size={15} /> : isSell ? <TrendingDown size={15} /> : null}
              {signal.direction}
            </span>
            <span className="font-mono font-bold text-base text-primary">{signal.symbol}</span>
            <span className="text-xs text-muted font-mono">[{signal.id}]</span>
          </div>
          <button className="btn-icon" onClick={onClose} title="Đóng">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Status & Confluence Score Banner */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              backgroundColor: 'var(--bg-card-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-color)',
              marginBottom: '18px',
            }}
          >
            <div>
              <div className="text-xs text-secondary">Trạng thái tín hiệu</div>
              <div className="font-bold text-sm text-primary" style={{ marginTop: '2px' }}>
                {signal.status}
              </div>
            </div>
            <div>
              <div className="text-xs text-secondary">Chiến lược & Khung thời gian</div>
              <div className="font-mono text-sm text-primary" style={{ marginTop: '2px' }}>
                {signal.strategyVersion} • {signal.timeframe}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="text-xs text-secondary">Confluence Score</div>
              <div className="font-mono font-extrabold text-lg text-gold" style={{ marginTop: '2px' }}>
                {signal.score} / 100
              </div>
            </div>
          </div>

          {/* Trade Parameters Matrix */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '12px',
              marginBottom: '18px',
            }}
          >
            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary">Entry Zone</div>
              <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '4px' }}>
                {signal.entryZone[0] ? `${signal.entryZone[0].toFixed(2)} - ${signal.entryZone[1].toFixed(2)}` : 'Chờ setup'}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px' }}>±1 giá</div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary">Stop Loss</div>
              <div className="font-mono font-bold text-sm text-sell" style={{ marginTop: '4px' }}>
                {signal.stopLoss ? `$${signal.stopLoss.toFixed(2)}` : 'N/A'}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Cắt lỗ tuyệt đối</div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary">Take Profit 1</div>
              <div className="font-mono font-bold text-sm text-buy" style={{ marginTop: '4px' }}>
                {signal.takeProfit1 ? `$${signal.takeProfit1.toFixed(2)}` : 'N/A'}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Chốt 50% TP1</div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary">Take Profit 2</div>
              <div className="font-mono font-bold text-sm text-buy" style={{ marginTop: '4px' }}>
                {signal.takeProfit2 ? `$${signal.takeProfit2.toFixed(2)}` : 'N/A'}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Gồng lãi TP2</div>
            </div>
          </div>

          {/* Trade Execution Rule Note */}
          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'rgba(245, 158, 11, 0.08)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              marginBottom: '18px',
              fontSize: '12px',
              color: 'var(--text-primary)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--color-accent-gold)', marginBottom: '4px' }}>
              👉 Quy tắc quản lý lệnh vàng thực chiến:
            </div>
            <ul style={{ paddingLeft: '18px', lineHeight: '1.6' }}>
              <li><strong>Entry:</strong> Điểm vào lệnh dao động ±1 giá quanh vùng đề xuất.</li>
              <li><strong>Lãi 5 giá:</strong> Tự động kéo Stop Loss về hòa vốn (Breakeven).</li>
              <li><strong>Lãi 10 giá:</strong> Chốt 50% khối lượng tại TP1, dời Stop Loss dương để nuôi TP2.</li>
            </ul>
          </div>

          {/* Reason & Invalidation */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div
              style={{
                padding: '12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs font-semibold text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <CheckCircle2 size={14} className="text-buy" /> Lý do phát tín hiệu:
              </div>
              <div className="text-sm text-primary">{signal.reason || 'Không có lý do chi tiết'}</div>
            </div>

            <div
              style={{
                padding: '12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs font-semibold text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <AlertCircle size={14} className="text-sell" /> Điều kiện hủy bỏ (Invalidation):
              </div>
              <div className="text-sm text-primary">{signal.invalidation || 'Không có điều kiện hủy cụ thể'}</div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            {onResendTelegram && (
              <button
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
                onClick={() => {
                  onResendTelegram(signal.id);
                  onClose();
                }}
              >
                <span>📢</span> Bắn Lại Lệnh Này Lên Telegram
              </button>
            )}
          </div>
          <button className="btn btn-secondary" onClick={onClose}>
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
