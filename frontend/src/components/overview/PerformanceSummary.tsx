import { Award } from 'lucide-react';
import type { PerformanceData } from '../../types';

interface PerformanceSummaryProps {
  data: PerformanceData;
}

export const PerformanceSummary: React.FC<PerformanceSummaryProps> = ({ data }) => {
  if (!data.hasRealData || data.totalSignals === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Award size={16} className="text-gold" /> Hiệu Suất Chiến Lược (Outcomes)
          </span>
        </div>
        <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <p className="font-medium text-sm">No performance data available.</p>
          <p className="text-xs" style={{ marginTop: '4px' }}>
            Hệ thống cần tích lũy thêm các lệnh đã chạm TP hoặc SL để tính toán thống kê chính xác.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <Award size={16} className="text-gold" /> Hiệu Suất Giao Dịch Thực Tế
        </span>
        <span className="text-xs text-secondary font-mono">{data.totalSignals} Lệnh đã giải quyết</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '12px',
          marginBottom: '16px',
        }}
      >
        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary">Tỷ Lệ Thắng</div>
          <div className="font-mono font-extrabold text-xl text-buy" style={{ marginTop: '4px' }}>
            {data.winRate.toFixed(1)}%
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Win Rate</div>
        </div>

        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary">Tỷ Lệ Thua</div>
          <div className="font-mono font-extrabold text-xl text-sell" style={{ marginTop: '4px' }}>
            {data.lossRate.toFixed(1)}%
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Loss Rate</div>
        </div>

        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary">Profit Factor</div>
          <div className="font-mono font-extrabold text-xl text-gold" style={{ marginTop: '4px' }}>
            {data.profitFactor.toFixed(2)}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Lãi / Lỗ</div>
        </div>

        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--bg-card-subtle)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div className="text-xs text-secondary">Trung Bình R:R</div>
          <div className="font-mono font-extrabold text-xl text-primary" style={{ marginTop: '4px' }}>
            +{data.averageR.toFixed(2)}R
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>Avg R</div>
        </div>
      </div>

      {/* Breakdown by Strategy */}
      {data.byStrategy && data.byStrategy.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <div className="text-xs text-secondary font-semibold" style={{ marginBottom: '8px' }}>
            Hiệu Suất Theo Chiến Lược
          </div>
          {data.byStrategy.map((st) => (
            <div
              key={st.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-card-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '6px',
                fontSize: '12px',
              }}
            >
              <span className="font-mono font-medium text-primary">{st.name}</span>
              <span className="text-secondary">{st.total} lệnh</span>
              <span className="text-buy font-bold">{st.winRate.toFixed(1)}% Win</span>
              <span className="text-gold font-bold">PF: {st.pf.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
