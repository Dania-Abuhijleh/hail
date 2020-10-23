import json
import logging
import asyncio
import pytest
import aiohttp

from hailtop.config import get_deploy_config
from hailtop.auth import service_auth_headers
from hailtop.tls import in_cluster_ssl_client_session, get_context_specific_ssl_client_session
import hailtop.utils as utils

pytestmark = pytest.mark.asyncio

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

sha = '6dcb09b5b57875f334f61aebed695e2e4193db5e'


async def test_submit():
    deploy_config = get_deploy_config()
    headers = service_auth_headers(deploy_config, 'benchmark')
    create_benchmark_url = deploy_config.url('benchmark', '/api/v1alpha/benchmark/create_benchmark')
    async with get_context_specific_ssl_client_session(
            raise_for_status=True,
            timeout=aiohttp.ClientTimeout(total=60)) as session:
        resp = await utils.request_retry_transient_errors(
            session, 'POST', f'{create_benchmark_url}', headers=headers, json={'sha': sha})

        resp_text = await resp.text()
        batch_info = json.loads(resp_text)
        batch_id = batch_info['batch_status']['id']
        batch_url = deploy_config.url('benchmark', f'/api/v1alpha/benchmark/batches/{sha}')

        async def wait_forever():
            batch_status = None
            complete = None
            while complete is None or complete is False:
                resp2 = await utils.request_retry_transient_errors(
                    session, 'GET', f'{batch_url}', headers=headers)
                batch_status = await resp2.json()
                log.info(f'batch_status:\n{json.dumps(batch_status, indent=2)}')
                print(f'status: {batch_status}')
                await asyncio.sleep(5)
                complete = batch_status['batch_status']['complete']
            return batch_status

        batch_status = await asyncio.wait_for(wait_forever(), timeout=30 * 60)
        assert batch_status['batch_status']['n_succeeded'] > 0
