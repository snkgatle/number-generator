import React, { useState, useEffect } from 'react';
import { requestTelegramOtp, verifyTelegramOtp } from '../services/api';
import { Sparkles, Send, ShieldCheck, AlertCircle, KeyRound, CheckCircle2, Clock } from 'lucide-react';

interface LoginViewProps {
  onAuthenticated: () => void;
}

const OTP_COOLDOWN_SECONDS = 60;

export const LoginView: React.FC<LoginViewProps> = ({ onAuthenticated }) => {
  const [step, setStep] = useState<'request' | 'verify'>('request');
  const [otpCode, setOtpCode] = useState<string>('');
  const [requesting, setRequesting] = useState<boolean>(false);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [cooldownLeft, setCooldownLeft] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // Cooldown timer when rate limited
  useEffect(() => {
    if (cooldownLeft <= 0) return;
    const timer = window.setInterval(() => {
      setCooldownLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownLeft]);

  const handleRequestOtp = async () => {
    if (cooldownLeft > 0) return;
    setRequesting(true);
    setError(null);
    setInfoMessage(null);
    try {
      const res = await requestTelegramOtp();
      setInfoMessage(res.message || 'OTP dispatched to Telegram.');
      setStep('verify');
    } catch (err: any) {
      if (err.message?.includes('Rate limit') || err.message?.includes('429')) {
        setCooldownLeft(OTP_COOLDOWN_SECONDS);
        setError(`Rate limited — please wait ${OTP_COOLDOWN_SECONDS}s before requesting again.`);
      } else {
        setError(err.message || 'Failed to request OTP. Please try again.');
      }
    } finally {
      setRequesting(false);
    }
  };

  const handleVerifyOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (otpCode.length !== 6) {
      setError('Please enter a complete 6-digit verification code.');
      return;
    }

    setVerifying(true);
    setError(null);
    try {
      await verifyTelegramOtp(otpCode);
      onAuthenticated();
    } catch (err: any) {
      setError(err.message || 'Invalid or expired OTP code.');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-0 px-4 py-12 relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md card overflow-hidden border border-line-strong shadow-2xl relative z-10 bg-surface-1/90 backdrop-blur-xl">
        {/* Top Decorative Glowing Bar */}
        <div className="h-1.5 w-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />

        <div className="p-8 space-y-6">
          {/* Header Brand */}
          <div className="flex flex-col items-center text-center space-y-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-[2px] shadow-lg shadow-indigo-500/25">
              <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-surface-0">
                <Sparkles className="h-7 w-7 text-indigo-400" />
              </div>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-zinc-50">LottoMind</h1>
              <p className="text-xs text-zinc-400 mt-1">Passwordless Telegram OTP Authentication</p>
            </div>
          </div>

          {/* Error & Info Banners */}
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {infoMessage && (
            <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
              <span>{infoMessage}</span>
            </div>
          )}

          {/* Step 1: Request OTP */}
          {step === 'request' && (
            <div className="space-y-4">
              <div className="rounded-lg border border-line bg-surface-2/60 p-4 text-xs text-zinc-300 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-zinc-200">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  <span>Authorized Administrator Access</span>
                </div>
                <p className="text-zinc-400 leading-relaxed">
                  Click below to dispatch a single-use 6-digit authentication token directly to your private Telegram Bot.
                </p>
              </div>

              <button
                id="btn-request-otp"
                onClick={handleRequestOtp}
                disabled={requesting}
                className="btn btn-primary w-full h-11 text-sm font-semibold shadow-lg shadow-indigo-500/20 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500"
              >
                {requesting ? (
                  <span className="flex items-center gap-2">
                    <span className="dot bg-white animate-pulse" />
                    <span>Sending code via Telegram…</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Send className="h-4 w-4" />
                    <span>Send Verification Code</span>
                  </span>
                )}
              </button>
            </div>
          )}

          {/* Step 2: Enter & Verify 6-digit OTP */}
          {step === 'verify' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="space-y-2">
                <label className="label text-center block text-zinc-300 font-medium">
                  Enter 6-digit Verification Code
                </label>
                <div className="relative">
                  <input
                    id="input-otp"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    autoFocus
                    placeholder="000000"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    className="input h-12 text-center text-2xl font-mono tracking-[0.5em] font-bold border-line-strong focus:border-indigo-500 bg-surface-2"
                  />
                  <KeyRound className="absolute right-3 top-3.5 h-5 w-5 text-zinc-600 pointer-events-none" />
                </div>
                <p className="text-[11px] text-center text-zinc-500">
                  Single-use token valid for 10 minutes.
                </p>
              </div>

              <button
                id="btn-verify-otp"
                type="submit"
                disabled={verifying || otpCode.length !== 6}
                className="btn btn-primary w-full h-11 text-sm font-semibold shadow-lg shadow-emerald-500/20 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500"
              >
                {verifying ? (
                  <span className="flex items-center gap-2">
                    <span className="dot bg-white animate-pulse" />
                    <span>Validating credentials…</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4" />
                    <span>Verify & Establish Session</span>
                  </span>
                )}
              </button>

              <div className="pt-2 flex justify-between text-xs">
                <button
                  type="button"
                  onClick={handleRequestOtp}
                  disabled={requesting || cooldownLeft > 0}
                  className={`flex items-center gap-1 ${cooldownLeft > 0 ? 'text-zinc-500 cursor-wait' : 'text-indigo-400 hover:text-indigo-300'} transition-colors`}
                >
                  {cooldownLeft > 0 ? (
                    <>
                      <Clock className="h-3 w-3" />
                      <span>Resend in {cooldownLeft}s</span>
                    </>
                  ) : (
                    'Resend code'
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStep('request');
                    setOtpCode('');
                    setError(null);
                  }}
                  className="text-zinc-500 hover:text-zinc-400 transition-colors"
                >
                  Back
                </button>
              </div>
            </form>
          )}

          {/* Security Notice */}
          <div className="pt-4 border-t border-line text-center text-[11px] text-zinc-600">
            <div className="flex items-center justify-center gap-1 mb-1">
              <ShieldCheck className="h-3 w-3 text-zinc-500" />
              <span>Rate limited: 1 request/min · 5 verifications/hour per IP</span>
            </div>
            Protected by HttpOnly 24-hour stateless session tokens & rate-limited OTP barriers.
          </div>
        </div>
      </div>
    </div>
  );
};
