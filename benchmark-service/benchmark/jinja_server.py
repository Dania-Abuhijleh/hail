import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict

import aiohttp_jinja2
import jinja2
from aiohttp import web
import logging

app = web.Application()
router = web.RouteTableDef()
logging.basicConfig(level=logging.DEBUG)


aiohttp_jinja2.setup(
    app, loader=jinja2.FileSystemLoader(os.path.join(os.getcwd(), "templates"))
)


@router.get('/{username}')
async def greet_user(request: web.Request) -> web.Response:

    context = {
        'username': request.match_info.get("username", ""),
        'current_date': 'July 10, 2020'
    }
    response = aiohttp_jinja2.render_template("user.html", request,
                                              context=context)
    return response


@router.get("/")
@aiohttp_jinja2.template("index.html")
async def index(request: web.Request) -> Dict[str, Any]:
    context = {
        'current_date': 'July 10, 2020'
    }
    response = aiohttp_jinja2.render_template("index.html", request,
                                              context=context)
    return response


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(router)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "templates"))
    )

    return app


web.run_app(init_app())