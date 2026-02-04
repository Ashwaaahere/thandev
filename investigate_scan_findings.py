#!/usr/bin/env python3
"""
Investigate why tools are returning 0 findings
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("❌ sqlalchemy not installed. Install with: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# Get database URL from environment
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require')

def investigate_scan(scan_id_partial: str):
    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Find the scan
        if len(scan_id_partial) < 36:
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at FROM scan_jobs WHERE id LIKE :scan_id ORDER BY created_at DESC LIMIT 1'),
                {'scan_id': f'{scan_id_partial}%'}
            )
        else:
            result = db.execute(
                text('SELECT id, status, scan_level, url, created_at FROM scan_jobs WHERE id = :scan_id'),
                {'scan_id': scan_id_partial}
            )
        
        scan = result.fetchone()
        
        if not scan:
            print(f'❌ No scan found with ID matching "{scan_id_partial}"')
            db.close()
            return
        
        scan_id = scan[0]
        print(f'\n{"="*80}')
        print(f'🔍 Investigating Scan: {scan_id}')
        print(f'{"="*80}')
        print(f'URL: {scan[3]}')
        print(f'Level: {scan[2]}')
        print(f'Status: {scan[1]}')
        print()
        
        # Get tool results with detailed info
        tools_result = db.execute(
            text('''
                SELECT 
                    tool_name,
                    status,
                    exit_code,
                    error_message,
                    error_code,
                    created_findings_count,
                    parsed_findings_count,
                    output,
                    stdout_preview,
                    execution_time,
                    command
                FROM tool_results 
                WHERE scan_job_id = :scan_id 
                ORDER BY created_at ASC
            '''),
            {'scan_id': scan_id}
        )
        tools = tools_result.fetchall()
        
        print(f'🔧 Tool Results Analysis ({len(tools)} tools):')
        print('-' * 80)
        
        for tool in tools:
            tool_name = tool[0]
            status = tool[1]
            exit_code = tool[2]
            error_msg = tool[3]
            error_code = tool[4]
            created_findings = tool[5] or 0
            parsed_findings = tool[6] or 0
            output = tool[7]
            stdout_preview = tool[8]
            exec_time = tool[9]
            command = tool[10]
            
            print(f'\n📦 {tool_name.upper()}')
            print(f'   Status: {status}')
            print(f'   Exit Code: {exit_code}')
            print(f'   Findings Created: {created_findings}')
            print(f'   Findings Parsed: {parsed_findings}')
            print(f'   Execution Time: {exec_time}s' if exec_time else '   Execution Time: N/A')
            
            if error_code:
                print(f'   Error Code: {error_code}')
            if error_msg:
                print(f'   Error: {error_msg}')
            
            # Check output
            output_len = len(output) if output else 0
            stdout_len = len(stdout_preview) if stdout_preview else 0
            print(f'   Output Length: {output_len} bytes')
            print(f'   Stdout Preview Length: {stdout_len} bytes')
            
            # Show output preview
            if output:
                output_preview = output[:500] if len(output) > 500 else output
                print(f'   Output Preview: {output_preview}...' if len(output) > 500 else f'   Output: {output_preview}')
                
                # Try to parse as JSON if it looks like JSON
                if output.strip().startswith('[') or output.strip().startswith('{'):
                    try:
                        parsed = json.loads(output)
                        if isinstance(parsed, list):
                            print(f'   ⚠️  Output is JSON array with {len(parsed)} items - findings might not be parsed!')
                            if len(parsed) > 0:
                                print(f'   First item: {json.dumps(parsed[0])[:200]}...')
                        elif isinstance(parsed, dict):
                            print(f'   ⚠️  Output is JSON object - might need parsing!')
                    except:
                        pass
            elif stdout_preview:
                print(f'   Stdout Preview: {stdout_preview[:200]}...')
            else:
                print(f'   ⚠️  No output or stdout preview available!')
            
            # Check if findings were received but not created
            if parsed_findings > 0 and created_findings == 0:
                print(f'   🚨 ISSUE: {parsed_findings} findings were parsed but 0 were created!')
                print(f'      This suggests an ingestion problem.')
            elif output_len > 0 and created_findings == 0 and parsed_findings == 0:
                print(f'   ⚠️  WARNING: Tool produced output ({output_len} bytes) but no findings were parsed!')
                print(f'      This suggests a parsing problem.')
            elif output_len == 0 and created_findings == 0:
                print(f'   ℹ️  No output - tool may have found nothing (this could be normal)')
            
            if command:
                print(f'   Command: {command[:100]}...' if len(command) > 100 else f'   Command: {command}')
        
        print()
        
        # Get findings count
        findings_result = db.execute(
            text('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
                    COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
                    COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium,
                    COUNT(CASE WHEN severity = 'low' THEN 1 END) as low,
                    COUNT(CASE WHEN severity = 'info' THEN 1 END) as info,
                    COUNT(DISTINCT tool_name) as tools_with_findings
                FROM findings 
                WHERE scan_job_id = :scan_id
            '''),
            {'scan_id': scan_id}
        )
        findings_stats = findings_result.fetchone()
        
        total_findings = findings_stats[0] if findings_stats else 0
        
        print(f'📋 Findings in Database:')
        print('-' * 80)
        if total_findings > 0:
            print(f'   Total: {total_findings}')
            print(f'   Critical: {findings_stats[1]}')
            print(f'   High: {findings_stats[2]}')
            print(f'   Medium: {findings_stats[3]}')
            print(f'   Low: {findings_stats[4]}')
            print(f'   Info: {findings_stats[5]}')
            print(f'   Tools with Findings: {findings_stats[6]}')
        else:
            print(f'   ⚠️  No findings found in database!')
        
        print()
        
        # Get findings by tool
        findings_by_tool_result = db.execute(
            text('''
                SELECT 
                    tool_name,
                    COUNT(*) as count
                FROM findings 
                WHERE scan_job_id = :scan_id
                GROUP BY tool_name
                ORDER BY count DESC
            '''),
            {'scan_id': scan_id}
        )
        findings_by_tool = findings_by_tool_result.fetchall()
        
        if findings_by_tool:
            print(f'📊 Findings by Tool:')
            print('-' * 80)
            for tool_finding in findings_by_tool:
                tool_name = tool_finding[0]
                count = tool_finding[1]
                print(f'   {tool_name}: {count}')
        else:
            print(f'📊 Findings by Tool: None')
        
        print()
        
        # Summary and recommendations
        print(f'🔍 DIAGNOSIS:')
        print('-' * 80)
        
        issues = []
        recommendations = []
        
        # Check for tools with output but no findings
        tools_with_output_no_findings = []
        for tool in tools:
            tool_name = tool[0]
            output = tool[7]
            created_findings = tool[5] or 0
            parsed_findings = tool[6] or 0
            
            if output and len(output) > 0 and created_findings == 0:
                tools_with_output_no_findings.append((tool_name, len(output), parsed_findings))
        
        if tools_with_output_no_findings:
            issues.append(f"⚠️  {len(tools_with_output_no_findings)} tool(s) produced output but created 0 findings:")
            for tool_name, output_len, parsed in tools_with_output_no_findings:
                issues.append(f"   - {tool_name}: {output_len} bytes output, {parsed} parsed, 0 created")
                if parsed > 0:
                    recommendations.append(f"   {tool_name}: Findings were parsed ({parsed}) but not created - check ingestion logic")
                else:
                    recommendations.append(f"   {tool_name}: Output exists but wasn't parsed - check parser for {tool_name}")
        
        # Check for parsing issues
        tools_with_parsed_no_created = []
        for tool in tools:
            tool_name = tool[0]
            parsed_findings = tool[6] or 0
            created_findings = tool[5] or 0
            
            if parsed_findings > 0 and created_findings == 0:
                tools_with_parsed_no_created.append(tool_name)
        
        if tools_with_parsed_no_created:
            issues.append(f"🚨 CRITICAL: {len(tools_with_parsed_no_created)} tool(s) parsed findings but didn't create them:")
            for tool_name in tools_with_parsed_no_created:
                issues.append(f"   - {tool_name}")
            recommendations.append("Check findings ingestion logic in backend/app/api/runner_ingest.py")
            recommendations.append("Check for exceptions during finding creation (look for [INGEST-DEBUG] logs)")
        
        if not issues:
            if total_findings == 0:
                issues.append("ℹ️  All tools completed but no findings were created")
                issues.append("   This could be normal if the target has no vulnerabilities")
                recommendations.append("Verify tools actually scanned the target (check output/commands)")
                recommendations.append("Compare with previous scans that had findings")
        
        for issue in issues:
            print(f'   {issue}')
        
        if recommendations:
            print()
            print(f'💡 RECOMMENDATIONS:')
            print('-' * 80)
            for rec in recommendations:
                print(f'   {rec}')
        
        db.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    scan_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not scan_id:
        print('Usage: python3 investigate_scan_findings.py <scan_id>')
        print('Example: python3 investigate_scan_findings.py A032D30F')
        sys.exit(1)
    investigate_scan(scan_id)


