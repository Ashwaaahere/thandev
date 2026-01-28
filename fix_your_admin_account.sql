-- Fix your admin account (asatishkumar@binghamton.edu)
-- Update with your GitHub ID and set admin flags

-- First, find your user ID
SELECT id, email, username, is_admin, is_approved, external_provider, external_user_id 
FROM users 
WHERE email = 'asatishkumar@binghamton.edu';

-- Then update with your GitHub ID (replace '97579623' with your actual GitHub ID if different)
UPDATE users 
SET 
    external_provider = 'github',
    external_user_id = '97579623',  -- Replace with your actual GitHub ID if different
    is_admin = true,
    is_approved = true
WHERE email = 'asatishkumar@binghamton.edu';

-- Verify the update
SELECT id, email, username, is_admin, is_approved, external_provider, external_user_id 
FROM users 
WHERE email = 'asatishkumar@binghamton.edu';

