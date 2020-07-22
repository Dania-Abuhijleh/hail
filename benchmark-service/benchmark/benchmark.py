import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict
import asyncio
import aiohttp
import aiohttp_session
import aiohttp_jinja2
import jinja2
from aiohttp import web
import logging
from gear import setup_aiohttp_session, web_authenticated_developers_only, rest_authenticated_developers_only

router = web.RouteTableDef()
logging.basicConfig(level=logging.DEBUG)


@router.get('/healthcheck')
async def healthcheck(request) -> web.Response:
    return web.Response()


@router.get('/{username}')
async def greet_user(request: web.Request) -> web.Response:

    context = {
        'username': request.match_info.get('username', ''),
        'current_date': 'July 10, 2020'
    }
    response = aiohttp_jinja2.render_template('user.html', request,
                                              context=context)
    return response


@router.get('/')
@web_authenticated_developers_only(redirect=False)
async def index(request: web.Request) -> Dict[str, Any]:
    context = {
        'current_date': 'July 10, 2020'
    }
    response = aiohttp_jinja2.render_template('index.html', request,
                                              context=context)
    return response


def init_app() -> web.Application:
    app = web.Application()
    setup_aiohttp_session(app)
    admin = web.Application()
    app.add_routes(router)
    admin.add_subapp('/dabuhijl/benchmark/', app)
    aiohttp_jinja2.setup(
        app, loader=jinja2.ChoiceLoader([
            jinja2.PackageLoader('benchmark')
        ]))
    return admin


web.run_app(init_app(), port=5000)
