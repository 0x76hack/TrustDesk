import React, { useState, useEffect } from 'react';
import type { User, UserRole, UserProvisionRequest, UserUpdateRequest } from '../types/auth';
import { listAdminUsers, provisionUser, updateAdminUser, deleteAdminUser } from '../api/auth';
import { Modal } from '../components/common/Modal';
import { Skeleton } from '../components/common/Skeleton';

interface TeamManagementViewProps {
  currentUserRole: UserRole;
  currentUserId: string;
}

export const TeamManagementView: React.FC<TeamManagementViewProps> = ({
  currentUserRole,
  currentUserId,
}) => {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const [createForm, setCreateForm] = useState<UserProvisionRequest>({
    name: '',
    username: '',
    email: '',
    phone: '',
    password: '',
    role: 'agent',
  });

  const [editForm, setEditForm] = useState<UserUpdateRequest>({
    name: '',
    email: '',
    phone: '',
    role: 'agent',
    password: '',
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  const isAdmin = currentUserRole === 'admin';

  const loadUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAdminUsers();
      setUsers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load team members');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleOpenEdit = (user: User) => {
    setSelectedUser(user);
    setEditForm({
      name: user.name,
      email: user.email,
      phone: user.phone || '',
      role: user.role,
      password: '',
    });
    setIsEditOpen(true);
  };

  const handleOpenDelete = (user: User) => {
    setSelectedUser(user);
    setIsDeleteOpen(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.name || !createForm.username || !createForm.email || !createForm.password) {
      setError('Please fill in all required fields.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const payload: UserProvisionRequest = {
        username: createForm.username.trim(),
        name: createForm.name.trim(),
        email: createForm.email.trim(),
        password: createForm.password,
        role: createForm.role,
        phone: createForm.phone?.trim() ? createForm.phone.trim() : undefined,
      };
      await provisionUser(payload);
      setSuccessMessage(`Operative '${createForm.username}' created successfully.`);
      setIsCreateOpen(false);
      setCreateForm({
        name: '',
        username: '',
        email: '',
        phone: '',
        password: '',
        role: 'agent',
      });
      await loadUsers();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const payload: UserUpdateRequest = {
        name: editForm.name?.trim() || selectedUser.name,
        email: editForm.email?.trim() || selectedUser.email,
        phone: editForm.phone?.trim() ? editForm.phone.trim() : undefined,
        role: editForm.role || selectedUser.role,
      };
      if (editForm.password && editForm.password.trim()) {
        payload.password = editForm.password.trim();
      }
      await updateAdminUser(selectedUser.id, payload);
      setSuccessMessage(`Account '${selectedUser.username}' updated successfully.`);
      setIsEditOpen(false);
      setSelectedUser(null);
      await loadUsers();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteSubmit = async () => {
    if (!selectedUser) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await deleteAdminUser(selectedUser.id);
      setSuccessMessage(`Operative '${selectedUser.username}' removed successfully.`);
      setIsDeleteOpen(false);
      setSelectedUser(null);
      await loadUsers();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isAdmin) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center font-sans">
        <div className="p-6 bg-white rounded-2xl border border-[#E9E9EB] shadow-xs">
          <h2 className="text-lg font-bold text-[#282C3F]">Administrator Access Required</h2>
          <p className="text-xs text-[#686B78] mt-2">
            Team management is restricted to users with the Administrator role.
          </p>
        </div>
      </div>
    );
  }

  const agentCount = users.filter((u) => u.role === 'agent').length;
  const seniorAgentCount = users.filter((u) => u.role === 'senior_agent').length;
  const adminCount = users.filter((u) => u.role === 'admin').length;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 text-left font-sans text-xs">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E9E9EB] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#282C3F]">
            Team Management
          </h1>
          <p className="text-xs text-[#686B78] mt-0.5">
            Manage support operatives, senior agents, and autonomous AI service accounts.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setError(null);
            setIsCreateOpen(true);
          }}
          className="px-4 py-2 bg-[#FC8019] text-white rounded-xl text-xs font-semibold hover:bg-[#E26A00] shadow-xs transition-all cursor-pointer flex items-center gap-2"
        >
          <span>+ Add New Agent</span>
        </button>
      </div>

      {error && (
        <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-xs text-[#C62828] font-medium flex items-center justify-between">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="p-1 rounded-lg hover:bg-black/5 text-[#C62828] transition-colors ml-4 cursor-pointer flex items-center justify-center" aria-label="Dismiss error">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-3 bg-[#EBF7E9] border border-[#60B246]/40 rounded-xl text-xs text-[#2A7E15] font-medium flex items-center justify-between">
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)} className="p-1 rounded-lg hover:bg-black/5 text-[#2A7E15] transition-colors ml-4 cursor-pointer flex items-center justify-center" aria-label="Dismiss notification">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] shadow-2xs">
          <span className="text-[11px] font-semibold text-[#686B78] uppercase tracking-wider block">
            Total Operatives
          </span>
          <span className="text-2xl font-extrabold text-[#282C3F] mt-1 block">
            {isLoading ? '...' : users.length}
          </span>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] shadow-2xs">
          <span className="text-[11px] font-semibold text-[#686B78] uppercase tracking-wider block">
            Support Agents
          </span>
          <span className="text-2xl font-extrabold text-[#60B246] mt-1 block">
            {isLoading ? '...' : agentCount}
          </span>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] shadow-2xs">
          <span className="text-[11px] font-semibold text-[#686B78] uppercase tracking-wider block">
            Senior Agents
          </span>
          <span className="text-2xl font-extrabold text-[#7B1FA2] mt-1 block">
            {isLoading ? '...' : seniorAgentCount}
          </span>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] shadow-2xs">
          <span className="text-[11px] font-semibold text-[#686B78] uppercase tracking-wider block">
            Administrators
          </span>
          <span className="text-2xl font-extrabold text-[#FC8019] mt-1 block">
            {isLoading ? '...' : adminCount}
          </span>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-[#E9E9EB] shadow-2xs overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[#E9E9EB] flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#282C3F]">
            Registered Team Members ({users.length})
          </h2>
          <button
            type="button"
            onClick={loadUsers}
            disabled={isLoading}
            className="text-xs text-[#FC8019] hover:text-[#E26A00] font-semibold cursor-pointer"
          >
            {isLoading ? 'Refreshing...' : 'Refresh List'}
          </button>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-[#93959F] text-xs">
            No operatives found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#F2F2F6] bg-[#FAFAFC] text-[11px] font-semibold text-[#686B78]">
                  <th className="py-3 px-5">Operative</th>
                  <th className="py-3 px-4">Contact Details</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">MFA Security</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F2F2F6]">
                {users.map((u) => {
                  const isSelf = u.id === currentUserId;
                  const isAiAgent = u.username === 'ai_agent';

                  return (
                    <tr key={u.id} className="hover:bg-[#FFFBF7] transition-colors">
                      <td className="py-3.5 px-5">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${
                            isAiAgent
                              ? 'bg-[#EBF7E9] text-[#2A7E15]'
                              : u.role === 'admin'
                              ? 'bg-[#FFF2E5] text-[#FC8019]'
                              : 'bg-[#F2F2F6] text-[#282C3F]'
                          }`}>
                            {isAiAgent ? 'AI' : u.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-[#282C3F] flex items-center gap-2">
                              <span>{u.name}</span>
                              {u.is_primary_admin && (
                                <span className="px-1.5 py-0.5 bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019]/40 rounded text-[10px] font-bold">
                                  Primary Admin
                                </span>
                              )}
                              {isSelf && (
                                <span className="px-1.5 py-0.2 bg-[#F2F2F6] text-[#686B78] rounded text-[10px] font-medium">
                                  You
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-[#93959F] font-mono">@{u.username}</span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-xs">
                        <div className="text-[#282C3F] font-medium">{u.email}</div>
                        {u.phone && <div className="text-[#686B78] text-[11px] mt-0.5">{u.phone}</div>}
                      </td>

                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${
                          u.role === 'admin'
                            ? 'bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019]/30'
                            : u.role === 'senior_agent'
                            ? 'bg-[#F3E5F5] text-[#7B1FA2] border border-[#7B1FA2]/30'
                            : 'bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/30'
                        }`}>
                          {u.role.replace('_', ' ')}
                        </span>
                      </td>

                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium ${
                          u.mfa_setup_completed ? 'text-[#2A7E15]' : 'text-[#D45D00]'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            u.mfa_setup_completed ? 'bg-[#60B246]' : 'bg-[#FC8019]'
                          }`} />
                          {u.mfa_setup_completed ? 'Active' : 'Pending Setup'}
                        </span>
                      </td>

                      <td className="py-3.5 px-5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(u)}
                            className="px-2.5 py-1 text-xs text-[#282C3F] hover:text-[#FC8019] bg-[#F2F2F6] hover:bg-[#FFF2E5] rounded-lg font-medium transition-all cursor-pointer"
                          >
                            Edit
                          </button>
                          {!isSelf && !isAiAgent && !u.is_primary_admin && (
                            <button
                              type="button"
                              onClick={() => handleOpenDelete(u)}
                              className="px-2.5 py-1 text-xs text-[#C62828] hover:text-white bg-[#FDF0EE] hover:bg-[#C62828] rounded-lg font-medium transition-all cursor-pointer"
                            >
                              Remove
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Add New Support Operative"
        description="Provision a new staff account with assigned role and credentials."
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-[#686B78] hover:text-[#282C3F] rounded-xl hover:bg-[#F2F2F6] transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreateSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 bg-[#FC8019] text-white rounded-xl text-xs font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 transition-all cursor-pointer"
            >
              {isSubmitting ? 'Creating...' : 'Create Agent Account'}
            </button>
          </div>
        }
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">Full Name *</label>
            <input
              type="text"
              required
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              placeholder="e.g. Ramesh Kumar"
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Username *</label>
              <input
                type="text"
                required
                value={createForm.username}
                onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                placeholder="ramesh.k"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
              />
            </div>
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Role *</label>
              <select
                value={createForm.role}
                onChange={(e) => setCreateForm({ ...createForm, role: e.target.value as UserRole })}
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
              >
                <option value="agent">Support Agent</option>
                <option value="senior_agent">Senior Agent</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Operational Email *</label>
              <input
                type="email"
                required
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                placeholder="ramesh@trustdesk.com"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
              />
            </div>
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Mobile Number (Optional)</label>
              <input
                type="tel"
                value={createForm.phone || ''}
                onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                placeholder="+91 98450 12345"
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">Temporary Password *</label>
            <input
              type="password"
              required
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              placeholder="••••••••••••"
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
            />
            <p className="mt-1 text-[11px] text-[#93959F]">
              The operative will be prompted to setup 2-Step MFA verification on first login.
            </p>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title={`Edit Operative: ${selectedUser?.name || ''}`}
        description="Update profile details, access role, or set a new password."
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => setIsEditOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-[#686B78] hover:text-[#282C3F] rounded-xl hover:bg-[#F2F2F6] transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleEditSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 bg-[#FC8019] text-white rounded-xl text-xs font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 transition-all cursor-pointer"
            >
              {isSubmitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        }
      >
        <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">Full Name *</label>
            <input
              type="text"
              required
              value={editForm.name || ''}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Operational Email *</label>
              <input
                type="email"
                required
                value={editForm.email || ''}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
              />
            </div>
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">Role *</label>
              <select
                value={editForm.role || 'agent'}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value as UserRole })}
                disabled={selectedUser?.id === currentUserId || selectedUser?.is_primary_admin}
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] disabled:opacity-60"
              >
                <option value="agent">Support Agent</option>
                <option value="senior_agent">Senior Agent</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">Mobile Number (Optional)</label>
            <input
              type="tel"
              value={editForm.phone || ''}
              onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
              placeholder="+91 98450 12345"
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
            />
          </div>

          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">
              Reset Password (Leave blank to keep existing)
            </label>
            <input
              type="password"
              value={editForm.password || ''}
              onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
              placeholder="••••••••••••"
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
            />
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        title="Remove Operative Account"
        description="Are you sure you want to revoke this operative's system access?"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => setIsDeleteOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-[#686B78] hover:text-[#282C3F] rounded-xl hover:bg-[#F2F2F6] transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDeleteSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 bg-[#C62828] text-white rounded-xl text-xs font-semibold hover:bg-[#B71C1C] shadow-xs disabled:opacity-50 transition-all cursor-pointer"
            >
              {isSubmitting ? 'Removing...' : 'Confirm Removal'}
            </button>
          </div>
        }
      >
        <div className="space-y-3 text-xs">
          <p className="text-[#282C3F]">
            This will permanently remove the account for{' '}
            <strong className="text-[#C62828]">
              {selectedUser?.name} (@{selectedUser?.username})
            </strong>
            .
          </p>
          <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-[#C62828]">
            ⚠️ This operative will no longer be able to log in or manage tickets. Previously handled tickets will retain their audit history.
          </div>
        </div>
      </Modal>
    </div>
  );
};
