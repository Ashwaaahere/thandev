/**
 * Cloud Run Jobs execution utility
 * Handles execution of Cloud Run Jobs with environment variables
 */

import { JobsClient } from '@google-cloud/run';

export interface CloudRunJobConfig {
  projectId: string;
  region: string;
  jobName: string;
  environment: Record<string, string>;
}

export interface CloudRunJobResult {
  success: boolean;
  executionId?: string;
  error?: string;
}

// Initialize the Cloud Run Jobs client
const jobsClient = new JobsClient();

/**
 * Execute a Cloud Run Job with the given configuration
 */
export async function executeCloudRunJob(config: CloudRunJobConfig): Promise<CloudRunJobResult> {
  try {
    console.log('Executing Cloud Run Job:', {
      job: `${config.jobName}`,
      region: config.region,
      environment: config.environment
    });
    
    // Get the job name
    const jobName = `projects/${config.projectId}/locations/${config.region}/jobs/${config.jobName}`;
    
    // Create execution request
    const request = {
      name: jobName,
      overrides: {
        containerOverrides: [{
          env: Object.entries(config.environment).map(([key, value]) => ({
            name: key,
            value: value
          }))
        }]
      }
    };
    
    // Execute the job
    const [operation] = await jobsClient.runJob(request);
    
    // Get the execution name from the operation
    const executionName = operation.name;
    const executionId = executionName.split('/').pop() || `exec-${Date.now()}`;
    
    console.log('Cloud Run Job execution started:', executionId);
    
    return {
      success: true,
      executionId
    };
    
  } catch (error) {
    console.error('Cloud Run Job execution failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Get the status of a Cloud Run Job execution
 */
export async function getCloudRunJobStatus(
  projectId: string,
  region: string,
  jobName: string,
  executionId: string
): Promise<{ status: string; completionTime?: string }> {
  try {
    // In a real implementation, you would:
    // 1. Use the Google Cloud Run Jobs API client
    // 2. Get the execution status
    // 3. Return the current status and completion time
    
    // For now, we'll simulate this
    return {
      status: 'RUNNING' // or 'SUCCEEDED', 'FAILED', etc.
    };
    
  } catch (error) {
    console.error('Failed to get Cloud Run Job status:', error);
    return {
      status: 'UNKNOWN'
    };
  }
}

/**
 * Scenario configuration mapping
 */
export const SCENARIO_CONFIG = {
  baseline: {
    VUS: 50,
    DURATION: 120,
    SPAWN: 10
  },
  spike: {
    VUS: 200,
    DURATION: 120,
    SPAWN: 100
  },
  soak: {
    VUS: 50,
    DURATION: 300,
    SPAWN: 5
  }
} as const;

export type ScenarioType = keyof typeof SCENARIO_CONFIG;
