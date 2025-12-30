'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

// Types
type ScanItem = {
  id: string;
  project_id: string;
  scan_level: string;
  status: string;
  risk_score?: number | null;
};

type ProjectListItem = {
  id: string;
  name: string;
  target_url?: string | null;
  root_domain?: string | null;
};

type DomainVerificationStatus = {
  id: string;
  project_id: string;
  domain: string;
  status: string;
  token: string;
  record_name: string;
  record_value: string;
  last_checked_at?: string;
  verified_at?: string;
  expires_at?: string;
  last_error?: string;
};

type DomainVerificationStartResponse = {
  verification_id: string;
  project_id: string;
  root_domain: string;
  txt_name: string;
  txt_value: string;
  status: 'PENDING' | 'VERIFIED' | 'ALLOWLISTED';
  message?: string;
};

type DomainVerificationCheckResponse = {
  status: string;
  verified_at?: string;
  last_checked_at?: string;
  last_check_error?: string;
};

type AllowedDomain = {
  id: string;
  domain: string;
  scope: 'global' | 'tenant';
  tenant_id?: string | null;
  enabled: boolean;
  notes?: string | null;
};

// Rough registrable-domain matcher: compare hostname against allowed domain (eTLD+1).
// Backend enforces exact registrable domain; here we treat host or any parent ending with allowed domain as allowed.
const isHostAllowedByDomain = (host: string | null, allowedDomain: string) => {
  if (!host) return false;
  const h = host.toLowerCase();
  const d = allowedDomain.toLowerCase();
  return h === d || h.endsWith(`.${d}`);
};

const getHostFromUrl = (url: string): string | null => {
  try {
    const u = new URL(url);
    return u.hostname || null;
  } catch {
    return null;
  }
};

