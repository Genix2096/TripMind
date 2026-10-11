import asyncio
import time
from unittest.mock import patch

import pytest

from app.core.errors import ProviderRequestError
from app.core.quota import TokenQuotaManager


@pytest.fixture
def quota_manager():
    # Use a small limit for testing
    mgr = TokenQuotaManager(limit_tpm=1000)
    # Clear any existing state since it's a singleton
    mgr.reservations.clear()
    TokenQuotaManager._instance = mgr
    try:
        yield mgr
    finally:
        mgr.reservations.clear()
        TokenQuotaManager._instance = None


@pytest.mark.asyncio
async def test_sequential_calls(quota_manager):
    # Call 1: 500 tokens
    res1 = await quota_manager.acquire(300, 200)
    assert len(quota_manager.reservations) == 1
    quota_manager.reconcile(res1, 400)  # used less than requested
    
    # Call 2: 500 tokens (fits because we used 400 + 500 = 900 <= 1000)
    await quota_manager.acquire(300, 200)
    assert len(quota_manager.reservations) == 2


@pytest.mark.asyncio
async def test_concurrent_requests(quota_manager):
    # Two concurrent requests that together fit the budget
    async def make_request():
        res = await quota_manager.acquire(200, 200)
        return res
        
    tasks = [make_request(), make_request()]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 2
    assert len(quota_manager.reservations) == 2
    assert quota_manager._current_usage(time.time()) == 800


@pytest.mark.asyncio
async def test_oversized_request(quota_manager):
    with pytest.raises(ProviderRequestError) as exc:
        await quota_manager.acquire(800, 300)  # 1100 > 1000
    assert "exceeding safe threshold" in str(exc.value)


@pytest.mark.asyncio
async def test_quota_exhaustion_and_delay(quota_manager):
    # Mock time to simulate rolling window
    current_time = [1000.0]
    
    def mock_time():
        return current_time[0]
        
    with patch("time.time", side_effect=mock_time):
        # Consume full quota
        await quota_manager.acquire(500, 500)
        assert len(quota_manager.reservations) == 1
        
        # Next request should block since quota is full
        # We will use an asyncio task and step time to unblock it
        
        async def delayed_request():
            # acquire will loop and call time.time()
            return await quota_manager.acquire(500, 500, timeout_seconds=70.0)
            
        task = asyncio.create_task(delayed_request())
        
        # Let the task start and block
        await asyncio.sleep(0.01)
        assert not task.done()
        
        # Advance time by 61 seconds so the first reservation expires
        current_time[0] = 1061.0
        
        # Let the task resume
        res2 = await task
        
        assert res2 is not None
        assert len(quota_manager.reservations) == 1 # The old one was cleaned up


@pytest.mark.asyncio
async def test_timeout_when_queue_full(quota_manager):
    current_time = [1000.0]
    
    def mock_time():
        # Each time we check the time, we advance slightly to simulate time passing
        # but not enough to clear the 60s window
        current_time[0] += 0.5
        return current_time[0]
        
    with patch("time.time", side_effect=mock_time):
        # Fill quota
        await quota_manager.acquire(500, 500)
        
        # Attempt to acquire more, with a short timeout
        with pytest.raises(ProviderRequestError) as exc:
            await quota_manager.acquire(500, 500, timeout_seconds=1.0)
            
        assert "Timeout waiting for token quota" in str(exc.value)

@pytest.mark.asyncio
async def test_reconciliation_frees_capacity(quota_manager):
    # acquire 800 tokens, which almost fills the quota
    res1 = await quota_manager.acquire(400, 400)
    assert len(quota_manager.reservations) == 1
    
    # reconcile with actual usage of 100
    quota_manager.reconcile(res1, 100)
    
    # now we should be able to acquire 900 more tokens immediately
    res2 = await quota_manager.acquire(450, 450)
    assert len(quota_manager.reservations) == 2
    assert quota_manager._current_usage(time.time()) == 1000

@pytest.mark.asyncio
async def test_failed_requests_do_not_leak_reservations(quota_manager):
    res1 = await quota_manager.acquire(500, 500)
    # simulate a failed request by reconciling with 0 tokens
    quota_manager.reconcile(res1, 0)
    
    # now we can acquire the full 1000 tokens again
    res2 = await quota_manager.acquire(500, 500)
    assert len(quota_manager.reservations) == 2
    assert quota_manager._current_usage(time.time()) == 1000
