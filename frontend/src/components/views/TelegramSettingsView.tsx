import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bell,
  CheckCircle2,
  MessageSquare,
  Send,
  Shield,
} from 'lucide-react';
import { api } from '../../services/api';
import type { TelegramStatusData } from '../../types';

export const TelegramSettingsView: React.FC = () => {
  const [status, setStatus] = useState<TelegramStatusData>({
    enabled: true,
    isConfigured: true,
    chatId: '@dbgtradingfx',
    totalSent: 0,
    totalFailed: 0,
  });

  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await api.getTelegramStatus();
      setStatus(data);
    } catch {
      // Keep defaults
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await api.testTelegramConnection();
      setTestResult({ type: 'success', message: res.message || 'Gửi tin nhắn thử nghiệm Telegram thành công!' });
      fetchStatus();
    } catch (err: any) {
      setTestResult({ type: 'error', message: err.message || 'Không thể gửi tin nhắn thử nghiệm tới Telegram.' });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Banner */}
      <div
        className="card"
        style={{
          borderLeft: '4px solid var(--color-accent-gold)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bell size={20} className="text-gold" />
            Cấu Hình & Quản Trị Kênh Telegram
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Quản trị kết nối Telegram Bot, bắn tin tức, phát lại lệnh và giám sát thông báo tới Kênh <strong>@dbgtradingfx</strong>.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className={`status-pill ${status.isConfigured ? 'connected' : 'disconnected'}`}>
            {status.isConfigured ? 'TELEGRAM BOT: SẴN SÀNG' : 'CHƯA CẤU HÌNH'}
          </span>
          <button
            className="btn btn-primary"
            onClick={handleTestConnection}
            disabled={isTesting}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
          >
            <Send size={13} />
            {isTesting ? 'Đang kiểm tra...' : 'Bắn Tin Nhắn Thử Nghiệm'}
          </button>
        </div>
      </div>

      {/* Test Result Alert */}
      {testResult && (
        <div
          style={{
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor:
              testResult.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${testResult.type === 'success' ? 'var(--color-buy)' : 'var(--color-sell)'}`,
            color: testResult.type === 'success' ? 'var(--color-buy)' : '#F87171',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {testResult.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            {testResult.message}
          </span>
          <button
            onClick={() => setTestResult(null)}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '12px' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Configuration Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', gap: '20px' }}>
        {/* Real-time Status Card */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Shield size={16} className="text-gold" /> Trạng Thái Kênh & Bot Telegram
            </span>
            <span className="status-pill connected" style={{ fontSize: '10px' }}>HOẠT ĐỘNG</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div className="text-xs text-secondary font-semibold">Kênh Nhận Tin Đích (Target Chat ID)</div>
              <div className="font-mono text-sm text-gold font-bold" style={{ marginTop: '4px' }}>
                {status.chatId || '@dbgtradingfx'}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div className="text-xs text-secondary font-semibold">Đã Bắn Thành Công</div>
                <div className="font-mono text-lg font-bold text-buy" style={{ marginTop: '4px' }}>
                  {status.totalSent} tin
                </div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div className="text-xs text-secondary font-semibold">Lỗi Kết Nối</div>
                <div className="font-mono text-lg font-bold text-sell" style={{ marginTop: '4px' }}>
                  {status.totalFailed} tin
                </div>
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div className="text-xs text-secondary font-semibold">Cơ Chế Chống Trùng Lặp (Deduplication)</div>
              <div className="font-mono text-xs text-buy" style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={13} /> Tự động khóa trùng lặp theo mã tín hiệu và trạng thái
              </div>
            </div>
          </div>
        </div>

        {/* Telegram Formats Preview Card */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <MessageSquare size={16} className="text-gold" /> Mẫu Bản Tin Bắn Kênh Telegram
            </span>
            <span className="text-xs text-secondary font-mono">ForexFactory / AI Bias</span>
          </div>

          <div
            style={{
              padding: '14px',
              backgroundColor: '#0E1624',
              borderRadius: 'var(--radius-md)',
              border: '1px solid #1E2D42',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              lineHeight: 1.6,
              color: '#F3F4F6',
              boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.4)',
            }}
          >
            <div style={{ color: '#F59E0B', fontWeight: 800 }}>
              📰 BẢN TIN KINH TẾ & DỰ BÁO XU HƯỚNG VÀNG
            </div>
            <div style={{ color: '#9CA3AF', fontSize: '11px' }}>
              ⏱ 21:30 (VN) | Nguồn: ForexFactory / Global News
            </div>
            <div style={{ margin: '6px 0', borderTop: '1px dashed #2A3C56' }} />
            <div>📌 Sự kiện: <b>Non-Farm Employment Change (USD)</b></div>
            <div>⚡ Mức độ ảnh hưởng: <span style={{ color: '#EF4444', fontWeight: 700 }}>🔴 TIN ĐỎ (HIGH)</span></div>
            <div>📊 Dự báo: <code>150K</code> | Kỳ trước: <code>142K</code></div>
            <div style={{ margin: '6px 0' }} />
            <div style={{ color: '#10B981', fontWeight: 800 }}>
              🟢 KỲ VỌNG: BUY VÀNG (BULLISH ↗)
            </div>
            <div style={{ color: '#D1D5DB', fontSize: '11px', marginTop: '4px' }}>
              👉 Phân tích AI: Dữ liệu việc làm suy yếu làm giảm kỳ vọng nâng lãi suất Fed, tạo lực đẩy tăng mạnh cho Vàng.
            </div>
            <div style={{ margin: '6px 0', borderTop: '1px dashed #2A3C56' }} />
            <div style={{ color: '#FBBF24', fontSize: '11px', lineHeight: 1.4 }}>
              ⚠️ LỜI CẢNH BÁO: Đây chỉ là dự đoán tham khảo dựa trên phân tích dữ liệu, không cam kết đúng 100%. Quý nhà đầu tư luôn tuân thủ quản trị rủi ro!
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
