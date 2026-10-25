import React from 'react';
import { ArrowLeft, Clock } from 'lucide-react';
import type { MenuId } from '../../types';

interface UpcomingPhaseNoticeProps {
  menuId: MenuId;
  onBackToOverview: () => void;
}

const PHASE_MAP: Record<MenuId, { title: string; phase: string; desc: string }> = {
  overview: { title: 'Overview Dashboard', phase: 'PHASE UI-1', desc: 'Trang tổng quan chính.' },
  signals: { title: 'Signals & Admin Controls', phase: 'Live', desc: 'Quản lý và bắn lại tín hiệu giao dịch.' },
  news: { title: 'News & AI Predictions', phase: 'Live', desc: 'Lịch kinh tế và dự đoán xu thế AI.' },
  system: { title: 'System & Telegram Admin', phase: 'Live', desc: 'Quản trị hệ thống và cấu hình Telegram.' },
  'live-signals': { title: 'Live Signals & Realtime Monitor', phase: 'PHASE UI-2', desc: 'Quản lý tín hiệu thời gian thực, bộ lọc chi tiết BUY/SELL/WAIT/ACTIVE/TP/SL.' },
  'signal-history': { title: 'Signal History & Pagination', phase: 'PHASE UI-2', desc: 'Lịch sử tín hiệu đầy đủ, phân trang server-side, tìm kiếm và xuất dữ liệu.' },
  'telegram-settings': { title: 'Telegram Multi-Recipient Settings', phase: 'PHASE UI-3', desc: 'Quản lý nhiều người nhận tín hiệu Telegram (Personal/Group/Channel), bot configuration an toàn, delivery logs.' },
  'market-analysis': { title: 'Market Analysis & Candlestick Charts', phase: 'PHASE UI-4', desc: 'Biểu đồ nến XAUUSD đa khung thời gian, tích hợp EMA, RSI, ATR và cấu trúc thị trường.' },
  strategy: { title: 'Strategy Configuration', phase: 'PHASE UI-5', desc: 'Cấu hình tham số chiến lược (EMA, RSI, Spread filter, Cooldown).' },
  'economic-calendar': { title: 'Economic News Calendar', phase: 'PHASE UI-5', desc: 'Lịch kinh tế và cảnh báo tin đỏ USD ForexFactory.' },
  'ai-models': { title: 'AI Model Management', phase: 'PHASE UI-5', desc: 'Quản lý mô hình Machine Learning, kiểm định và phê duyệt Candidate -> Production.' },
  backtest: { title: 'Backtest Engine Control', phase: 'PHASE UI-5', desc: 'Khởi chạy kiểm thử lịch sử tương tác trên UI, xem báo cáo Walk-Forward.' },
  performance: { title: 'Performance Analytics', phase: 'PHASE UI-1', desc: 'Báo cáo hiệu suất chi tiết.' },
  'system-monitoring': { title: 'Deep System Telemetry', phase: 'PHASE UI-6', desc: 'Giám sát chi tiết CPU, RAM, Network, Database WAL connections.' },
  logs: { title: 'System & Execution Logs', phase: 'PHASE UI-6', desc: 'Xem log file theo thời gian thực.' },
  settings: { title: 'General & Security Settings', phase: 'PHASE UI-6', desc: 'Cấu hình chung hệ thống và bảo mật.' },
};

export const UpcomingPhaseNotice: React.FC<UpcomingPhaseNoticeProps> = ({ menuId, onBackToOverview }) => {
  const info = PHASE_MAP[menuId] || { title: menuId, phase: 'LỘ TRÌNH KẾ TIẾP', desc: 'Đang theo lộ trình.' };

  return (
    <div
      className="card"
      style={{
        maxWidth: '720px',
        margin: '40px auto',
        padding: '36px',
        textAlign: 'center',
        border: '1px solid var(--border-color)',
      }}
    >
      <div
        style={{
          width: '54px',
          height: '54px',
          borderRadius: '50%',
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          color: 'var(--color-accent-gold)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 18px',
        }}
      >
        <Clock size={28} />
      </div>

      <div className="status-pill demo" style={{ display: 'inline-flex', marginBottom: '12px' }}>
        {info.phase}
      </div>

      <h2 className="text-xl font-bold text-primary" style={{ marginBottom: '8px' }}>
        {info.title}
      </h2>

      <p className="text-secondary text-sm" style={{ marginBottom: '24px', lineHeight: '1.6' }}>
        {info.desc}
        <br />
        Hiện tại hệ thống đang hoàn thành và bàn giao <strong>PHASE UI-1 (Overview Dashboard)</strong>.
        Sau khi bạn nghiệm thu Phase UI-1, các màn hình này sẽ được kích hoạt tuần tự theo yêu cầu.
      </p>

      <button className="btn btn-primary" onClick={onBackToOverview}>
        <ArrowLeft size={16} /> Quay lại Overview Dashboard
      </button>
    </div>
  );
};
