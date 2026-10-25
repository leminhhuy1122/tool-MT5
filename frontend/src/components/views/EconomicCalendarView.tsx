import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Calendar,
  CheckCircle2,
  Copy,
  Edit3,
  FileText,
  Globe,
  Key,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import type { EconomicEventItem, NewsCalendarData } from '../../types';
import { api } from '../../services/api';

interface EconomicCalendarViewProps {
  data: NewsCalendarData;
}

export const EconomicCalendarView: React.FC<EconomicCalendarViewProps> = ({ data }) => {
  // Navigation inside News Tab
  const [activeTab, setActiveTab] = useState<'studio' | 'calendar' | 'settings'>('studio');

  // Filter & Search for Calendar Feed
  const [filterImpact, setFilterImpact] = useState<'ALL' | 'HIGH' | 'USD'>('HIGH');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // AI News Studio State
  const [generatedContent, setGeneratedContent] = useState<string>('');
  const [contentSource, setContentSource] = useState<'openai' | 'local_nlp' | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // SJC Price parameters for Gold article
  const [sjcBuy, setSjcBuy] = useState<number>(139.0);
  const [sjcSell, setSjcSell] = useState<number>(142.0);

  // OpenAI & Auto-pilot settings state
  const [openAIKey, setOpenAIKey] = useState<string>('');
  const [openAIModel, setOpenAIModel] = useState<string>('gpt-4o-mini');
  const [autoPostEnabled, setAutoPostEnabled] = useState<boolean>(false);
  const [isConfigured, setIsConfigured] = useState<boolean>(false);
  const [isSavingSettings, setIsSavingSettings] = useState<boolean>(false);

  // Load AI Settings on Mount
  useEffect(() => {
    api.getAINewsSettings()
      .then((res) => {
        setIsConfigured(res.openai_configured);
        setOpenAIModel(res.openai_model || 'gpt-4o-mini');
        setAutoPostEnabled(res.auto_post_enabled || false);
      })
      .catch(() => {});
  }, []);

  const formatEventTime = (timeIso: string) => {
    try {
      const dt = new Date(timeIso);
      const hours = String(dt.getHours()).padStart(2, '0');
      const mins = String(dt.getMinutes()).padStart(2, '0');
      const day = String(dt.getDate()).padStart(2, '0');
      const month = String(dt.getMonth() + 1).padStart(2, '0');
      return `${hours}:${mins} (${day}/${month})`;
    } catch {
      return timeIso;
    }
  };

  const getEventBias = (ev: EconomicEventItem): { label: string; dir: 'BUY' | 'SELL' | 'WAIT'; reasoning: string } => {
    const title = ev.title.toLowerCase();
    const isUSD = ev.country === 'USD';

    if (isUSD) {
      if (title.includes('cpi') || title.includes('inflation') || title.includes('pce')) {
        return {
          label: 'BUY VÀNG KHI LẠM PHÁT GIẢM',
          dir: 'BUY',
          reasoning: 'Lạm phát hạ nhiệt củng cố khả năng Fed nới lỏng lãi suất, tạo đà tăng trưởng mạnh cho Vàng.',
        };
      }
      if (title.includes('non-farm') || title.includes('unemployment') || title.includes('payroll')) {
        return {
          label: 'BIẾN ĐỘNG CỰC MẠNH (BUY/SELL)',
          dir: 'WAIT',
          reasoning: 'Tin việc làm Mỹ gây quét 2 đầu 15-30 giá. Đứng ngoài chờ nến M5 xác nhận hướng đi trước khi vào lệnh.',
        };
      }
      if (title.includes('fed') || title.includes('fomc') || title.includes('rate') || title.includes('powell')) {
        return {
          label: 'RUNG LẮC QUAN SÁT FED',
          dir: 'WAIT',
          reasoning: 'Chính sách tiền tệ Fed quyết định xu hướng dài hạn. Chờ bài phát biểu kết thúc.',
        };
      }
      if (title.includes('retail') || title.includes('pmi') || title.includes('gdp')) {
        return {
          label: 'SELL NẾU KINH TẾ MỸ KHỎE',
          dir: 'SELL',
          reasoning: 'Dữ liệu vĩ mô Mỹ tích cực củng cố sức mạnh đồng USD, gây áp lực điều chỉnh lên giá Vàng.',
        };
      }
    }

    return {
      label: 'THEO DÕI NẾN M5',
      dir: 'WAIT',
      reasoning: 'Sự kiện kinh tế định kỳ, tác động nhẹ đến trung bình lên xu hướng chung.',
    };
  };

  const filteredEvents = useMemo(() => {
    return data.events.filter((ev) => {
      const matchesSearch =
        searchQuery === '' ||
        ev.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.country.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesFilter =
        filterImpact === 'ALL'
          ? true
          : filterImpact === 'HIGH'
          ? ev.impact === 'HIGH'
          : ev.country === 'USD';

      return matchesSearch && matchesFilter;
    });
  }, [data.events, filterImpact, searchQuery]);

  // Handler: Tự động tạo bản tin Lịch Kinh Tế (Mẫu 1)
  const handleGenerateDigest = async () => {
    setIsGenerating(true);
    setActionFeedback(null);
    try {
      const res = await api.generateCalendarDigest(true);
      setGeneratedContent(res.content);
      setContentSource(res.has_openai ? 'openai' : 'local_nlp');
      setActionFeedback({
        type: 'success',
        message: `Đã tạo Bản tin Lịch Kinh Tế thành công (${res.has_openai ? 'OpenAI GPT' : 'Động cơ NLP Nội bộ'})!`,
      });
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Lỗi khi tạo bản tin lịch kinh tế.' });
    } finally {
      setIsGenerating(false);
    }
  };

  // Handler: Tự động tạo bài báo Điểm Tin Vàng SJC & Thế Giới (Mẫu 2)
  const handleGenerateArticle = async () => {
    setIsGenerating(true);
    setActionFeedback(null);
    try {
      const res = await api.generateGoldArticle({
        sjc_buy: sjcBuy,
        sjc_sell: sjcSell,
        use_ai: true,
      });
      setGeneratedContent(res.content);
      setContentSource(res.has_openai ? 'openai' : 'local_nlp');
      setActionFeedback({
        type: 'success',
        message: `Đã tạo Bài báo Điểm Tin Vàng thành công (${res.has_openai ? 'OpenAI GPT' : 'Động cơ NLP Nội bộ'})!`,
      });
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Lỗi khi tạo bài báo điểm tin vàng.' });
    } finally {
      setIsGenerating(false);
    }
  };

  // Handler: Đăng nội dung hiện tại lên Telegram
  const handlePublishCurrent = async () => {
    if (!generatedContent.trim()) {
      setActionFeedback({ type: 'error', message: 'Vui lòng tạo hoặc soạn bài viết trước khi đăng!' });
      return;
    }

    setIsPublishing(true);
    setActionFeedback(null);
    try {
      const res = await api.publishNewsArticle(generatedContent);
      setActionFeedback({ type: 'success', message: res.message || 'Đã xuất bản bài viết lên Kênh Telegram @dbgtradingfx!' });
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Lỗi xuất bản bài viết lên Telegram.' });
    } finally {
      setIsPublishing(false);
    }
  };

  // Handler: Sao chép nội dung
  const handleCopyContent = () => {
    if (!generatedContent) return;
    navigator.clipboard.writeText(generatedContent);
    setActionFeedback({ type: 'success', message: 'Đã sao chép nội dung vào khay nhớ tạm (Clipboard)!' });
  };

  // Handler: Lưu cài đặt OpenAI API Key
  const handleSaveAISettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingSettings(true);
    setActionFeedback(null);

    try {
      const res = await api.updateAINewsSettings({
        openai_api_key: openAIKey.trim() || undefined,
        openai_model: openAIModel,
        auto_post_enabled: autoPostEnabled,
      });
      setIsConfigured(res.openai_configured);
      setActionFeedback({ type: 'success', message: res.message || 'Đã lưu cấu hình OpenAI API thành công!' });
      setOpenAIKey('');
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Lỗi lưu cấu hình OpenAI.' });
    } finally {
      setIsSavingSettings(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner Alert: Mandatory Disclaimer */}
      <div
        style={{
          padding: '12px 18px',
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          border: '1px solid var(--color-accent-gold)',
          borderRadius: 'var(--radius-md)',
          color: '#FDE68A',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.25)',
        }}
      >
        <AlertTriangle size={22} className="text-gold" style={{ flexShrink: 0 }} />
        <div style={{ fontSize: '13px', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--color-accent-gold)', textTransform: 'uppercase' }}>
            ⚠️ Lời Cảnh Báo Miễn Trừ Trách Nhiệm:
          </strong>{' '}
          Đây chỉ là dự đoán tham khảo dựa trên phân tích dữ liệu và số liệu kinh tế vĩ mô, không cam kết đúng 100%. Quý nhà đầu tư luôn tuân thủ nguyên tắc quản trị rủi ro!
        </div>
      </div>

      {/* Main Header & Sub-Navigation */}
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
            <Sparkles size={20} className="text-gold" />
            AI Financial Newsroom — Tự Động Biên Tập & Xuất Bản Kênh Telegram
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Tổng hợp lịch kinh tế hàng ngày (chuẩn cờ quốc gia, giờ VN), điểm tin Vàng SJC/PNJ/MT5 và tự động đăng lên Kênh <strong>@dbgtradingfx</strong>.
          </p>
        </div>

        {/* Sub-Tab Navigation Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'var(--bg-card-subtle)', padding: '3px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
          <button
            className={`btn ${activeTab === 'studio' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
            onClick={() => setActiveTab('studio')}
          >
            <Sparkles size={13} />
            Xưởng Tạo Tin AI
          </button>
          <button
            className={`btn ${activeTab === 'calendar' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
            onClick={() => setActiveTab('calendar')}
          >
            <Globe size={13} />
            Lịch ForexFactory
          </button>
          <button
            className={`btn ${activeTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
            onClick={() => setActiveTab('settings')}
          >
            <Bot size={13} />
            Cấu Hình OpenAI & Auto
          </button>
        </div>
      </div>

      {/* Action Feedback Banner */}
      {actionFeedback && (
        <div
          style={{
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '13px',
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
            {actionFeedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            {actionFeedback.message}
          </span>
          <button
            onClick={() => setActionFeedback(null)}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '12px' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 1: AI NEWSROOM STUDIO (Soạn & Đăng Chuẩn Mẫu 1 và Mẫu 2)           */}
      {/* ==================================================================== */}
      {activeTab === 'studio' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Quick Action Cards: Template 1 & Template 2 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', gap: '16px' }}>
            {/* Card Template 1: Daily Economic Calendar Digest */}
            <div
              className="card"
              style={{
                border: '1px solid rgba(245, 158, 11, 0.35)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Calendar size={16} className="text-gold" /> Mẫu 1: Lịch Kinh Tế Tổng Hợp Ngày
                  </span>
                  <span className="status-pill connected" style={{ fontSize: '10px' }}>CHUẨN ẢNH 1</span>
                </div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  Tự động lấy các sự kiện kinh tế trong ngày từ ForexFactory, nhóm các khung giờ, gán cờ quốc gia (🇪🇺🇬🇧🇺🇸), dịch tiếng Việt súc tích, gắn tâm điểm và lời chúc ACE giao dịch.
                </p>
              </div>

              <button
                className="btn btn-primary"
                onClick={handleGenerateDigest}
                disabled={isGenerating}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '10px 16px', fontWeight: 700 }}
              >
                <Sparkles size={15} />
                {isGenerating ? 'Đang phân tích...' : '✨ Tạo Bản Tin Lịch Kinh Tế (Chuẩn Mẫu 1)'}
              </button>
            </div>

            {/* Card Template 2: Financial Gold Market News Article */}
            <div
              className="card"
              style={{
                border: '1px solid rgba(16, 185, 129, 0.35)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText size={16} className="text-buy" /> Mẫu 2: Điểm Tin Giá Vàng SJC & Thế Giới
                  </span>
                  <span className="status-pill connected" style={{ fontSize: '10px' }}>CHUẨN ẢNH 2</span>
                </div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  Biên tập bài báo tài chính chuyên nghiệp: Điểm giá Vàng miếng SJC, PNJ, Vàng nhẫn 9999, lấy giá XAUUSD thực tế trực tiếp từ MT5 và đính kèm lời cảnh báo quản trị vốn.
                </p>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px', fontSize: '12px' }}>
                  <div style={{ flex: 1 }}>
                    <span className="text-muted">Giá SJC Mua (triệu):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={sjcBuy}
                      onChange={(e) => setSjcBuy(parseFloat(e.target.value) || 139.0)}
                      style={{
                        width: '100%',
                        padding: '4px 8px',
                        marginTop: '2px',
                        backgroundColor: 'var(--bg-card-subtle)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <span className="text-muted">Giá SJC Bán (triệu):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={sjcSell}
                      onChange={(e) => setSjcSell(parseFloat(e.target.value) || 142.0)}
                      style={{
                        width: '100%',
                        padding: '4px 8px',
                        marginTop: '2px',
                        backgroundColor: 'var(--bg-card-subtle)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                      }}
                    />
                  </div>
                </div>
              </div>

              <button
                className="btn btn-primary"
                onClick={handleGenerateArticle}
                disabled={isGenerating}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '10px 16px', fontWeight: 700 }}
              >
                <Sparkles size={15} />
                {isGenerating ? 'Đang biên tập...' : '✨ Tạo Bài Báo Điểm Tin Vàng (Chuẩn Mẫu 2)'}
              </button>
            </div>
          </div>

          {/* Interactive News Editor & Telegram Preview */}
          <div className="card">
            <div className="card-header" style={{ flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 size={16} className="text-gold" />
                <span className="card-title">Khung Soạn Thảo & Xem Trước Bản Tin Telegram</span>
                {contentSource && (
                  <span className={`status-pill ${contentSource === 'openai' ? 'connected' : 'standby'}`} style={{ fontSize: '10px' }}>
                    {contentSource === 'openai' ? '🤖 ĐÃ TẠO QUA OPENAI' : '⚡ ĐỘNG CƠ NLP NỘI BỘ'}
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="btn btn-secondary"
                  onClick={handleCopyContent}
                  disabled={!generatedContent}
                  style={{ padding: '6px 12px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <Copy size={13} />
                  Sao chép
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handlePublishCurrent}
                  disabled={isPublishing || !generatedContent.trim()}
                  style={{ padding: '6px 16px', fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Send size={14} />
                  {isPublishing ? 'Đang phát...' : '📢 Đăng Ngay Lên Kênh Telegram @dbgtradingfx'}
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: '16px' }}>
              {/* Left Column: Direct Editor */}
              <div>
                <div className="text-xs text-secondary font-semibold" style={{ marginBottom: '6px' }}>
                  Nội dung có thể chỉnh sửa tự do trước khi phát:
                </div>
                <textarea
                  rows={14}
                  value={generatedContent}
                  onChange={(e) => setGeneratedContent(e.target.value)}
                  placeholder="Bấm nút 'Tạo Bản Tin Lịch Kinh Tế' hoặc 'Tạo Bài Báo Điểm Tin Vàng' ở trên để AI tự động điền nội dung vào đây..."
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    backgroundColor: 'var(--bg-card-subtle)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '13px',
                    lineHeight: 1.6,
                    resize: 'vertical',
                  }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  <span>Hỗ trợ thẻ HTML: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;</span>
                  <span>Độ dài: {generatedContent.length} ký tự</span>
                </div>
              </div>

              {/* Right Column: Telegram Live Card Simulation */}
              <div>
                <div className="text-xs text-secondary font-semibold" style={{ marginBottom: '6px' }}>
                  Mô phỏng giao diện hiển thị trên Kênh Telegram:
                </div>
                <div
                  style={{
                    padding: '16px',
                    backgroundColor: '#0E1624',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid #1E2D42',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '13px',
                    lineHeight: 1.65,
                    color: '#F3F4F6',
                    minHeight: '280px',
                    maxHeight: '380px',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    boxShadow: 'inset 0 2px 6px rgba(0, 0, 0, 0.4)',
                  }}
                  dangerouslySetInnerHTML={{
                    __html: generatedContent
                      ? generatedContent
                      : '<div style="color: #64748B; text-align: center; padding-top: 80px;">Chưa có nội dung. Bấm nút phía trên để AI tự động sinh bài viết!</div>',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: LIVE FOREX FACTORY CALENDAR FEED & RADAR                     */}
      {/* ==================================================================== */}
      {activeTab === 'calendar' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Top 2 Cards: Next High Impact Event & News Protection Rule */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', gap: '16px' }}>
            <div className="card" style={{ border: '1px solid rgba(245, 158, 11, 0.4)' }}>
              <div className="card-header">
                <span className="card-title">
                  <Zap size={16} className="text-gold" /> Tin Đỏ USD Tiếp Theo
                </span>
                <span className="status-pill standby" style={{ fontSize: '10px' }}>
                  {data.minutesUntilNext !== null && data.minutesUntilNext > 0
                    ? `Còn ${(data.minutesUntilNext / 60).toFixed(1)} Giờ`
                    : 'SẮP RA TIN'}
                </span>
              </div>

              {data.nextHighImpactEvent ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span className="font-mono font-extrabold text-lg text-primary">
                      {data.nextHighImpactEvent.title}
                    </span>
                    <span className="badge-direction sell" style={{ fontSize: '10px' }}>
                      {data.nextHighImpactEvent.country} HIGH
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
                    <div>
                      <span className="text-muted">Thời gian (VN): </span>
                      <strong className="text-gold font-mono">{formatEventTime(data.nextHighImpactEvent.timeUtc)}</strong>
                    </div>
                    <div>
                      <span className="text-muted">Dự báo: </span>
                      <span className="font-mono text-primary font-bold">{data.nextHighImpactEvent.forecast || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted">Kỳ trước: </span>
                      <span className="font-mono text-secondary">{data.nextHighImpactEvent.previous || 'N/A'}</span>
                    </div>
                  </div>
                  <div
                    style={{
                      padding: '10px 12px',
                      backgroundColor: 'var(--bg-card-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '12px',
                      lineHeight: 1.5,
                      color: 'var(--text-secondary)',
                    }}
                  >
                    💡 <strong>Dự đoán xu hướng AI: </strong>
                    {getEventBias(data.nextHighImpactEvent).reasoning}
                  </div>
                </div>
              ) : (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Không có tin đỏ USD nào trong 48 giờ tới.
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">
                  <ShieldAlert size={16} className="text-sell" /> Cơ Chế Bảo Vệ Vốn Tự Động (News Shield)
                </span>
                <span className="status-pill connected" style={{ fontSize: '10px' }}>TỰ ĐỘNG BẬT</span>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                Hệ thống tự động đồng bộ lịch kinh tế trực tiếp từ ForexFactory:
                <ul style={{ paddingLeft: '18px', marginTop: '6px' }}>
                  <li><strong>Trước 30 phút tin đỏ:</strong> Tạm hoãn phát tín hiệu mới trên toàn bộ khung thời gian.</li>
                  <li><strong>Sau 20 phút tin đỏ:</strong> Chờ nến ổn định và spread co hẹp bình thường mới tiếp tục quét setup.</li>
                  <li><strong>Cảnh báo minh bạch:</strong> Tất cả bản tin bắn lên Telegram đều đính kèm lời cảnh báo quản trị vốn.</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Events Table */}
          <div className="card">
            <div className="card-header" style={{ flexWrap: 'wrap', gap: '10px' }}>
              <span className="card-title">
                <Globe size={16} className="text-gold" /> Bảng Lịch Kinh Tế Tuần Này (ForexFactory Feed)
              </span>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', backgroundColor: 'var(--bg-card-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '2px', gap: '2px' }}>
                  {[
                    { label: 'Tin Đỏ (High)', val: 'HIGH' },
                    { label: 'Tất cả tin USD', val: 'USD' },
                    { label: 'Tất cả sự kiện', val: 'ALL' },
                  ].map((f) => (
                    <button
                      key={f.val}
                      onClick={() => setFilterImpact(f.val as any)}
                      style={{
                        padding: '3px 8px',
                        fontSize: '11px',
                        fontWeight: 700,
                        borderRadius: '4px',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: filterImpact === f.val ? 'var(--color-accent-gold)' : 'transparent',
                        color: filterImpact === f.val ? '#0B0F19' : 'var(--text-secondary)',
                      }}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'var(--bg-card-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '4px 8px' }}>
                  <Search size={13} className="text-muted" />
                  <input
                    type="text"
                    placeholder="Tìm tin (CPI, NFP, Fed...)"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '11px', width: '150px' }}
                  />
                </div>
              </div>
            </div>

            <div className="table-container">
              <table className="trading-table">
                <thead>
                  <tr>
                    <th>Giờ Công Bố (VN)</th>
                    <th>Tiền Tệ</th>
                    <th>Tên Sự Kiện</th>
                    <th>Mức Độ</th>
                    <th>Dự Báo / Kỳ Trước</th>
                    <th>Kỳ Vọng Xu Hướng Vàng</th>
                    <th>Phân Tích AI</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.map((ev) => {
                    const isHigh = ev.impact === 'HIGH';
                    const isMed = ev.impact === 'MEDIUM';
                    const biasInfo = getEventBias(ev);

                    return (
                      <tr key={ev.id}>
                        <td className="font-mono text-xs font-semibold text-gold">
                          {formatEventTime(ev.timeUtc)}
                        </td>
                        <td>
                          <span className="font-mono font-bold text-xs" style={{ color: ev.country === 'USD' ? '#60A5FA' : 'var(--text-secondary)' }}>
                            {ev.country}
                          </span>
                        </td>
                        <td className="font-semibold text-primary">
                          {ev.title}
                        </td>
                        <td>
                          <span className={`badge-direction ${isHigh ? 'sell' : isMed ? 'wait' : 'buy'}`} style={{ fontSize: '10px' }}>
                            {ev.impact}
                          </span>
                        </td>
                        <td className="font-mono text-xs">
                          <span className="font-bold text-primary">{ev.forecast || '-'}</span>
                          <span className="text-muted"> / </span>
                          <span className="text-secondary">{ev.previous || '-'}</span>
                        </td>
                        <td>
                          <span className={`badge-direction ${biasInfo.dir === 'BUY' ? 'buy' : biasInfo.dir === 'SELL' ? 'sell' : 'wait'}`} style={{ fontSize: '11px', fontWeight: 700 }}>
                            {biasInfo.dir === 'BUY' ? <TrendingUp size={12} /> : biasInfo.dir === 'SELL' ? <TrendingDown size={12} /> : null}
                            {biasInfo.label}
                          </span>
                        </td>
                        <td className="text-xs text-secondary" style={{ maxWidth: '280px', lineHeight: 1.4 }}>
                          {biasInfo.reasoning}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: CẤU HÌNH OPENAI API & TỰ ĐỘNG ĐĂNG (AUTO-PILOT)                */}
      {/* ==================================================================== */}
      {activeTab === 'settings' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: '20px' }}>
          {/* OpenAI Configuration Card */}
          <div className="card">
            <div className="card-header">
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Key size={16} className="text-gold" /> Cài Đặt OpenAI API Key
              </span>
              <span className={`status-pill ${isConfigured ? 'connected' : 'standby'}`} style={{ fontSize: '10px' }}>
                {isConfigured ? 'ĐÃ KÍCH HOẠT OPENAI' : 'DÙNG NLP NỘI BỘ'}
              </span>
            </div>

            <form onSubmit={handleSaveAISettings} style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
              <div>
                <label className="text-xs text-secondary font-semibold">OpenAI API Key (sk-...)</label>
                <input
                  type="password"
                  placeholder={isConfigured ? '•••••••••••••••••••••••• (Đã nạp an toàn)' : 'Dán OpenAI API Key của bạn vào đây (sk-...)'}
                  value={openAIKey}
                  onChange={(e) => setOpenAIKey(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    marginTop: '4px',
                    backgroundColor: 'var(--bg-card-subtle)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12px',
                  }}
                />
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Key sẽ được lưu mã hóa an toàn vào file .env trên máy bạn. Không chia sẻ ra ngoài.
                </p>
              </div>

              <div>
                <label className="text-xs text-secondary font-semibold">Mô hình AI (Model)</label>
                <select
                  value={openAIModel}
                  onChange={(e) => setOpenAIModel(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    marginTop: '4px',
                    backgroundColor: 'var(--bg-card-subtle)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                  }}
                >
                  <option value="gpt-4o-mini">gpt-4o-mini (Khuyên dùng: Nhanh, chuẩn tiếng Việt, siêu tiết kiệm)</option>
                  <option value="gpt-4o">gpt-4o (Thông minh và phân tích sâu nhất)</option>
                  <option value="gpt-3.5-turbo">gpt-3.5-turbo (Cơ bản)</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 0', borderTop: '1px solid var(--border-subtle)' }}>
                <input
                  type="checkbox"
                  id="autoPostCheckbox"
                  checked={autoPostEnabled}
                  onChange={(e) => setAutoPostEnabled(e.target.checked)}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="autoPostCheckbox" style={{ cursor: 'pointer', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Bật chế độ Auto-Post: Tự động tổng hợp và đăng Lịch Kinh Tế mỗi sáng (07:30 VN) lên Kênh Telegram
                </label>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSavingSettings}
                style={{ padding: '10px 18px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <CheckCircle2 size={15} />
                {isSavingSettings ? 'Đang lưu...' : 'Lưu Cấu Hình AI & Auto-Pilot'}
              </button>
            </form>
          </div>

          {/* AI Capabilities Information Card */}
          <div className="card">
            <div className="card-header">
              <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Bot size={16} className="text-gold" /> Cơ Chế Hoạt Động Của Hệ Thống AI
              </span>
              <span className="status-pill connected" style={{ fontSize: '10px' }}>HOÀN TOÀN TỰ ĐỘNG</span>
            </div>

            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <p>Hệ thống hỗ trợ 2 cơ chế hoạt động song song:</p>
              <ul style={{ paddingLeft: '18px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <li>
                  <strong className="text-gold">1. Động cơ NLP Nội Bộ (Mặc định):</strong> Không cần API key, tự động dịch thuật ngữ kinh tế, nhóm các khung giờ, gắn cờ quốc gia và tạo bản tin 100% chuẩn định dạng như hình mẫu.
                </li>
                <li>
                  <strong className="text-buy">2. Tích hợp OpenAI GPT-4o-mini (Tùy chọn):</strong> Khi bạn nhập API Key, AI sẽ đọc toàn bộ dữ liệu lịch kinh tế và giá Vàng thực tế, phân tích bối cảnh vĩ mô sâu sắc hơn và viết bài bằng giọng văn báo chí tài chính mượt mà.
                </li>
                <li>
                  <strong>Tự Động Đăng:</strong> Bạn có thể để bot tự động đăng theo lịch định sẵn, hoặc bấm nút kiểm duyệt và xuất bản thủ công trên giao diện bất kỳ lúc nào.
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
