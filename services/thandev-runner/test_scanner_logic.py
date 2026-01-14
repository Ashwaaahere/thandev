
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.tools import ToolExecutor

from pathlib import Path

@pytest.fixture
def tool_executor():
    return ToolExecutor(Path("/tmp/catalog.yaml"))

@pytest.mark.asyncio
async def test_crawl_target_integration(tool_executor):
    """Verify crawler is called and returns expected format."""
    with patch('app.services.tools.SmartCrawler') as MockCrawler:
        # Setup mock
        instance = MockCrawler.return_value
        instance.crawl = AsyncMock(return_value=(
            ['http://test.com', 'http://test.com/page1'], 
            ['http://test.com/search?q=1']
        ))
        
        # Test
        all_urls, params = await tool_executor._crawl_target('http://test.com', 'job1', 'advanced')
        
        # Verify
        assert len(all_urls) == 2
        assert 'http://test.com/search?q=1' in params
        assert instance.crawl.called

@pytest.mark.asyncio
async def test_tools_use_crawled_urls(tool_executor):
    """Verify tools construct commands using crawled URLs."""
    
    # Mock crawler to return specific URLs
    tool_executor._crawl_target = AsyncMock(return_value=(
        ['http://test.com', 'http://test.com/page1', 'http://test.com/page2'], 
        ['http://test.com/search?q=1']
    ))
    
    # Mock subprocess.run
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        
        # Test Dalfox
        await tool_executor._run_dalfox('http://test.com', 'pro')
        
        # Verify Dalfox Args
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert 'pipe' in cmd
        assert 'dalfox' in cmd[0]
        # Verify input was passed (stdin)
        assert kwargs.get('input') == 'http://test.com\nhttp://test.com/page1\nhttp://test.com/page2'
        
        # Test Nuclei
        mock_run.reset_mock()
        mock_run.return_value.returncode = 0
        await tool_executor._run_nuclei('http://test.com', 'pro')
        
        # Verify Nuclei Args
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert '-u' not in cmd  # Should use stdin
        # Verify input was passed
        assert kwargs.get('input') == 'http://test.com\nhttp://test.com/page1\nhttp://test.com/page2'

@pytest.mark.asyncio
async def test_sqlmap_bulk_mode(tool_executor):
    """Verify SQLMap uses bulk file for parameterized URLs."""
    
    # Mock crawler
    tool_executor._crawl_target = AsyncMock(return_value=(
        ['http://test.com', 'http://test.com/search?q=1'], 
        ['http://test.com/search?q=1']
    ))
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        
        # Test SQLMap
        await tool_executor._run_sqlmap(
            'http://test.com', 'pro', 
            scan_job_id='test_job',
            scan_job_dir='/tmp/test_job'
        )
        
        # Verify SQLMap Args
        args, kwargs = mock_run.call_args
        cmd = args[0]
        # Check for bulk file flag -m
        assert '-m' in cmd
        assert '--smart' in cmd

@pytest.mark.asyncio
async def test_crawler_js_discovery():
    from app.utils.crawler import SmartCrawler
    
    crawler = SmartCrawler("http://test.com", depth=2, limit=10)
    
    html_content = """
    <html>
        <body>
            <script>
                var url = "http://test.com/api/data";
                location.href = 'http://test.com/redirect';
            </script>
            <iframe src="/frame/content"></iframe>
            <div data-url="http://test.com/data-attr"></div>
        </body>
    </html>
    """
    
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.text = html_content
    mock_response.headers = {'content-type': 'text/html'}
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_context = AsyncMock()
        mock_context.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_context
        
        urls, params = await crawler.crawl()
        
        # Verify discovered URLs
        # Note: urls will be full absolute URLs
        all_urls_str = " ".join(urls)
        assert "http://test.com/api/data" in all_urls_str
        assert "http://test.com/redirect" in all_urls_str
        assert "http://test.com/frame/content" in all_urls_str