export default function SecurityScannerClient() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'existing' | 'new'>('existing');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [targetUrl, setTargetUrl] = useState<string>('https://');
  const [scanLevel, setScanLevel] = useState<'basic' | 'pro' | 'advanced'>('pro');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dvStatus, setDvStatus] = useState<DomainVerificationStatus | null>(null);
  const [dvLoading, setDvLoading] = useState(false);
  const [preparedProjectId, setPreparedProjectId] = useState<string>('');
  const [allowedDomains, setAllowedDomains] = useState<AllowedDomain[]>([]);
  
  // New target verification state
  const [verificationData, setVerificationData] = useState<DomainVerificationStartResponse | null>(null);
  const [verificationChecking, setVerificationChecking] = useState(false);
  const [verificationPollInterval, setVerificationPollInterval] = useState<NodeJS.Timeout | null>(null);
  
  // New state for URL selection in existing project mode
  const [existingUrls, setExistingUrls] = useState<string[]>([]);
  const [loadingUrls, setLoadingUrls] = useState(false);
  const [urlSelectionMode, setUrlSelectionMode] = useState<'existing' | 'new'>('existing');
  const [selectedUrl, setSelectedUrl] = useState<string>('');
  const [newUrlForProject, setNewUrlForProject] = useState<string>('');
  
  // Refs to prevent repeated fetches
  const lastLoadedProjectIdRef = useRef<string>('');
  const lastLoadedDvProjectIdRef = useRef<string>('');
  const loadUrlsAbortControllerRef = useRef<AbortController | null>(null);

  const loadProjects = useCallback(async () => {
    if (!session) return;
    
    setLoadingProjects(true);
    try {
      const res = await thandevFetchJSON<{ items: ProjectListItem[] }>(
        '/api/projects',
        session
      );
      const projectsList = res.items ?? [];
      setProjects(projectsList);
      
      // Default to first project if available
      if (projectsList.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projectsList[0].id);
      }
    } catch (e) {
      console.error('Failed to load projects', e);
    } finally {
      setLoadingProjects(false);
    }
  }, [session, selectedProjectId]);

  // Load existing URLs for selected project
  const loadExistingUrls = useCallback(async (projectId: string) => {
    if (!session || !projectId) {
      setExistingUrls([]);
      setSelectedUrl('');
      return;
    }
    
    // Prevent repeated fetches for the same project
    if (lastLoadedProjectIdRef.current === projectId && existingUrls.length > 0) {
      return;
    }
    
    // Abort any in-flight request
    if (loadUrlsAbortControllerRef.current) {
      loadUrlsAbortControllerRef.current.abort();
    }
    
    lastLoadedProjectIdRef.current = projectId;
    loadUrlsAbortControllerRef.current = new AbortController();

    setLoadingUrls(true);
    try {
      // Check verification status before loading URLs
      const isAdmin = Boolean(session.user?.isAdmin);
      const project = projects.find(p => p.id === projectId);
      const isAllowed = project?.root_domain && allowedDomains.some(ad => 
        ad.domain === project.root_domain.toLowerCase()
      );
      
      console.log('loadExistingUrls: Checking before API call', {
        projectId,
        rootDomain: project?.root_domain,
        isAdmin,
        isAllowed,
        dvStatus: dvStatus?.status,
        allowedDomains: allowedDomains.map(ad => ad.domain)
      });
      
      // Only load URLs if domain is verified, allowlisted, or user is admin
      if (!isAdmin && !isAllowed) {
        // Check if domain is verified
        if (!dvStatus || dvStatus.status !== 'verified') {
          console.log('Domain not verified and not allowlisted, NOT loading URLs. Status:', dvStatus?.status, 'Root domain:', project?.root_domain);
          setExistingUrls([]);
          setSelectedUrl('');
          setUrlSelectionMode('new');
          setNewUrlForProject('https://');
          setLoadingUrls(false);
          return;
        }
        console.log('Domain is verified, proceeding to load URLs');
      } else {
        console.log('Domain is allowlisted or user is admin, proceeding to load URLs');
      }
      
      // Use the new targets endpoint (backend will also filter)
      const urls = await thandevFetchJSON<string[]>(
        `/api/projects/${projectId}/targets`,
        session,
        { signal: loadUrlsAbortControllerRef.current?.signal }
      );
      
      console.log('Loaded URLs for project:', projectId, 'URLs:', urls);
      setExistingUrls(urls || []);
      
      // If we have URLs, select the first one by default
      if (urls && urls.length > 0) {
        setSelectedUrl(urls[0]);
        setUrlSelectionMode('existing');
      } else {
        // No existing URLs, default to new URL mode
        setUrlSelectionMode('new');
        setNewUrlForProject('https://');
      }
    } catch (e) {
      console.error('Failed to load existing URLs', e);
      setExistingUrls([]);
      setSelectedUrl('');
      setUrlSelectionMode('new');
      setNewUrlForProject('https://');
    } finally {
      setLoadingUrls(false);
    }
  }, [session, dvStatus, projects, allowedDomains]);

  // Load URLs when project is selected - but only if domain is verified
  useEffect(() => {
    if (selectedMode === 'existing' && selectedProjectId) {
      // Only load URLs if domain is verified or allowlisted
      // Check dvStatus to ensure we don't show URLs for unverified domains
      const isAdmin = Boolean(session?.user?.isAdmin);
      const project = projects.find(p => p.id === selectedProjectId);
      const isAllowed = project?.root_domain && allowedDomains.some(ad => 
        ad.domain === project.root_domain.toLowerCase()
      );
      
      console.log('useEffect [selectedProjectId]: Checking URL loading', {
        projectId: selectedProjectId,
        rootDomain: project?.root_domain,
        isAdmin,
        isAllowed,
        dvStatus: dvStatus?.status,
        existingUrlsCount: existingUrls.length
      });
      
      // Only load URLs if: admin, allowlisted, or verified
      if (isAdmin || isAllowed || (dvStatus && dvStatus.status === 'verified')) {
        console.log('Conditions met, loading URLs');
        loadExistingUrls(selectedProjectId);
      } else {
        // Domain not verified - clear URLs
        console.log('Conditions NOT met, clearing URLs. isAdmin:', isAdmin, 'isAllowed:', isAllowed, 'dvStatus:', dvStatus?.status);
        setExistingUrls([]);
        setSelectedUrl('');
        setUrlSelectionMode('new');
        setNewUrlForProject('https://');
      }
    } else {
      // Reset URL-related state when switching modes
      setExistingUrls([]);
      setSelectedUrl('');
      setNewUrlForProject('');
      setUrlSelectionMode('existing');
    }
  }, [selectedProjectId, selectedMode, session?.user?.isAdmin, dvStatus?.status]);

  const loadAllowedDomains = useCallback(async () => {
    if (!session) return;
    try {
      const res = await thandevFetchJSON<AllowedDomain[]>(
        '/api/access/allowed-domains',
        session
      );
      setAllowedDomains(res || []);
    } catch (e) {
      console.warn('Allowed domains fetch failed', e);
      setAllowedDomains([]);
    }
  }, [session]);

  const loadDomainVerification = useCallback(async (projectId: string, autoCreate: boolean = true) => {
    if (!session || !projectId) {
      setDvStatus(null);
      return;
    }
    
    // Prevent repeated fetches for the same project
    if (lastLoadedDvProjectIdRef.current === projectId && dvStatus) {
      return;
    }
    
    // Check if domain is allowlisted before making API call
    const project = projects.find(p => p.id === projectId);
    const isAdmin = Boolean(session.user?.isAdmin);
    const isAllowed = project?.root_domain && allowedDomains.some(ad => 
      ad.domain === project.root_domain.toLowerCase()
    );
    
    // If allowlisted or admin, treat as verified without API call
    if (isAllowed || isAdmin) {
      setDvStatus({
        id: 'allowlist',
        project_id: projectId,
        domain: project?.root_domain || '',
        status: 'verified',
        token: '',
        record_name: '',
        record_value: '',
      });
      lastLoadedDvProjectIdRef.current = projectId;
      setDvLoading(false);
      return;
    }
    
    lastLoadedDvProjectIdRef.current = projectId;
    setDvLoading(true);
    setError(null);
    try {
      const res = await thandevFetchJSON<DomainVerificationStatus>(
        `/api/projects/${projectId}/domain-verification`,
        session
      );
      setDvStatus(res);
      lastLoadedDvProjectIdRef.current = projectId;
    } catch (err: any) {
      // If not found (404), only auto-create if requested (not after deletion)
      if (err?.message?.includes('404') || err?.message?.includes('not found')) {
        if (autoCreate) {
          // Auto-create only when explicitly requested (e.g., on project selection)
          try {
            const req = await thandevFetchJSON<DomainVerificationStatus>(
              `/api/projects/${projectId}/domain-verification/request`,
              session,
              { method: 'POST' }
            );
            setDvStatus(req);
            lastLoadedDvProjectIdRef.current = projectId;
          } catch (e) {
            console.log('No domain verification found (expected after deletion)');
            setDvStatus(null);
          }
        } else {
          // Don't auto-create - just clear state (e.g., after deletion)
          console.log('No domain verification found, clearing state');
          setDvStatus(null);
        }
      } else {
        console.error('DV load failed', err);
        setDvStatus(null);
      }
    } finally {
      setDvLoading(false);
    }
  }, [session, projects, allowedDomains]);

  useEffect(() => {
    if (sessionStatus === 'unauthenticated') {
      router.push('/auth/signin');
      return;
    }
    if (sessionStatus !== 'authenticated') return;
    loadProjects();
    loadAllowedDomains();
  }, [sessionStatus, loadProjects, loadAllowedDomains, router]);

  useEffect(() => {
    if (selectedProjectId && lastLoadedDvProjectIdRef.current !== selectedProjectId) {
      loadDomainVerification(selectedProjectId);
    } else if (!selectedProjectId) {
      setDvStatus(null);
      lastLoadedDvProjectIdRef.current = '';
    }
  }, [selectedProjectId]);
  
  // Clear URLs when verification status changes to unverified or deleted
  useEffect(() => {
    if (selectedMode === 'existing' && selectedProjectId) {
      const isAdmin = Boolean(session?.user?.isAdmin);
      const project = projects.find(p => p.id === selectedProjectId);
      const isAllowed = project?.root_domain && allowedDomains.some(ad => 
        ad.domain === project.root_domain.toLowerCase()
      );
      
      console.log('Checking URL visibility:', {
        projectId: selectedProjectId,
        rootDomain: project?.root_domain,
        isAdmin,
        isAllowed,
        dvStatus: dvStatus?.status,
        existingUrlsCount: existingUrls.length
      });
      
      // If domain is not verified and not allowlisted (and not admin), clear URLs
      if (!isAdmin && !isAllowed) {
        if (!dvStatus || dvStatus.status !== 'verified') {
          // Domain not verified or verification deleted - clear URLs immediately
          console.log('Domain not verified or verification deleted, clearing URLs. dvStatus:', dvStatus?.status);
          if (existingUrls.length > 0) {
            setExistingUrls([]);
            setSelectedUrl('');
            setUrlSelectionMode('new');
            setNewUrlForProject('https://');
          }
        } else {
          console.log('Domain is verified, URLs can be shown. Status:', dvStatus.status);
        }
      } else {
        console.log('Domain is allowlisted or user is admin, URLs can be shown');
      }
    }
  }, [dvStatus, selectedProjectId, selectedMode, session, allowedDomains, projects, existingUrls.length]);
  
  // Clear URLs when verification status changes to unverified or deleted
  useEffect(() => {
    if (selectedMode === 'existing' && selectedProjectId) {
      const isAdmin = Boolean(session?.user?.isAdmin);
      const isAllowed = allowedDomains.some(ad => {
        const project = projects.find(p => p.id === selectedProjectId);
        if (!project?.root_domain) return false;
        return ad.domain === project.root_domain.toLowerCase();
      });
      
      // If domain is not verified and not allowlisted (and not admin), clear URLs
      if (!isAdmin && !isAllowed) {
        if (!dvStatus || dvStatus.status !== 'verified') {
          // Domain not verified or verification deleted - clear URLs immediately
          console.log('Domain not verified, clearing URLs. dvStatus:', dvStatus);
          setExistingUrls([]);
          setSelectedUrl('');
          setUrlSelectionMode('new');
          setNewUrlForProject('https://');
        }
      }
    }
  }, [dvStatus, selectedProjectId, selectedMode, session, allowedDomains, projects]);

  // New target flow removed for all users

  const deriveProjectName = (url: string) => {
    try {
      const u = new URL(url);
      return u.hostname.replace(/^www\./, '') || 'New Project';
    } catch {
      return 'New Project';
    }
  };

  const startDomainVerification = async () => {
    if (!session) return;
    const trimmed = targetUrl.trim();
    if (!trimmed) {
      setError('Please enter a target URL');
      return;
    }
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      setError('URL must start with http:// or https://');
      return;
    }
    setSubmitting(true);
    setError(null);
    setVerificationData(null);
    
    try {
      const response = await thandevFetchJSON<DomainVerificationStartResponse>(
        '/api/domain-verifications/start',
        session,
        {
          method: 'POST',
          body: JSON.stringify({ url: trimmed }),
        }
      );
      
      console.log('Domain verification start response:', response);
      
      // Validate response has required fields
      if (!response) {
        throw new Error('Empty response from server');
      }
      
      if (response.status === 'PENDING' && (!response.txt_name || !response.txt_value)) {
        console.error('Invalid response: PENDING status but missing TXT record details', response);
        throw new Error('Server returned PENDING status but missing TXT record details. Please try again.');
      }
      
      setVerificationData(response);
      setPreparedProjectId(response.project_id);
      
      // If allowlisted, automatically proceed
      if (response.status === 'ALLOWLISTED') {
        // Add URL to project targets
        try {
          await thandevFetchJSON(
            `/api/projects/${response.project_id}/targets`,
            session,
            {
              method: 'POST',
              body: JSON.stringify({ url: trimmed }),
            }
          );
        } catch (e) {
          console.warn('Failed to add URL to project targets', e);
        }
        
        // Switch to existing project tab
        setSelectedProjectId(response.project_id);
        await loadProjects();
        await loadExistingUrls(response.project_id);
        setSelectedMode('existing');
        setVerificationData(null);
      } else if (response.status === 'VERIFIED') {
        // Already verified, add URL and switch
        try {
          await thandevFetchJSON(
            `/api/projects/${response.project_id}/targets`,
            session,
            {
              method: 'POST',
              body: JSON.stringify({ url: trimmed }),
            }
          );
        } catch (e) {
          console.warn('Failed to add URL to project targets', e);
        }
        
        setSelectedProjectId(response.project_id);
        await loadProjects();
        await loadExistingUrls(response.project_id);
        setSelectedMode('existing');
        setVerificationData(null);
      }
      // If PENDING, stay on new target tab and show TXT records
    } catch (e: any) {
      setError(e?.message || 'Failed to start domain verification');
    } finally {
      setSubmitting(false);
    }
  };

  const deleteDomainVerification = async () => {
    if (!session) return;
    
    if (!confirm('Are you sure you want to remove this pending verification? You can start a new verification anytime.')) {
      return;
    }
    
    try {
      // Determine which verification to delete
      let verificationId: string | null = null;
      
      // Priority 1: Check verificationData (new target tab)
      if (verificationData && verificationData.verification_id) {
        verificationId = verificationData.verification_id;
        console.log('Using verification_id from verificationData:', verificationId);
      } 
      // Priority 2: Check dvStatus (existing project tab)
      else if (dvStatus && dvStatus.id) {
        verificationId = dvStatus.id;
        console.log('Using id from dvStatus:', verificationId);
      }
      // Priority 3: If we have project_id and domain, try to find verification
      else if (selectedProjectId && targetUrl) {
        console.log('Attempting to find verification by project and domain...');
        // Try to get verification from project
        try {
          const projectDv = await thandevFetchJSON<DomainVerificationStatus>(
            `/api/projects/${selectedProjectId}/domain-verification`,
            session
          );
          if (projectDv && projectDv.id) {
            verificationId = projectDv.id;
            console.log('Found verification ID from project endpoint:', verificationId);
          }
        } catch (e) {
          console.warn('Could not fetch verification from project:', e);
        }
      }
      
      if (!verificationId) {
        console.error('No verification ID found. verificationData:', verificationData, 'dvStatus:', dvStatus);
        throw new Error('No verification ID found. Please try refreshing the page.');
      }
      
      console.log('Deleting verification with ID:', verificationId);
      
      await thandevFetchJSON(
        `/api/domain-verifications/${verificationId}`,
        session,
        {
          method: 'DELETE',
        }
      );
      
      console.log('Verification deleted successfully');
      
      // Clear verification data and reset state
      if (verificationData) {
        setVerificationData(null);
        setPreparedProjectId(null);
        if (verificationPollInterval) {
          clearInterval(verificationPollInterval);
          setVerificationPollInterval(null);
        }
        // Reset target URL input
        setTargetUrl('');
      }
      
      // Clear dvStatus for existing project tab - DO NOT reload verification, just clear state
      // Reloading would trigger get_or_create_verification which creates a new one!
      if (dvStatus) {
        const deletedDomain = dvStatus.domain;
        setDvStatus(null);
        console.log('Verification deleted for domain:', deletedDomain, 'State cleared. Not reloading to prevent auto-creation.');
        
        // IMMEDIATELY clear URLs state - don't wait for reload
        // Check if domain is allowlisted - if not, clear URLs
        const project = projects.find(p => p.id === selectedProjectId);
        const isAllowed = project?.root_domain && allowedDomains.some(ad => 
          ad.domain === project.root_domain.toLowerCase()
        );
        const isAdmin = Boolean(session?.user?.isAdmin);
        
        // Only clear URLs if domain is NOT allowlisted (allowlisted domains don't need verification)
        if (!isAdmin && !isAllowed) {
          console.log('Domain is not allowlisted, clearing URLs after verification deletion');
          setExistingUrls([]);
          setSelectedUrl('');
          setUrlSelectionMode('new');
          setNewUrlForProject('https://');
          
          // Then reload existing URLs to ensure backend filtering is applied
          if (selectedProjectId) {
            try {
              await loadExistingUrls(selectedProjectId);
              console.log('URLs reloaded after verification deletion - should be empty');
            } catch (e) {
              console.warn('Failed to reload URLs after deletion:', e);
              // Ensure state is cleared even if reload fails
              setExistingUrls([]);
              setSelectedUrl('');
            }
          }
        } else {
          console.log('Domain is allowlisted or user is admin, keeping URLs');
        }
      }
    } catch (e: any) {
      console.error('Failed to delete verification:', e);
      setError(e?.message || 'Failed to delete verification');
    }
  };

  const checkDomainVerification = async () => {
    if (!session || !verificationData) return;
    
    setVerificationChecking(true);
    try {
      const response = await thandevFetchJSON<DomainVerificationCheckResponse>(
        '/api/domain-verifications/check',
        session,
        {
          method: 'POST',
          body: JSON.stringify({ verification_id: verificationData.verification_id }),
        }
      );
      
      if (response.status === 'VERIFIED') {
        // Update verification data
        setVerificationData({ ...verificationData, status: 'VERIFIED' });
        
        // Add URL to project targets
        try {
          await thandevFetchJSON(
            `/api/projects/${verificationData.project_id}/targets`,
            session,
            {
              method: 'POST',
              body: JSON.stringify({ url: targetUrl.trim() }),
            }
          );
        } catch (e) {
          console.warn('Failed to add URL to project targets', e);
        }
        
        // Switch to existing project tab
        setSelectedProjectId(verificationData.project_id);
        await loadProjects();
        await loadExistingUrls(verificationData.project_id);
        setSelectedMode('existing');
        setVerificationData(null);
        
        // Stop polling
        if (verificationPollInterval) {
          clearInterval(verificationPollInterval);
          setVerificationPollInterval(null);
        }
      }
    } catch (e: any) {
      console.error('Failed to check verification', e);
    } finally {
      setVerificationChecking(false);
    }
  };

  // Auto-poll when verification is pending
  useEffect(() => {
    if (verificationData && verificationData.status === 'PENDING' && !verificationPollInterval) {
      const interval = setInterval(() => {
          checkDomainVerification();
        }, 15000); // Poll every 15 seconds
      setVerificationPollInterval(interval);
    } else if (verificationData && verificationData.status !== 'PENDING' && verificationPollInterval) {
      clearInterval(verificationPollInterval);
      setVerificationPollInterval(null);
    }
    
    return () => {
      if (verificationPollInterval) {
        clearInterval(verificationPollInterval);
      }
    };
  }, [verificationData, verificationPollInterval]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (verificationPollInterval) {
        clearInterval(verificationPollInterval);
      }
    };
  }, [verificationPollInterval]);

  const refreshVerification = useCallback(async () => {
    if (!session) return;
    const pid = selectedProjectId;
    if (!pid) return;
    setDvLoading(true);
    try {
      await loadDomainVerification(pid);
    } finally {
      setDvLoading(false);
    }
  }, [session, selectedProjectId, loadDomainVerification]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }

    const isAdmin = Boolean(session.user?.isAdmin);

    // Validation
    if (selectedMode === 'existing') {
      if (!selectedProjectId) {
        setError('Please select a project');
        return;
      }
      
      // Validate URL selection
      if (urlSelectionMode === 'existing' && !selectedUrl) {
        setError('Please select an existing URL or switch to "New URL" tab');
        return;
      }
      if (urlSelectionMode === 'new') {
        const trimmed = newUrlForProject.trim();
        if (!trimmed) {
          setError('Please enter a target URL');
          return;
        }
        if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
          setError('URL must start with http:// or https://');
          return;
        }
      }
      
      // Check domain verification status
      if (!isAdmin && !allowedForSelectedProject) {
        if (!dvStatus) {
          setError('Domain verification required. Please verify domain ownership before scanning.');
          return;
        }
        if (dvStatus.status === 'pending') {
          setError('Domain verification is pending. Please complete DNS verification before scanning.');
          return;
        }
        if (dvStatus.status !== 'verified') {
          setError('Domain not verified. Please add DNS TXT record and verify domain ownership before scanning.');
          return;
        }
      }
    } else {
      const trimmed = targetUrl.trim();
      if (!trimmed) {
        setError('Please enter a target URL');
        return;
      }
      if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
        setError('URL must start with http:// or https://');
        return;
      }
      if (!isAdmin) {
        if (!preparedProjectId || preparedProjectId !== selectedProjectId) {
          setError('Domain verification required. Please verify domain ownership before scanning.');
          return;
        }
        if (!allowedForTargetUrl) {
          if (!verificationData) {
            setError('Domain verification required. Please verify domain ownership before scanning.');
            return;
          }
          if (verificationData.status === 'PENDING') {
            setError('Domain verification is pending. Please complete DNS verification before scanning.');
            return;
          }
          if (verificationData.status !== 'VERIFIED' && verificationData.status !== 'ALLOWLISTED') {
            setError('Domain not verified. Please add DNS TXT record and verify domain ownership before scanning.');
            return;
          }
        }
      }
    }

    setSubmitting(true);
    setError(null);

    try {
      const body: any = {
        scan_level: scanLevel,
      };

      if (selectedMode === 'existing') {
        body.project_id = selectedProjectId;
        // Add target_url if user selected a specific URL
        if (urlSelectionMode === 'existing' && selectedUrl) {
          body.target_url = selectedUrl;
        } else if (urlSelectionMode === 'new' && newUrlForProject.trim()) {
          body.target_url = newUrlForProject.trim();
        }
      } else {
        // New target mode - must have verified project
        if (!preparedProjectId) {
          setError('Please verify domain ownership first');
          return;
        }
        body.project_id = preparedProjectId;
        body.target_url = targetUrl.trim();
      }

      let scan: { project_id: string; scan_id: string };
      try {
        scan = await thandevFetchJSON<{ project_id: string; scan_id: string }>(
          '/api/scans/quick',
          session,
          {
            method: 'POST',
            body: JSON.stringify(body),
          }
        );
      } catch (error) {
        // Use async error message parser to properly handle Response objects
        const { getErrorMessage } = await import('@/lib/errorUtils');
        const errorMessage = await getErrorMessage(error);
        console.error('Scan creation error:', errorMessage, error);
        
        // Check if it's a structured error from backend
        let displayMessage = errorMessage;
        if (errorMessage.includes('DB_COMMIT_FAILED') || errorMessage.includes('database')) {
          displayMessage = 'Database error: Failed to create scan. Please try again or contact support if the issue persists.';
        } else if (errorMessage.includes('LIMIT_EXCEEDED') || errorMessage.includes('limit')) {
          displayMessage = errorMessage; // Show the limit error as-is
        } else if (errorMessage.includes('403') || errorMessage.includes('Forbidden')) {
          displayMessage = errorMessage; // Show permission errors as-is
        }
        
        // Ensure displayMessage is always a string, never [object Object]
        if (typeof displayMessage !== 'string') {
          displayMessage = String(displayMessage);
        }
        
        alert(displayMessage);
        setSubmitting(false);
        return;
      }

      // On success: go to scan detail
      if (scan?.scan_id && scan?.project_id) {
        router.push(`/projects/${scan.project_id}/scans/${scan.scan_id}`);
      } else {
        // fallback: go to scan history
        router.push('/dashboard/history');
      }
      } catch (err: any) {
        console.error('Failed to start scan', err);
        // Use error message parser to never show [object Object]
        const { getErrorMessageSync } = await import('@/lib/errorUtils');
        const errorMessage = getErrorMessageSync(err) || 'Failed to start scan. Please try again.';
        
        // Check for DOMAIN_NOT_VERIFIED error
        if (errorMessage.includes('DOMAIN_NOT_VERIFIED') || errorMessage.includes('Verify domain ownership')) {
          setError('Domain not verified. Please verify domain ownership in the "New target" tab first.');
          setSelectedMode('new');
          return;
        }
        
        setError(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  // Loading state
  if (sessionStatus === 'loading') {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={undefined} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-3xl mx-auto">
              <div className="rounded-xl border p-8 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-8"></div>
                <div className="space-y-4">
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Unauthenticated state (will redirect)
  if (sessionStatus === 'unauthenticated') {
    router.push('/auth');
    return null;
  }

  if (!session) {
    return null;
  }

  const tenantId = (session.user as any)?.tenantId || (session.user as any)?.tenant_id;
  const currentProject = projects.find((p) => p.id === selectedProjectId);
  const currentRootDomain = currentProject?.root_domain || (currentProject?.target_url ? getHostFromUrl(currentProject.target_url) : null);
  const targetHost = getHostFromUrl(targetUrl);

  const isAllowedDomain = (domain: string | null) =>
    !!domain &&
    allowedDomains.some((ad) => {
      if (!ad.enabled) return false;
      if (ad.scope === 'tenant' && ad.tenant_id && tenantId && ad.tenant_id !== tenantId) return false;
      return isHostAllowedByDomain(domain, ad.domain);
    });

  const allowedForSelectedProject = isAllowedDomain(currentRootDomain);
  const allowedForTargetUrl = isAllowedDomain(targetHost);
  const allowedDomainMatch = allowedDomains.find((ad) => ad.enabled && targetHost && isHostAllowedByDomain(targetHost, ad.domain));

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={session.user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-3xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                Security Scanner
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Launch a new security assessment for your website or API.
              </p>
            </div>

            {/* Scanner Card */}
            <div className="rounded-xl border p-8" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <form onSubmit={handleSubmit}>
                {/* Mode Selector Tabs */}
                <div className="mb-6">
                  <div className="flex gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedMode('existing');
                        setError(null);
                        setDvStatus(null);
                      }}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        selectedMode === 'existing'
                          ? 'border-b-2 text-white'
                          : 'text-gray-400 hover:text-gray-300'
                      }`}
                      style={{
                        borderColor: selectedMode === 'existing' ? 'var(--brand)' : 'transparent',
                        color: selectedMode === 'existing' ? 'white' : 'var(--muted)'
                      }}
                    >
                      Existing project
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedMode('new');
                        setError(null);
                        setDvStatus(null);
                      }}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        selectedMode === 'new'
                          ? 'border-b-2 text-white'
                          : 'text-gray-400 hover:text-gray-300'
                      }`}
                      style={{
                        borderColor: selectedMode === 'new' ? 'var(--brand)' : 'transparent',
                        color: selectedMode === 'new' ? 'white' : 'var(--muted)'
                      }}
                    >
                      New target
                    </button>
                  </div>
                </div>

                {/* Existing Project Mode */}
                {selectedMode === 'existing' && (
                  <div className="space-y-6">
                    {/* Project Selection */}
                    <div>
                      <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                        Select Project
                      </label>
                      {loadingProjects ? (
                        <div className="px-3 py-2 rounded-lg border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                        </div>
                      ) : projects.length === 0 ? (
                        <div className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                          No projects available. Please create a project first.
                        </div>
                      ) : (
                        <select
                          value={selectedProjectId}
                          onChange={(e) => {
                            setSelectedProjectId(e.target.value);
                            setSelectedUrl('');
                            setNewUrlForProject('');
                            setUrlSelectionMode('existing');
                          }}
                          required
                          className="w-full px-3 py-2 rounded-lg border text-sm"
                          style={{
                            borderColor: 'var(--border)',
                            background: 'var(--surface-2)',
                            color: 'var(--fg)'
                          }}
                        >
                          <option value="">Select a project...</option>
                          {projects.map((project) => (
                            <option key={project.id} value={project.id}>
                              {project.name} {project.target_url ? `(${project.target_url})` : ''}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    {/* URL Selection - Only show if project is selected */}
                    {selectedProjectId && (
                      <div>
                        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                          Select or Enter URL
                        </label>
                        
                        {/* URL Selection Mode Tabs */}
                        <div className="mb-3">
                          <div className="flex gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                            <button
                              type="button"
                              onClick={() => {
                                setUrlSelectionMode('existing');
                                setNewUrlForProject('');
                              }}
                              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                                urlSelectionMode === 'existing'
                                  ? 'border-b-2'
                                  : ''
                              }`}
                              style={{
                                borderColor: urlSelectionMode === 'existing' ? 'var(--brand)' : 'transparent',
                                color: urlSelectionMode === 'existing' ? 'white' : 'var(--muted)'
                              }}
                            >
                              Existing URLs
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setUrlSelectionMode('new');
                                setSelectedUrl('');
                                setNewUrlForProject('https://');
                              }}
                              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                                urlSelectionMode === 'new'
                                  ? 'border-b-2'
                                  : ''
                              }`}
                              style={{
                                borderColor: urlSelectionMode === 'new' ? 'var(--brand)' : 'transparent',
                                color: urlSelectionMode === 'new' ? 'white' : 'var(--muted)'
                              }}
                            >
                              New URL
                            </button>
                          </div>
                        </div>

                        {/* Existing URLs Selection */}
                        {urlSelectionMode === 'existing' && (
                          <div>
                            {loadingUrls ? (
                              <div className="px-3 py-2 rounded-lg border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                              </div>
                            ) : existingUrls.length === 0 ? (
                              <div className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                                No existing URLs found. Use "New URL" tab to add one.
                              </div>
                            ) : (
                              <select
                                value={selectedUrl}
                                onChange={(e) => setSelectedUrl(e.target.value)}
                                required
                                className="w-full px-3 py-2 rounded-lg border text-sm"
                                style={{
                                  borderColor: 'var(--border)',
                                  background: 'var(--surface-2)',
                                  color: 'var(--fg)'
                                }}
                              >
                                <option value="">Select an existing URL...</option>
                                {existingUrls.map((url, index) => (
                                  <option key={index} value={url}>
                                    {url}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        )}

                        {/* New URL Input */}
                        {urlSelectionMode === 'new' && (
                          <div>
                            <input
                              type="url"
                              value={newUrlForProject}
                              onChange={(e) => setNewUrlForProject(e.target.value)}
                              placeholder="https://example.com/path"
                              required
                              className="w-full px-3 py-2 rounded-lg border text-sm"
                              style={{
                                borderColor: 'var(--border)',
                                background: 'var(--surface-2)',
                                color: 'var(--fg)'
                              }}
                            />
                            <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                              Enter a new URL to scan under this project.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* New Target Mode */}
                {selectedMode === 'new' && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                      Target URL
                    </label>
                    <input
                      type="url"
                      value={targetUrl}
                      onChange={(e) => {
                        setTargetUrl(e.target.value);
                        setVerificationData(null);
                        setError(null);
                      }}
                      placeholder="https://example.com"
                      required
                      className="w-full px-3 py-2 rounded-lg border text-sm"
                      style={{
                        borderColor: 'var(--border)',
                        background: 'var(--surface-2)',
                        color: 'var(--fg)'
                      }}
                    />
                    <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                      Enter the URL you want to scan. You'll need to verify domain ownership via DNS.
                    </p>
                    {!session.user?.isAdmin && (
                      <button
                        type="button"
                        onClick={startDomainVerification}
                        disabled={submitting}
                        className="mt-4 px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50 hover:opacity-90"
                      >
                        {submitting ? 'Starting verification...' : 'Verify domain ownership'}
                      </button>
                    )}
                    
                    {/* Verification Status */}
                    {verificationData && (
                      <div className="mt-4 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                        {verificationData.status === 'ALLOWLISTED' && (
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-sm font-medium text-emerald-400">✓ Demo domain approved</span>
                            </div>
                            <p className="text-xs" style={{ color: 'var(--muted)' }}>
                              {verificationData.message || 'This domain is allowlisted. DNS verification not required.'}
                            </p>
                          </div>
                        )}
                        
                        {verificationData.status === 'VERIFIED' && (
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-sm font-medium text-emerald-400">✓ Domain verified</span>
                            </div>
                            <p className="text-xs" style={{ color: 'var(--muted)' }}>
                              Your domain has been verified. You can now proceed to scan.
                            </p>
                          </div>
                        )}
                        
                        {verificationData.status === 'PENDING' && (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <div className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                                Domain verification
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs px-2 py-1 rounded bg-yellow-900/50 text-yellow-200 border border-yellow-700">
                                  PENDING
                                </span>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    deleteDomainVerification();
                                  }}
                                  className="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 border border-red-600/50 hover:bg-red-600/30 transition-colors"
                                  title="Remove this pending verification"
                                >
                                  Remove
                                </button>
                              </div>
                            </div>
                            <p className="text-xs" style={{ color: 'var(--muted)' }}>
                              Add the following DNS TXT record to verify domain ownership:
                            </p>
                            <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                              <div>
                                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>TXT Name:</div>
                                <div className="font-mono text-sm flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                  <span className="break-all">{verificationData.txt_name}</span>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigator.clipboard.writeText(verificationData.txt_name);
                                    }}
                                    className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:opacity-80"
                                  >
                                    Copy
                                  </button>
                                </div>
                              </div>
                              <div>
                                <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>TXT Value:</div>
                                <div className="font-mono text-sm flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                  <span className="break-all">{verificationData.txt_value}</span>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigator.clipboard.writeText(verificationData.txt_value);
                                    }}
                                    className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:opacity-80"
                                  >
                                    Copy
                                  </button>
                                </div>
                              </div>
                            </div>
                            <p className="text-xs text-yellow-400">
                              You must add this TXT record in DNS of this domain. Once added, click "Check verification" below.
                            </p>
                            <button
                              type="button"
                              onClick={checkDomainVerification}
                              disabled={verificationChecking}
                              className="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50 hover:opacity-90"
                            >
                              {verificationChecking ? 'Checking...' : 'Check verification'}
                            </button>
                            {verificationPollInterval && (
                              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                                Auto-checking every 15 seconds...
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Admin allowlist visible to all users */}
                    {allowedDomains.length > 0 && !verificationData && (
                      <div className="mt-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                          Admin allowlist (pre-approved domains)
                        </div>
                        <div className="space-y-1 text-xs" style={{ color: 'var(--muted)' }}>
                          {allowedDomains.map((ad) => (
                            <div key={ad.id} className="flex items-center justify-between">
                              <span className="font-mono text-sm text-gray-200">{ad.domain}</span>
                              <span className="px-2 py-0.5 rounded border" style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}>
                                {ad.scope}
                              </span>
                            </div>
                          ))}
                        </div>
                        {allowedDomainMatch && (
                          <div className="mt-2 text-emerald-300 text-xs">
                            This target matches an allowlisted domain; DNS verification not required.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Domain verification status */}
                {!session.user?.isAdmin && !allowedForSelectedProject && !allowedForTargetUrl && dvStatus && (
                  <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                        Domain verification
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className="text-xs px-2 py-1 rounded"
                          style={{
                            background: dvStatus.status === 'verified' ? '#065f46' : '#92400e',
                            color: 'white',
                          }}
                        >
                          {dvStatus.status}
                        </span>
                        {dvStatus.status === 'pending' && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              deleteDomainVerification();
                            }}
                            className="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 border border-red-600/50 hover:bg-red-600/30 transition-colors"
                            title="Remove this pending verification"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    </div>
                    {dvStatus.status !== 'verified' && (
                      <div className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                        <div>Add this TXT record to verify:</div>
                        <div className="font-mono text-sm text-gray-200">TXT Name: {dvStatus.record_name}</div>
                        <div className="font-mono text-sm text-gray-200">TXT Value: {dvStatus.record_value}</div>
                        <div className="text-yellow-400 text-xs mt-1">Scanning is disabled until domain is verified.</div>
                        <button
                          type="button"
                          onClick={refreshVerification}
                          className="text-blue-400 hover:text-blue-300 mt-2 disabled:opacity-60"
                          disabled={dvLoading}
                        >
                          {dvLoading ? 'Checking...' : 'Refresh status'}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Scan Level Selector */}
                {!(selectedMode === 'new' && !session.user?.isAdmin) && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-3" style={{ color: 'var(--fg)' }}>
                      Scan Level
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                      <button
                        type="button"
                        onClick={() => setScanLevel('basic')}
                        className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                          scanLevel === 'basic'
                            ? 'text-white shadow-sm'
                            : 'hover:opacity-80'
                        }`}
                        style={{
                          background: scanLevel === 'basic' ? 'var(--brand)' : 'var(--surface-2)',
                          borderColor: scanLevel === 'basic' ? 'var(--brand)' : 'var(--border)',
                          color: scanLevel === 'basic' ? 'white' : 'var(--fg)'
                        }}
                      >
                        <div className="font-semibold mb-1">Basic</div>
                        <div className="text-xs opacity-80">Fast surface scan</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => setScanLevel('pro')}
                        className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                          scanLevel === 'pro'
                            ? 'text-white shadow-sm'
                            : 'hover:opacity-80'
                        }`}
                        style={{
                          background: scanLevel === 'pro' ? 'var(--brand)' : 'var(--surface-2)',
                          borderColor: scanLevel === 'pro' ? 'var(--brand)' : 'var(--border)',
                          color: scanLevel === 'pro' ? 'white' : 'var(--fg)'
                        }}
                      >
                        <div className="font-semibold mb-1">Pro</div>
                        <div className="text-xs opacity-80">Deeper coverage</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => setScanLevel('advanced')}
                        className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                          scanLevel === 'advanced'
                            ? 'text-white shadow-sm'
                            : 'hover:opacity-80'
                        }`}
                        style={{
                          background: scanLevel === 'advanced' ? 'var(--brand)' : 'var(--surface-2)',
                          borderColor: scanLevel === 'advanced' ? 'var(--brand)' : 'var(--border)',
                          color: scanLevel === 'advanced' ? 'white' : 'var(--fg)'
                        }}
                      >
                        <div className="font-semibold mb-1">Advanced</div>
                        <div className="text-xs opacity-80">Full-stack probes</div>
                      </button>
                    </div>
                  </div>
                )}

                {/* Error State */}
                {error && (
                  <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between gap-4">
                  <button
                    type="submit"
                    disabled={
                      submitting ||
                      (selectedMode === 'existing'
                        ? (!selectedProjectId || (!session.user?.isAdmin && !allowedForSelectedProject && dvStatus && dvStatus.status !== 'verified'))
                        : (
                            !preparedProjectId || 
                            (verificationData && verificationData.status !== 'VERIFIED' && verificationData.status !== 'ALLOWLISTED')
                          ))
                    }
                    className="px-6 py-3 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                    style={{ background: 'var(--brand)' }}
                  >
                    {submitting ? (
                      <span className="flex items-center gap-2">
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                        Starting scan...
                      </span>
                    ) : (
                      'Start scan'
                    )}
                  </button>
                  <Link
                    href="/dashboard/history"
                    className="text-sm font-medium hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--brand)' }}
                  >
                    View scan history
                  </Link>
                </div>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
