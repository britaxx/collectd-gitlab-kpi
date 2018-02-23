"""
   Collect KPI about Gilab
"""
# coding: utf8
#!./environment/bin/python

__author__ = "Alexandre BRIT (@britaxx)"
__maintainer__ = "Alexandre BRIT"

from multiprocessing import Queue
import collectd
import urllib3
import urllib3.contrib.pyopenssl
import certifi
import json
import time


URL = "https://gitlab.example.com"
PRIVATE_TOKEN = "vfvsdvdshgkawhgsk5gse"
GROUPS = []
PROJECTS = []  # Not implement yet
# Pool manager for requests
urllib3.contrib.pyopenssl.inject_into_urllib3()
http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                           ca_certs=certifi.where(), num_pools=50)


def config_func(config):
    '''
       Fetch module configuration or set default Value
    '''
    url_set = False
    private_token_set = False
    groups_set = False

    for node in config.children:
        key = node.key.lower()
        val = node.values[0]

        if key == 'url':
            global URL
            URL = val
            url_set = True
        elif key == 'private_token':
            global PRIVATE_TOKEN
            PRIVATE_TOKEN = val
            private_token_set = True
        elif key == 'groups':
            # val format "group_1, group_2"
            global GROUPS
            GROUPS = val.split(',')
            groups_set = True
        else:
            collectd.info('gitlab_kpi plugin: Unknown config key "%s"' % key)

    collectd.info('gitlab_kpi plugin: Using url "%s"' % URL)
    collectd.info('gitlab_kpi plugin: Using Token "%s"' % PRIVATE_TOKEN)
    collectd.info('gitlab_kpi plugin: Using Groups %s' % GROUPS)

def make_resquest(url, method='GET',
                  headers={'PRIVATE-TOKEN': PRIVATE_TOKEN},
                  body=None):
    '''
       Make request to Gitlab api
       Return response data and headers
    '''
#    print('gitlab_kpi plugin: Checking "%s"' % url)
    response = http.request('GET', url, body=body,
                            headers={'PRIVATE-TOKEN': PRIVATE_TOKEN})
    r_data = json.loads(response.data.decode('utf-8'))
    return r_data, response.headers


def define_pagination(headers):
    '''
        Define if you are at the end or not
    '''
    x_next_page = headers.get('X-Next-Page')
    if x_next_page != '':
        return True
    return False


def define_next_page(headers):
    '''
       Define next Url to check or return None
    '''
    link = headers.get('Link')
    for url in link.split(','):
        if url.endswith('rel="next"'):
            next = url.strip().split(';')[0][1:-1]
            return next
    return None


def crawl_groups():
    '''
      Crawl Groups and fetch projects in global PROJECTS
    '''
    for group in GROUPS:
        url = URL + '/groups/{}/projects?simple=1'.format(group)
        data, headers = make_resquest(url=url)
        PROJECTS.append(data)
        pagination = define_pagination(headers)
        while pagination:
            url = define_next_page(headers)
            data, headers = make_resquest(url=url)
            PROJECTS.append(data)
            pagination = define_pagination(headers)


def get_x_total(q, url, key, project_id, project_name):
    '''
       Return X-total from headers
    '''
    data, headers = make_resquest(url=url)
    q.put({'key': key,
           'total': headers.get('X-Total', 0),
           'project_id': project_id,
           'project_name': project_name})
    return headers.get('X-Total', 0)


def write(key, value, project_id, type_instance, timestamp, interval=300):
    '''
      Write in Datastore
    '''
    val = collectd.Values(type='counter')
    val.plugin = key
    val.plugin_instance = str(project_id)
    val.type_instance = type_instance
    val.values = [int(value)]
    val.time = timestamp
    val.dispatch(interval=interval)
#    collectd.info('gitlab_kpi plugin: Write {} with value {}, type_instance {}, plugin_instance {}'.format(
#        key, value, type_instance, str(project_id)))

def consume_queue(q, timestamp):
    '''
       Consume Queue that Process generated
    '''
    while not q.empty():
        values = q.get()
        total = values.get('total', 0)
        key =  values.get('key', None)
        project_id = values.get('project_id', None)
        project_name = values.get('project_name', None)
        write(key, total, project_id, project_name, timestamp)

def read_func():
    '''
       Fetch Kpi from Gitlab
    '''
    crawl_groups()
    timestamp = int(time.time())

    q1 = Queue()
    all_args = [
        ('/issues?state=opened', 'gitlab_kpi_issue_opened'),
        ('/issues?state=closed', 'gitlab_kpi_issue_closed'),
        ('/jobs?scope[]=pending&scope[]=running', 'gitlab_kpi_in_progress_jobs'),
        ('/jobs?scope[]=failed', 'gitlab_kpi_failed_jobs'),
        ('/jobs?scope[]=success', 'gitlab_kpi_success_jobs'),
        ('/repository/commits', 'gitlab_kpi_commits'),
        ('/merge_requests?state=opened', 'gitlab_kpi_merge_requests_opened'),
        ('/merge_requests?state=closed', 'gitlab_kpi_merge_requests_closed'),
        ('/merge_requests?state=merged', 'gitlab_kpi_merge_requests_merged'),
    ]
    collectd.info('gitlab_kpi plugin: Start kpi collection')
    for page in PROJECTS:
        for project in page:
            url = URL + '/projects/{}'.format(project.get('id'))
            type_instance = 'project_{}'.format(project.get('name'))

            for get_parameter, key in all_args:
                get_x_total(q1, url + get_parameter,
                key, project.get('id'), type_instance)

    consume_queue(q1, timestamp)
    ts = int(time.time())
    collectd.info('gitlab_kpi plugin: Stop kpi collection in {}s'.format(ts - timestamp))
    return


collectd.register_config(config_func)
collectd.register_read(read_func)
