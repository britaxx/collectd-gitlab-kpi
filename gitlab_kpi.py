"""
   Collect KPI about Gilab
"""
# coding: utf8
#!./environment/bin/python

__author__ = "Alexandre BRIT (@britaxx)"
__maintainer__ = "Alexandre BRIT"

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
    urllib3.contrib.pyopenssl.inject_into_urllib3()
    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                               ca_certs=certifi.where())
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

def find_subgroup(group_name):
    '''
        Find Subgroup of group
    '''
    url = URL + '/groups/{}/subgroups'.format(group_name)
    data, headers = make_resquest(url=url)
    for subgroup in data:
        GROUPS.append(subgroup.get('id'))
        find_subgroup(subgroup.get('id'))


def crawl_groups():
    '''
      Crawl Groups and fetch projects in global PROJECTS
    '''
    for group in GROUPS:
        find_subgroup(group)
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


def get_x_total(url):
    '''
       Return X-total from headers
    '''
    data, headers = make_resquest(url=url)
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
    collectd.info('gitlab_kpi plugin: Write {} with value {} and type_instance {}'.format(key, value, type_instance))


def read_func():
    '''
       Fetch Kpi from Gitlab
    '''
    crawl_groups()
    timestamp = int(time.time())
    collectd.info('gitlab_kpi plugin: Start kpi collection')
    for page in PROJECTS:
        for project in page:
            url = URL + '/projects/{}'.format(project.get('id'))
            type_instance = 'project_{}'.format(project.get('name'))

            opened_issue = get_x_total(url + '/issues?state=opened')
            closed_issue = get_x_total(url + '/issues?state=closed')
            in_progress_jobs = get_x_total(url + '/jobs?scope[]=pending&scope[]=running')
            failed_jobs = get_x_total(url + '/jobs?scope[]=failed')
            success_jobs = get_x_total(url + '/jobs?scope[]=success')
            commits = get_x_total(url + '/repository/commits')
            merge_requests_opened = get_x_total(url + '/merge_requests?state=opened')
            merge_requests_closed = get_x_total(url + '/merge_requests?state=closed')
            merge_requests_merged = get_x_total(url + '/merge_requests?state=merged')

            write('gitlab_kpi_issue_opened', opened_issue, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_issue_closed', closed_issue, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_in_progress_jobs', in_progress_jobs, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_failed_jobs', failed_jobs, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_success_jobs', success_jobs, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_commits', commits, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_merge_requests_opened', merge_requests_opened, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_merge_requests_closed', merge_requests_closed, project.get('id'), type_instance, timestamp)
            write('gitlab_kpi_merge_requests_merged', merge_requests_merged, project.get('id'), type_instance, timestamp)

    collectd.info('gitlab_kpi plugin: Stop kpi collection')
    return


collectd.register_config(config_func)
collectd.register_read(read_func)
