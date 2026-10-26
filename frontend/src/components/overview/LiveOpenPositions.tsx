import React from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Crosshair,
  ExternalLink,
  Flame,
  ShieldAlert,
  Target,
  Zap,
} from 'lucide-react';
import type { SignalItem } from '../../types';

interface LiveOpenPositionsProps {
  signals: SignalItem[];
  currentPrice: number;
  onSelectSignal?: (signal: SignalItem) => void;
}

export const LiveOpenPositions: React.FC<LiveOpenPositionsProps> = ({
  signals,
  currentPrice,
  onSelectSignal,
}) => {
  // Lọc các tín hiệu đang mở (ENTRY_REACHED: Đang khớp lệnh thả nổi PnL; ACTIVE: Đang chờ khớp entry)
  const openPositions = signals.filter(
    (s) => s.status === 'ENTRY_REACHED' || s.status === 'ACTIVE'
  );

  // Phân loại
  const matchedPositions = openPositions.filter((s) => s.status === 'ENTRY_REACHED');
  const pendingPositions = openPositions.filter((s) => s.status === 'ACTIVE');

  return (
    <div
      className="card"
      id="live-open-positions-widget"
      style={{
        marginBottom: '20px',
        border: '1px solid rgba(245, 158, 11, 0.25)',
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.35)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Decorative ambient glow */}
      <div
        style={{
          position: 'absolute',
          top: '-60px',
          right: '-60px',
          width: '180px',
          height: '180px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0) 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* Header */}
      <div
        className="card-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: '12px',
          flexWrap: 'wrap',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              backgroundColor: 'rgba(245, 158, 11, 0.15)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: 'var(--color-accent-gold)',
            }}
          >
            <Zap size={18} />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#F8FAFC', letterSpacing: '0.3px', margin: 0 }}>
              Vị Thế Đang Khớp Lệnh & Lời Lỗ Thả Nổi (Live Floating PnL)
            </h3>
            <p style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px', margin: 0 }}>
              Bám sát thời gian thực giá nến MT5 • Tính toán số Pip và Giá lời/lỗ tức thì
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: 700,
              backgroundColor: matchedPositions.length > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.1)',
              border: `1px solid ${matchedPositions.length > 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(148, 163, 184, 0.2)'}`,
              color: matchedPositions.length > 0 ? '#10B981' : '#94A3B8',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: matchedPositions.length > 0 ? '#10B981' : '#94A3B8',
                boxShadow: matchedPositions.length > 0 ? '0 0 8px #10B981' : 'none',
              }}
            />
            {matchedPositions.length} VỊ THẾ ĐANG KHỚP
          </span>

          {pendingPositions.length > 0 && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '999px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                color: '#F59E0B',
              }}
            >
              <Crosshair size={12} />
              {pendingPositions.length} CHỜ ENTRY
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div style={{ paddingTop: '16px' }}>
        {openPositions.length === 0 ? (
          <div
            style={{
              padding: '24px 16px',
              textAlign: 'center',
              backgroundColor: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '8px',
              border: '1px dashed rgba(255, 255, 255, 0.1)',
            }}
          >
            <Activity size={24} style={{ color: '#64748B', margin: '0 auto 8px auto', display: 'block' }} />
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#CBD5E1' }}>
              Hiện tại chưa có vị thế nào đang mở
            </div>
            <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
              Bot đang liên tục quét nến M5 và các khung lớn H1/H4. Khi có setup Order Block hoặc FVG hợp lệ, lệnh sẽ xuất hiện tại đây.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* 1. Lệnh ĐÃ KHỚP (ENTRY_REACHED) */}
            {matchedPositions.map((pos) => {
              const isSell = pos.direction === 'SELL';
              const entryPrice = pos.plannedEntry || (pos.entryZone[0] + pos.entryZone[1]) / 2;
              const livePrice = currentPrice > 0 ? currentPrice : entryPrice;

              // Tính toán chênh lệch (Points và Pips cho XAUUSD: 1 giá = 10 pips)
              const pnlPoints = isSell ? entryPrice - livePrice : livePrice - entryPrice;
              const pnlPips = pnlPoints * 10;
              const isProfit = pnlPoints >= 0;

              // Khoảng cách tới TP1 và SL
              const tp1DistancePoints = Math.abs(pos.takeProfit1 - entryPrice); // mục tiêu (thường 10 giá)
              const remainingToTp1 = isSell ? livePrice - pos.takeProfit1 : pos.takeProfit1 - livePrice;
              const remainingToSl = isSell ? pos.stopLoss - livePrice : livePrice - pos.stopLoss;

              // Tiến trình đến TP1 (%)
              const progressPct =
                tp1DistancePoints > 0
                  ? Math.min(100, Math.max(0, (pnlPoints / tp1DistancePoints) * 100))
                  : 0;

              return (
                <div
                  key={pos.id}
                  id={`matched-position-${pos.id}`}
                  style={{
                    backgroundColor: 'rgba(15, 23, 42, 0.85)',
                    border: `1px solid ${isProfit ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}`,
                    borderRadius: '10px',
                    padding: '16px',
                    position: 'relative',
                    boxShadow: isProfit
                      ? '0 4px 20px rgba(16, 185, 129, 0.08)'
                      : '0 4px 20px rgba(239, 68, 68, 0.08)',
                  }}
                >
                  {/* Top Bar của Card */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '8px',
                      marginBottom: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 800,
                          backgroundColor: isSell ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                          color: isSell ? '#EF4444' : '#10B981',
                          border: `1px solid ${isSell ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                        }}
                      >
                        {isSell ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}
                        {pos.direction} {pos.symbol}
                      </span>

                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          color: '#94A3B8',
                          backgroundColor: 'rgba(255, 255, 255, 0.06)',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                        }}
                      >
                        #{pos.id} • {pos.timeframe}
                      </span>

                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          color: '#10B981',
                          backgroundColor: 'rgba(16, 185, 129, 0.1)',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <Flame size={12} />
                        ĐÃ KHỚP LỆNH (IN-TRADE)
                      </span>
                    </div>

                    {/* Điểm Confluence Score */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="text-xs text-muted">Setup: {pos.strategyVersion}</span>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 800,
                          color: 'var(--color-accent-gold)',
                          backgroundColor: 'rgba(245, 158, 11, 0.12)',
                          padding: '2px 8px',
                          borderRadius: '4px',
                        }}
                      >
                        Score: {pos.score}/100
                      </span>
                      {onSelectSignal && (
                        <button
                          onClick={() => onSelectSignal(pos)}
                          style={{
                            background: 'transparent',
                            border: '1px solid rgba(255, 255, 255, 0.15)',
                            color: '#94A3B8',
                            borderRadius: '4px',
                            padding: '3px 8px',
                            fontSize: '11px',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <ExternalLink size={11} /> Chi tiết
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Khu Vực Hiển Thị PnL Khủng (Headline Floating PnL) */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: '12px',
                      padding: '14px',
                      borderRadius: '8px',
                      backgroundColor: isProfit ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                      border: `1px solid ${isProfit ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                      marginBottom: '14px',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 600 }}>
                        LỜI / LỖ THẢ NỔI THỜI GIAN THỰC (FLOATING PNL)
                      </div>
                      <div
                        style={{
                          fontSize: '24px',
                          fontWeight: 900,
                          fontFamily: 'monospace',
                          color: isProfit ? '#10B981' : '#EF4444',
                          marginTop: '2px',
                          letterSpacing: '-0.5px',
                        }}
                      >
                        {isProfit ? `+${pnlPips.toFixed(1)} PIPS` : `${pnlPips.toFixed(1)} PIPS`}
                        <span
                          style={{
                            fontSize: '14px',
                            fontWeight: 700,
                            marginLeft: '8px',
                            opacity: 0.9,
                          }}
                        >
                          ({isProfit ? `+${pnlPoints.toFixed(2)}` : pnlPoints.toFixed(2)} giá)
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: isProfit ? '#34D399' : '#F87171', marginTop: '2px' }}>
                        {isProfit
                          ? `✓ Đang có lãi (+${(pnlPoints * 100).toFixed(0)}$ trên 1 lot tiêu chuẩn)`
                          : `⚠️ Đang âm (${(pnlPoints * 100).toFixed(0)}$ trên 1 lot tiêu chuẩn)`}
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', textAlign: 'right' }}>
                      <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '6px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: '#94A3B8' }}>Giá Khớp Entry</div>
                        <div style={{ fontSize: '13px', fontWeight: 800, fontFamily: 'monospace', color: '#F8FAFC' }}>
                          ${entryPrice.toFixed(2)}
                        </div>
                      </div>
                      <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '6px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: '#94A3B8' }}>Giá Thị Trường</div>
                        <div
                          style={{
                            fontSize: '13px',
                            fontWeight: 800,
                            fontFamily: 'monospace',
                            color: isProfit ? '#10B981' : '#EF4444',
                          }}
                        >
                          ${livePrice.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 4 Mức Giá Quản Trị Lệnh */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                      gap: '10px',
                      marginBottom: '14px',
                    }}
                  >
                    {/* Entry */}
                    <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.03)', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <div style={{ fontSize: '10px', color: '#94A3B8' }}>Vùng Khớp Entry</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, fontFamily: 'monospace', color: '#F1F5F9', marginTop: '2px' }}>
                        ${pos.entryZone[0].toFixed(2)} - ${pos.entryZone[1].toFixed(2)}
                      </div>
                    </div>

                    {/* SL */}
                    <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.05)', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.15)' }}>
                      <div style={{ fontSize: '10px', color: '#F87171', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <ShieldAlert size={11} /> Cắt Lỗ (SL 10 giá)
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, fontFamily: 'monospace', color: '#EF4444', marginTop: '2px' }}>
                        ${pos.stopLoss.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '2px' }}>
                        Cách {remainingToSl > 0 ? remainingToSl.toFixed(2) : '0.00'} giá ({Math.max(0, remainingToSl * 10).toFixed(0)} pips)
                      </div>
                    </div>

                    {/* TP1 */}
                    <div style={{ backgroundColor: 'rgba(16, 185, 129, 0.05)', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.15)' }}>
                      <div style={{ fontSize: '10px', color: '#34D399', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Target size={11} /> Chốt Lời 1 (TP1 10 giá)
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, fontFamily: 'monospace', color: '#10B981', marginTop: '2px' }}>
                        ${pos.takeProfit1.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '2px' }}>
                        {remainingToTp1 <= 0 ? '✓ ĐÃ CHẠM TP1!' : `Còn ${remainingToTp1.toFixed(2)} giá (${(remainingToTp1 * 10).toFixed(0)} pips)`}
                      </div>
                    </div>

                    {/* TP2 */}
                    <div style={{ backgroundColor: 'rgba(16, 185, 129, 0.03)', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.1)' }}>
                      <div style={{ fontSize: '10px', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Target size={11} /> Chốt Lời 2 (Kỳ vọng)
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, fontFamily: 'monospace', color: '#10B981', marginTop: '2px' }}>
                        ${pos.takeProfit2.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '2px' }}>
                        Tỷ lệ R:R 1:{pos.riskReward.toFixed(1)}
                      </div>
                    </div>
                  </div>

                  {/* Thanh Tiến Trình R:R và Mục Tiêu TP1 */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94A3B8', marginBottom: '4px' }}>
                      <span>Tiến trình mục tiêu TP1:</span>
                      <span style={{ fontWeight: 700, color: isProfit ? '#10B981' : '#F87171' }}>
                        {progressPct.toFixed(1)}% hoàn thành ({pnlPoints > 0 ? `+${pnlPoints.toFixed(1)}` : '0.0'} / 10.0 giá)
                      </span>
                    </div>
                    <div
                      style={{
                        width: '100%',
                        height: '6px',
                        backgroundColor: 'rgba(255, 255, 255, 0.08)',
                        borderRadius: '3px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${progressPct}%`,
                          height: '100%',
                          backgroundColor: isProfit ? '#10B981' : '#EF4444',
                          transition: 'width 0.4s ease',
                          borderRadius: '3px',
                          boxShadow: isProfit ? '0 0 10px rgba(16, 185, 129, 0.5)' : 'none',
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}

            {/* 2. Lệnh ĐANG CHỜ KHỚP VÙNG ENTRY (ACTIVE) */}
            {pendingPositions.map((pos) => {
              const entryMid = (pos.entryZone[0] + pos.entryZone[1]) / 2;
              const livePrice = currentPrice > 0 ? currentPrice : entryMid;
              const distanceToEntry = Math.abs(livePrice - entryMid);
              const distancePips = distanceToEntry * 10;

              return (
                <div
                  key={pos.id}
                  style={{
                    backgroundColor: 'rgba(15, 23, 42, 0.6)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 800,
                        backgroundColor: pos.direction === 'SELL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                        color: pos.direction === 'SELL' ? '#EF4444' : '#10B981',
                      }}
                    >
                      {pos.direction}
                    </span>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#F1F5F9' }}>
                      Vùng Entry: ${pos.entryZone[0].toFixed(2)} – ${pos.entryZone[1].toFixed(2)}
                    </span>
                    <span style={{ fontSize: '11px', color: '#94A3B8' }}>
                      (SL: ${pos.stopLoss.toFixed(2)} • TP1: ${pos.takeProfit1.toFixed(2)})
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '12px', color: '#F59E0B', fontWeight: 700 }}>
                      ⏳ Cách vùng Entry: {distanceToEntry.toFixed(2)} giá ({distancePips.toFixed(1)} Pips)
                    </span>
                    {onSelectSignal && (
                      <button
                        onClick={() => onSelectSignal(pos)}
                        style={{
                          background: 'transparent',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#94A3B8',
                          borderRadius: '4px',
                          padding: '3px 8px',
                          fontSize: '11px',
                          cursor: 'pointer',
                        }}
                      >
                        Chi tiết
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
