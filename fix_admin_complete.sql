-- Complete fix for admin account
-- Run all these commands in order

-- Step 1: Check if account exists
SELECT id, email, username, is_admin, is_approved, external_provider, external_user_id 
FROM users 
WHERE email = 'asatishkumar@binghamton.edu';

-- Step 2: If account exists, update it
UPDATE users 
SET 
    external_provider = 'github',
    external_user_id = '97579623',
    is_admin = true,
    is_approved = true,
    updated_at = NOW()
WHERE email = 'asatishkumar@binghamton.edu';

-- Step 3: If account doesn't exist, you may need to sign in first via GitHub OAuth
-- The bootstrap endpoint will create it automatically when you sign in

-- Step 4: Verify the update
SELECT id, email, username, is_admin, is_approved, external_provider, external_user_id 
FROM users 
WHERE email = 'asatishkumar@binghamton.edu';

-- Step 5: Also check by GitHub ID to see if there's a mismatch
SELECT id, email, username, is_admin, is_approved, external_provider, external_user_id 
FROM users 
WHERE external_user_id = '97579623';

