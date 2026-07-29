import asyncio

import pytest

from buy_agent.adapters.persistence.local_lock_manager import LocalLockManager


async def test_same_key_serializes_and_different_keys_parallelize() -> None:
    manager = LocalLockManager()
    active = 0
    same_max = 0

    async def same_worker() -> None:
        nonlocal active, same_max
        async with manager.lock("same"):
            active += 1
            same_max = max(same_max, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(same_worker(), same_worker())
    assert same_max == 1

    entered = asyncio.Event()

    async def first() -> None:
        async with manager.lock("first"):
            entered.set()
            await asyncio.sleep(0.02)

    async def second() -> None:
        await entered.wait()
        async with manager.lock("second"):
            assert entered.is_set()

    await asyncio.gather(first(), second())


async def test_lock_is_released_after_exception() -> None:
    manager = LocalLockManager()
    with pytest.raises(RuntimeError):
        async with manager.lock("key"):
            raise RuntimeError("boom")
    async with manager.lock("key"):
        pass
