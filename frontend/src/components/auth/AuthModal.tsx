import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import {
  login,
  loginOAuth,
  verifyMfa,
  setupSendOtp,
  setupVerifyOtp,
  resendLoginOtp,
  getSetupStatus,
  setupPrimaryAdmin,
} from '../../api/auth';
import type { User, SetupStatusResponse } from '../../types/auth';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: User) => void;
}

type AuthMode = 'password' | 'oauth';
type AuthStep =
  | 'credentials'
  | 'first_time_setup_email'
  | 'first_time_setup_otp'
  | 'mfa_verify'
  | 'primary_admin_setup'
  | 'primary_admin_otp';

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [authMode, setAuthMode] = useState<AuthMode>('password');
  const [authStep, setAuthStep] = useState<AuthStep>('credentials');
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [oauthEmail, setOauthEmail] = useState('');
  const [oauthProvider, setOauthProvider] = useState<'google' | 'okta' | 'azure'>('google');

  const [mfaToken, setMfaToken] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [setupEmail, setSetupEmail] = useState('');
  const [setupPhone, setSetupPhone] = useState('');

  const [adminName, setAdminName] = useState('');
  const [adminUsername, setAdminUsername] = useState('admin');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [adminPhone, setAdminPhone] = useState('');
  const [adminOtp, setAdminOtp] = useState('');

  const [devCode, setDevCode] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [otpExpirySeconds, setOtpExpirySeconds] = useState(120);
  const [resendCooldown, setResendCooldown] = useState(0);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      getSetupStatus()
        .then((status) => {
          setSetupStatus(status);
          if (!status.is_initialized) {
            setAuthStep('primary_admin_setup');
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  useEffect(() => {
    if (
      (authStep === 'mfa_verify' ||
        authStep === 'first_time_setup_otp' ||
        authStep === 'primary_admin_otp') &&
      otpExpirySeconds > 0
    ) {
      const timer = setInterval(() => {
        setOtpExpirySeconds((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [authStep, otpExpirySeconds]);

  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setInterval(() => {
        setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [resendCooldown]);

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const resetAllState = () => {
    setAuthStep('credentials');
    setAuthMode('password');
    setUsername('');
    setPassword('');
    setOauthEmail('');
    setMfaToken('');
    setMfaCode('');
    setSetupEmail('');
    setSetupPhone('');
    setAdminName('');
    setAdminUsername('admin');
    setAdminEmail('');
    setAdminPassword('');
    setAdminPhone('');
    setAdminOtp('');
    setDevCode(null);
    setStatusMessage(null);
    setError(null);
    setOtpExpirySeconds(120);
    setResendCooldown(0);
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please provide both username and password.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await login(username.trim(), password);
      if ('mfa_required' in res && res.mfa_required) {
        setMfaToken(res.mfa_token);
        if (res.mfa_setup_required) {
          setSetupEmail(res.current_email && !res.current_email.endsWith('@trustdesk.local') ? res.current_email : '');
          setSetupPhone(res.current_phone || '');
          setStatusMessage(res.message);
          setAuthStep('first_time_setup_email');
        } else {
          setOtpExpirySeconds(res.expires_in_seconds || 120);
          setResendCooldown(30);
          setDevCode(res.dev_code || null);
          setStatusMessage(res.message);
          setAuthStep('mfa_verify');
        }
      } else if ('user' in res) {
        onLoginSuccess(res.user);
        resetAllState();
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed. Please verify your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oauthEmail.trim()) {
      setError('Please provide your corporate email address.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await loginOAuth(oauthProvider, oauthEmail.trim());
      if (res.mfa_required) {
        setMfaToken(res.mfa_token);
        if (res.mfa_setup_required) {
          setSetupEmail(res.current_email && !res.current_email.endsWith('@trustdesk.local') ? res.current_email : '');
          setSetupPhone(res.current_phone || '');
          setStatusMessage(res.message);
          setAuthStep('first_time_setup_email');
        } else {
          setOtpExpirySeconds(res.expires_in_seconds || 120);
          setResendCooldown(30);
          setDevCode(res.dev_code || null);
          setStatusMessage(res.message);
          setAuthStep('mfa_verify');
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'SSO lookup failed. Contact corporate IT.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDispatchSetupOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setupEmail.trim() || !setupEmail.includes('@') || !setupEmail.includes('.')) {
      setError('Please provide a valid operational email address.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await setupSendOtp(mfaToken, setupEmail.trim(), setupPhone.trim() || undefined);
      setOtpExpirySeconds(res.expires_in_seconds || 120);
      setResendCooldown(30);
      setDevCode(res.dev_code || null);
      setStatusMessage(res.message);
      setAuthStep('first_time_setup_otp');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to dispatch setup OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifySetupOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanCode = mfaCode.trim();
    if (cleanCode.length !== 6 || !/^\d+$/.test(cleanCode)) {
      setError('Verification code must be exactly 6 numeric digits.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await setupVerifyOtp(mfaToken, setupEmail.trim(), cleanCode, setupPhone.trim() || undefined);
      onLoginSuccess(res.user);
      resetAllState();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired setup verification code.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanCode = mfaCode.trim();
    if (cleanCode.length !== 6 || !/^\d+$/.test(cleanCode)) {
      setError('Verification code must be exactly 6 numeric digits.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await verifyMfa(mfaToken, cleanCode);
      onLoginSuccess(res.user);
      resetAllState();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired MFA verification code.');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrimaryAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = adminEmail.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@') || !cleanEmail.includes('.')) {
      setError('Please provide a valid operational email address to bind to the primary administrator.');
      return;
    }
    if (cleanEmail.endsWith('@trustdesk.local')) {
      setError('A real corporate or operational email address is required (not @trustdesk.local).');
      return;
    }
    if (!adminPassword || adminPassword.length < 8) {
      setError('Master password must be at least 8 characters with letters and numbers.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await setupPrimaryAdmin({
        name: adminName.trim() || 'System Administrator',
        email: cleanEmail,
        username: adminUsername.trim().toLowerCase() || 'admin',
        password: adminPassword,
        phone: adminPhone.trim() || undefined,
      });

      if ('otp_required' in res && res.otp_required) {
        setOtpExpirySeconds(res.expires_in_seconds || 120);
        setResendCooldown(30);
        setDevCode(res.dev_code || null);
        if (res.dev_code) {
          setAdminOtp(res.dev_code);
        }
        setStatusMessage(res.message);
        setAuthStep('primary_admin_otp');
      } else if ('user' in res) {
        onLoginSuccess(res.user);
        resetAllState();
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Primary administrator registration failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyPrimaryAdminOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanCode = adminOtp.trim();
    if (cleanCode.length !== 6 || !/^\d+$/.test(cleanCode)) {
      setError('Verification code must be exactly 6 numeric digits.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await setupPrimaryAdmin({
        name: adminName.trim() || 'System Administrator',
        email: adminEmail.trim().toLowerCase(),
        username: adminUsername.trim().toLowerCase() || 'admin',
        password: adminPassword,
        phone: adminPhone.trim() || undefined,
        code: cleanCode,
      });

      if ('user' in res) {
        onLoginSuccess(res.user);
        resetAllState();
        onClose();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired setup verification code.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendLoginOtp = async () => {
    if (resendCooldown > 0 || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await resendLoginOtp(mfaToken);
      setOtpExpirySeconds(res.expires_in_seconds || 120);
      setResendCooldown(30);
      setDevCode(res.dev_code || null);
      setStatusMessage(res.message);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resend verification code.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBackToCredentials = () => {
    setAuthStep('credentials');
    setMfaToken('');
    setMfaCode('');
    setDevCode(null);
    setStatusMessage(null);
    setError(null);
  };

  const getModalTitle = () => {
    switch (authStep) {
      case 'primary_admin_setup':
        return 'Register First Admin Account';
      case 'primary_admin_otp':
        return 'Verify Primary Administrator Email';
      case 'first_time_setup_email':
        return 'Configure Multi-Factor Authentication';
      case 'first_time_setup_otp':
        return 'Verify Your Email Address';
      case 'mfa_verify':
        return 'Two-Step Verification';
      default:
        return 'Sign In to TrustDesk';
    }
  };

  const getModalDescription = () => {
    switch (authStep) {
      case 'primary_admin_setup':
        return 'Register and bind a new operational email address to the root administrator account.';
      case 'primary_admin_otp':
        return 'Enter the 6-digit verification code dispatched to your new email to complete root binding.';
      case 'first_time_setup_email':
        return 'Provide your operational email and optional mobile number to activate two-factor protection on your account.';
      case 'first_time_setup_otp':
        return 'Enter the 6-digit verification code sent to your operational email to finalize setup.';
      case 'mfa_verify':
        return 'Enter the 2-minute 6-digit verification code sent to your registered contact channel.';
      default:
        return 'Enter your operative credentials to access the support workspace.';
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        resetAllState();
        onClose();
      }}
      title={getModalTitle()}
      description={getModalDescription()}
      footer={
        <div className="flex items-center justify-between w-full font-sans text-xs">
          {authStep === 'primary_admin_setup' ? (
            <>
              <button
                type="button"
                onClick={handleBackToCredentials}
                className="text-[#686B78] hover:text-[#282C3F] font-medium transition-colors cursor-pointer"
              >
                ← Back to Sign In
              </button>
              <button
                type="button"
                onClick={handlePrimaryAdminSubmit}
                disabled={isLoading || !adminEmail.trim() || !adminPassword}
                className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
              >
                {isLoading ? 'Dispatching...' : 'Dispatch Verification Code'}
              </button>
            </>
          ) : authStep === 'primary_admin_otp' ? (
            <>
              <button
                type="button"
                onClick={() => setAuthStep('primary_admin_setup')}
                className="text-[#686B78] hover:text-[#282C3F] font-medium transition-colors cursor-pointer"
              >
                ← Edit Registration Details
              </button>
              <button
                type="button"
                onClick={handleVerifyPrimaryAdminOtp}
                disabled={isLoading || adminOtp.trim().length !== 6 || otpExpirySeconds === 0}
                className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
              >
                {isLoading ? 'Verifying...' : 'Verify & Bind Admin Account'}
              </button>
            </>
          ) : authStep !== 'credentials' ? (
            <>
              <button
                type="button"
                onClick={handleBackToCredentials}
                className="text-[#686B78] hover:text-[#282C3F] font-medium transition-colors cursor-pointer"
              >
                ← Back to Sign In
              </button>

              {authStep === 'first_time_setup_email' && (
                <button
                  type="button"
                  onClick={handleDispatchSetupOtp}
                  disabled={isLoading || !setupEmail.trim()}
                  className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
                >
                  {isLoading ? 'Sending...' : 'Send Verification Code'}
                </button>
              )}

              {authStep === 'first_time_setup_otp' && (
                <button
                  type="button"
                  onClick={handleVerifySetupOtp}
                  disabled={isLoading || mfaCode.trim().length !== 6 || otpExpirySeconds === 0}
                  className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
                >
                  {isLoading ? 'Verifying...' : 'Verify & Complete Setup'}
                </button>
              )}

              {authStep === 'mfa_verify' && (
                <button
                  type="button"
                  onClick={handleMfaSubmit}
                  disabled={isLoading || mfaCode.trim().length !== 6 || otpExpirySeconds === 0}
                  className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
                >
                  {isLoading ? 'Verifying...' : 'Verify & Enter Workspace'}
                </button>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('password');
                    setError(null);
                  }}
                  className={`text-xs transition-colors cursor-pointer ${
                    authMode === 'password'
                      ? 'font-bold text-[#FC8019]'
                      : 'text-[#93959F] hover:text-[#282C3F]'
                  }`}
                >
                  Password Login
                </button>
                <span className="text-[#E9E9EB]">|</span>
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('oauth');
                    setError(null);
                  }}
                  className={`text-xs transition-colors cursor-pointer ${
                    authMode === 'oauth'
                      ? 'font-bold text-[#FC8019]'
                      : 'text-[#93959F] hover:text-[#282C3F]'
                  }`}
                >
                  Corporate SSO
                </button>
              </div>

              <button
                type="button"
                onClick={authMode === 'password' ? handlePasswordSubmit : handleOAuthSubmit}
                disabled={isLoading}
                className="px-4 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
              >
                {isLoading ? 'Signing In...' : authMode === 'password' ? 'Sign In' : 'Continue with SSO'}
              </button>
            </>
          )}
        </div>
      }
    >
      <div className="space-y-4 text-left font-sans text-xs">
        {authStep === 'credentials' && (
          <div className="flex items-center border-b border-[#E9E9EB] pb-2 mb-3">
            <button
              type="button"
              onClick={() => {
                setAuthStep('credentials');
                setError(null);
              }}
              className="pb-2 font-bold text-xs text-[#FC8019] border-b-2 border-[#FC8019] cursor-pointer mr-4"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthStep('primary_admin_setup');
                setError(null);
              }}
              className="pb-2 font-semibold text-xs text-[#686B78] hover:text-[#282C3F] cursor-pointer transition-colors"
            >
              Register First Admin
            </button>
          </div>
        )}

        {authStep === 'primary_admin_setup' && (
          <div className="flex items-center border-b border-[#E9E9EB] pb-2 mb-3">
            <button
              type="button"
              onClick={() => {
                setAuthStep('credentials');
                setError(null);
              }}
              className="pb-2 font-semibold text-xs text-[#686B78] hover:text-[#282C3F] cursor-pointer mr-4 transition-colors"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthStep('primary_admin_setup');
                setError(null);
              }}
              className="pb-2 font-bold text-xs text-[#FC8019] border-b-2 border-[#FC8019] cursor-pointer"
            >
              Register First Admin
            </button>
          </div>
        )}

        {error && (
          <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-[#C62828] font-medium leading-relaxed">
            {error}
          </div>
        )}

        {statusMessage && (
          <div className="p-3 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl text-[#FC8019] font-medium leading-relaxed">
            {statusMessage}
          </div>
        )}

        {devCode && (
          <div className="p-3 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl text-[#282C3F]">
            <div className="font-semibold text-[#FC8019]">Development Fallback Code</div>
            <div className="mt-1 font-mono font-bold text-lg tracking-widest text-[#FC8019]">
              {devCode}
            </div>
            <span className="text-[11px] text-[#686B78] mt-0.5 block">
              Valid for 2 minutes from dispatch.
            </span>
          </div>
        )}

        {authStep === 'primary_admin_setup' && (
          <form onSubmit={handlePrimaryAdminSubmit} className="space-y-3">
            <div className="p-3 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl text-[#686B78] space-y-1">
              <div className="font-semibold text-[#282C3F]">Bind Primary Administrator Account</div>
              <p className="text-[11px] leading-relaxed">
                Provide a new operational email address to establish the primary administrator account with root permissions.
              </p>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                New Operational Email Address *
              </label>
              <input
                type="email"
                required
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                placeholder="operative@company.com"
                autoFocus
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
              <p className="mt-1 text-[11px] text-[#93959F]">
                A 6-digit one-time verification code will be dispatched to this email to verify account ownership.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  value={adminName}
                  onChange={(e) => setAdminName(e.target.value)}
                  placeholder="e.g. Primary Administrator"
                  className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Admin Username *
                </label>
                <input
                  type="text"
                  required
                  value={adminUsername}
                  onChange={(e) => setAdminUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Master Password *
              </label>
              <input
                type="password"
                required
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
              <p className="mt-1 text-[11px] text-[#93959F]">
                Must be at least 8 characters with uppercase, lowercase, and numbers.
              </p>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Mobile Number for Alerts (Optional)
              </label>
              <input
                type="tel"
                value={adminPhone}
                onChange={(e) => setAdminPhone(e.target.value)}
                placeholder="+91 98450 12345"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
          </form>
        )}

        {authStep === 'primary_admin_otp' && (
          <form onSubmit={handleVerifyPrimaryAdminOtp} className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl">
              <span className="font-semibold text-[#282C3F]">Code Expiration:</span>
              <span className={`font-bold font-mono text-sm ${otpExpirySeconds < 30 ? 'text-[#EC3D25] animate-pulse' : 'text-[#FC8019]'}`}>
                {formatTimer(otpExpirySeconds)}
              </span>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Enter 6-Digit Verification Code
              </label>
              <input
                type="text"
                maxLength={6}
                value={adminOtp}
                onChange={(e) => setAdminOtp(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                autoFocus
                className="w-full text-center tracking-widest text-2xl font-bold font-mono p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-[#686B78]">
                Sent to: <strong className="text-[#282C3F]">{adminEmail}</strong>
              </span>
              <button
                type="button"
                onClick={handlePrimaryAdminSubmit}
                disabled={resendCooldown > 0 || isLoading}
                className="text-xs text-[#FC8019] hover:text-[#E26A00] font-semibold disabled:opacity-40 cursor-pointer transition-colors"
              >
                {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
              </button>
            </div>
          </form>
        )}

        {authStep === 'first_time_setup_email' && (
          <form onSubmit={handleDispatchSetupOtp} className="space-y-3">
            <div className="p-3 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl text-[#686B78] space-y-1">
              <div className="font-semibold text-[#282C3F]">Security Setup Required</div>
              <p className="text-[11px] leading-relaxed">
                Your account does not have a registered contact channel for Multi-Factor Authentication. Please enter your email address to receive your 2-minute verification code.
              </p>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Operational Email Address *
              </label>
              <input
                type="email"
                required
                value={setupEmail}
                onChange={(e) => setSetupEmail(e.target.value)}
                placeholder="operative@company.com"
                autoFocus
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
              <p className="mt-1 text-[11px] text-[#93959F]">
                A 6-digit code will be dispatched immediately.
              </p>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Mobile Number for SMS / Alerts (Optional)
              </label>
              <input
                type="tel"
                value={setupPhone}
                onChange={(e) => setSetupPhone(e.target.value)}
                placeholder="+91 98450 12345"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
          </form>
        )}

        {authStep === 'first_time_setup_otp' && (
          <form onSubmit={handleVerifySetupOtp} className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl">
              <span className="font-semibold text-[#282C3F]">Code Expiration:</span>
              <span className={`font-bold font-mono text-sm ${otpExpirySeconds < 30 ? 'text-[#EC3D25] animate-pulse' : 'text-[#FC8019]'}`}>
                {formatTimer(otpExpirySeconds)}
              </span>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Enter 6-Digit Verification Code
              </label>
              <input
                type="text"
                maxLength={6}
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                autoFocus
                className="w-full text-center tracking-widest text-2xl font-bold font-mono p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-[#686B78]">
                Sent to: <strong className="text-[#282C3F]">{setupEmail}</strong>
              </span>
              <button
                type="button"
                onClick={handleDispatchSetupOtp}
                disabled={resendCooldown > 0 || isLoading}
                className="text-xs text-[#FC8019] hover:text-[#E26A00] font-semibold disabled:opacity-40 cursor-pointer transition-colors"
              >
                {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
              </button>
            </div>
          </form>
        )}

        {authStep === 'mfa_verify' && (
          <form onSubmit={handleMfaSubmit} className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl">
              <span className="font-semibold text-[#282C3F]">Code Expiration:</span>
              <span className={`font-bold font-mono text-sm ${otpExpirySeconds < 30 ? 'text-[#EC3D25] animate-pulse' : 'text-[#FC8019]'}`}>
                {formatTimer(otpExpirySeconds)}
              </span>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Enter 6-Digit Security Code
              </label>
              <input
                type="text"
                maxLength={6}
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                autoFocus
                className="w-full text-center tracking-widest text-2xl font-bold font-mono p-3 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
              <p className="mt-1 text-[11px] text-[#93959F]">
                A 6-digit verification code has been dispatched to your configured contact address.
              </p>
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-[#686B78]">
                Strict 2-minute rate-limited window.
              </span>
              <button
                type="button"
                onClick={handleResendLoginOtp}
                disabled={resendCooldown > 0 || isLoading}
                className="text-xs text-[#FC8019] hover:text-[#E26A00] font-semibold disabled:opacity-40 cursor-pointer transition-colors"
              >
                {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
              </button>
            </div>
          </form>
        )}

        {authStep === 'credentials' && authMode === 'password' && (
          <form onSubmit={handlePasswordSubmit} className="space-y-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Operative Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. admin"
                autoFocus
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>

            {setupStatus && (
              <div className="flex items-center justify-between pt-1 text-[11px]">
                <span className="text-[#93959F]">
                  {setupStatus.is_initialized
                    ? 'Root Admin: Active'
                    : 'Primary admin registration required'}
                </span>
                {!setupStatus.is_initialized && (
                  <button
                    type="button"
                    onClick={() => {
                      setAuthStep('primary_admin_setup');
                      setError(null);
                    }}
                    className="text-[#FC8019] hover:text-[#E26A00] font-semibold cursor-pointer"
                  >
                    Register First Admin
                  </button>
                )}
              </div>
            )}
          </form>
        )}

        {authStep === 'credentials' && authMode === 'oauth' && (
          <form onSubmit={handleOAuthSubmit} className="space-y-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Identity Provider
              </label>
              <select
                value={oauthProvider}
                onChange={(e) => setOauthProvider(e.target.value as 'google' | 'okta' | 'azure')}
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              >
                <option value="google">Google Workspace</option>
                <option value="okta">Okta Enterprise SSO</option>
                <option value="azure">Microsoft Entra / Azure AD</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Corporate Email Address
              </label>
              <input
                type="email"
                value={oauthEmail}
                onChange={(e) => setOauthEmail(e.target.value)}
                placeholder="operative@company.com"
                autoFocus
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
            <div className="pt-1 text-[11px] text-[#93959F]">
              Identity federated across enterprise directory. Mandatory 2-step verification applies.
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
};
