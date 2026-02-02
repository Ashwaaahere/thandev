-- Find the user with ID d36da182-2f87-4c52-9ab2-b8a7dcd28bcf
-- This is the user ID from the logs that's trying to access admin

-- Step 1: Check what user this is
SELECT 
    id, 
    email, 
    username, 
    is_admin, 
    is_approved, 
    external_provider, 
    external_user_id,
    tenant_id
FROM users 
WHERE id = 'd36da182-2f87-4c52-9ab2-b8a7dcd28bcf';

-- Step 2: If this is your account (asatishkumar@binghamton.edu), update it
-- If it's a different account, update the email in the WHERE clause
UPDATE users 
SET 
    external_provider = 'github',
    external_user_id = '97579623',  -- Your GitHub ID
    is_admin = true,
    is_approved = true,
    updated_at = NOW()
WHERE id = 'd36da182-2f87-4c52-9ab2-b8a7dcd28bcf';

-- Step 3: Verify the update
SELECT 
    id, 
    email, 
    username, 
    is_admin, 
    is_approved, 
    external_provider, 
    external_user_id
FROM users 
WHERE id = 'd36da182-2f87-4c52-9ab2-b8a7dcd28bcf';

-- Step 4: Also check if there are multiple accounts that need fixing
-- Find all users missing external_user_id
SELECT 
    id, 
    email, 
    username, 
    is_admin, 
    is_approved, 
    external_provider, 
    external_user_id
FROM users 
WHERE external_user_id IS NULL OR external_user_id = '';



