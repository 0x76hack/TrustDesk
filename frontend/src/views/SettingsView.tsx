import React, { useState, useEffect, useCallback } from 'react';
import type { User, UserProvisionRequest, UserRole } from '../types/auth';
import type { Ticket } from '../types/ticket';
import { updateProfile, provisionUser, changePassword } from '../api/auth';
import { getMyHandledTickets } from '../api/tickets';
import { StatusBadge, CategoryPill } from '../components/common/Badge';

interface SettingsViewProps {
  currentUser: User;
  onLogout: () => void;
  onSelectTicket?: (ticketId: string) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  currentUser,
  onLogout,
  onSelectTicket,
}) => {
  const [name, setName] = useState(currentUser.name || '');
  const [email, setEmail] = useState(currentUser.email || '');
  const [phone, setPhone] = useState(currentUser.phone || '');
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [myTickets, setMyTickets] = useState<Ticket[]>([]);
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);

  const [newUsername, setNewUsername] = useState('');
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newRole, setNewRole] = useState<UserRole>('agent');
  const [provPassword, setProvPassword] = useState('');
  const [isProvisioning, setIsProvisioning] = useState(false);
  const [provisionResult, setProvisionResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchHandledTickets = useCallback(async () => {
    setIsLoadingTickets(true);
    try {
      const tickets = await getMyHandledTickets();
      setMyTickets(tickets);
    } catch {
      setMyTickets([]);
    } finally {
      setIsLoadingTickets(false);
    }
  }, []);

  useEffect(() => {
    fetchHandledTickets();
  }, [fetchHandledTickets]);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUpdatingProfile(true);
    setProfileMsg(null);
    try {
      await updateProfile({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
      });
      setProfileMsg({ type: 'success', text: 'Operative profile updated successfully.' });
    } catch (err: unknown) {
      setProfileMsg({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update profile.' });
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMsg(null);
    if (!currentPassword || !newPassword) {
      setPasswordMsg({ type: 'error', text: 'Current password and new password are required.' });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ type: 'error', text: 'New password must be at least 8 characters long.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: 'error', text: 'New password and confirmation do not match.' });
      return;
    }

    setIsChangingPassword(true);
    try {
      const res = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordMsg({ type: 'success', text: res.message || 'Password changed successfully.' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      setPasswordMsg({ type: 'error', text: err instanceof Error ? err.message : 'Failed to change password.' });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleProvisionUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newName.trim() || !newEmail.trim() || !provPassword.trim()) {
      setProvisionResult({ type: 'error', text: 'All provisioning fields are required.' });
      return;
    }

    setIsProvisioning(true);
    setProvisionResult(null);
    try {
      const payload: UserProvisionRequest = {
        username: newUsername.trim(),
        name: newName.trim(),
        email: newEmail.trim(),
        phone: newPhone.trim() || undefined,
        role: newRole,
        password: provPassword.trim(),
      };
      const created = await provisionUser(payload);
      setProvisionResult({
        type: 'success',
        text: `Operative '${created.username}' provisioned with role [${created.role}] and temporary credentials.`,
      });
      setNewUsername('');
      setNewName('');
      setNewEmail('');
      setNewPhone('');
      setProvPassword('');
    } catch (err: unknown) {
      setProvisionResult({ type: 'error', text: err instanceof Error ? err.message : 'Provisioning failed.' });
    } finally {
      setIsProvisioning(false);
    }
  };

  const formatRoleName = (role: string) => {
    switch (role) {
      case 'senior_agent':
        return 'Senior Agent';
      case 'admin':
        return 'Administrator';
      case 'agent':
      default:
        return 'Support Agent';
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 text-left font-sans text-xs">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E9E9EB] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#282C3F]">
            Account Profile & Settings
          </h1>
          <p className="text-xs text-[#686B78] mt-0.5">
            Manage your personal profile, credentials, and review your assigned ticket history.
          </p>
        </div>

        <button
          type="button"
          onClick={onLogout}
          className="px-3.5 py-1.5 rounded-lg border border-[#F5A398] bg-[#FDF0EE] text-[#C62828] font-semibold hover:bg-[#FBE3E0] transition-colors cursor-pointer text-xs shadow-2xs"
        >
          Sign Out
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-5 rounded-2xl border border-[#E9E9EB] shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F2F2F6] pb-3">
            <span className="font-bold text-[#282C3F] text-xs uppercase tracking-wide">
              Identity & Profile
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-[#FFF2E5] border border-[#FFD7B0] font-semibold text-xs text-[#FC8019]">
              {formatRoleName(currentUser.role)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-[#686B78]">
            <div>
              <span className="text-[11px] text-[#93959F] block">System ID</span>
              <div className="font-mono text-xs font-semibold text-[#282C3F] truncate">{currentUser.id}</div>
            </div>
            <div>
              <span className="text-[11px] text-[#93959F] block">Username</span>
              <div className="font-mono text-xs font-semibold text-[#FC8019]">@{currentUser.username}</div>
            </div>
          </div>

          <form onSubmit={handleUpdateProfile} className="space-y-3 pt-2 border-t border-[#F2F2F6]">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Corporate Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Mobile Number (SMS / MFA)
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            {profileMsg && (
              <div
                className={`p-2.5 rounded-lg text-xs font-medium ${
                  profileMsg.type === 'success'
                    ? 'bg-[#EBF7E9] text-[#2A7E15] border border-[#BDE8B5]'
                    : 'bg-[#FDF0EE] text-[#C62828] border border-[#F5A398]'
                }`}
              >
                {profileMsg.text}
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={isUpdatingProfile}
                className="px-3.5 py-1.5 bg-[#FC8019] text-white rounded-lg font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 cursor-pointer transition-all text-xs"
              >
                {isUpdatingProfile ? 'Saving...' : 'Update Profile'}
              </button>
            </div>
          </form>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E9E9EB] shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F2F2F6] pb-3">
            <span className="font-bold text-[#282C3F] text-xs uppercase tracking-wide">
              Security & Password
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-[#EBF7E9] border border-[#BDE8B5] font-semibold text-xs text-[#2A7E15]">
              Audited Action
            </span>
          </div>

          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Current Password
              </label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                New Password
              </label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
              />
            </div>

            {passwordMsg && (
              <div
                className={`p-2.5 rounded-lg text-xs font-medium ${
                  passwordMsg.type === 'success'
                    ? 'bg-[#EBF7E9] text-[#2A7E15] border border-[#BDE8B5]'
                    : 'bg-[#FDF0EE] text-[#C62828] border border-[#F5A398]'
                }`}
              >
                {passwordMsg.text}
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={isChangingPassword}
                className="px-3.5 py-1.5 bg-[#FC8019] text-white rounded-lg font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 cursor-pointer transition-all text-xs"
              >
                {isChangingPassword ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="bg-white p-5 rounded-2xl border border-[#E9E9EB] shadow-xs space-y-3">
        <div className="flex items-center justify-between border-b border-[#F2F2F6] pb-3">
          <span className="font-bold text-[#282C3F] text-xs uppercase tracking-wide">
            Tickets Handled By You ({myTickets.length})
          </span>
          <button
            type="button"
            onClick={fetchHandledTickets}
            className="text-xs text-[#FC8019] hover:text-[#E26A00] font-semibold cursor-pointer transition-colors"
          >
            Refresh
          </button>
        </div>

        {isLoadingTickets ? (
          <div className="p-6 text-center text-[#93959F]">
            Loading ticket history...
          </div>
        ) : myTickets.length === 0 ? (
          <div className="p-6 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB] text-center text-[#686B78]">
            No tickets currently assigned or handled by @{currentUser.username}.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-[#E9E9EB]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#F9FAFC] border-b border-[#E9E9EB] text-[#686B78] text-[11px] font-semibold">
                  <th className="py-2.5 px-3">Ticket ID</th>
                  <th className="py-2.5 px-3">Subject</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F2F2F6]">
                {myTickets.map((t) => (
                  <tr key={t.id} className="hover:bg-[#FFF9F5] transition-colors">
                    <td className="py-2.5 px-3 font-semibold whitespace-nowrap">
                      {onSelectTicket ? (
                        <a
                          href={`#ticket-${t.id}`}
                          onClick={(e) => {
                            e.preventDefault();
                            onSelectTicket(t.id);
                          }}
                          className="text-[#FC8019] hover:text-[#E26A00] font-mono cursor-pointer underline"
                          title={`Open ticket #${t.id.slice(0, 8)}`}
                        >
                          #{t.id.slice(0, 8)}
                        </a>
                      ) : (
                        <span className="text-[#282C3F] font-mono">#{t.id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-[#282C3F] truncate max-w-xs">
                      {t.subject}
                    </td>
                    <td className="py-2.5 px-3">
                      <CategoryPill category={t.category} />
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={t.status} escalationFlag={t.escalation_flag} />
                    </td>
                    <td className="py-2.5 px-3 text-[#93959F] text-[11px]">
                      {t.created_at ? new Date(t.created_at).toLocaleDateString() : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {currentUser.role === 'admin' && (
        <div className="bg-white p-5 rounded-2xl border border-[#E9E9EB] shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F2F2F6] pb-3">
            <span className="font-bold text-[#282C3F] text-xs uppercase tracking-wide">
              Administrator: Provision New Operative
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-[#1C1C24] text-white font-semibold text-[11px]">
              Admin Privileged
            </span>
          </div>

          <form onSubmit={handleProvisionUser} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. agent_alex"
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
                />
              </div>
              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Alex Morgan"
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Corporate Email
                </label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="alex@company.com"
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Mobile Number (Optional)
                </label>
                <input
                  type="tel"
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="+91 98765 00000"
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Role Assignment
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as UserRole)}
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all cursor-pointer"
                >
                  <option value="agent">Support Agent</option>
                  <option value="senior_agent">Senior Agent</option>
                  <option value="admin">System Administrator</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-[#282C3F] mb-1">
                  Temporary Password
                </label>
                <input
                  type="password"
                  value={provPassword}
                  onChange={(e) => setProvPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
                />
              </div>
            </div>

            {provisionResult && (
              <div
                className={`p-2.5 rounded-lg text-xs font-medium ${
                  provisionResult.type === 'success'
                    ? 'bg-[#EBF7E9] text-[#2A7E15] border border-[#BDE8B5]'
                    : 'bg-[#FDF0EE] text-[#C62828] border border-[#F5A398]'
                }`}
              >
                {provisionResult.text}
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={isProvisioning}
                className="px-3.5 py-1.5 bg-[#FC8019] text-white rounded-lg font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 cursor-pointer transition-all text-xs"
              >
                {isProvisioning ? 'Provisioning...' : 'Provision Operative Account'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
