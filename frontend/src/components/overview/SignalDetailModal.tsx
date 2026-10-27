import {
  AlertCircle,
  CheckCircle2,
  Scale,
  TrendingDown,
  TrendingUp,
  Trophy,
  X,
  XCircle,
  Zap,
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

  const isWin = Boolean(signal.isWin || signal.status === 'TP_REACHED' || (signal.pnlPoints && signal.pnlPoints > 0));
  const isLoss = Boolean(signal.isLoss || signal.status === 'SL_REACHED' || (signal.pnlPoints && signal.pnlPoints < 0));
  const isBreakeven = Boolean(signal.isBreakeven || (signal.pnlPoints === 0 && signal.exitPrice));

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
          {/* Win / Loss Outcome Highlight Banner */}
          {isWin && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                marginBottom: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Trophy size={20} color="#10b981" />
                <div>
                  <div style={{ fontWeight: 800, color: '#10b981', fontSize: '14px' }}>
                    🏆 LỆNH THẮNG (WIN) • TAKE PROFIT THÀNH CÔNG
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {signal.exitPrice ? `Thoát lệnh chốt lời tại giá $${signal.exitPrice.toFixed(2)}` : 'Đã đạt mục tiêu Take Profit'}
                    {signal.durationSeconds ? ` • Thời gian giữ lệnh: ${Math.round(signal.durationSeconds / 60)} phút` : ''}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="font-mono font-bold text-base" style={{ color: '#10b981' }}>
                  {signal.pnlPoints ? `+${signal.pnlPoints.toFixed(1)} pts` : '+TP'}
                </div>
                {signal.pnlPips ? (
                  <div className="font-mono text-xs text-buy">+{signal.pnlPips.toFixed(1)} pips</div>
                ) : null}
              </div>
            </div>
          )}

          {isLoss && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                marginBottom: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <XCircle size={20} color="#ef4444" />
                <div>
                  <div style={{ fontWeight: 800, color: '#ef4444', fontSize: '14px' }}>
                    ❌ LỆNH THUA (LOST) • ĐÃ CHẠM STOP LOSS
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {signal.exitPrice ? `Thoát lệnh cắt lỗ tại giá $${signal.exitPrice.toFixed(2)}` : 'Đã chạm mốc Stop Loss để bảo vệ vốn'}
                    {signal.durationSeconds ? ` • Thời gian giữ lệnh: ${Math.round(signal.durationSeconds / 60)} phút` : ''}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="font-mono font-bold text-base" style={{ color: '#ef4444' }}>
                  {signal.pnlPoints ? `${signal.pnlPoints.toFixed(1)} pts` : '-SL'}
                </div>
                {signal.pnlPips ? (
                  <div className="font-mono text-xs text-sell">{signal.pnlPips.toFixed(1)} pips</div>
                ) : null}
              </div>
            </div>
          )}

          {(signal.isDca || signal.setupType?.startsWith('DCA_')) && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(168, 85, 247, 0.12)',
                border: '1px solid rgba(168, 85, 247, 0.35)',
                marginBottom: '14px',
              }}
            >
              <Scale size={20} color="#c084fc" />
              <div>
                <div style={{ fontWeight: 800, color: '#c084fc', fontSize: '13px' }}>
                  🎯 CHIẾN LƯỢC SMART DCA • CỨU LỆNH VỀ HÒA & X2 LỢI NHUẬN
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {signal.dcaBreakevenPrice
                    ? `Điểm hòa vốn giỏ lệnh: $${signal.dcaBreakevenPrice.toFixed(2)}. Chạm TP1 hòa vốn an toàn; giữ đến TP2 $${signal.takeProfit2.toFixed(2)} để X2 LỢI NHUẬN cả 2 lệnh!`
                    : 'Tín hiệu DCA vào tại cản đảo chiều giúp kéo điểm hòa vốn về gần, chốt lời kép khi giá quay lại xu hướng ban đầu.'}
                </div>
              </div>
            </div>
          )}

          {isBreakeven && !isWin && !isLoss && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                marginBottom: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Scale size={20} color="#f59e0b" />
                <div>
                  <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: '14px' }}>
                    ⚖️ HÒA VỐN (BREAKEVEN)
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {signal.exitPrice ? `Thoát lệnh bảo toàn vốn tại giá $${signal.exitPrice.toFixed(2)}` : 'Lệnh đóng không phát sinh lỗ'}
                  </div>
                </div>
              </div>
              <div className="font-mono font-bold text-sm text-gold">0.0 pts</div>
            </div>
          )}

          {signal.setupType === 'SMC_LIQUIDITY_SWEEP' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isSell ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                border: `1px solid ${isSell ? 'rgba(239, 68, 68, 0.35)' : 'rgba(16, 185, 129, 0.35)'}`,
                marginBottom: '14px',
              }}
            >
              <Zap size={20} color={isSell ? '#ef4444' : '#10b981'} />
              <div>
                <div style={{ fontWeight: 800, color: isSell ? '#ef4444' : '#10b981', fontSize: '13px' }}>
                  {isSell ? '🎯 CHIẾN LƯỢC BẮT ĐỈNH • SĂN THANH KHOẢN (BSL SWEEP)' : '🎯 CHIẾN LƯỢC BẮT ĐÁY • SĂN THANH KHOẢN (SSL SWEEP)'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {isSell
                    ? 'Nến M5 đâm xuyên đỉnh cũ để bẫy phe Buy FOMO, sau đó để lại râu từ chối (Rejection Wick >= 0.6 giá) và đóng nến quay đầu. Kích hoạt SELL bắt đỉnh an toàn!'
                    : 'Nến M5 đạp thủng đáy cũ để bẫy phe Sell đuổi, sau đó rút chân từ chối giá thấp (Rejection Wick >= 0.6 giá) và đóng nến tăng. Kích hoạt BUY bắt đáy an toàn!'}
                </div>
              </div>
            </div>
          )}

          {signal.setupType === 'RSI_DIVERGENCE' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                marginBottom: '14px',
              }}
            >
              <Zap size={20} color="#f59e0b" />
              <div>
                <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: '13px' }}>
                  {isSell ? '⚡ CHIẾN LƯỢC BẮT ĐỈNH ĐẢO CHIỀU • PHÂN KỲ RSI QUÁ MUA' : '⚡ CHIẾN LƯỢC BẮT ĐÁY ĐẢO CHIỀU • PHÂN KỲ RSI QUÁ BÁN'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {isSell
                    ? 'Giá tạo đỉnh mới nhưng RSI tạo đỉnh thấp hơn (Phân kỳ giảm) tại vùng kháng cự. Động lượng mua cạn kiệt, báo hiệu đảo chiều giảm!'
                    : 'Giá tạo đáy mới nhưng RSI tạo đáy cao hơn (Phân kỳ tăng) tại vùng hỗ trợ. Động lượng bán suy yếu, báo hiệu đảo chiều tăng!'}
                </div>
              </div>
            </div>
          )}

          {(signal.isPredictive || signal.setupType === 'PREDICTIVE_LIMIT') && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(168, 85, 247, 0.12)',
                border: '1px solid rgba(168, 85, 247, 0.35)',
                marginBottom: '14px',
              }}
            >
              <Zap size={20} color="#C084FC" />
              <div>
                <div style={{ fontWeight: 800, color: '#C084FC', fontSize: '13px' }}>
                  🔮 KẾ HOẠCH DỰ ĐOÁN ĐÓN SÓNG TỪ XA ({signal.direction} LIMIT)
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Hệ thống phân tích Order Block và cấu trúc cản chưa kiểm định từ xa. Cho phép Trader chủ động cài đặt Limit đón sóng trước!
                </div>
              </div>
            </div>
          )}

          {signal.status === 'ENTRY_REACHED' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                marginBottom: '14px',
              }}
            >
              <Zap size={18} color="#38bdf8" />
              <div>
                <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '13px' }}>
                  ⚡ LỆNH ĐÃ KHỚP & ĐANG CHẠY THỰC TẾ (IN-TRADE)
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Hệ thống đang bám sát giá trực tiếp từ MT5 và quản trị rủi ro trailing stop theo thời gian thực.
                </div>
              </div>
            </div>
          )}
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
              👉 Quy tắc quản lý lệnh chuẩn Đỉnh/Đáy Kháng Cự & Hỗ Trợ:
            </div>
            <ul style={{ paddingLeft: '18px', lineHeight: '1.6' }}>
              <li><strong>Entry:</strong> Điểm vào lệnh dao động ±1 giá quanh vùng cản đề xuất.</li>
              <li><strong>Stop Loss:</strong> Đặt sát sau đỉnh/đáy cản then chốt + 0.8 giá đệm (3.0 - 8.0 giá). Thủng cản là cắt ngay để bảo toàn vốn.</li>
              <li><strong>Take Profit:</strong> TP1 chốt ngay trước vùng cản đối diện (≥ 1.5R), TP2 mở rộng đón trọn con sóng (≥ 2.5R).</li>
              <li><strong>Khóa hòa vốn:</strong> Khi giá đi được 50% chặng đường đến TP1, tự động kéo SL về Breakeven.</li>
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
