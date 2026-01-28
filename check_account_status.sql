-- Check account status for asatishkumar@binghamton.edu
-- Run this first to see the current state

SELECT 
    id, 
    email, 
    username, 
    is_admin, 
    is_approved, 
    external_provider, 
    external_user_id,
    tenant_id,
    created_at,
    updated_at
FROM users 
WHERE email = 'asatishkumar@binghamton.edu';

-- Also check if account exists with different casing or variations
SELECT 
    id, 
    email, 
    username, 
    is_admin, 
    is_approved, 
    external_provider, 
    external_user_id
FROM users 
WHERE LOWER(email) LIKE '%asatish%' OR LOWER(email) LIKE '%binghamton%';

