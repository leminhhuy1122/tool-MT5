import React, { useMemo, useState } from 'react';
import {
  BarChart2,
  CheckCircle2,
  PieChart,
  Scale,
  TrendingUp,
  Trophy,
} from 'lucide-react';
import type { PerformanceData, SignalItem } from '../../types';

interface PerformanceChartsProps {
  performance: PerformanceData;
  signals: SignalItem[];
}

export const PerformanceCharts: React.FC<PerformanceChartsProps> = ({ performance, signals }) => {
  const [hoveredPoint, setHoveredPoint] = useState<{
    index: number;
    pips: number;
    cumulative: number;
    id: string;
    x: number;
    y: number;
  } | null>(null);

  // Tính chuỗi điểm Cumulative PnL từ các lệnh đã giải quyết
  const closedSignals = useMemo(() => {
    return signals
      .filter((s) => s.isWin || s.isLoss || s.isBreakeven || s.status === 'TP_REACHED' || s.status === 'SL_REACHED')
      .reverse(); // từ cũ nhất đến mới nhất
  }, [signals]);

  // Chuỗi tích lũy pips
  const equityPoints = useMemo(() => {
    if (closedSignals.length === 0) {
      // Mock khởi tạo mốc cơ sở nếu dữ liệu lệnh mới bắt đầu
      return [
        { id: 'Start', pips: 0, cumulative: 0 },
        { id: 'Lệnh 1', pips: 100, cumulative: 100 },
        { id: 'Lệnh 2', pips: -100, cumulative: 0 },
        { id: 'Lệnh 3', pips: 25.2, cumulative: 25.2 },
      ];
    }

    let runningPips = 0;
    const pts = [{ id: 'Start', pips: 0, cumulative: 0 }];

    for (const s of closedSignals) {
      let pips = s.pnlPips ?? (s.isWin || s.status === 'TP_REACHED' ? 100 : s.isLoss || s.status === 'SL_REACHED' ? -100 : 0);
      runningPips += pips;
      pts.push({
        id: s.id,
        pips,
        cumulative: runningPips,
      });
    }

    return pts;
  }, [closedSignals]);

  // Kích thước SVG biểu đồ đường
  const svgWidth = 520;
  const svgHeight = 180;
  const paddingX = 40;
  const paddingY = 25;

  const minCum = Math.min(0, ...equityPoints.map((p) => p.cumulative));
  const maxCum = Math.max(10, ...equityPoints.map((p) => p.cumulative));
  const cumRange = Math.max(1, maxCum - minCum);

  const getX = (idx: number) => paddingX + (idx / Math.max(1, equityPoints.length - 1)) * (svgWidth - paddingX * 2);
  const getY = (val: number) => svgHeight - paddingY - ((val - minCum) / cumRange) * (svgHeight - paddingY * 2);

  // Tạo đường dẫn SVG Path cho biểu đồ đường
  const pathD = useMemo(() => {
    if (equityPoints.length === 0) return '';
    return equityPoints.reduce((acc, pt, i) => {
      const x = getX(i);
      const y = getY(pt.cumulative);
      return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
    }, '');
  }, [equityPoints, minCum, cumRange]);

  // Tạo vùng gradient đóng
  const areaD = useMemo(() => {
    if (equityPoints.length === 0) return '';
    const firstX = getX(0);
    const lastX = getX(equityPoints.length - 1);
    const zeroY = getY(0);
    return `${pathD} L ${lastX} ${zeroY} L ${firstX} ${zeroY} Z`;
  }, [pathD, equityPoints, minCum, cumRange]);

  // Thống kê Doughnut chart
  const wins = performance.winsCount ?? (performance.winRate > 0 ? 1 : 0);
  const losses = performance.lossesCount ?? (performance.lossRate > 0 ? 1 : 0);
  const total = Math.max(1, wins + losses);
  const winPercent = Math.round((wins / total) * 100);

  // Tính chu vi đường tròn SVG Doughnut (bán kính r = 42, chu vi ~ 264)
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const winStrokeDash = (winPercent / 100) * circumference;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
        gap: '20px',
        marginBottom: '20px',
      }}
    >
      {/* 1. Biểu đồ Đường Cong Tích Lũy Lãi Lỗ (Cumulative PnL Equity Curve) */}
      <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
        <div className="card-header">
          <span className="card-title">
            <TrendingUp size={16} className="text-buy" /> Biểu Đồ Tăng Trưởng PnL Tích Lũy (Pips)
          </span>
          <span className="text-xs text-buy font-mono font-bold">
            Net: +{equityPoints[equityPoints.length - 1]?.cumulative.toFixed(1)} Pips
          </span>
        </div>

        <div style={{ position: 'relative', width: '100%', height: `${svgHeight}px` }}>
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ width: '100%', height: '100%', overflow: 'visible' }}
          >
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10B981" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Trục hoành mức 0 (Zero Baseline) */}
            <line
              x1={paddingX}
              y1={getY(0)}
              x2={svgWidth - paddingX}
              y2={getY(0)}
              stroke="rgba(255, 255, 255, 0.15)"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
            <text
              x={paddingX - 6}
              y={getY(0) + 4}
              fill="var(--text-muted)"
              fontSize="10"
              fontFamily="var(--font-mono)"
              textAnchor="end"
            >
              0p
            </text>

            {/* Vùng gradient mượt bên dưới đường cong */}
            <path d={areaD} fill="url(#equityGrad)" />

            {/* Đường nét chính biểu đồ PnL */}
            <path
              d={pathD}
              fill="none"
              stroke="#10B981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Các điểm mốc tròn tương tác */}
            {equityPoints.map((pt, i) => {
              const cx = getX(i);
              const cy = getY(pt.cumulative);
              const isProfit = pt.pips >= 0;

              return (
                <g key={i}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={hoveredPoint?.index === i ? 6 : 4}
                    fill={isProfit ? '#10B981' : '#EF4444'}
                    stroke="var(--bg-card)"
                    strokeWidth="2"
                    style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
                    onMouseEnter={() =>
                      setHoveredPoint({
                        index: i,
                        pips: pt.pips,
                        cumulative: pt.cumulative,
                        id: pt.id,
                        x: cx,
                        y: cy,
                      })
                    }
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                </g>
              );
            })}
          </svg>

          {/* Hover Tooltip Popup */}
          {hoveredPoint && (
            <div
              style={{
                position: 'absolute',
                left: `${(hoveredPoint.x / svgWidth) * 100}%`,
                top: `${(hoveredPoint.y / svgHeight) * 100 - 35}%`,
                transform: 'translate(-50%, -100%)',
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid var(--border-color)',
                padding: '6px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '11px',
                pointerEvents: 'none',
                whiteSpace: 'nowrap',
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                zIndex: 10,
              }}
            >
              <div style={{ color: 'var(--text-secondary)' }}>Mã: {hoveredPoint.id}</div>
              <div
                style={{
                  fontWeight: 700,
                  color: hoveredPoint.pips >= 0 ? 'var(--color-buy)' : 'var(--color-sell)',
                }}
              >
                {hoveredPoint.pips >= 0 ? `+${hoveredPoint.pips}p` : `${hoveredPoint.pips}p`} • Tích lũy:{' '}
                {hoveredPoint.cumulative >= 0 ? `+${hoveredPoint.cumulative}p` : `${hoveredPoint.cumulative}p`}
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '8px',
            fontSize: '11px',
            color: 'var(--text-secondary)',
          }}
        >
          <span>Khởi tạo</span>
          <span className="font-mono text-xs text-muted">
            {closedSignals.length} giao dịch đã kết thúc
          </span>
          <span>Mới nhất</span>
        </div>
      </div>

      {/* 2. Biểu đồ Vòng Tròn Tỷ Lệ Thắng (Winrate Doughnut) & Chỉ Số Hiệu Suất */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <PieChart size={16} className="text-gold" /> Tỷ Lệ Thắng & Chỉ Số Hiệu Suất Lệnh
          </span>
          <span className="text-xs text-secondary font-mono">
            {wins + losses} Lệnh Đã Giải Quyết
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-around',
            gap: '16px',
            flexWrap: 'wrap',
          }}
        >
          {/* SVG Doughnut Ring */}
          <div style={{ position: 'relative', width: '110px', height: '110px', flexShrink: 0 }}>
            <svg viewBox="0 0 100 100" style={{ transform: 'rotate(-90deg)', width: '100%', height: '100%' }}>
              {/* Vòng nền (Losses) */}
              <circle
                cx="50"
                cy="50"
                r={radius}
                fill="none"
                stroke="#EF4444"
                strokeWidth="12"
                strokeOpacity="0.85"
              />
              {/* Vòng phần trăm thắng (Wins) */}
              <circle
                cx="50"
                cy="50"
                r={radius}
                fill="none"
                stroke="#10B981"
                strokeWidth="12"
                strokeDasharray={`${winStrokeDash} ${circumference}`}
                strokeLinecap="round"
                style={{ transition: 'stroke-dasharray 0.5s ease' }}
              />
            </svg>

            {/* Số tỷ lệ Winrate ở tâm vòng tròn */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center',
              }}
            >
              <div className="font-mono font-extrabold text-lg text-buy">
                {performance.winRate.toFixed(1)}%
              </div>
              <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Win Rate
              </div>
            </div>
          </div>

          {/* Cụm 3 Thẻ Chỉ Số Cốt Lõi */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', flex: 1 }}>
            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={12} className="text-buy" /> Tỷ Lệ Lệnh
              </div>
              <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '2px' }}>
                <span className="text-buy">{wins} W</span> / <span className="text-sell">{losses} L</span>
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px', fontSize: '10px' }}>
                Hòa vốn: 0 lệnh
              </div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <BarChart2 size={12} className="text-gold" /> Profit Factor
              </div>
              <div className="font-mono font-bold text-sm text-gold" style={{ marginTop: '2px' }}>
                {performance.profitFactor.toFixed(2)}
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px', fontSize: '10px' }}>
                Lợi nhuận / Thua lỗ
              </div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Scale size={12} className="text-primary" /> Trung Bình R:R
              </div>
              <div className="font-mono font-bold text-sm text-primary" style={{ marginTop: '2px' }}>
                +{performance.averageR.toFixed(2)}R
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px', fontSize: '10px' }}>
                Risk to Reward
              </div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="text-xs text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Trophy size={12} className="text-buy" /> Tổng PnL Đã Chốt
              </div>
              <div className="font-mono font-bold text-sm text-buy" style={{ marginTop: '2px' }}>
                +25.2 Pips
              </div>
              <div className="text-xs text-muted" style={{ marginTop: '2px', fontSize: '10px' }}>
                +2.52 giá vàng
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
