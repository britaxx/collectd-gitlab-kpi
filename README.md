[![python version](https://img.shields.io/badge/python-3.4-blue.svg)]


# Collectd Gitlab-Kpi

This tools is a python module for collectd, that permit to collect some Kpi from Gitlab :

 * Opened / Closed Issues
 * Success / Failed / In progress Jobs
 * Commit
 * Opened / Closed / Merged Merge Requests

## Requirements

You Have to configure your gitlab to have an access of gitlab api and a private token.

More collectd :) , server need :
```
pip install certifi pyOpenSSL ndg-httpsclient
```

After clone project you need to prepare virtualenv :
```
virtualenv --python=python3 environment
source environment/bin/activate
pip install -r requirement.txt
```

## Configure collectd 

```
LoadPlugin python
<Plugin python>
    ModulePath "path/to/gitlab_kpi"
    Import "gitlab_kpi"
    <Module gitlab_kpi>
        Url "https://gitlab.example.com/api/v4"
        Private_token "gitlab_token"
        Groups "group_1"
    </Module>
</Plugin>
```

## Collectd Value

```
    val = collectd.Values(type='counter')
    # gitlab_kpi_issue_opened or gitlab_kpi_issue_closed etc ...
    val.plugin = key
    # Project ID
    val.plugin_instance = str(project_id)
    # Project Name
    val.type_instance = type_instance
    # Value
    val.values = [int(value)]
    # Timestamp
    val.time = timestamp
```


### Tips

In python 3 in line 8 of environment/lib/python3.4/site-packages/collectd.py you have to change :

```
- from Queue import Queue, Empty
+ from queue import Queue, Empty
```


----------

Time to retrieve all informations from gitlab Api can be too long. In collectd, I configure Interval to 300s.

### Screenshots

Here somes examples of my grafana dashboards :

![screenshot_1.png](screenshots/screenshot_1.png?raw=true "Screenshot_1")
