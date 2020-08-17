from aiohttp import web
import logging
from gear import setup_aiohttp_session, web_authenticated_developers_only
from hailtop.config import get_deploy_config
from hailtop.tls import get_in_cluster_server_ssl_context
from hailtop.hail_logging import AccessLogger, configure_logging
from web_common import setup_aiohttp_jinja2, setup_common_static_routes, render_template
from benchmark.utils import ReadGoogleStorage, get_geometric_mean, parse_file_path, enumerate_list_index
import json
import re
import plotly
import plotly.express as px
from scipy.stats.mstats import gmean, hmean
import numpy as np

configure_logging()
router = web.RouteTableDef()
logging.basicConfig(level=logging.DEBUG)
deploy_config = get_deploy_config()
log = logging.getLogger('benchmark')

BENCHMARK_FILE_REGEX = re.compile(r'gs://((?P<bucket>[^/]+)/)((?P<user>[^/]+)/)((?P<version>[^-]+)-)((?P<sha>[^-]+))(-(?P<tag>[^\.]+))?\.json')


def get_benchmarks(file_path):
    read_gs = ReadGoogleStorage()
    try:
        json_data = read_gs.get_data_as_string(file_path)
        pre_data = json.loads(json_data)
    except Exception:
        message = f'could not find file, {file_path}'
        log.info('could not get blob: ' + message, exc_info=True)
        raise web.HTTPBadRequest(text=message)

    data = []
    prod_of_means = 1
    for d in pre_data['benchmarks']:
        stats = dict()
        stats['name'] = d['name']
        stats['failed'] = d['failed']
        if not d['failed']:
            prod_of_means *= d['mean']
            stats['f-stat'] = round(d['f-stat'], 6)
            stats['mean'] = round(d['mean'], 6)
            stats['median'] = round(d['median'], 6)
            stats['p-value'] = round(d['p-value'], 6)
            stats['stdev'] = round(d['stdev'], 6)
            stats['times'] = d['times']
            stats['trials'] = d['trials']
        data.append(stats)
    geometric_mean = get_geometric_mean(prod_of_means, len(pre_data['benchmarks']))

    file_info = parse_file_path(BENCHMARK_FILE_REGEX, file_path)
    sha = file_info['sha']
    benchmarks = dict()
    benchmarks['sha'] = sha
    benchmarks['geometric_mean'] = geometric_mean
    benchmarks['data'] = sorted(data, key=lambda i: i['name'])
    return benchmarks


def get_comparisons(benchmarks1, benchmarks2, metric):
    def get_metric(data):
        if metric == 'median':
            return data['median']
        assert metric == 'best'
        return min(data['times'])

    # comparisons = []
    # for d in benchmarks1['data']:
    #     for item in benchmarks2['data']:
    #         if item['name'] == d['name']:
    #             comparisons.append((d['name'], get_metric(d), get_metric(item)))
    # return comparisons
    comparisons = []
    for d in benchmarks1['data']:
        item = next((item for item in benchmarks2['data'] if item['name'] == d['name']),
                    None)
        if item is None:
            comparisons.append(d['name'], get_metric(d), None)
        else:
            comparisons.append(d['name'], get_metric(d), get_metric(item))
    for d2 in benchmarks2['data']:
        item1 = next((item for item in benchmarks1['data'] if item['name'] == d2['name']),
                     None)
        if item1 is None:
            comparisons.append(d2['name'], None, get_metric(d2))
    return comparisons


def fmt_time(t):
    return round(t, 3)


def fmt_diff(ratio):
    return round(ratio * 100, 3)


def final_comparisons(comparisons):
    comps = []
    ratios = []
    final_comps = {}
    for name, r1, r2 in comparisons:
        # r = r1 / r2
        # ratios.append(r)
        # comps.append((name, fmt_diff(r), fmt_time(r1), fmt_time(r2)))
        if r1 is None:
            comps.append((name, None, None, fmt_time(r2)))
        elif r2 is None:
            comps.append((name, None, fmt_time(r1), None))
        else:
            r = r1 / r2
            ratios.append(r)
            comps.append((name, fmt_diff(r), fmt_time(r1), fmt_time(r2)))
    final_comps['comps'] = comps
    final_comps['harmonic_mean'] = fmt_diff(hmean(ratios))
    final_comps['geometric_mean'] = fmt_diff(gmean(ratios))
    final_comps['arithmetic_mean'] = fmt_diff(np.mean(ratios))
    final_comps['median'] = fmt_diff(np.median(ratios))
    return final_comps


@router.get('/healthcheck')
async def healthcheck(request: web.Request) -> web.Response:  # pylint: disable=unused-argument
    return web.Response()


@router.get('/name/{name}')
@web_authenticated_developers_only(redirect=False)
async def show_name(request: web.Request, userdata) -> web.Response:  # pylint: disable=unused-argument
    file_path = request.query.get('file')
    benchmarks = get_benchmarks(file_path)
    name_data = next((item for item in benchmarks['data'] if item['name'] == str(request.match_info['name'])),
                     None)

    try:
        fig = px.scatter(x=enumerate_list_index(name_data['trials']), y=name_data['times'])
        plot = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception:
        message = 'could not find name'
        log.info('name is of type NoneType: ' + message, exc_info=True)
        raise web.HTTPBadRequest(text=message)

    context = {
        'name': request.match_info.get('name', ''),
        'plot': plot
    }

    return await render_template('benchmark', request, userdata, 'name.html', context)


@router.get('/')
@router.get('')
@web_authenticated_developers_only(redirect=False)
async def index(request, userdata):  # pylint: disable=unused-argument
    file = request.query.get('file')
    if file is None:
        benchmarks_context = None
    else:
        benchmarks_context = get_benchmarks(file)
    context = {'file': file,
               'benchmarks': benchmarks_context}
    return await render_template('benchmark', request, userdata, 'index.html', context)


@router.get('/compare')
@web_authenticated_developers_only(redirect=False)
async def compare(request, userdata):  # pylint: disable=unused-argument
    file1 = request.query.get('file1')
    file2 = request.query.get('file2')
    metric = request.query.get('metrics')
    if file1 is None or file2 is None:
        benchmarks_context1 = None
        benchmarks_context2 = None
        comparisons = None
    else:
        benchmarks_context1 = get_benchmarks(file1)
        benchmarks_context2 = get_benchmarks(file2)
        comparisons = final_comparisons(get_comparisons(benchmarks_context1, benchmarks_context2, metric))
    context = {'file1': file1,
               'file2': file2,
               'metric': metric,
               'benchmarks1': benchmarks_context1,
               'benchmarks2': benchmarks_context2,
               'comparisons': comparisons}
    return await render_template('benchmark', request, userdata, 'compare.html', context)


def init_app() -> web.Application:
    app = web.Application()
    setup_aiohttp_jinja2(app, 'benchmark')
    setup_aiohttp_session(app)

    setup_common_static_routes(router)
    app.add_routes(router)
    return app


web.run_app(deploy_config.prefix_application(init_app(), 'benchmark'),
            host='0.0.0.0',
            port=5000,
            access_log_class=AccessLogger,
            ssl_context=get_in_cluster_server_ssl_context())
